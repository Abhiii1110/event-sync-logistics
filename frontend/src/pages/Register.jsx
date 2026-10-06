import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: "", email: "", password: "", phone: "", role: "CLIENT",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await register(form);
      navigate("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>Create account</h2>
      <form onSubmit={onSubmit}>
        <label>I am a
          <select name="role" value={form.role} onChange={onChange}>
            <option value="CLIENT">Event planner (client)</option>
            <option value="VENDOR">Vendor</option>
          </select>
        </label>
        <label>Username
          <input name="username" value={form.username} onChange={onChange} required />
        </label>
        <label>Email
          <input name="email" type="email" value={form.email} onChange={onChange} required />
        </label>
        <label>Phone (optional)
          <input name="phone" value={form.phone} onChange={onChange} />
        </label>
        <label>Password (min 8 characters)
          <input name="password" type="password" minLength={8} value={form.password} onChange={onChange} required />
        </label>
        {error && <p className="error">{error}</p>}
        <button disabled={busy}>{busy ? "Creating..." : "Sign up"}</button>
      </form>
      <p>Already registered? <Link to="/login">Log in</Link></p>
    </div>
  );
}