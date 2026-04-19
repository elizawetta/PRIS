from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from psycopg.errors import UniqueViolation
from psycopg_pool import ConnectionPool
from fastapi.middleware.cors import CORSMiddleware


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_alg: str = Field(default="HS256", alias="JWT_ALG")
    access_token_expire_minutes: int = Field(default=120, alias="ACCESS_TOKEN_EXPIRE_MINUTES")


settings = Settings()

pool = ConnectionPool(conninfo=settings.database_url, min_size=1, max_size=10)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


UserRole = Literal["patient", "doctor", "org_admin", "platform_admin"]

def _to_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    role: UserRole
    display_name: str = Field(min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    password: str = Field(min_length=6, max_length=200)


class MeResponse(BaseModel):
    id: UUID
    role: UserRole
    display_name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class DocumentCreateRequest(BaseModel):
    doc_type: Literal["note", "lab_result", "discharge", "prescription", "imaging", "other"] = "other"
    title: str = Field(min_length=1, max_length=300)
    content_text: str = Field(min_length=1)
    issued_at: Optional[str] = None  # YYYY-MM-DD for MVP
    org_id: Optional[UUID] = None


class DocumentResponse(BaseModel):
    id: UUID
    patient_user_id: UUID
    doc_type: str
    title: str
    content_text: str
    issued_at: Optional[str] = None
    created_at: datetime


class ConsentCreateRequest(BaseModel):
    granted_to_user_id: Optional[UUID] = None
    granted_to_org_id: Optional[UUID] = None
    scope: Literal["single_document", "all_documents"]
    document_id: Optional[UUID] = None
    purpose: Optional[str] = Field(default=None, max_length=500)
    valid_until: Optional[datetime] = None


class ConsentResponse(BaseModel):
    id: UUID
    patient_user_id: UUID
    granted_to_user_id: Optional[UUID]
    granted_to_org_id: Optional[UUID]
    scope: str
    document_id: Optional[UUID]
    purpose: Optional[str]
    status: str
    valid_from: datetime
    valid_until: Optional[datetime]
    created_at: datetime
    revoked_at: Optional[datetime]
    revoked_by_user_id: Optional[UUID]


class OrgCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)


class OrgResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime


class OrgMemberAddRequest(BaseModel):
    user_id: UUID
    member_role: Literal["member", "admin"] = "member"


class OrgMemberResponse(BaseModel):
    id: UUID
    org_id: UUID
    user_id: UUID
    member_role: str
    created_at: datetime


class AuditEventResponse(BaseModel):
    id: UUID
    occurred_at: datetime
    actor_user_id: Optional[UUID] = None
    actor_org_id: Optional[UUID] = None
    action: str
    target_type: str
    target_id: Optional[UUID] = None
    patient_user_id: Optional[UUID] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: dict[str, Any]


def _create_access_token(sub: str) -> str:
    now = datetime.now(tz=timezone.utc)
    exp = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": sub, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def _audit(
    *,
    actor_user_id: UUID,
    actor_org_id: Optional[UUID],
    action: str,
    target_type: str,
    target_id: Optional[UUID],
    patient_user_id: Optional[UUID],
    request: Request,
    metadata: dict[str, Any] | None = None,
) -> None:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_events (actor_user_id, actor_org_id, action, target_type, target_id, patient_user_id, ip, user_agent, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s::inet, %s, %s::jsonb)
                """,
                [
                    str(actor_user_id),
                    str(actor_org_id) if actor_org_id else None,
                    action,
                    target_type,
                    str(target_id) if target_id else None,
                    str(patient_user_id) if patient_user_id else None,
                    ip,
                    ua,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ],
            )
        conn.commit()


def _get_user(user_id: UUID) -> dict[str, Any]:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, role, display_name, email, phone, is_active FROM users WHERE id = %s",
                [str(user_id)],
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            user = {
                "id": _to_uuid(row[0]),
                "role": row[1],
                "display_name": row[2],
                "email": row[3],
                "phone": row[4],
                "is_active": row[5],
            }
            if not user["is_active"]:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User disabled")
            return user


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return _get_user(UUID(sub))
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


app = FastAPI(title="MediConnect API (MVP)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=MeResponse)
def register(body: RegisterRequest) -> MeResponse:
    password_hash = pwd_context.hash(body.password)
    user_id = uuid4()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, role, display_name, email, phone)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, role, display_name, email, phone
                """,
                [str(user_id), body.role, body.display_name, str(body.email) if body.email else None, body.phone],
            )
            cur.execute(
                """
                INSERT INTO user_identities (user_id, provider, provider_subject, password_hash)
                VALUES (%s, 'password', %s, %s)
                """,
                [str(user_id), str(body.email) if body.email else (body.phone or str(user_id)), password_hash],
            )
        conn.commit()
    return MeResponse(
        id=user_id,
        role=body.role,
        display_name=body.display_name,
        email=str(body.email) if body.email else None,
        phone=body.phone,
    )


