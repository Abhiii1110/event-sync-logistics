import { useState } from "react";
import api, { errorMessage } from "../api/client";
import { CATEGORIES, PLATFORM_FEE_PERCENT } from "../utils/constants";
import { formatDuration, formatPaise, paiseToRupees, rupeesToPaise } from "../utils/format";

export default function ServiceForm({ service, onSaved, onCancel }) {
  const [form, setForm] = useState({
    category: service?.category ?? CATEGORIES[0].value,
    title: service?.title ?? "",
    description: service?.description ?? "",
    price: service ? paiseToRupees(service.price_paise) : "",
    duration_minutes: service?.duration_minutes ?? 240,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const paise = rupeesToPaise(form.price);
  const minutes = Number(form.duration_minutes);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (paise === null) {
      setError("Enter a price of at least ₹1.");
      return;
    }
    setBusy(true);
    const payload = {
      category: form.category,
      title: form.title.trim(),
      description: form.description.trim(),
      price_paise: paise,
      duration_minutes: minutes,
    };
    try {
      if (service) await api.patch(`/vendors/me/services/${service.id}/`, payload);
      else await api.post("/vendors/me/services/", payload);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <form className="inline-form" onSubmit={onSubmit}>
      <label>Category
        <select name="category" value={form.category} onChange={onChange}>
          {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </label>
      <label>Title
        <input name="title" value={form.title} onChange={onChange} maxLength={150} required
               placeholder="e.g. Street Food Package (up to 150 guests)" />
      </label>
      <label>Description (optional)
        <textarea name="description" rows={3} value={form.description} onChange={onChange}
                  placeholder="What is included, capacity, equipment..." />
      </label>
      <label>Price (₹)
        <input name="price" type="number" min="1" step="0.01" value={form.price}
               onChange={onChange} required />
      </label>
      <label>Duration (minutes)
        <input name="duration_minutes" type="number" min="30" max="1440" step="30"
               value={form.duration_minutes} onChange={onChange} required />
      </label>

      {paise !== null && (
        <p className="muted-text">
          Clients see {formatPaise(paise)} for {formatDuration(minutes || 0)}. After the{" "}
          {PLATFORM_FEE_PERCENT}% platform fee you receive about{" "}
          {formatPaise(paise - Math.floor((paise * PLATFORM_FEE_PERCENT) / 100))}.
        </p>
      )}

      {error && <p className="error">{error}</p>}
      <div className="row">
        <button disabled={busy}>{busy ? "Saving..." : service ? "Save changes" : "Add service"}</button>
        <button type="button" className="secondary" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
    </form>
  );
}