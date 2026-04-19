-- MediConnect (MVP) schema for PostgreSQL
-- Documents are stored as strings in documents.content_text.

BEGIN;

-- Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()

-- Enums
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
    CREATE TYPE user_role AS ENUM ('patient', 'doctor', 'org_admin', 'platform_admin');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'org_member_role') THEN
    CREATE TYPE org_member_role AS ENUM ('member', 'admin');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_type') THEN
    CREATE TYPE document_type AS ENUM ('note', 'lab_result', 'discharge', 'prescription', 'imaging', 'other');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'consent_scope') THEN
    CREATE TYPE consent_scope AS ENUM ('single_document', 'all_documents');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'consent_status') THEN
    CREATE TYPE consent_status AS ENUM ('active', 'revoked', 'expired');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audit_action') THEN
    CREATE TYPE audit_action AS ENUM ('create', 'read', 'update', 'delete', 'grant', 'revoke', 'login');
  END IF;
END$$;

-- Core: users / identities
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role user_role NOT NULL,
  display_name text NOT NULL,
  email text UNIQUE,
  phone text UNIQUE,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS user_identities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider text NOT NULL,          -- e.g. 'password', 'oauth', 'sso'
  provider_subject text NOT NULL,  -- external id / login
  password_hash text,              -- optional for MVP
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_subject),
  UNIQUE (user_id, provider)
);

-- Organizations / memberships (tenants)
CREATE TABLE IF NOT EXISTS orgs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS org_memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  member_role org_member_role NOT NULL DEFAULT 'member',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, user_id)
);

