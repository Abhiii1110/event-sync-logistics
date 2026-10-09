import { useEffect, useMemo, useState } from "react";
import api, { errorMessage } from "../api/client";
import { addDays, dayLabel, slotStart, timeLabel, todayIST } from "../utils/time";

const FIRST_HOUR = 6;    // earliest start time offered
const LAST_HOUR = 22;    // latest start time offered
const DAYS_AHEAD = 14;

export default function AvailabilityCalendar({ vendorId, service, selected, onSelect }) {
  const today = todayIST();
  const [date, setDate] = useState(today);
  const [busy, setBusy] = useState([]);
  const [status, setStatus] = useState("loading");   // loading | ready | error
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const days = useMemo(
    () => Array.from({ length: DAYS_AHEAD }, (_, i) => addDays(today, i)),
    [today]
  );

  // Load busy windows for the chosen day AND the next day
  useEffect(() => {
    let ignore = false;
    setStatus("loading");

    const fetchDay = (d) =>
      api.get(`/bookings/vendors/${vendorId}/busy/`, { params: { date: d } });

    Promise.all([fetchDay(date), fetchDay(addDays(date, 1))])
      .then(([a, b]) => {
        if (ignore) return;
        setBusy(
          [...a.data, ...b.data].map((w) => ({
            start: new Date(w.start),
            end: new Date(w.end),
          }))
        );
        setStatus("ready");
      })
      .catch((err) => {
        if (ignore) return;
        setError(errorMessage(err));
        setStatus("error");
      });

    return () => { ignore = true; };
  }, [vendorId, date, reloadKey]);

  const slots = useMemo(() => {
    const durationMs = service.duration_minutes * 60000;
    const now = Date.now();
    const list = [];
    for (let h = FIRST_HOUR; h <= LAST_HOUR; h++) {
      const start = slotStart(date, h);
      const end = new Date(start.getTime() + durationMs);
      let state = "free";
      if (start.getTime() <= now) state = "past";
      else if (busy.some((w) => start < w.end && end > w.start)) state = "busy";
      list.push({ start, end, state });
    }
    return list;
  }, [busy, date, service.duration_minutes]);

  const pickDate = (d) => {
    setDate(d);
    onSelect(null);
  };

  return (
    <div>
      <div className="date-strip">
        {days.map((d) => (
          <button
            key={d}
            type="button"
            className={`date-btn ${d === date ? "active" : ""}`}
            onClick={() => pickDate(d)}
          >
            {dayLabel(d)}
          </button>
        ))}
      </div>

      {status === "loading" && <p className="muted-text">Checking availability...</p>}

      {status === "error" && (
        <p className="error">
          {error}{" "}
          <button type="button" className="secondary" onClick={() => setReloadKey((k) => k + 1)}>
            Retry
          </button>
        </p>
      )}

      {status === "ready" && (
        <>
          <div className="slot-grid">
            {slots.map((s) => {
              const isSelected = selected && selected.getTime() === s.start.getTime();
              return (
                <button
                  key={s.start.toISOString()}
                  type="button"
                  disabled={s.state !== "free"}
                  className={`slot ${s.state} ${isSelected ? "selected" : ""}`}
                  title={s.state === "busy" ? "Already booked" : s.state === "past" ? "In the past" : "Available"}
                  onClick={() => onSelect(isSelected ? null : s.start)}
                >
                  {timeLabel(s.start)}
                </button>
              );
            })}
          </div>
          <div className="legend">
            <span><i className="dot free" /> Available</span>
            <span><i className="dot busy" /> Booked</span>
            <span><i className="dot past" /> Past</span>
            <span><i className="dot selected" /> Selected</span>
          </div>
        </>
      )}
    </div>
  );
}