@app.post("/auth/token", response_model=TokenResponse)
def token(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    username = form.username
    password = form.password
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.is_active, ui.password_hash
                FROM user_identities ui
                JOIN users u ON u.id = ui.user_id
                WHERE ui.provider = 'password' AND ui.provider_subject = %s
                """,
                [username],
            )
            row = cur.fetchone()
            if not row or not row[1]:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")
            user_id = _to_uuid(row[0])
            password_hash = row[2]
            if not password_hash or not pwd_context.verify(password, password_hash):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")
    return TokenResponse(access_token=_create_access_token(str(user_id)))


@app.get("/me", response_model=MeResponse)
def me(user: dict[str, Any] = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=user["id"],
        role=user["role"],
        display_name=user["display_name"],
        email=user["email"],
        phone=user["phone"],
    )


@app.post("/documents", response_model=DocumentResponse)
def create_document(
    body: DocumentCreateRequest,
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> DocumentResponse:
    if user["role"] not in ("patient", "doctor", "org_admin", "platform_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    patient_user_id = user["id"] if user["role"] == "patient" else None
    if patient_user_id is None:
        raise HTTPException(status_code=400, detail="For MVP only patient can create own documents")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (patient_user_id, created_by_user_id, org_id, doc_type, title, content_text, issued_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::date)
                RETURNING id, patient_user_id, doc_type, title, content_text, issued_at, created_at
                """,
                [
                    str(patient_user_id),
                    str(user["id"]),
                    str(body.org_id) if body.org_id else None,
                    body.doc_type,
                    body.title,
                    body.content_text,
                    body.issued_at,
                ],
            )
            row = cur.fetchone()
        conn.commit()

    doc = DocumentResponse(
        id=_to_uuid(row[0]),
        patient_user_id=_to_uuid(row[1]),
        doc_type=row[2],
        title=row[3],
        content_text=row[4],
        issued_at=str(row[5]) if row[5] else None,
        created_at=row[6],
    )

    _audit(
        actor_user_id=user["id"],
        actor_org_id=None,
        action="create",
        target_type="document",
        target_id=doc.id,
        patient_user_id=doc.patient_user_id,
        request=request,
        metadata={"doc_type": doc.doc_type},
    )
    return doc


@app.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    request: Request,
    actor_org_id: Optional[UUID] = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> DocumentResponse:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT can_read_document(%s, %s, %s)", [str(user["id"]), str(document_id), str(actor_org_id) if actor_org_id else None])
            allowed = cur.fetchone()[0]
            if not allowed:
                raise HTTPException(status_code=403, detail="No access")
            cur.execute(
                """
                SELECT id, patient_user_id, doc_type, title, content_text, issued_at, created_at
                FROM documents
                WHERE id = %s
                """,
                [str(document_id)],
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Not found")

    doc = DocumentResponse(
        id=_to_uuid(row[0]),
        patient_user_id=_to_uuid(row[1]),
        doc_type=row[2],
        title=row[3],
        content_text=row[4],
        issued_at=str(row[5]) if row[5] else None,
        created_at=row[6],
    )
    _audit(
        actor_user_id=user["id"],
        actor_org_id=actor_org_id,
        action="read",
        target_type="document",
        target_id=doc.id,
        patient_user_id=doc.patient_user_id,
        request=request,
    )
    return doc


@app.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    request: Request,
    patient_user_id: Optional[UUID] = None,
    actor_org_id: Optional[UUID] = None,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[DocumentResponse]:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, patient_user_id, doc_type, title, content_text, issued_at, created_at FROM list_accessible_documents(%s, %s, %s)",
                [str(user["id"]), str(patient_user_id) if patient_user_id else None, str(actor_org_id) if actor_org_id else None],
            )
            rows = cur.fetchall()
    _audit(
        actor_user_id=user["id"],
        actor_org_id=actor_org_id,
        action="read",
        target_type="document_list",
        target_id=None,
        patient_user_id=patient_user_id,
        request=request,
        metadata={"filter_patient_user_id": str(patient_user_id) if patient_user_id else None},
    )
    return [
        DocumentResponse(
            id=_to_uuid(r[0]),
            patient_user_id=_to_uuid(r[1]),
            doc_type=r[2],
            title=r[3],
            content_text=r[4],
            issued_at=str(r[5]) if r[5] else None,
            created_at=r[6],
        )
        for r in rows
    ]


