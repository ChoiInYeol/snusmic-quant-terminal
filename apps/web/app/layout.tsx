import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'SNUSMIC Quant Terminal',
  description: 'SNUSMIC 리포트 기반 가격 기회와 MTT 전략 성과 대시보드',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
