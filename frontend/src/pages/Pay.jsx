import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PayPalButtons, PayPalScriptProvider } from "@paypal/react-paypal-js";
import api, { errorMessage } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import useCountdown from "../hooks/useCountdown";
import { formatPaise } from "../utils/format";
import { dateTimeLabel, timeLabel } from "../utils/time";

const CLIENT_ID = import.meta.env.VITE_PAYPAL_CLIENT_ID;
const CURRENCY = import.meta.env.VITE_PAYPAL_CURRENCY || "USD";

const mmss = (s) =>
  `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

export default function Pay() {
  const { id } = useParams();
  const [booking, setBooking] = useState(null);
  const [state, setState] = useState("loading");     // loading | ready | notfound | error
  const [error, setError] = useState("");
  const [payError, setPayError] = useState("");
  const [processing, setProcessing] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/bookings/${id}/`);
      setBooking(data);
      setState("ready");
    } catch (err) {
      if (err.response?.status === 404) {
        setState("notfound");
      } else {
        setError(errorMessage(err));
        setState("error");
      }
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const awaiting = booking?.status === "PENDING_PAYMENT";
  const secondsLeft = useCountdown(awaiting ? booking.hold_seconds_left : null);

  if (state === "loading") return <p className="center">Loading...</p>;
  if (state === "notfound") {
    return <p className="center">Booking not found. <Link to="/dashboard">Go to my bookings</Link></p>;
  }
  if (state === "error") return <p className="error center">{error}</p>;

  const start = new Date(booking.start_time);
  const end = new Date(booking.end_time);
  const sandboxAmount = (booking.total_paise / 100).toFixed(2);

  const details = (
    <div className="summary-box">
      <p><strong>{booking.service_title}</strong> with {booking.vendor_name}</p>
      <p>{dateTimeLabel(start)} to {timeLabel(end)}</p>
      <p>{booking.event_location}</p>
      <p className="price">{formatPaise(booking.total_paise)}</p>
    </div>
  );

  // The server decides everything. These handlers only pass IDs.
  const createOrder = async () => {
    setPayError("");
    try {
      const { data } = await api.post("/payments/paypal/create-order/", { booking_id: booking.id });
      return data.paypal_order_id;
    } catch (err) {
      setPayError(errorMessage(err));
      throw err;
    }
  };

  const onApprove = async (data) => {
    setProcessing(true);
    setPayError("");
    try {
      await api.post("/payments/paypal/capture/", { paypal_order_id: data.orderID });
    } catch (err) {
      setPayError(
        `${errorMessage(err)} Do not pay again until you have checked your booking status in your dashboard.`
      );
    } finally {
      await load();            // shows the success screen if the payment really went through
      setProcessing(false);
    }
  };

  // 1. Waiting for payment and the hold is still active
  if (awaiting && secondsLeft > 0) {
    return (
      <div className="card wide">
        <h2>Pay for your booking</h2>
        {details}
        <p className={`timer ${secondsLeft < 120 ? "urgent" : ""}`}>Slot held for {mmss(secondsLeft)}</p>
        <p className="notice">
          Sandbox demo: PayPal will charge {CURRENCY} {sandboxAmount} (the rupee price divided by 100,
          with no real conversion). No real money moves.
        </p>

        {payError && <p className="error">{payError}</p>}
        {processing && <p className="notice">Confirming your payment. Please don't close this page...</p>}

        {!CLIENT_ID ? (
          <p className="error">
            PayPal is not configured. Set VITE_PAYPAL_CLIENT_ID in frontend/.env and restart npm run dev.
          </p>
        ) : (
          <PayPalScriptProvider options={{ clientId: CLIENT_ID, currency: CURRENCY, intent: "capture" }}>
            <PayPalButtons
              style={{ layout: "vertical" }}
              disabled={processing}
              createOrder={createOrder}
              onApprove={onApprove}
              onCancel={() => setPayError("Payment cancelled. You can try again while your slot is held.")}
              onError={() => setPayError((m) => m || "PayPal could not complete the payment. Please try again.")}
            />
          </PayPalScriptProvider>
        )}

        <p><Link to="/dashboard">Pay later from my bookings</Link></p>
      </div>
    );
  }

  // 2. The hold ran out
  if (awaiting) {
    return (
      <div className="card wide">
        <h2>Your slot hold has expired</h2>
        {details}
        <p>The time may now be available to other clients. You can try booking it again.</p>
        <Link className="btn" to={`/vendors/${booking.vendor}`}>Back to {booking.vendor_name}</Link>
      </div>
    );
  }

  // 3. Paid (or further along)
  if (["PAID", "VENDOR_CONFIRMED", "COMPLETED", "PAYOUT_RELEASED"].includes(booking.status)) {
    return (
      <div className="card wide">
        <h2>Payment received</h2>
        <p>Status: <StatusBadge status={booking.status} /></p>
        {details}
        {booking.status === "PAID" && (
          <p>
            The vendor now has a limited time to confirm. If they decline or don't respond,
            you are refunded in full.
          </p>
        )}
        <Link className="btn" to="/dashboard">View my bookings</Link>
      </div>
    );
  }

  // 4. Cancelled or refunded
  return (
    <div className="card wide">
      <h2>This booking was cancelled</h2>
      <p>Status: <StatusBadge status={booking.status} /></p>
      {details}
      <Link className="btn" to="/dashboard">View my bookings</Link>
    </div>
  );
}