// Event times are always shown in India time, whatever the browser's timezone is.
export const TZ = "Asia/Kolkata";
export const TZ_OFFSET = "+05:30";

// Today's date in India as "YYYY-MM-DD"
export function todayIST() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
}

// Plain calendar-date maths on "YYYY-MM-DD" strings
export function addDays(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

// The exact moment of "hour:00 India time" on a given date
export function slotStart(dateStr, hour) {
  return new Date(`${dateStr}T${String(hour).padStart(2, "0")}:00:00${TZ_OFFSET}`);
}

export function dayLabel(dateStr) {
  return new Date(`${dateStr}T12:00:00Z`).toLocaleDateString("en-IN", {
    timeZone: "UTC", weekday: "short", day: "numeric", month: "short",
  });
}

export function timeLabel(date) {
  return date.toLocaleTimeString("en-IN", {
    timeZone: TZ, hour: "numeric", minute: "2-digit", hour12: true,
  });
}

export function dateTimeLabel(date) {
  return date.toLocaleString("en-IN", {
    timeZone: TZ, weekday: "short", day: "numeric", month: "short",
    hour: "numeric", minute: "2-digit", hour12: true,
  });
}