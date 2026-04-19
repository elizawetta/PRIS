-- Useful queries / examples for MediConnect (MVP)

-- 1) List all documents of a patient (as the patient)
-- SELECT * FROM list_accessible_documents('11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111');

-- 2) Doctor lists docs accessible for a given patient (via consent)
-- SELECT * FROM list_accessible_documents('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111');

-- 3) Organization member lists docs accessible for a patient (consent to org)
-- SELECT * FROM list_accessible_documents(
--   p_actor_user_id := '22222222-2222-2222-2222-222222222222',
--   p_patient_user_id := '11111111-1111-1111-1111-111111111111',
--   p_actor_org_id := '33333333-3333-3333-3333-333333333333'
-- );

-- 4) Create a new document (by patient)
-- INSERT INTO documents (patient_user_id, created_by_user_id, doc_type, title, content_text, issued_at)
-- VALUES ('11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'note', 'Заметка', 'TEXT...', CURRENT_DATE)
-- RETURNING id;

-- 5) Grant consent to a doctor for all documents for 30 days
-- INSERT INTO consents (patient_user_id, granted_to_user_id, scope, purpose, valid_from, valid_until)
-- VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'all_documents', 'treatment', now(), now() + interval '30 days');

-- 6) Revoke consent
-- UPDATE consents
-- SET status = 'revoked', revoked_at = now(), revoked_by_user_id = '11111111-1111-1111-1111-111111111111'
-- WHERE id = '55555555-5555-5555-5555-555555555555';

-- 7) Audit: record a document read (пример)
-- INSERT INTO audit_events (actor_user_id, actor_org_id, action, target_type, target_id, patient_user_id, metadata)
-- VALUES ('22222222-2222-2222-2222-222222222222', NULL, 'read', 'document', '44444444-4444-4444-4444-444444444444', '11111111-1111-1111-1111-111111111111', '{"source":"api"}');

