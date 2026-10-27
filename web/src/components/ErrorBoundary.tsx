import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Error de interfaz", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="screen-message">
          <div className="panel message-panel">
            <h2>La vista encontro un error</h2>
            <p>La aplicacion sigue activa. Recarga la pagina para volver al panel.</p>
            <button className="btn primary" onClick={() => window.location.reload()}>
              Recargar
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
