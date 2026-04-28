export default function MethodologyPage() {
  return (
    <>
      <section className="hero">
        <div className="eyebrow">Methodology</div>
        <h1>Python computes. Next.js explains.</h1>
        <p>The web app is an artifact viewer for the existing SNUSMIC pipeline, not a second simulation engine.</p>
      </section>
      <section className="grid">
        <div className="panel">
          <h2>Pipeline boundary</h2>
          <p>SNUSMIC PDFs are downloaded and converted to markdown, target prices/tickers/publication dates are extracted to CSV, yfinance prices are normalized to KRW, and the Python simulation writes report-level and persona artifacts under <code>data/</code>.</p>
        </div>
        <div className="panel">
          <h2>Report evidence model</h2>
          <p>Each detail page joins <code>data/sim/report_performance.csv</code>, <code>data/warehouse/reports.csv</code>, markdown snippets, and <code>data/warehouse/daily_prices.csv</code>. The chart marks publication date, extracted target price, and target-hit date when available.</p>
        </div>
        <div className="panel">
          <h2>Strategy honesty</h2>
          <p>Oracle/prophet personas are upper bounds with future information. SMIC follower personas are mechanical baselines. Future Optuna runs must stay local-only and export results as artifacts for public visualization.</p>
        </div>
        <div className="panel">
          <h2>Static deployment</h2>
          <p>Next.js uses static export so Vercel/GitHub Pages can serve a reproducible snapshot. The public app must not trigger Optuna, market-data refreshes, or PDF parsing.</p>
        </div>
      </section>
    </>
  );
}
