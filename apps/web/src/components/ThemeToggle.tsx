'use client';

/**
 * Phase 6a — minimal Sun/Moon toggle for ``next-themes``. Cycles between
 * ``light`` and ``dark`` only; ``system`` is reachable via the OS
 * preference (re-loading with no override). Rendered after the provider
 * has hydrated to avoid an SSR/CSR mismatch on initial paint.
 */

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const next = resolvedTheme === 'dark' ? 'light' : 'dark';
  const label = resolvedTheme === 'dark' ? '라이트 모드로' : '다크 모드로';

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={() => setTheme(next)}
      aria-label={label}
      title={label}
    >
      <span aria-hidden="true">{resolvedTheme === 'dark' ? '☀' : '☾'}</span>
    </button>
  );
}
