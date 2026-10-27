import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { clearSession, getSession, login as loginRequest, onLogout, saveSession } from "./api";
import type { Session } from "./types";

interface AuthContextValue {
  session: Session | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => getSession());

  useEffect(() => {
    const unsubscribe = onLogout(() => setSession(null));
    return unsubscribe;
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      login: async (email, password) => {
        const next = await loginRequest(email, password);
        saveSession(next);
        setSession(next);
      },
      logout: () => {
        clearSession();
        setSession(null);
      }
    }),
    [session]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
