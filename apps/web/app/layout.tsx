import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'SNUSMIC 퀀트 터미널',
  description: 'SNUSMIC 리포트 근거, 가격 경로, 데이터 품질, 전략 방법론을 정적 아티팩트로 탐색하는 한국어 터미널입니다.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <div className="site-shell">
          <header className="topbar">
            <Link className="brand" href="/" aria-label="SNUSMIC 퀀트 터미널 홈">
              <span>
                SNUSMIC Quant
                <span className="brand-kicker">Korean evidence terminal</span>
              </span>
            </Link>
            <nav className="nav" aria-label="주요 탐색">
              <Link href="/reports">리포트</Link>
              <Link href="/strategies">전략</Link>
              <Link href="/data-quality">데이터 품질</Link>
              <Link href="/methodology">방법론</Link>
              <Link href="/lab">연구실</Link>
            </nav>
          </header>
          <main>{children}</main>
          <footer className="footer-note">
            정적 내보내기 호환: 배포된 웹은 커밋된 CSV/JSON/Markdown 아티팩트만 읽고, 시장 데이터·PDF·Optuna 작업을 실행하지 않습니다.
          </footer>
        </div>
      </body>
    </html>
  );
}
