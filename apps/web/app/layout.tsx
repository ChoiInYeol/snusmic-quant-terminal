import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'SNUSMIC Quant Showcase',
  description: 'Report evidence, price paths, data quality, and strategy methodology for the SNUSMIC quant simulation.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <div className="site-shell">
          <header className="topbar">
            <Link className="brand" href="/">SNUSMIC Quant</Link>
            <nav className="nav" aria-label="Primary navigation">
              <Link href="/reports">Reports</Link>
              <Link href="/data-quality">Data quality</Link>
              <Link href="/methodology">Methodology</Link>
            </nav>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
