import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'SNUSMIC 매매 대시보드',
  description: 'SNUSMIC 리포트 기반 전략의 매매내역, 현재 포트폴리오, 과거 포트폴리오, 원문 근거를 제공하는 한국어 투자 대시보드입니다.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" data-scroll-behavior="smooth">
      <body>
        <div className="site-shell">
          <header className="topbar">
            <Link className="brand" href="/" aria-label="SNUSMIC 매매 대시보드 홈">
              <span>
                SNUSMIC Ledger
                <span className="brand-kicker">trades · portfolio · evidence</span>
              </span>
            </Link>
            <nav className="nav" aria-label="주요 탐색">
              <Link href="/trades">매매내역</Link>
              <Link href="/portfolio">포트폴리오</Link>
              <Link href="/reports">리포트 근거</Link>
              <Link href="/strategies">전략 기준</Link>
            </nav>
          </header>
          <main>{children}</main>
          <footer className="footer-note">
            이 화면은 커밋된 CSV/JSON/Markdown/PDF 아티팩트만 표시합니다. 원문은 GitHub 또는 SNUSMIC PDF 링크로 확인할 수 있습니다.
          </footer>
        </div>
      </body>
    </html>
  );
}
