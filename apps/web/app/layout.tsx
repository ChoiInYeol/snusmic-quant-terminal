import type { Metadata } from 'next';
import './globals.css';
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
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
