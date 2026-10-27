import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { useAuth } from "./lib/auth";
import { Admin } from "./pages/Admin";
import { Agent } from "./pages/Agent";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { Pipeline } from "./pages/Pipeline";
import { Reports } from "./pages/Reports";

function RequireAuth({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function NotFound() {
  return (
    <div className="screen-message">
      <div className="panel message-panel">
        <h1>Pagina no encontrada</h1>
        <p className="muted">La ruta solicitada no existe en SismoWatch.</p>
        <a className="btn primary" href="/dashboard">
          Volver al dashboard
        </a>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/agente" element={<Agent />} />
          <Route path="/reportes" element={<Reports />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/admin" element={<Admin />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </ErrorBoundary>
  );
}
