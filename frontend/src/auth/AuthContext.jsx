import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api, { tokenStore } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  // The API client fires this event when a refresh fails
  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener("auth:logout", onLogout);
    return () => window.removeEventListener("auth:logout", onLogout);
  }, []);

  // On first load, restore the session if a token exists
  useEffect(() => {
    if (!tokenStore.access) {
      setLoading(false);
      return;
    }
    api.get("/auth/me/")
      .then(({ data }) => setUser(data))
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  const login = async (username, password) => {
    const { data } = await api.post("/auth/login/", { username, password });
    tokenStore.set(data.access, data.refresh);
    const me = await api.get("/auth/me/");
    setUser(me.data);
    return me.data;
  };

  const register = async (form) => {
    await api.post("/auth/register/", form);
    return login(form.username, form.password);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);