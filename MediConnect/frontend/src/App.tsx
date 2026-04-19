import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import "./App.css";
import { useAuth } from "./auth/AuthContext";
import { AuditPage } from "./pages/AuditPage";
import { ConsentsPage } from "./pages/ConsentsPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { LoginPage } from "./pages/LoginPage";
import { OrgsPage } from "./pages/OrgsPage";
import { RegisterPage } from "./pages/RegisterPage";

function Protected({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();
  const loc = useLocation();
  if (state.status === "loading") return <div className="container">Loading...</div>;
  if (state.status === "anonymous") return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

function TopNav() {
  const { state, logout } = useAuth();
  return (
    <header className="topbar">
      <div className="container topbar-inner">
        <div className="brand">
          <span className="brand-dot" />
          <span>MediConnect</span>
        </div>
        <nav className="nav">
          <Link to="/documents">Documents</Link>
          <Link to="/consents">Consents</Link>
          <Link to="/orgs">Orgs</Link>
          <Link to="/audit">Audit</Link>
        </nav>
        <div className="topbar-right">
          {state.status === "authenticated" ? (
            <>
              <span className="me">
                {state.me.display_name} ({state.me.role})
              </span>
              <button className="btn" onClick={logout}>
                Logout
              </button>
            </>
          ) : (
            <Link className="btn" to="/login">
              Login
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <>
      <TopNav />
      <main className="container" style={{ paddingTop: 18, paddingBottom: 28 }}>
        <Routes>
          <Route path="/" element={<Navigate to="/documents" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/documents"
            element={
              <Protected>
                <DocumentsPage />
              </Protected>
            }
          />
          <Route
            path="/consents"
            element={
              <Protected>
                <ConsentsPage />
              </Protected>
            }
          />
          <Route
            path="/orgs"
            element={
              <Protected>
                <OrgsPage />
              </Protected>
            }
          />
          <Route
            path="/audit"
            element={
              <Protected>
                <AuditPage />
              </Protected>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}
