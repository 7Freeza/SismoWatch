export function Loading({ label = "Cargando datos" }: { label?: string }) {
  return (
    <div className="feedback">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="feedback error" role="alert">
      <span>{message}</span>
      {onRetry ? (
        <button className="btn small" onClick={onRetry}>
          Reintentar
        </button>
      ) : null}
    </div>
  );
}

export function Empty({ message }: { message: string }) {
  return <div className="feedback empty">{message}</div>;
}

export function LiveBadge({ connected }: { connected: boolean }) {
  return (
    <span className={`live-badge ${connected ? "on" : "off"}`}>
      <span className="dot" />
      {connected ? "EN VIVO" : "RECONECTANDO"}
    </span>
  );
}
