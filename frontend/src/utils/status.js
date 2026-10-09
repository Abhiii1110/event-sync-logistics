export const STATUS = {
  PENDING_PAYMENT: { label: "Awaiting payment", tone: "warn" },
  PAID: { label: "Paid, waiting for vendor", tone: "info" },
  VENDOR_CONFIRMED: { label: "Confirmed", tone: "good" },
  COMPLETED: { label: "Completed", tone: "good" },
  PAYOUT_RELEASED: { label: "Completed", tone: "good" },
  CANCELLED: { label: "Cancelled", tone: "bad" },
  REFUNDED: { label: "Cancelled, refunded", tone: "bad" },
};