-- Documents (string-based payload)
CREATE TABLE IF NOT EXISTS documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  org_id uuid REFERENCES orgs(id) ON DELETE SET NULL,
  doc_type document_type NOT NULL DEFAULT 'other',
  title text NOT NULL,
  content_text text NOT NULL, -- MVP: the "document" itself (url/path/text)
  issued_at date,             -- when the medical document was issued
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_patient_created_at ON documents (patient_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_org_created_at ON documents (org_id, created_at DESC);

-- Consents (patient grants access to doctor or org)
CREATE TABLE IF NOT EXISTS consents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  granted_to_user_id uuid REFERENCES users(id) ON DELETE CASCADE, -- typically a doctor
  granted_to_org_id uuid REFERENCES orgs(id) ON DELETE CASCADE,    -- alternatively an org
  scope consent_scope NOT NULL,
  document_id uuid REFERENCES documents(id) ON DELETE CASCADE,
  purpose text, -- "treatment", "second opinion", etc.
  status consent_status NOT NULL DEFAULT 'active',
  valid_from timestamptz NOT NULL DEFAULT now(),
  valid_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  revoked_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  CHECK (
    (granted_to_user_id IS NOT NULL AND granted_to_org_id IS NULL)
    OR
    (granted_to_user_id IS NULL AND granted_to_org_id IS NOT NULL)
  ),
  CHECK (
    (scope = 'single_document' AND document_id IS NOT NULL)
    OR
    (scope = 'all_documents' AND document_id IS NULL)
  ),
  CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE INDEX IF NOT EXISTS idx_consents_patient_status ON consents (patient_user_id, status);
CREATE INDEX IF NOT EXISTS idx_consents_granted_to_user ON consents (granted_to_user_id) WHERE granted_to_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_consents_granted_to_org ON consents (granted_to_org_id) WHERE granted_to_org_id IS NOT NULL;

-- Audit log (immutable by convention; enforce with privileges in app)
CREATE TABLE IF NOT EXISTS audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  occurred_at timestamptz NOT NULL DEFAULT now(),
  actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  actor_org_id uuid REFERENCES orgs(id) ON DELETE SET NULL,
  action audit_action NOT NULL,
  target_type text NOT NULL, -- 'document', 'consent', 'user', etc.
  target_id uuid,
  patient_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  ip inet,
  user_agent text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_audit_patient_time ON audit_events (patient_user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor_time ON audit_events (actor_user_id, occurred_at DESC);

-- Access checks (MVP)
-- Rule: patient always has access to own docs.
-- Rule: platform_admin has access to everything (for ops; can be removed).
-- Rule: doctor/org access is only via effective consent:
--   - consent to user OR consent to org
--   - scope all_documents or specific document_id
CREATE OR REPLACE FUNCTION is_effective_consent(c consents)
RETURNS boolean AS $$
BEGIN
  RETURN (
    c.status = 'active'
    AND c.valid_from <= now()
    AND (c.valid_until IS NULL OR c.valid_until > now())
  );
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION can_read_document(
  p_actor_user_id uuid,
  p_document_id uuid,
  p_actor_org_id uuid DEFAULT NULL
)
RETURNS boolean AS $$
DECLARE
  v_doc documents;
  v_role user_role;
  v_allowed boolean := false;
BEGIN
  SELECT * INTO v_doc FROM documents WHERE id = p_document_id;
  IF NOT FOUND THEN
    RETURN false;
  END IF;

  SELECT role INTO v_role FROM users WHERE id = p_actor_user_id AND is_active = true;
  IF NOT FOUND THEN
    RETURN false;
  END IF;

  -- Patient can read own documents
  IF v_doc.patient_user_id = p_actor_user_id THEN
    RETURN true;
  END IF;

  -- Platform admin can read everything (optional for MVP)
  IF v_role = 'platform_admin' THEN
    RETURN true;
  END IF;

  -- Consent granted directly to user
  SELECT true INTO v_allowed
  FROM consents c
  WHERE c.patient_user_id = v_doc.patient_user_id
    AND c.granted_to_user_id = p_actor_user_id
    AND is_effective_consent(c)
    AND (
      (c.scope = 'all_documents')
      OR
      (c.scope = 'single_document' AND c.document_id = v_doc.id)
    )
  LIMIT 1;

  IF COALESCE(v_allowed, false) THEN
    RETURN true;
  END IF;

  -- Consent granted to org (actor must be member of that org)
  IF p_actor_org_id IS NOT NULL THEN
    SELECT true INTO v_allowed
    FROM consents c
    WHERE c.patient_user_id = v_doc.patient_user_id
      AND c.granted_to_org_id = p_actor_org_id
      AND is_effective_consent(c)
      AND (
        (c.scope = 'all_documents')
        OR
        (c.scope = 'single_document' AND c.document_id = v_doc.id)
      )
    LIMIT 1;

    IF COALESCE(v_allowed, false) THEN
      -- ensure actor is a member of org
      PERFORM 1 FROM org_memberships m
      WHERE m.org_id = p_actor_org_id AND m.user_id = p_actor_user_id;
      IF FOUND THEN
        RETURN true;
      END IF;
    END IF;
  END IF;

  RETURN false;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION list_accessible_documents(
  p_actor_user_id uuid,
  p_patient_user_id uuid DEFAULT NULL,
  p_actor_org_id uuid DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  patient_user_id uuid,
  doc_type document_type,
  title text,
  content_text text,
  issued_at date,
  created_at timestamptz
) AS $$
BEGIN
  -- If p_patient_user_id is NULL, list docs across patients where any consent exists.
  RETURN QUERY
  SELECT d.id, d.patient_user_id, d.doc_type, d.title, d.content_text, d.issued_at, d.created_at
  FROM documents d
  WHERE
    (p_patient_user_id IS NULL OR d.patient_user_id = p_patient_user_id)
    AND can_read_document(p_actor_user_id, d.id, p_actor_org_id)
  ORDER BY d.created_at DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Convenience: updated_at maintenance
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_users_updated_at'
  ) THEN
    CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_documents_updated_at'
  ) THEN
    CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END$$;

-- Optional: simple "state" view of valid consents (active + in time window)
CREATE OR REPLACE VIEW v_effective_consents AS
SELECT
  c.*,
  is_effective_consent(c) AS is_effective
FROM consents c;

COMMIT;

