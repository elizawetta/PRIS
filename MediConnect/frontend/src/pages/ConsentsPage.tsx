import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { ApiError } from "../lib/api";
import type { Consent, ConsentScope } from "../lib/types";
import { useAuth } from "../auth/AuthContext";

export function ConsentsPage() {
  const { state } = useAuth();
  const me = state.status === "authenticated" ? state.me : null;

  const [items, setItems] = useState<Consent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [open, setOpen] = useState(false);
  const [grantedToUserId, setGrantedToUserId] = useState("");
  const [grantedToOrgId, setGrantedToOrgId] = useState("");
  const [scope, setScope] = useState<ConsentScope>("single_document");
  const [documentId, setDocumentId] = useState("");
  const [purpose, setPurpose] = useState("treatment");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const list = await api<Consent[]>("/consents");
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
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const payload: any = { scope, purpose };
      if (grantedToUserId) payload.granted_to_user_id = grantedToUserId;
      if (grantedToOrgId) payload.granted_to_org_id = grantedToOrgId;
      if (scope === "single_document") payload.document_id = documentId;
      await api<Consent>("/consents", { method: "POST", json: payload });
      setOpen(false);
      setGrantedToUserId("");
      setGrantedToOrgId("");
      setDocumentId("");
      await load();
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
    }
  }

  async function revoke(id: string) {
    setError(null);
    try {
      await api<Consent>(`/consents/${id}/revoke`, { method: "POST" });
      await load();
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
    }
  }

  const canGrant = me?.role === "patient";

  return (
    <div className="stack">
      <div className="row">
        <div>
          <h2>Consents</h2>
          <div className="muted">
            Patient sees issued consents; doctor sees received consents; platform_admin sees all.
          </div>
        </div>
        <div className="row">
          <button className="btn" onClick={load}>
            Refresh
          </button>
          <button className="btn primary" disabled={!canGrant} onClick={() => setOpen((v) => !v)}>
            New consent
          </button>
        </div>
      </div>

      {!canGrant && (
        <div className="notice">
          <b>Note:</b> In this MVP only <code>patient</code> can grant/revoke consents.
        </div>
      )}

      {open && (
        <div className="card">
          <h3>Create consent</h3>
          <form className="form" onSubmit={onCreate}>
            <div className="grid-2">
              <label>
                <div className="label">granted_to_user_id (doctor)</div>
                <input value={grantedToUserId} onChange={(e) => setGrantedToUserId(e.target.value)} placeholder="uuid" />
              </label>
              <label>
                <div className="label">granted_to_org_id</div>
                <input value={grantedToOrgId} onChange={(e) => setGrantedToOrgId(e.target.value)} placeholder="uuid" />
              </label>
            </div>
            <label>
              <div className="label">Scope</div>
              <select value={scope} onChange={(e) => setScope(e.target.value as ConsentScope)}>
                <option value="single_document">single_document</option>
                <option value="all_documents">all_documents</option>
              </select>
            </label>
            {scope === "single_document" && (
              <label>
                <div className="label">document_id</div>
                <input value={documentId} onChange={(e) => setDocumentId(e.target.value)} placeholder="uuid" required />
              </label>
            )}
            <label>
              <div className="label">purpose</div>
              <input value={purpose} onChange={(e) => setPurpose(e.target.value)} />
            </label>
            <div className="row">
              <button className="btn primary" type="submit" disabled={!canGrant}>
                Create
              </button>
              <button className="btn" type="button" onClick={() => setOpen(false)}>
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
          <div className="muted">No consents</div>
        ) : (
          <div className="table">
            <div className="tr head">
              <div>ID</div>
              <div>Status</div>
              <div>Scope</div>
              <div>Granted to</div>
              <div>Document</div>
              <div>Valid until</div>
              <div></div>
            </div>
            {items.map((c) => (
              <div key={c.id} className="tr">
                <div className="mono">{c.id}</div>
                <div>{c.status}</div>
                <div>{c.scope}</div>
                <div className="mono">{c.granted_to_user_id || c.granted_to_org_id || "-"}</div>
                <div className="mono">{c.document_id || "-"}</div>
                <div className="mono">{c.valid_until ? new Date(c.valid_until).toLocaleString() : "-"}</div>
                <div style={{ textAlign: "right" }}>
                  <button className="btn" disabled={!canGrant || c.status !== "active"} onClick={() => revoke(c.id)}>
                    Revoke
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

