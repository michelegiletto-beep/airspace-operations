import { useEffect, useState } from 'react';

const storageKey = 'sl-companion-motion';
const eventName = 'sl-companion-motion';

function readPreference() {
  try { return localStorage.getItem(storageKey) !== 'off'; }
  catch { return true; }
}

export function useCompanionMotion() {
  const [enabled, setEnabled] = useState(readPreference);
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);

  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const updatePreference = (event: Event) => {
      const value = (event as CustomEvent<boolean>).detail;
      setEnabled(typeof value === 'boolean' ? value : readPreference());
    };
    const updateSystem = () => setReduced(query?.matches ?? false);
    window.addEventListener(eventName, updatePreference);
    query?.addEventListener?.('change', updateSystem);
    return () => {
      window.removeEventListener(eventName, updatePreference);
      query?.removeEventListener?.('change', updateSystem);
    };
  }, []);

  function toggle() {
    if (reduced) return;
    const next = !enabled;
    try { localStorage.setItem(storageKey, next ? 'on' : 'off'); }
    catch { /* The current page can still honour the preference. */ }
    setEnabled(next);
    window.dispatchEvent(new CustomEvent(eventName, { detail: next }));
  }

  return { motion: enabled && !reduced, enabled, reduced, toggle };
}
