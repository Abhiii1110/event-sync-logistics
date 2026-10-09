import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import BookingBoard from "../components/BookingBoard";
import { formatPaise } from "../utils/format";

const isDone = (b) => ["COMPLETED", "PAYOUT_RELEASED"].includes(b.status);
const isCancelled = (b) => ["CANCELLED", "REFUNDED"].includes(b.status);
const hasEnded = (b) => new Date(b.end_time) <= new Date();

const CLIENT_TABS = [
  {
    key: "active", label: "Active", empty: "No active bookings.",
    match: (b) => ["PENDING_PAYMENT", "PAID", "VENDOR_CONFIRMED"].includes(b.status),
  },
  { key: "completed", label: "Completed", empty: "No completed bookings yet.", match: isDone },
  { key: "cancelled", label: "Cancelled", empty: "No cancelled bookings.", match: isCancelled },
];

const VENDOR_TABS = [
  {
    key: "action", label: "Needs action", empty: "Nothing needs your attention.",
    match: (b) => b.status === "PAID" || (b.status === "VENDOR_CONFIRMED" && hasEnded(b)),
  },
  {
    key: "upcoming", label: "Upcoming", empty: "No upcoming bookings.",
    match: (b) =>
      (b.status === "PENDING_PAYMENT" && (b.hold_seconds_left ?? 0) > 0) ||
      (b.status === "VENDOR_CONFIRMED" && !hasEnded(b)),
  },
  { key: "completed", label: "Completed", empty: "No completed bookings yet.", match: isDone },
  { key: "cancelled", label: "Cancelled", empty: "No cancelled bookings.", match: isCancelled },
];

function Earnings({ refreshKey }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;
    api.get("/payments/earnings/")
      .then(({ data }) => { if (!ignore) setData(data); })
      .catch((err) => { if (!ignore) setError(errorMessage(err)); });
    return () => { ignore = true; };
  }, [refreshKey]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted-text">Loading earnings...</p>;

  const items = [
    ["Paid out", data.released_paise, "good"],
    ["Pending release", data.pending_paise, "info"],
    ["In dispute", data.disputed_paise, "warn"],
    ["Upcoming bookings", data.expected_paise, "info"],
  ];
  if (data.failed_paise > 0) items.push(["Needs attention", data.failed_paise, "bad"]);

  return (
    <div className="stats">
      {items.map(([label, paise, tone]) => (
        <div key={label} className={`stat ${tone}`}>
          <span className="muted-text">{label}</span>
          <strong>{formatPaise(paise)}</strong>
        </div>
      ))}
    </div>
  );
}

function ClientDashboard() {
  return (
    <div>
      <div className="page-head">
        <h2>My bookings</h2>
        <Link className="btn" to="/vendors">Find vendors</Link>
      </div>
      <BookingBoard viewer="CLIENT" tabs={CLIENT_TABS} />
    </div>
  );
}

function VendorDashboard() {
  const [refreshKey, setRefreshKey] = useState(0);
  return (
    <div>
      <h2>Vendor dashboard</h2>
      <Earnings refreshKey={refreshKey} />
      <BookingBoard
        viewer="VENDOR"
        tabs={VENDOR_TABS}
        onChanged={() => setRefreshKey((k) => k + 1)}
      />
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  return user.role === "VENDOR" ? <VendorDashboard /> : <ClientDashboard />;
}