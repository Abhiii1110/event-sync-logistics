import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import ServicesManager from "../components/ServicesManager";

function ProfileForm({ profile, onSaved }) {
  const [form, setForm] = useState({
    business_name: profile?.business_name ?? "",
    city: profile?.city ?? "",
    description: profile?.description ?? "",
    service_radius_km: profile?.service_radius_km ?? 25,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const onChange = (e) => {
    setSaved(false);
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    const payload = {
      business_name: form.business_name.trim(),
      city: form.city.trim(),
      description: form.description.trim(),
      service_radius_km: Number(form.service_radius_km),
    };
    try {
      const { data } = profile
        ? await api.patch("/vendors/me/profile/", payload)
        : await api.post("/vendors/me/profile/", payload);
      setSaved(true);
      onSaved(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={onSubmit}>
      <label>Business name
        <input name="business_name" value={form.business_name} onChange={onChange} maxLength={150} required />
      </label>
      <label>City
        <input name="city" value={form.city} onChange={onChange} maxLength={80} required placeholder="e.g. Pune" />
      </label>
      <label>About your business (optional)
        <textarea name="description" rows={3} value={form.description} onChange={onChange} />
      </label>
      <label>Service radius (km)
        <input name="service_radius_km" type="number" min="1" max="500" value={form.service_radius_km} onChange={onChange} required />
      </label>
      {error && <p className="error">{error}</p>}
      {saved && <p className="muted-text">Saved.</p>}
      <button disabled={busy}>{busy ? "Saving..." : profile ? "Save profile" : "Create profile"}</button>
    </form>
  );
}

export default function VendorBusiness() {
  const [profile, setProfile] = useState(null);
  const [state, setState] = useState("loading");      // loading | none | ready | error
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/vendors/me/profile/");
      setProfile(data);
      setState("ready");
    } catch (err) {
      if (err.response?.status === 404) setState("none");
      else {
        setError(errorMessage(err));
        setState("error");
      }
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onSaved = (data) => {
    setProfile(data);
    setState("ready");
  };

  if (state === "loading") return <p className="center">Loading...</p>;
  if (state === "error") return <p className="error center">{error}</p>;

  return (
    <div>
      <div className="page-head">
        <h2>My business</h2>
        <Link to="/dashboard">&larr; Dashboard</Link>
      </div>

      {profile && !profile.is_verified && (
        <p className="notice">
          Waiting for verification. Clients can't see your business yet. (In this demo, an admin
          ticks "Is verified" in the Django admin.)
        </p>
      )}
      {profile?.is_verified && (
        <p className="muted-text">
          Your business is live. <Link to={`/vendors/${profile.id}`}>View your public page</Link>
        </p>
      )}

      <div className="panel">
        <h3>Business profile</h3>
        <ProfileForm key={profile?.id ?? "new"} profile={profile} onSaved={onSaved} />
      </div>

      {profile ? (
        <ServicesManager />
      ) : (
        <p className="muted-text">Save your profile first, then you can add services.</p>
      )}
    </div>
  );
}