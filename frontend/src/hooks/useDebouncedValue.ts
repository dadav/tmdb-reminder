import { useEffect, useState } from "react";

/** Return `value` after it has stayed unchanged for `delayMs`. Used to debounce
 *  search input (350 ms) so keystrokes don't each trigger a request. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
