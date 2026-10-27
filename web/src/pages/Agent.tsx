import { useEffect, useRef, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import type { AskResponse } from "../lib/types";
import { Empty, ErrorBox } from "../components/Feedback";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  response?: AskResponse;
  failed?: boolean;
}

const SUGGESTIONS = [
  "Hola",
  "Cuantos sismos se registraron en las ultimas 24 horas?",
  "Cual fue el sismo de mayor magnitud en los ultimos 7 dias?",
  "Que regiones tienen mas actividad en los ultimos 7 dias?",
  "Hubo eventos con alerta de tsunami en las ultimas 24 horas?",
  "Cual es la magnitud promedio de las ultimas 24 horas?",
  "Cual fue el sismo mas profundo de los ultimos 7 dias?",
  "Muestrame los ultimos 10 sismos."
];

export function Agent() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function ask(text: string) {
    const clean = text.trim();
    if (!clean || loading) return;
    const history = messages.slice(-6).map((message) => ({
      role: message.role,
      content: message.text
    }));
    setMessages((current) => [...current, { role: "user", text: clean }]);
    setQuestion("");
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch<AskResponse>("/api/ask", {
        method: "POST",
        body: JSON.stringify({ question: clean, history })
      });
      setMessages((current) => [
        ...current,
        { role: "assistant", text: response.answer, response }
      ]);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "El agente no pudo responder la consulta";
      setMessages((current) => [
        ...current,
        { role: "assistant", text: message, failed: true }
      ]);
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Agente IA de consultas</h1>
          <p className="muted">
            Conversa en lenguaje natural. El agente responde con datos reales de curated y te
            deja la tabla y el SQL validado como evidencia.
          </p>
        </div>
        <span className="badge">Solo lectura · curated</span>
      </header>

      {error ? <ErrorBox message={error} /> : null}

      <section className="panel agent-panel">
        <div className="suggestions">
          {SUGGESTIONS.map((item) => (
            <button key={item} className="chip" onClick={() => ask(item)} disabled={loading}>
              {item}
            </button>
          ))}
        </div>

        <div className="chat">
          {messages.length === 0 ? (
            <Empty message="Pregunta lo que quieras sobre la actividad sísmica. También puedes saludarme." />
          ) : (
            messages.map((message, index) => (
              <div key={index} className={`chat-row ${message.role}`}>
                <div className={`bubble ${message.failed ? "failed" : ""}`}>
                  <p>{message.text}</p>
                  {message.response && message.response.rows.length > 0 ? (
                    <div className="table-wrap agent-table">
                      <table>
                        <thead>
                          <tr>
                            {message.response.columns.map((column) => (
                              <th key={column}>{column}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {message.response.rows.slice(0, 50).map((row, rowIndex) => (
                            <tr key={rowIndex}>
                              {message.response?.columns.map((column) => (
                                <td key={column}>{String(row[column] ?? "")}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  {message.response?.sql ? (
                    <details className="sql-box">
                      <summary>Ver SQL validado</summary>
                      <pre>{message.response.sql}</pre>
                      {message.response.explanation ? (
                        <p className="muted">{message.response.explanation}</p>
                      ) : null}
                      <div className="badges">
                        <span className="badge">respuesta: {message.response.answer_provider}</span>
                        <span className="badge">consulta: {message.response.provider}</span>
                        <span className="badge">filas: {message.response.row_count}</span>
                        <span className="badge">validado</span>
                      </div>
                    </details>
                  ) : null}
                </div>
              </div>
            ))
          )}
          {loading ? (
            <div className="chat-row assistant">
              <div className="bubble typing">
                <span className="spinner" /> Procesando la consulta...
              </div>
            </div>
          ) : null}
          <div ref={endRef} />
        </div>

        <form
          className="chat-input"
          onSubmit={(event) => {
            event.preventDefault();
            ask(question);
          }}
        >
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ejemplo: cuantos sismos hubo en las ultimas 24 horas?"
            maxLength={500}
            disabled={loading}
          />
          <button className="btn primary" type="submit" disabled={loading || !question.trim()}>
            Preguntar
          </button>
        </form>
      </section>
    </div>
  );
}
