// Backend stores money as integer paise. Convert only for display.
export const formatPaise = (paise) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(paise / 100);

export const formatDuration = (minutes) => {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (!h) return `${m} min`;
  return m ? `${h} h ${m} min` : `${h} h`;
};

// Vendors type rupees; the backend stores integer paise. Returns null if invalid.
export function rupeesToPaise(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 1) return null;
  return Math.round(n * 100);
}

export const paiseToRupees = (paise) => (paise / 100).toFixed(2);