import { useState } from "react";
import { errorMessage } from "../api/client";

export default function ReasonForm({ intro, label, submitLabel, required, danger, onSubmit, onClose }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSubmit(reason.trim());
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <form className="inline-form" onSubmit={submit}>
      {intro}
      <label>{label}
        <input value={reason} maxLength={255} required={required}
               onChange={(e) => setReason(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button className={danger ? "danger" : ""} disabled={busy}>
          {busy ? "Please wait..." : submitLabel}
        </button>
        <button type="button" className="secondary" onClick={onClose} disabled={busy}>Close</button>
      </div>
    </form>
  );
}