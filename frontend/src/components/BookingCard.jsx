import { useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import { formatPaise } from "../utils/format";
import { dateTimeLabel, timeLabel } from "../utils/time";
import CancelForm from "./CancelForm";
import ReasonForm from "./ReasonForm";
import StatusBadge from "./StatusBadge";

export default function BookingCard({ booking: b, viewer, onChanged }) {
  const isVendor = viewer === "VENDOR";
  const [mode, setMode] = useState(null);      // "cancel" | "decline" | "dispute"
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const start = new Date(b.start_time);
  const end = new Date(b.end_time);
  const ended = end.getTime() <= Date.now();
  const holdActive = b.status === "PENDING_PAYMENT" && (b.hold_seconds_left ?? 0) > 0;
  const holdExpired = b.status === "PENDING_PAYMENT" && !holdActive;
  const isCancelled = b.status === "CANCELLED" || b.status === "REFUNDED";
  const canDispute =
    !isVendor && b.status === "COMPLETED" && b.payout_status === "PENDING" &&
    b.payout_release_at && new Date(b.payout_release_at) > new Date();

  const close = () => setMode(null);
  const done = () => { setMode(null); onChanged(); };

  const act = async (path) => {
    setBusy(true);
    setError("");
    try {
      await api.post(`/bookings/${b.id}/${path}/`);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="booking">
      <div className="booking-head">
        <div>
          <h3>{b.service_title}</h3>
          <p className="muted-text">{isVendor ? `Client: ${b.client_name}` : b.vendor_name}</p>
        </div>
        <StatusBadge status={b.status} viewer={viewer} expired={holdExpired} />
      </div>

      <p><strong>{dateTimeLabel(start)}</strong> to {timeLabel(end)}</p>
      <p>{b.event_location}</p>
      {b.notes && <p className="muted-text">Notes: {b.notes}</p>}

      {isVendor ? (
        <p className="muted-text">
          Total {formatPaise(b.total_paise)} · platform fee {formatPaise(b.platform_fee_paise)} ·{" "}
          <strong>you receive {formatPaise(b.vendor_amount_paise)}</strong>
        </p>
      ) : (
        <p className="price">{formatPaise(b.total_paise)}</p>
      )}

      {isVendor && b.payout_status && (
        <p className="muted-text">
          Payout: {b.payout_status.toLowerCase()}
          {b.payout_status === "PENDING" && b.payout_release_at &&
            <> (released after {dateTimeLabel(new Date(b.payout_release_at))})</>}
        </p>
      )}
      {!isVendor && b.status === "COMPLETED" && b.payout_status === "PENDING" && (
        <p className="muted-text">The vendor is paid after a short review window, so you can still report a problem.</p>
      )}
      {!isVendor && b.payout_status === "DISPUTED" && (
        <p className="muted-text">Your report is under review.</p>
      )}

      {isCancelled && (
        <p className="muted-text">
          Cancelled by {b.cancelled_by.toLowerCase()}
          {b.cancel_reason && <>: {b.cancel_reason}</>}
          {b.refund_paise > 0 && (
            <> · Refund {formatPaise(b.refund_paise)} ({b.refund_status === "DONE" ? "sent" : "processing"})</>
          )}
        </p>
      )}

      {error && <p className="error">{error}</p>}

      {mode === null && (
        <div className="row">
          {!isVendor && holdActive && (
            <Link className="btn" to={`/bookings/${b.id}/pay`}>Pay now</Link>
          )}
          {!isVendor && b.status === "PENDING_PAYMENT" && (
            <button className="secondary" onClick={() => setMode("cancel")}>
              {holdActive ? "Cancel" : "Remove"}
            </button>
          )}
          {!isVendor && ["PAID", "VENDOR_CONFIRMED"].includes(b.status) && !ended && (
            <button className="secondary" onClick={() => setMode("cancel")}>Cancel booking</button>
          )}
          {canDispute && (
            <button className="secondary" onClick={() => setMode("dispute")}>Report a problem</button>
          )}

          {isVendor && b.status === "PAID" && (
            <>
              <button disabled={busy} onClick={() => act("confirm")}>{busy ? "Please wait..." : "Confirm"}</button>
              <button className="secondary" onClick={() => setMode("decline")}>Decline</button>
            </>
          )}
          {isVendor && b.status === "VENDOR_CONFIRMED" && !ended && (
            <button className="secondary" onClick={() => setMode("cancel")}>Cancel booking</button>
          )}
          {isVendor && b.status === "VENDOR_CONFIRMED" && ended && (
            <button disabled={busy} onClick={() => act("complete")}>{busy ? "Please wait..." : "Mark completed"}</button>
          )}
        </div>
      )}

      {mode === "cancel" && <CancelForm booking={b} actor={viewer} onDone={done} onClose={close} />}

      {mode === "decline" && (
        <ReasonForm
          intro={<p>The client will be refunded in full.</p>}
          label="Reason (optional)"
          submitLabel="Decline booking"
          danger
          onSubmit={async (reason) => {
            await api.post(`/bookings/${b.id}/decline/`, { reason });
            done();
          }}
          onClose={close}
        />
      )}

      {mode === "dispute" && (
        <ReasonForm
          intro={<p>Reporting a problem pauses the vendor's payout until the platform team reviews it.</p>}
          label="What went wrong?"
          submitLabel="Submit report"
          required
          onSubmit={async (reason) => {
            await api.post(`/payments/bookings/${b.id}/dispute/`, { reason });
            done();
          }}
          onClose={close}
        />
      )}
    </div>
  );
}