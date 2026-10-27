import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";

export function Login() {
  const { session, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@sismowatch.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (session) return <Navigate to="/dashboard" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo iniciar sesion");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-hero">
        <span className="brand-mark large">SW</span>
        <h1>SismoWatch</h1>
        <p>
          Monitoreo sismico global en tiempo casi real. Ingesta USGS, calidad de datos y
          consultas en lenguaje natural sobre la capa curated.
        </p>
        <ul>
          <li>Dashboard, mapa y eventos en vivo</li>
          <li>Reportes diarios generados con IA</li>
          <li>Agente IA con SQL de solo lectura</li>
        </ul>
      </div>
      <form className="panel login-panel" onSubmit={submit}>
        <h2>Iniciar sesion</h2>
        <p className="muted">Credenciales sembradas desde variables de entorno.</p>
        <label>
          Correo
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoComplete="username"
          />
        </label>
        <label>
          Contrasena
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        {error ? <div className="feedback error">{error}</div> : null}
        <button className="btn primary full" type="submit" disabled={loading}>
          {loading ? "Validando..." : "Entrar"}
        </button>
        <div className="login-help">
          <span>Admin: admin@sismowatch.local</span>
          <span>Viewer: viewer@sismowatch.local</span>
          <span>Las contrasenas estan en el README y en .env.</span>
        </div>
      </form>
    </div>
  );
}
