/**
 * Phase 6b — small UI primitives extracted from the original ``app/page.tsx``
 * monolith. Stateless, theme-aware via globals.css tokens.
 */

export function Metric({ title, value, tone = '' }: { title: string; value: string; tone?: string }) {
  return (
    <article className={`metric ${tone}`}>
      <span>{title}</span>
      <strong>{value}</strong>
    </article>
  );
}

export function SectionIntro({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="section-intro">
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p>{body}</p>
    </div>
  );
}
