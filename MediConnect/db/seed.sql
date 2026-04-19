-- Minimal seed data for MediConnect (MVP)
BEGIN;

-- Users
INSERT INTO users (id, role, display_name, email)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'patient', 'Пациент Тест', 'patient@example.com'),
  ('22222222-2222-2222-2222-222222222222', 'doctor',  'Врач Тест',    'doctor@example.com')
ON CONFLICT DO NOTHING;

-- Org
INSERT INTO orgs (id, name)
VALUES ('33333333-3333-3333-3333-333333333333', 'Городская клиника №1')
ON CONFLICT DO NOTHING;

-- Membership (doctor in org)
INSERT INTO org_memberships (org_id, user_id, member_role)
VALUES ('33333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222', 'member')
ON CONFLICT DO NOTHING;

-- Document created by patient
INSERT INTO documents (id, patient_user_id, created_by_user_id, doc_type, title, content_text, issued_at)
VALUES
  ('44444444-4444-4444-4444-444444444444',
   '11111111-1111-1111-1111-111111111111',
   '11111111-1111-1111-1111-111111111111',
   'lab_result',
   'Анализ крови (строка)',
   'LAB: Hb=140; WBC=6.2; PLT=250',
   CURRENT_DATE
  )
ON CONFLICT DO NOTHING;

-- Consent: patient grants doctor access to single document for 14 days
INSERT INTO consents (
  id,
  patient_user_id,
  granted_to_user_id,
  scope,
  document_id,
  purpose,
  valid_from,
  valid_until
)
VALUES (
  '55555555-5555-5555-5555-555555555555',
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222',
  'single_document',
  '44444444-4444-4444-4444-444444444444',
  'treatment',
  now(),
  now() + interval '14 days'
)
ON CONFLICT DO NOTHING;

-- Audit examples
INSERT INTO audit_events (actor_user_id, action, target_type, target_id, patient_user_id, metadata)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'create', 'document', '44444444-4444-4444-4444-444444444444', '11111111-1111-1111-1111-111111111111', '{"note":"seed"}'),
  ('11111111-1111-1111-1111-111111111111', 'grant',  'consent',  '55555555-5555-5555-5555-555555555555', '11111111-1111-1111-1111-111111111111', '{"note":"seed"}')
;

COMMIT;

