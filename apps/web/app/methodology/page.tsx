export default function MethodologyPage() {
  return (
    <>
      <section className="hero"><div className="eyebrow">Methodology</div><h1>Python computes. Next.js explains.</h1><p>The public app is a static artifact viewer for the existing SNUSMIC data and simulation pipeline.</p></section>
      <section className="grid">
        <div className="panel"><h2>Pipeline boundary</h2><p>PDF/markdown extraction writes report rows, yfinance/FX normalization writes the warehouse, and Python simulations write persona/report artifacts. The web app reads generated JSON only.</p></div>
        <div className="panel"><h2>Baseline personas</h2><p>SMIC Follower strategies mechanically rebalance around published reports. Prophet variants are labeled lookahead upper bounds. All-Weather is a benchmark basket.</p></div>
        <div className="panel"><h2>Local Optuna</h2><p>Strategy search runs locally via Python scripts and exports <code>strategy-runs.json</code>, <code>optuna-trials.json</code>, and parameter-importance artifacts. The web runtime never imports Optuna or runs optimization.</p></div>
        <div className="panel"><h2>Public disclaimer</h2><p>This is an educational backtest and extraction audit. It is not investment advice and does not guarantee future performance.</p></div>
      </section>
    </>
  );
}
