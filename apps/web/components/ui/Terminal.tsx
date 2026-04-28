import Link from 'next/link';
import type { ReactNode } from 'react';

type Tone = 'neutral' | 'good' | 'bad' | 'warn' | 'accent';

export function TerminalHero({ eyebrow, title, children, actions }: { eyebrow: string; title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="hero terminal-frame">
      <div className="terminal-frame__bar" aria-hidden="true"><span /><span /><span /></div>
      <div className="eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      <div className="hero-copy">{children}</div>
      {actions ? <div className="action-row">{actions}</div> : null}
    </section>
  );
}

export function MetricCard({ label, value, detail, tone = 'neutral' }: { label: string; value: ReactNode; detail?: ReactNode; tone?: Tone }) {
  return (
    <article className={`card metric-card tone-${tone}`}>
      <div className="muted">{label}</div>
      <div className="metric">{value}</div>
      {detail ? <p>{detail}</p> : null}
    </article>
  );
}

export function Panel({ title, children, className = '' }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`.trim()}>
      {title ? <h2>{title}</h2> : null}
      {children}
    </section>
  );
}

export function StatusPill({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`pill tone-${tone}`}>{children}</span>;
}

export function TerminalLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link className="terminal-link" href={href}>{children}</Link>;
}
