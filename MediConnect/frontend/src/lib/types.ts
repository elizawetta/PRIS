export type UserRole = "patient" | "doctor" | "org_admin" | "platform_admin";

export type Me = {
  id: string;
  role: UserRole;
  display_name: string;
  email?: string | null;
  phone?: string | null;
};

export type DocumentType = "note" | "lab_result" | "discharge" | "prescription" | "imaging" | "other";

export type Document = {
  id: string;
  patient_user_id: string;
  doc_type: DocumentType;
  title: string;
  content_text: string;
  issued_at?: string | null;
  created_at: string;
};

export type ConsentScope = "single_document" | "all_documents";
export type ConsentStatus = "active" | "revoked" | "expired";

export type Consent = {
  id: string;
  patient_user_id: string;
  granted_to_user_id?: string | null;
  granted_to_org_id?: string | null;
  scope: ConsentScope;
  document_id?: string | null;
  purpose?: string | null;
  status: ConsentStatus;
  valid_from: string;
  valid_until?: string | null;
  created_at: string;
  revoked_at?: string | null;
  revoked_by_user_id?: string | null;
};

export type Org = {
  id: string;
  name: string;
  created_at: string;
};

export type OrgMember = {
  id: string;
  org_id: string;
  user_id: string;
  member_role: "member" | "admin";
  created_at: string;
};

export type AuditEvent = {
  id: string;
  occurred_at: string;
  actor_user_id?: string | null;
  actor_org_id?: string | null;
  action: string;
  target_type: string;
  target_id?: string | null;
  patient_user_id?: string | null;
  ip?: string | null;
  user_agent?: string | null;
  metadata: Record<string, unknown>;
};

