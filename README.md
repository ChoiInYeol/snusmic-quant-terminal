# SNUSMIC quant simulation data

SNUSMIC 리서치 PDF에서 목표가·티커·메타데이터를 추출하고, 가격 데이터와 결합해 서버에서 투자 시뮬레이션을 재현하는 Python/data 저장소입니다.

저장소의 계약은 Python 코드와 `data/` 아래 CSV/JSON 구조입니다.

## 고정 시나리오

현재 백테스트는 다음 저축/투자 가정을 기준으로 생성됩니다.

- 초기 투자금: 10,000,000원
- 월 적립금: 1,000,000원
- 리밸런싱일마다 현금이 남지 않도록 비중 재조정
- `oracle`: 미래를 아는 예언자 전략. 구간 내 효율적인 long-only 진입/청산을 선택
- `smic_follower_1n`: SNUSMIC 추종자 전략. 1/N 투자, 목표가 도달 시 매도, 미도달/하락 구간에는 목표가 도달을 믿고 계속 적립금 투입

## 남기는 데이터 구조

- `data/extracted_reports.csv` — PDF에서 추출한 리포트/목표가 원천 테이블
- `data/price_metrics.json` — 추출 행별 가격/목표가 메트릭
- `data/portfolio_backtests.json` — legacy 호환 전략 결과
- `data/warehouse/*.csv` — v3 normalized warehouse
- `data/quant_v3/*.json` — 서버/분석 도구가 바로 읽을 v3 전략·런·일별 지분곡선 JSON
- `docs/schemas/*.json` — 공개 데이터 계약 스키마

## 재생산 명령

```bash
uv sync --group dev
uv run python -m snusmic_pipeline refresh-market
uv run python -m snusmic_pipeline build-warehouse
uv run python -m snusmic_pipeline refresh-prices
uv run python -m snusmic_pipeline run-backtest
uv run python -m snusmic_pipeline export-dashboard
```

`export-dashboard`라는 CLI 이름은 호환성을 위해 남겨두었지만, 실제 의미는 `data/quant_v3/` JSON export입니다.

## 검증

```bash
uv run pytest tests/ -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python scripts/export_schemas.py --check
uv run python scripts/check_schema_compat.py --base-ref origin/main
```

## CI

GitHub Actions는 Python lint/type/test/schema 검증과 데이터 refresh을 수행합니다.
