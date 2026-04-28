import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'SNUSMIC Quant Showcase',
  description: 'SMIC 리포트 기반 백테스트, 리포트 증거, 데이터 품질, 로컬 Optuna 전략 쇼케이스.',
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
              <Link href="/strategies">Strategies</Link>
              <Link href="/lab">Lab</Link>
              <Link href="/data-quality">Data quality</Link>
              <Link href="/methodology">Methodology</Link>
            </nav>
          </header>
          <main>{children}</main>
          <footer className="footer">투자 추천 아님 · Python 산출물을 읽는 정적 쇼케이스 · Optuna는 로컬에서만 실행</footer>
        </div>
      </body>
    </html>
  );
}
