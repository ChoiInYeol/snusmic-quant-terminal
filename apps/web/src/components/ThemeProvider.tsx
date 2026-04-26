'use client';

/**
 * Phase 6a — light wrapper around ``next-themes``' provider so the rest of
 * the app can stay theme-agnostic. ``attribute='data-theme'`` keeps the CSS
 * selectors symmetric with ``[data-theme="dark"]`` in ``globals.css``.
 *
 * ``defaultTheme='system'`` follows the user's OS preference (per
 * docs/decisions / plan resolution: "system default lets OS preference
 * win"); ``enableSystem`` lets the toggle round-trip back to system.
 */

import { ThemeProvider as NextThemesProvider } from 'next-themes';
import type { ReactNode } from 'react';

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemesProvider
      attribute="data-theme"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
