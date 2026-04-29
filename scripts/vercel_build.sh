#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv sync --group dev
scripts/refresh_web_artifacts.sh

corepack enable
corepack prepare pnpm@10.33.2 --activate
(
  cd apps/web
  pnpm install --frozen-lockfile
  pnpm build
)

rm -rf public
mkdir -p public
cp -R apps/web/out/. public/
