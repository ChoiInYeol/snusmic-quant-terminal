import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'SNUSMIC Quant Terminal',
  description: 'Candidate pool 기반 SNUSMIC 리서치 전략 대시보드',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
