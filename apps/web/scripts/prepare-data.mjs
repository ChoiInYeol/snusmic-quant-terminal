import { cp, mkdir, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = path.resolve(webRoot, '../..');
const target = path.join(webRoot, 'public', 'data');

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });

const copies = [
  ['data/quant_v3', 'quant_v3'],
  ['data/price_metrics.json', 'price_metrics.json'],
  ['data/portfolio_backtests.json', 'portfolio_backtests.json'],
  ['site/public/data/reports.json', 'reports.json'],
  ['site/public/data/site_summary.json', 'site_summary.json'],
];

for (const [sourceRel, destRel] of copies) {
  const source = path.join(repoRoot, sourceRel);
  if (!existsSync(source)) continue;
  await cp(source, path.join(target, destRel), { recursive: true });
}
