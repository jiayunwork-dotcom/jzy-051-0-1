import { useEffect, useRef, useState } from "react";

// Returns a debounced copy of `value`. The spec fixes the settle time at
// ~150ms so rendering does not reflow on every keystroke.
export function useDebounced<T>(value: T, delayMs = 150): T {
  const [debounced, setDebounced] = useState(value);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setDebounced(value), delayMs);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [value, delayMs]);

  return debounced;
}
