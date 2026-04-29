#!/usr/bin/env bash
set -euo pipefail

# Convert the already-built static Next.js export into Vercel's Build Output
# API layout so GitHub Actions can deploy it with `vercel deploy --prebuilt`.
# This keeps Python artifact generation and `next build` on the CI runner,
# not on Vercel's remote Git build machine.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STATIC_OUT="apps/web/out"
PREBUILT_OUT=".vercel/output"

if [ ! -d "$STATIC_OUT" ]; then
  echo "$STATIC_OUT does not exist; run scripts/refresh_web_artifacts.sh and apps/web pnpm build first" >&2
  exit 1
fi

rm -rf "$PREBUILT_OUT"
mkdir -p "$PREBUILT_OUT/static"
cp -R "$STATIC_OUT/." "$PREBUILT_OUT/static/"
cat > "$PREBUILT_OUT/config.json" <<'JSON'
{
  "version": 3
}
JSON

printf 'Prepared Vercel prebuilt output at %s from %s\n' "$PREBUILT_OUT" "$STATIC_OUT"
