import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("bagn_token");
    if (!token) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => localStorage.removeItem("bagn_token"))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    localStorage.setItem("bagn_token", r.data.token);
    setUser({ email: r.data.email });
  };

  const logout = () => {
    localStorage.removeItem("bagn_token");
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthCtx.Provider>
  );
};

export const useAuth = () => useContext(AuthCtx);
