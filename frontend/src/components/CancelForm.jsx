import { useEffect, useState } from "react";
import api, { errorMessage } from "../api/client";
import { formatPaise } from "../utils/format";
import ReasonForm from "./ReasonForm";

export default function CancelForm({ booking, actor, onDone, onClose }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");

  // Ask the server what the refund would be BEFORE the user commits
  useEffect(() => {
    let ignore = false;
    api.get(`/bookings/${booking.id}/cancel-preview/`)
      .then(({ data }) => { if (!ignore) setPreview(data); })
      .catch((err) => { if (!ignore) setError(errorMessage(err)); });
    return () => { ignore = true; };
  }, [booking.id]);

  if (error) return <p className="error">{error}</p>;
  if (!preview) return <p className="muted-text">Checking the refund...</p>;
  if (!preview.can_cancel) return <p className="muted-text">This booking can no longer be cancelled.</p>;

  let intro;
  if (booking.status === "PENDING_PAYMENT") {
    intro = <p>No payment has been taken, so there is nothing to refund.</p>;
  } else if (actor === "VENDOR") {
    intro = <p>The client will be refunded <strong>{formatPaise(preview.refund_paise)}</strong> (in full).</p>;
  } else {
    intro = (
      <p>If you cancel now you get back <strong>{formatPaise(preview.refund_paise)}</strong> of {formatPaise(preview.total_paise)}.</p>
    );
  }

  return (
    <ReasonForm
      intro={intro}
      label="Reason (optional)"
      submitLabel="Confirm cancellation"
      danger
      onSubmit={async (reason) => {
        await api.post(`/bookings/${booking.id}/cancel/`, { reason });
        onDone();
      }}
      onClose={onClose}
    />
  );
}