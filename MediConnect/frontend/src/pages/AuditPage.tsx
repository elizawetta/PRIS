import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { ApiError } from "../lib/api";
import type { AuditEvent } from "../lib/types";
import { useAuth } from "../auth/AuthContext";

export function AuditPage() {
  const { state } = useAuth();
  const me = state.status === "authenticated" ? state.me : null;

  const [items, setItems] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [patientUserId, setPatientUserId] = useState("");
  const [limit, setLimit] = useState(200);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const list = await api<AuditEvent[]>("/audit", {
        query: {
          patient_user_id: patientUserId || undefined,
          limit,
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

  return (
    <div className="stack">
      <div className="row">
        <div>
          <h2>Audit</h2>
          <div className="muted">
            Patient sees own audit. <code>platform_admin</code> can specify <code>patient_user_id</code>.
          </div>
        </div>
        <div className="row">
          <button className="btn" onClick={load}>
            Refresh
          </button>
        </div>
      </div>

      <div className="card">
        <div className="filters">
          <label>
            <div className="label">limit</div>
            <input
              value={String(limit)}
              onChange={(e) => setLimit(Number(e.target.value || "200"))}
              inputMode="numeric"
              placeholder="200"
            />
          </label>
          <label>
            <div className="label">patient_user_id (admin only)</div>
            <input
              value={patientUserId}
              onChange={(e) => setPatientUserId(e.target.value)}
              placeholder={me?.role === "platform_admin" ? "uuid" : "N/A"}
              disabled={me?.role !== "platform_admin"}
            />
          </label>
          <button className="btn" onClick={load} style={{ alignSelf: "end" }}>
            Apply
          </button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="card">
        {loading ? (
          <div>Loading...</div>
        ) : items.length === 0 ? (
          <div className="muted">No events</div>
        ) : (
          <div className="table">
            <div className="tr head">
              <div>Time</div>
              <div>Action</div>
              <div>Target</div>
              <div>Actor</div>
              <div>Patient</div>
            </div>
            {items.map((e) => (
              <details key={e.id} className="tr">
                <summary className="tr-sum">
                  <div className="mono">{new Date(e.occurred_at).toLocaleString()}</div>
                  <div>{e.action}</div>
                  <div className="mono">
                    {e.target_type}:{e.target_id || "-"}
                  </div>
                  <div className="mono">{e.actor_user_id || "-"}</div>
                  <div className="mono">{e.patient_user_id || "-"}</div>
                </summary>
                <div className="tr-body">
                  <div className="label">metadata</div>
                  <pre className="pre">{JSON.stringify(e.metadata || {}, null, 2)}</pre>
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

