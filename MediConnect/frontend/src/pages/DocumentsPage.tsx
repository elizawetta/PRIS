import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type { ApiError } from "../lib/api";
import type { Document, DocumentType } from "../lib/types";
import { useAuth } from "../auth/AuthContext";

const DOC_TYPES: DocumentType[] = ["note", "lab_result", "discharge", "prescription", "imaging", "other"];

export function DocumentsPage() {
  const { state } = useAuth();
  const me = state.status === "authenticated" ? state.me : null;

  const [items, setItems] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [patientUserId, setPatientUserId] = useState("");
  const [actorOrgId, setActorOrgId] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [docType, setDocType] = useState<DocumentType>("other");
  const [title, setTitle] = useState("");
  const [contentText, setContentText] = useState("");
  const [issuedAt, setIssuedAt] = useState("");

  const canCreate = useMemo(() => me?.role === "patient", [me?.role]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const list = await api<Document[]>("/documents", {
        query: {
          patient_user_id: patientUserId || undefined,
          actor_org_id: actorOrgId || undefined,
        },
      });
      setItems(list);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api<Document>("/documents", {
        method: "POST",
        json: {
          doc_type: docType,
          title,
          content_text: contentText,
          issued_at: issuedAt || null,
        },
      });
      setCreateOpen(false);
      setTitle("");
      setContentText("");
      setIssuedAt("");
      await load();
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
    }
  }

  return (
    <div className="stack">
      <div className="row">
        <div>
          <h2>Documents</h2>
          <div className="muted">List accessible documents (by consents). For org-based access, pass `actor_org_id`.</div>
        </div>
        <div className="row">
          <button className="btn" onClick={load}>
            Refresh
          </button>
          <button className="btn primary" disabled={!canCreate} onClick={() => setCreateOpen((v) => !v)}>
            New document
          </button>
        </div>
      </div>

      {!canCreate && (
        <div className="notice">
          <b>Note:</b> In this MVP only <code>patient</code> can create own documents.
        </div>
      )}

      <div className="card">
        <div className="filters">
          <label>
            <div className="label">patient_user_id (optional)</div>
            <input value={patientUserId} onChange={(e) => setPatientUserId(e.target.value)} placeholder="uuid" />
          </label>
          <label>
            <div className="label">actor_org_id (optional)</div>
            <input value={actorOrgId} onChange={(e) => setActorOrgId(e.target.value)} placeholder="uuid" />
          </label>
          <button className="btn" onClick={load} style={{ alignSelf: "end" }}>
            Apply
          </button>
        </div>
      </div>

      {createOpen && (
        <div className="card">
          <h3>Create document</h3>
          <form className="form" onSubmit={onCreate}>
            <label>
              <div className="label">Type</div>
              <select value={docType} onChange={(e) => setDocType(e.target.value as DocumentType)}>
                {DOC_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <div className="label">Title</div>
              <input value={title} onChange={(e) => setTitle(e.target.value)} required />
            </label>
            <label>
              <div className="label">Content (string)</div>
              <textarea value={contentText} onChange={(e) => setContentText(e.target.value)} rows={5} required />
            </label>
            <label>
              <div className="label">Issued at (YYYY-MM-DD)</div>
              <input value={issuedAt} onChange={(e) => setIssuedAt(e.target.value)} placeholder="2026-04-15" />
            </label>
            <div className="row">
              <button className="btn primary" type="submit" disabled={!canCreate}>
                Create
              </button>
              <button className="btn" type="button" onClick={() => setCreateOpen(false)}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <div className="card">
        {loading ? (
          <div>Loading...</div>
        ) : items.length === 0 ? (
          <div className="muted">No documents</div>
        ) : (
          <div className="table">
            <div className="tr head">
              <div>ID</div>
              <div>Type</div>
              <div>Title</div>
              <div>Patient</div>
              <div>Issued</div>
              <div>Created</div>
            </div>
            {items.map((d) => (
              <details key={d.id} className="tr">
                <summary className="tr-sum">
                  <div className="mono">{d.id}</div>
                  <div>{d.doc_type}</div>
                  <div>{d.title}</div>
                  <div className="mono">{d.patient_user_id}</div>
                  <div className="mono">{d.issued_at || "-"}</div>
                  <div className="mono">{new Date(d.created_at).toLocaleString()}</div>
                </summary>
                <div className="tr-body">
                  <div className="label">content_text</div>
                  <pre className="pre">{d.content_text}</pre>
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

