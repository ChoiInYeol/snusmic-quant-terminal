import type { Metadata } from 'next';
import './globals.css';
import { NuqsAdapter } from 'nuqs/adapters/next/app';
import { ThemeProvider } from '../src/components/ThemeProvider';

export const metadata: Metadata = {
  title: 'SNUSMIC Quant Terminal',
  description: 'SNUSMIC 리포트 기반 가격 기회와 MTT 전략 성과 대시보드',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // ``suppressHydrationWarning`` lets next-themes set ``data-theme`` on
    // the <html> tag during pre-paint without React flagging it as a
    // hydration mismatch (server emits no attribute; client injects one
    // before the first React render). Closes Phase 6a AC #3 — no FOUC on
    // first load with prefers-color-scheme: dark.
    <html lang="ko" suppressHydrationWarning>
      <body>
        {/* Phase 6c — ``NuqsAdapter`` lets ``useQueryState`` round-trip
            dashboard navigation state (selected runId, symbol, query) to
            the URL bar. ``ThemeProvider`` wraps children so theme +
            URL-state hooks both work in nested client components. */}
        <NuqsAdapter>
          <ThemeProvider>{children}</ThemeProvider>
        </NuqsAdapter>
      </body>
    </html>
  );
}
