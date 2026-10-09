import { STATUS } from "../utils/status";

export default function StatusBadge({ status, viewer, expired }) {
  const s = STATUS[status] || { label: status, tone: "info" };
  let { label, tone } = s;
  if (status === "PENDING_PAYMENT" && expired) { label = "Hold expired"; tone = "bad"; }
  if (status === "PAID" && viewer === "VENDOR") label = "Needs your response";
  return <span className={`badge ${tone}`}>{label}</span>;
}