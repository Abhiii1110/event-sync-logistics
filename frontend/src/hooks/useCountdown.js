import { useEffect, useState } from "react";

// Counts down from a number of seconds the SERVER gave us.
// Returns null when there is nothing to count.
export default function useCountdown(initialSeconds) {
  const [target, setTarget] = useState(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (initialSeconds == null) {
      setTarget(null);
      return;
    }
    const t = Date.now();
    setNow(t);
    setTarget(t + initialSeconds * 1000);
  }, [initialSeconds]);

  useEffect(() => {
    if (target == null) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [target]);

  if (initialSeconds == null) return null;
  if (target == null) return initialSeconds;   // first render, before the effect runs
  return Math.max(0, Math.ceil((target - now) / 1000));
}