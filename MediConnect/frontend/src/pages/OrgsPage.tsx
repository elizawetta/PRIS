import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { ApiError } from "../lib/api";
import type { Org, OrgMember } from "../lib/types";
import { useAuth } from "../auth/AuthContext";

export function OrgsPage() {
  const { state } = useAuth();
  const me = state.status === "authenticated" ? state.me : null;

  const [orgs, setOrgs] = useState<Org[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string>("");
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newOrgName, setNewOrgName] = useState("");
  const [addUserId, setAddUserId] = useState("");
  const [addRole, setAddRole] = useState<"member" | "admin">("member");

  const canCreateOrg = me?.role === "org_admin" || me?.role === "platform_admin";

  async function loadOrgs() {
    setLoading(true);
    setError(null);
    try {
      const list = await api<Org[]>("/orgs");
      setOrgs(list);
      if (!selectedOrgId && list.length > 0) setSelectedOrgId(list[0].id);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadMembers(orgId: string) {
    setError(null);
    try {
      const list = await api<OrgMember[]>(`/orgs/${orgId}/members`);
      setMembers(list);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
    }
  }

  useEffect(() => {
    void loadOrgs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedOrgId) void loadMembers(selectedOrgId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgId]);

  async function createOrg(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const org = await api<Org>("/orgs", { method: "POST", json: { name: newOrgName } });
      setNewOrgName("");
      await loadOrgs();
      setSelectedOrgId(org.id);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
    }
  }

  async function addMember(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedOrgId) return;
    setError(null);
    try {
      await api<OrgMember>(`/orgs/${selectedOrgId}/members`, {
        method: "POST",
        json: { user_id: addUserId, member_role: addRole },
      });
      setAddUserId("");
      await loadMembers(selectedOrgId);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
    }
  }

  return (
    <div className="stack">
      <div className="row">
        <div>
          <h2>Organizations</h2>
          <div className="muted">List orgs and manage memberships (role permitting).</div>
        </div>
        <div className="row">
          <button className="btn" onClick={loadOrgs}>
            Refresh
          </button>
        </div>
      </div>

      {canCreateOrg && (
        <div className="card">
          <h3>Create org</h3>
          <form className="row" onSubmit={createOrg}>
            <input value={newOrgName} onChange={(e) => setNewOrgName(e.target.value)} placeholder="Org name" required />
            <button className="btn primary">Create</button>
          </form>
          <div className="muted" style={{ marginTop: 8 }}>
            Creator is automatically added as <code>admin</code> member.
          </div>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <div className="grid-2">
        <div className="card">
          <h3>My orgs</h3>
          {loading ? (
            <div>Loading...</div>
          ) : orgs.length === 0 ? (
            <div className="muted">No orgs</div>
          ) : (
            <div className="listbox">
              {orgs.map((o) => (
                <button
                  key={o.id}
                  className={"listbox-item " + (o.id === selectedOrgId ? "active" : "")}
                  onClick={() => setSelectedOrgId(o.id)}
                >
                  <div>{o.name}</div>
                  <div className="mono muted">{o.id}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="row" style={{ alignItems: "baseline" }}>
            <h3 style={{ margin: 0 }}>Members</h3>
            {selectedOrgId && <span className="mono muted">{selectedOrgId}</span>}
          </div>

          {selectedOrgId && (
            <>
              <form className="row" onSubmit={addMember} style={{ marginTop: 12 }}>
                <input value={addUserId} onChange={(e) => setAddUserId(e.target.value)} placeholder="user_id uuid" required />
                <select value={addRole} onChange={(e) => setAddRole(e.target.value as any)}>
                  <option value="member">member</option>
                  <option value="admin">admin</option>
                </select>
                <button className="btn">Add</button>
              </form>

              <div className="table" style={{ marginTop: 12 }}>
                <div className="tr head">
                  <div>User</div>
                  <div>Role</div>
                  <div>Created</div>
                </div>
                {members.map((m) => (
                  <div key={m.id} className="tr">
                    <div className="mono">{m.user_id}</div>
                    <div>{m.member_role}</div>
                    <div className="mono">{new Date(m.created_at).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          {!selectedOrgId && <div className="muted">Select an org</div>}
        </div>
      </div>
    </div>
  );
}

