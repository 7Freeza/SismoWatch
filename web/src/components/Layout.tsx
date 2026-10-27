import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/agente", label: "Agente IA" },
  { to: "/reportes", label: "Reportes" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/admin", label: "Administracion", admin: true }
];

export function Layout() {
  const { session, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">SW</span>
          <div>
            <strong>SismoWatch</strong>
            <small>Monitoreo sismico</small>
          </div>
        </div>
        <nav className="nav">
          {links
            .filter((link) => !link.admin || session?.role === "admin")
            .map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
              >
                {link.label}
              </NavLink>
            ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-card">
            <span>{session?.email}</span>
            <span className={`role-badge ${session?.role}`}>{session?.role}</span>
          </div>
          <button
            className="btn ghost full"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            Cerrar sesion
          </button>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
