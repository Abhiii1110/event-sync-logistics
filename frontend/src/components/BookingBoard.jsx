import { useCallback, useEffect, useState } from "react";
import api, { errorMessage } from "../api/client";
import BookingCard from "./BookingCard";

export default function BookingBoard({ viewer, tabs, onChanged }) {
  const [bookings, setBookings] = useState([]);
  const [tabKey, setTabKey] = useState(tabs[0].key);
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/bookings/");
      setBookings(Array.isArray(data) ? data : data.results ?? []);
      setState("ready");
    } catch (err) {
      setError(errorMessage(err));
      setState("error");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const changed = async () => {
    await load();
    onChanged?.();
  };

  if (state === "loading") return <p className="center">Loading bookings...</p>;
  if (state === "error") {
    return (
      <p className="error center">
        {error} <button className="secondary" onClick={load}>Retry</button>
      </p>
    );
  }

  const current = tabs.find((t) => t.key === tabKey);
  const visible = bookings.filter(current.match);

  return (
    <div>
      <div className="tabs">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`tab ${t.key === tabKey ? "active" : ""}`}
            onClick={() => setTabKey(t.key)}
          >
            {t.label} ({bookings.filter(t.match).length})
          </button>
        ))}
      </div>

      {visible.length === 0 && <p className="center muted-text">{current.empty}</p>}
      {visible.map((b) => (
        <BookingCard key={b.id} booking={b} viewer={viewer} onChanged={changed} />
      ))}
    </div>
  );
}