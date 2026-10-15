import { useCallback, useEffect, useState } from "react";
import api, { errorMessage } from "../api/client";
import { categoryLabel } from "../utils/constants";
import { formatDuration, formatPaise } from "../utils/format";
import ServiceForm from "./ServiceForm";

export default function ServicesManager() {
  const [services, setServices] = useState([]);
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");
  const [rowError, setRowError] = useState("");
  const [editing, setEditing] = useState(null);     // the service being edited
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/vendors/me/services/");
      setServices(Array.isArray(data) ? data : data.results ?? []);
      setState("ready");
    } catch (err) {
      setError(errorMessage(err));
      setState("error");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const saved = async () => {
    setEditing(null);
    setAdding(false);
    await load();
  };

  const toggle = async (s) => {
    setRowError("");
    try {
      await api.patch(`/vendors/me/services/${s.id}/`, { is_active: !s.is_active });
      await load();
    } catch (err) {
      setRowError(errorMessage(err));
    }
  };

  const remove = async (s) => {
    if (!window.confirm(`Delete "${s.title}"? This cannot be undone.`)) return;
    setRowError("");
    try {
      await api.delete(`/vendors/me/services/${s.id}/`);
      await load();
    } catch (err) {
      setRowError(errorMessage(err));
    }
  };

  if (state === "loading") return <p className="muted-text">Loading services...</p>;
  if (state === "error") return <p className="error">{error}</p>;

  return (
    <div className="panel">
      <div className="section-head">
        <h3>Your services</h3>
        {!adding && (
          <button onClick={() => { setAdding(true); setEditing(null); }}>Add a service</button>
        )}
      </div>
      <p className="muted-text">
        Hidden services disappear from the marketplace. Existing bookings are not affected.
        Price and duration changes only apply to new bookings.
      </p>

      {adding && <ServiceForm onSaved={saved} onCancel={() => setAdding(false)} />}
      {rowError && <p className="error">{rowError}</p>}
      {services.length === 0 && !adding && (
        <p className="muted-text">No services yet. Add your first one so clients can book you.</p>
      )}

      {services.map((s) => (
        <div key={s.id} className={`service-row ${s.is_active ? "" : "inactive"}`}>
          {editing?.id === s.id ? (
            <ServiceForm service={s} onSaved={saved} onCancel={() => setEditing(null)} />
          ) : (
            <>
              <div>
                <strong>{s.title}</strong>{" "}
                {!s.is_active && <span className="badge bad">Hidden</span>}
                <div className="muted-text">
                  {categoryLabel(s.category)} · {formatDuration(s.duration_minutes)} · {formatPaise(s.price_paise)}
                </div>
                {s.description && <div className="muted-text">{s.description}</div>}
              </div>
              <div className="row">
                <button className="secondary" onClick={() => { setEditing(s); setAdding(false); }}>Edit</button>
                <button className="secondary" onClick={() => toggle(s)}>{s.is_active ? "Hide" : "Show"}</button>
                <button className="secondary" onClick={() => remove(s)}>Delete</button>
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}