@app.post("/consents", response_model=ConsentResponse)
def create_consent(
    body: ConsentCreateRequest,
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> ConsentResponse:
    if user["role"] != "patient":
        raise HTTPException(status_code=403, detail="Only patient can grant consents in MVP")

    if (body.granted_to_user_id is None) == (body.granted_to_org_id is None):
        raise HTTPException(status_code=400, detail="Provide exactly one of granted_to_user_id or granted_to_org_id")
    if body.scope == "single_document" and body.document_id is None:
        raise HTTPException(status_code=400, detail="document_id required for single_document")
    if body.scope == "all_documents" and body.document_id is not None:
        raise HTTPException(status_code=400, detail="document_id must be null for all_documents")

    consent_id = uuid4()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO consents (
                  id, patient_user_id, granted_to_user_id, granted_to_org_id, scope, document_id,
                  purpose, status, valid_from, valid_until
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', now(), %s)
                RETURNING id, patient_user_id, granted_to_user_id, granted_to_org_id, scope, document_id,
                          purpose, status, valid_from, valid_until, created_at, revoked_at, revoked_by_user_id
                """,
                [
                    str(consent_id),
                    str(user["id"]),
                    str(body.granted_to_user_id) if body.granted_to_user_id else None,
                    str(body.granted_to_org_id) if body.granted_to_org_id else None,
                    body.scope,
                    str(body.document_id) if body.document_id else None,
                    body.purpose,
                    body.valid_until,
                ],
            )
            row = cur.fetchone()
        conn.commit()

    consent = ConsentResponse(
        id=_to_uuid(row[0]),
        patient_user_id=_to_uuid(row[1]),
        granted_to_user_id=_to_uuid(row[2]) if row[2] else None,
        granted_to_org_id=_to_uuid(row[3]) if row[3] else None,
        scope=row[4],
        document_id=_to_uuid(row[5]) if row[5] else None,
        purpose=row[6],
        status=row[7],
        valid_from=row[8],
        valid_until=row[9],
        created_at=row[10],
        revoked_at=row[11],
        revoked_by_user_id=_to_uuid(row[12]) if row[12] else None,
    )
    _audit(
        actor_user_id=user["id"],
        actor_org_id=None,
        action="grant",
        target_type="consent",
        target_id=consent.id,
        patient_user_id=consent.patient_user_id,
        request=request,
        metadata={"scope": consent.scope, "granted_to_user_id": str(consent.granted_to_user_id) if consent.granted_to_user_id else None, "granted_to_org_id": str(consent.granted_to_org_id) if consent.granted_to_org_id else None},
    )
    return consent


@app.post("/consents/{consent_id}/revoke", response_model=ConsentResponse)
def revoke_consent(
    consent_id: UUID,
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> ConsentResponse:
    if user["role"] != "patient":
        raise HTTPException(status_code=403, detail="Only patient can revoke in MVP")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE consents
                SET status = 'revoked', revoked_at = now(), revoked_by_user_id = %s
                WHERE id = %s AND patient_user_id = %s
                RETURNING id, patient_user_id, granted_to_user_id, granted_to_org_id, scope, document_id,
                          purpose, status, valid_from, valid_until, created_at, revoked_at, revoked_by_user_id
                """,
                [str(user["id"]), str(consent_id), str(user["id"])],
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Consent not found")
        conn.commit()

    consent = ConsentResponse(
        id=_to_uuid(row[0]),
        patient_user_id=_to_uuid(row[1]),
        granted_to_user_id=_to_uuid(row[2]) if row[2] else None,
        granted_to_org_id=_to_uuid(row[3]) if row[3] else None,
        scope=row[4],
        document_id=_to_uuid(row[5]) if row[5] else None,
        purpose=row[6],
        status=row[7],
        valid_from=row[8],
        valid_until=row[9],
        created_at=row[10],
        revoked_at=row[11],
        revoked_by_user_id=_to_uuid(row[12]) if row[12] else None,
    )
    _audit(
        actor_user_id=user["id"],
        actor_org_id=None,
        action="revoke",
        target_type="consent",
        target_id=consent.id,
        patient_user_id=consent.patient_user_id,
        request=request,
    )
    return consent


@app.get("/consents", response_model=list[ConsentResponse])
def list_consents(user: dict[str, Any] = Depends(get_current_user)) -> list[ConsentResponse]:
    """
    - patient: sees consents where patient_user_id = me
    - doctor: sees consents granted_to_user_id = me
    - platform_admin: sees all
    """
    where = ""
    params: list[Any] = []
    if user["role"] == "patient":
        where = "WHERE patient_user_id = %s"
        params = [str(user["id"])]
    elif user["role"] == "doctor":
        where = "WHERE granted_to_user_id = %s"
        params = [str(user["id"])]
    elif user["role"] == "platform_admin":
        where = ""
        params = []
    else:
        raise HTTPException(status_code=403, detail="Forbidden")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, patient_user_id, granted_to_user_id, granted_to_org_id, scope, document_id,
                       purpose, status, valid_from, valid_until, created_at, revoked_at, revoked_by_user_id
                FROM consents
                {where}
                ORDER BY created_at DESC
                """,
                params,
            )
            rows = cur.fetchall()

    return [
        ConsentResponse(
            id=_to_uuid(r[0]),
            patient_user_id=_to_uuid(r[1]),
            granted_to_user_id=_to_uuid(r[2]) if r[2] else None,
            granted_to_org_id=_to_uuid(r[3]) if r[3] else None,
            scope=r[4],
            document_id=_to_uuid(r[5]) if r[5] else None,
            purpose=r[6],
            status=r[7],
            valid_from=r[8],
            valid_until=r[9],
            created_at=r[10],
            revoked_at=r[11],
            revoked_by_user_id=_to_uuid(r[12]) if r[12] else None,
        )
        for r in rows
    ]


@app.post("/orgs", response_model=OrgResponse)
def create_org(
    body: OrgCreateRequest,
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> OrgResponse:
    if user["role"] not in ("org_admin", "platform_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    org_id = uuid4()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orgs (id, name) VALUES (%s, %s) RETURNING id, name, created_at",
                [str(org_id), body.name],
            )
            row = cur.fetchone()

            # Make creator an admin member by default.
            # This matches the authorization rule in /orgs/{org_id}/members.
            cur.execute(
                """
                INSERT INTO org_memberships (org_id, user_id, member_role)
                VALUES (%s, %s, 'admin')
                ON CONFLICT (org_id, user_id) DO NOTHING
                """,
                [str(org_id), str(user["id"])],
            )
        conn.commit()

    org = OrgResponse(id=_to_uuid(row[0]), name=row[1], created_at=row[2])
    _audit(
        actor_user_id=user["id"],
        actor_org_id=org.id,
        action="create",
        target_type="org",
        target_id=org.id,
        patient_user_id=None,
        request=request,
        metadata={"name": org.name},
    )
    return org


@app.get("/orgs", response_model=list[OrgResponse])
def list_orgs(user: dict[str, Any] = Depends(get_current_user)) -> list[OrgResponse]:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            if user["role"] == "platform_admin":
                cur.execute("SELECT id, name, created_at FROM orgs ORDER BY created_at DESC")
            else:
                cur.execute(
                    """
                    SELECT o.id, o.name, o.created_at
                    FROM orgs o
                    JOIN org_memberships m ON m.org_id = o.id
                    WHERE m.user_id = %s
                    ORDER BY o.created_at DESC
                    """,
                    [str(user["id"])],
                )
            rows = cur.fetchall()
    return [OrgResponse(id=_to_uuid(r[0]), name=r[1], created_at=r[2]) for r in rows]


@app.post("/orgs/{org_id}/members", response_model=OrgMemberResponse)
def add_org_member(
    org_id: UUID,
    body: OrgMemberAddRequest,
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> OrgMemberResponse:
    # platform_admin can manage any org; org_admin must be admin member of that org
    if user["role"] != "platform_admin":
        if user["role"] != "org_admin":
            raise HTTPException(status_code=403, detail="Forbidden")
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM org_memberships
                    WHERE org_id = %s AND user_id = %s AND member_role = 'admin'
                    """,
                    [str(org_id), str(user["id"])],
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=403, detail="Not an org admin for this org")

    membership_id = uuid4()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO org_memberships (id, org_id, user_id, member_role)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, org_id, user_id, member_role, created_at
                    """,
                    [str(membership_id), str(org_id), str(body.user_id), body.member_role],
                )
                row = cur.fetchone()
            except UniqueViolation:
                raise HTTPException(status_code=409, detail="User already in org")
        conn.commit()

    membership = OrgMemberResponse(
        id=_to_uuid(row[0]),
        org_id=_to_uuid(row[1]),
        user_id=_to_uuid(row[2]),
        member_role=row[3],
        created_at=row[4],
    )
    _audit(
        actor_user_id=user["id"],
        actor_org_id=membership.org_id,
        action="update",
        target_type="org_membership",
        target_id=membership.id,
        patient_user_id=None,
        request=request,
        metadata={"added_user_id": str(membership.user_id), "member_role": membership.member_role},
    )
    return membership


@app.get("/orgs/{org_id}/members", response_model=list[OrgMemberResponse])
def list_org_members(org_id: UUID, user: dict[str, Any] = Depends(get_current_user)) -> list[OrgMemberResponse]:
    if user["role"] != "platform_admin":
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM org_memberships WHERE org_id = %s AND user_id = %s",
                    [str(org_id), str(user["id"])],
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=403, detail="Forbidden")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, org_id, user_id, member_role, created_at FROM org_memberships WHERE org_id = %s ORDER BY created_at DESC",
                [str(org_id)],
            )
            rows = cur.fetchall()

    return [
        OrgMemberResponse(
            id=_to_uuid(r[0]),
            org_id=_to_uuid(r[1]),
            user_id=_to_uuid(r[2]),
            member_role=r[3],
            created_at=r[4],
        )
        for r in rows
    ]


@app.get("/audit", response_model=list[AuditEventResponse])
def list_audit(
    patient_user_id: Optional[UUID] = None,
    limit: int = 100,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[AuditEventResponse]:
    limit = max(1, min(limit, 500))

    # patient can see own audit; platform_admin can see any; others forbidden in MVP
    if user["role"] == "patient":
        patient_user_id = user["id"]
    elif user["role"] == "platform_admin":
        pass
    else:
        raise HTTPException(status_code=403, detail="Forbidden")

    if patient_user_id is None:
        raise HTTPException(status_code=400, detail="patient_user_id required")

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, occurred_at, actor_user_id, actor_org_id, action, target_type, target_id,
                       patient_user_id, ip::text, user_agent, metadata
                FROM audit_events
                WHERE patient_user_id = %s
                ORDER BY occurred_at DESC
                LIMIT %s
                """,
                [str(patient_user_id), limit],
            )
            rows = cur.fetchall()

    def _meta(v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        try:
            return json.loads(v)
        except Exception:
            return {"raw": str(v)}

    return [
        AuditEventResponse(
            id=_to_uuid(r[0]),
            occurred_at=r[1],
            actor_user_id=_to_uuid(r[2]) if r[2] else None,
            actor_org_id=_to_uuid(r[3]) if r[3] else None,
            action=r[4],
            target_type=r[5],
            target_id=_to_uuid(r[6]) if r[6] else None,
            patient_user_id=_to_uuid(r[7]) if r[7] else None,
            ip=r[8],
            user_agent=r[9],
            metadata=_meta(r[10]),
        )
        for r in rows
    ]

