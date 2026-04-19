import os
import time
import uuid

import httpx


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


def _register(client: httpx.Client, *, role: str, email: str, password: str, display_name: str):
    r = client.post(
        f"{BASE_URL}/auth/register",
        json={"role": role, "display_name": display_name, "email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _token(client: httpx.Client, *, username: str, password: str) -> str:
    r = client.post(
        f"{BASE_URL}/auth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health():
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_patient_document_consent_audit_flow():
    with httpx.Client(timeout=20) as client:
        patient_email = _unique_email("patient")
        doctor_email = _unique_email("doctor")
        pw = "secret123"

        patient = _register(client, role="patient", email=patient_email, password=pw, display_name="Пациент Тест")
        doctor = _register(client, role="doctor", email=doctor_email, password=pw, display_name="Врач Тест")

        patient_token = _token(client, username=patient_email, password=pw)
        doctor_token = _token(client, username=doctor_email, password=pw)

        # patient creates a document
        r = client.post(
            f"{BASE_URL}/documents",
            headers={**_auth_headers(patient_token), "Content-Type": "application/json"},
            json={
                "doc_type": "lab_result",
                "title": "Анализ (строка)",
                "content_text": "Hb=140; WBC=6.2",
                "issued_at": "2026-04-15",
            },
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        doc_id = doc["id"]

        # doctor should not access without consent
        r = client.get(f"{BASE_URL}/documents/{doc_id}", headers=_auth_headers(doctor_token))
        assert r.status_code == 403

        # patient grants consent to doctor for that document
        r = client.post(
            f"{BASE_URL}/consents",
            headers={**_auth_headers(patient_token), "Content-Type": "application/json"},
            json={
                "granted_to_user_id": doctor["id"],
                "scope": "single_document",
                "document_id": doc_id,
                "purpose": "treatment",
            },
        )
        assert r.status_code == 200, r.text
        consent = r.json()
        consent_id = consent["id"]

        # doctor can access now
        r = client.get(f"{BASE_URL}/documents/{doc_id}", headers=_auth_headers(doctor_token))
        assert r.status_code == 200, r.text
        assert r.json()["id"] == doc_id

        # list consents: patient sees their grants
        r = client.get(f"{BASE_URL}/consents", headers=_auth_headers(patient_token))
        assert r.status_code == 200, r.text
        ids = {c["id"] for c in r.json()}
        assert consent_id in ids

        # list consents: doctor sees received
        r = client.get(f"{BASE_URL}/consents", headers=_auth_headers(doctor_token))
        assert r.status_code == 200, r.text
        ids = {c["id"] for c in r.json()}
        assert consent_id in ids

        # patient audit should have at least create+grant events (and maybe read/list)
        # small delay so audit commit is visible everywhere
        time.sleep(0.2)
        r = client.get(f"{BASE_URL}/audit?limit=200", headers=_auth_headers(patient_token))
        assert r.status_code == 200, r.text
        events = r.json()
        actions = {e["action"] for e in events}
        assert "create" in actions
        assert "grant" in actions


def test_org_create_and_membership():
    with httpx.Client(timeout=20) as client:
        admin_email = _unique_email("orgadmin")
        member_email = _unique_email("member")
        pw = "secret123"

        admin = _register(client, role="org_admin", email=admin_email, password=pw, display_name="Org Admin")
        member = _register(client, role="doctor", email=member_email, password=pw, display_name="Доктор В Org")

        admin_token = _token(client, username=admin_email, password=pw)

        # create org
        r = client.post(
            f"{BASE_URL}/orgs",
            headers={**_auth_headers(admin_token), "Content-Type": "application/json"},
            json={"name": f"Clinic {uuid.uuid4().hex[:6]}"},
        )
        assert r.status_code == 200, r.text
        org = r.json()
        org_id = org["id"]

        # add doctor member
        r = client.post(
            f"{BASE_URL}/orgs/{org_id}/members",
            headers={**_auth_headers(admin_token), "Content-Type": "application/json"},
            json={"user_id": member["id"], "member_role": "member"},
        )
        assert r.status_code == 200, r.text

        # list members
        r = client.get(f"{BASE_URL}/orgs/{org_id}/members", headers=_auth_headers(admin_token))
        assert r.status_code == 200, r.text
        users = {m["user_id"] for m in r.json()}
        assert admin["id"] in users
        assert member["id"] in users


def test_full_e2e_org_consent_flow():
    """
    End-to-end scenario:
    - create org (org_admin auto becomes admin member)
    - add doctor to org
    - patient creates doc
    - patient grants consent to ORG for all documents
    - doctor reads doc via actor_org_id
    - patient revokes consent
    - doctor loses access
    - patient audit contains create/grant/revoke/read attempts
    """
    with httpx.Client(timeout=30) as client:
        pw = "secret123"

        org_admin_email = _unique_email("orgadmin")
        doctor_email = _unique_email("doctor-org")
        patient_email = _unique_email("patient-org")

        org_admin = _register(client, role="org_admin", email=org_admin_email, password=pw, display_name="Org Admin")
        doctor = _register(client, role="doctor", email=doctor_email, password=pw, display_name="Doctor Member")
        patient = _register(client, role="patient", email=patient_email, password=pw, display_name="Patient")

        org_admin_token = _token(client, username=org_admin_email, password=pw)
        doctor_token = _token(client, username=doctor_email, password=pw)
        patient_token = _token(client, username=patient_email, password=pw)

        # create org
        r = client.post(
            f"{BASE_URL}/orgs",
            headers={**_auth_headers(org_admin_token), "Content-Type": "application/json"},
            json={"name": f"Clinic {uuid.uuid4().hex[:6]}"},
        )
        assert r.status_code == 200, r.text
        org = r.json()
        org_id = org["id"]

        # add doctor to org
        r = client.post(
            f"{BASE_URL}/orgs/{org_id}/members",
            headers={**_auth_headers(org_admin_token), "Content-Type": "application/json"},
            json={"user_id": doctor["id"], "member_role": "member"},
        )
        assert r.status_code == 200, r.text

        # patient creates doc
        r = client.post(
            f"{BASE_URL}/documents",
            headers={**_auth_headers(patient_token), "Content-Type": "application/json"},
            json={
                "doc_type": "note",
                "title": "E2E note",
                "content_text": "text",
                "issued_at": "2026-04-15",
            },
        )
        assert r.status_code == 200, r.text
        doc_id = r.json()["id"]

        # doctor cannot read without org consent
        r = client.get(
            f"{BASE_URL}/documents/{doc_id}",
            headers=_auth_headers(doctor_token),
            params={"actor_org_id": org_id},
        )
        assert r.status_code == 403, r.text

        # patient grants consent to org for all documents
        r = client.post(
            f"{BASE_URL}/consents",
            headers={**_auth_headers(patient_token), "Content-Type": "application/json"},
            json={
                "granted_to_org_id": org_id,
                "scope": "all_documents",
                "purpose": "treatment",
            },
        )
        assert r.status_code == 200, r.text
        consent_id = r.json()["id"]

        # doctor can read with actor_org_id
        r = client.get(
            f"{BASE_URL}/documents/{doc_id}",
            headers=_auth_headers(doctor_token),
            params={"actor_org_id": org_id},
        )
        assert r.status_code == 200, r.text

        # doctor can list accessible docs for that patient (via org)
        r = client.get(
            f"{BASE_URL}/documents",
            headers=_auth_headers(doctor_token),
            params={"patient_user_id": patient["id"], "actor_org_id": org_id},
        )
        assert r.status_code == 200, r.text
        ids = {d["id"] for d in r.json()}
        assert doc_id in ids

        # patient revokes consent
        r = client.post(f"{BASE_URL}/consents/{consent_id}/revoke", headers=_auth_headers(patient_token))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "revoked"

        # doctor loses access
        r = client.get(
            f"{BASE_URL}/documents/{doc_id}",
            headers=_auth_headers(doctor_token),
            params={"actor_org_id": org_id},
        )
        assert r.status_code == 403, r.text

        # patient audit contains create/grant/revoke at least
        time.sleep(0.2)
        r = client.get(f"{BASE_URL}/audit?limit=300", headers=_auth_headers(patient_token))
        assert r.status_code == 200, r.text
        actions = {e["action"] for e in r.json()}
        assert {"create", "grant", "revoke"}.issubset(actions)


def test_permissions_and_validation_smoke():
    with httpx.Client(timeout=20) as client:
        pw = "secret123"
        patient_email = _unique_email("patient-perm")
        doctor_email = _unique_email("doctor-perm")

        patient = _register(client, role="patient", email=patient_email, password=pw, display_name="P")
        doctor = _register(client, role="doctor", email=doctor_email, password=pw, display_name="D")

        patient_token = _token(client, username=patient_email, password=pw)
        doctor_token = _token(client, username=doctor_email, password=pw)

        # doctor cannot grant consent
        r = client.post(
            f"{BASE_URL}/consents",
            headers={**_auth_headers(doctor_token), "Content-Type": "application/json"},
            json={"granted_to_user_id": doctor["id"], "scope": "all_documents"},
        )
        assert r.status_code == 403

        # patient cannot create org
        r = client.post(
            f"{BASE_URL}/orgs",
            headers={**_auth_headers(patient_token), "Content-Type": "application/json"},
            json={"name": "X"},
        )
        assert r.status_code == 403

        # consent validation: must provide exactly one grantee
        r = client.post(
            f"{BASE_URL}/consents",
            headers={**_auth_headers(patient_token), "Content-Type": "application/json"},
            json={"scope": "all_documents"},
        )
        assert r.status_code == 400

