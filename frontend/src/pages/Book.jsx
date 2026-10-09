import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import { formatDuration, formatPaise } from "../utils/format";
import { dateTimeLabel, timeLabel } from "../utils/time";

export default function Book() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const [eventLocation, setEventLocation] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!state) return <Navigate to="/vendors" replace />;

  const start = new Date(state.startISO);
  const end = new Date(start.getTime() + state.durationMinutes * 60000);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/bookings/", {
        service_id: state.serviceId,
        start_time: state.startISO,
        event_location: eventLocation.trim(),
        notes: notes.trim(),
      });
      // replace: the Back button should not return to a form that already created a booking
      navigate(`/bookings/${data.id}/pay`, { replace: true });
    } catch (err) {
      if (err.response?.status === 409) {
        navigate(`/vendors/${state.vendorId}`, {
          replace: true,
          state: {
            notice:
              "That time is no longer available. Someone else may have booked it, or it is on hold for an unpaid booking. Please pick another slot.",
          },
        });
        return;
      }
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <div className="card wide">
      <h2>Confirm your booking</h2>

      <div className="summary-box">
        <p><strong>{state.serviceTitle}</strong> with {state.vendorName}</p>
        <p>{dateTimeLabel(start)} to {timeLabel(end)} ({formatDuration(state.durationMinutes)})</p>
        <p className="price">{formatPaise(state.pricePaise)}</p>
      </div>

      <form onSubmit={onSubmit}>
        <label>Event location
          <input
            value={eventLocation}
            onChange={(e) => setEventLocation(e.target.value)}
            maxLength={255}
            required
            placeholder="Venue and area, e.g. Green Lawns, Baner, Pune"
          />
        </label>
        <label>Notes for the vendor (optional)
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Guest count, setup access, special requests..."
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button disabled={busy}>{busy ? "Reserving your slot..." : "Reserve slot and continue to payment"}</button>
      </form>

      <p className="muted-text">
        Your slot is held for a short time while you pay. If you don't pay in time, it is released.
      </p>
      <Link to={`/vendors/${state.vendorId}`}>&larr; Change time</Link>
    </div>
  );
}