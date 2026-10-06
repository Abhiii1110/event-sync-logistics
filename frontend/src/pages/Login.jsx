import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(form.username, form.password);
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.status === 401 ? "Wrong username or password." : errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>Log in</h2>
      <form onSubmit={onSubmit}>
        <label>Username
          <input name="username" value={form.username} onChange={onChange} required />
        </label>
        <label>Password
          <input name="password" type="password" value={form.password} onChange={onChange} required />
        </label>
        {error && <p className="error">{error}</p>}
        <button disabled={busy}>{busy ? "Logging in..." : "Log in"}</button>
      </form>
      <p>New here? <Link to="/register">Create an account</Link></p>
    </div>
  );
}