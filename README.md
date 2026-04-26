# SNUSMIC Quant Simulation

서울대 SMIC(서울대학교 학생 투자 동아리, [snusmic.com](https://www.snusmic.com)) 리서치 PDF를 수집·파싱해 추출한 **목표가/티커/발간일 데이터**와, yfinance에서 받은 **KRW 환산 일봉 가격**을 결합해, 다양한 투자자 페르소나의 **계좌 단위 누적 수익률**을 재현하는 Python/data 저장소입니다.

> "예언자처럼 미래를 알고 사면 얼마, 추종자처럼 사라는대로만 사면 얼마, 1억 적금 + 월 100만원으로 5년 굴리면 얼마인지" 를 한 번에 보여줍니다.

이 저장소는 데이터 + 시뮬레이션 코드만 남긴 **server-simulation-first** 구조입니다. 프론트엔드(Vercel, GitHub Pages, Next.js)는 모두 제거되었고, 모든 결과물은 `data/` 디렉토리의 CSV/JSON과 PNG 차트입니다.

---

## 목차

1. [핵심 결과](#1-핵심-결과)
2. [무엇을 재현하나요?](#2-무엇을-재현하나요)
3. [페르소나 시뮬레이션](#3-페르소나-시뮬레이션)
4. [현실적 수익률 계산 — share-based 증권 원장](#4-현실적-수익률-계산--share-based-증권-원장)
5. [적립식 시나리오 (1천만 + 월 100만 + 2년마다 +50만)](#5-적립식-시나리오-1천만--월-100만--2년마다-50만)
6. [데이터 설계 (SSOT/SDD/TDD)](#6-데이터-설계-ssotsddtdd)
7. [저장소 구조](#7-저장소-구조)
8. [실행 방법](#8-실행-방법)
9. [산출물](#9-산출물)
10. [검증 / CI](#10-검증--ci)
11. [참고 문서](#11-참고-문서)

---

## 1. 핵심 결과

기간: **2021-01-04 → 2026-04-15** (약 5년 3개월, 영업일 1,313일)
저축 시나리오: **초기 1천만 + 월 100만 (2년마다 +50만 에스컬레이션) → 누적 1억 적립**
유니버스: SMIC 리서치 리포트 **216개, 종목 202개** (KRX/KOSDAQ/해외 ETF 포함, 모두 KRW 환산)

| 페르소나 | 최종 평가금 | 누적 적립 | 순이익 | IRR (현금흐름 가중) | 최대 낙폭 | 거래 수 |
|---|---:|---:|---:|---:|---:|---:|
| **Prophet** (예언자, 상한선) | 22억 4,911M | 1억 | **+21억 4,911M** | **134.94%** | 30.3% | 2,454 |
| **Weak Prophet** (6M 룩어헤드) | 15억 0,374M | 1억 | +14억 0,374M | 114.52% | 27.2% | 884 |
| **All-Weather** (벤치마크) | 2억 2,421M | 1억 | +1억 2,421M | 31.68% | 9.6% | 212 |
| **SMIC Follower** (1/N 충신) | 1억 4,274M | 1억 | +0억 4,274M | 13.94% | 11.4% | 3,238 |
| **SMIC Follower v2** (손절 추가) | 1억 2,597M | 1억 | +0억 2,597M | 9.06% | 9.0% | 1,574 |

![Equity curves](data/sim/equity_curves.png)

![Net profit bar](data/sim/net_profit_bar.png)

![Drawdowns](data/sim/drawdowns.png)

> 모든 평가금/순이익은 **share-based** 회계 — 정수 주식 + 가중평균원가 + 매수 0.015% 수수료 + 매도 0.18% 거래세 + 0.05% 슬리피지가 모든 체결에 적용된 결과입니다. 증권사 앱에서 보는 숫자와 같은 의미를 갖습니다.
>
> equity curve는 **로그 Y 축** — 직선의 기울기가 곧 CAGR이고, 5년 동안 100→1,000 (10x) 과 1,000→10,000 (10x)이 같은 시각적 거리로 보입니다. 마크-투-마켓은 종목 close가 결측되는 휴장/거래정지일에도 직전 close를 forward-fill (`board.asof`) 해서, 기존에 있던 가짜 −30% 스파이크를 제거했습니다.

핵심 관찰:

- **예언자 vs 약한 예언자**: 풀 룩어헤드와 6개월 룩어헤드의 차이는 +20%p IRR — 짧은 룩어헤드도 max-Sharpe를 통해 분산되면 큰 알파.
- **충신 vs 충신 v2**: 손절 룰 3종이 적용되면 MDD는 11.4% → 9.0%로 줄지만, 동시에 IRR도 13.9% → 9.1%로 깎입니다. **'손실 안 보는 대신 상승도 일부 포기'** 의 정량적 지표.
- **올웨더 vs 충신**: 단순 4분할 ETF 적립(MDD 9.6%)이 SMIC 1/N 적립(MDD 11.4%)을 IRR·MDD 양쪽에서 모두 제칩니다 — 추종자가 사라는 대로 사면 분산만으로는 부족하다는 증거.
- **All-Weather의 MDD가 9.6%로 낮은 이유**: 4자산이 서로 상관관계 0에 가깝고 (금 vs 미국 주식 vs 한국 주식), 매월 비중을 강제로 25/25/25/25 로 되돌리는 mean-reversion 효과 덕분.

---

## 2. 무엇을 재현하나요?

### 2-1. PDF 리서치 수집·추출 파이프라인

```
SNUSMIC 사이트 인덱스 → 218개 PDF 다운로드 → opendataloader-pdf로 OCR/텍스트 추출
        ↓
data/extracted_reports.csv  (리포트명, 종목명, 발간일, 목표가 Bear/Base/Bull, 티커, 거래소)
        ↓
yfinance로 종목별 일봉 다운로드 + 환율 변환 (USD/JPY/HKD/CNY → KRW)
        ↓
data/warehouse/daily_prices.csv  (전 종목 KRW 환산 OHLCV)
        ↓
data/warehouse/reports.csv       (목표가도 모두 KRW 환산)
```

이 데이터 자체가 한국어 리서치 PDF에서 정량 데이터를 끌어내는 **재현 가능한 추출 컨트랙트**의 산출물입니다. 추출 품질은 `data/extraction_quality.json` 으로 추적됩니다.

### 2-2. 두 종류의 시뮬레이션 모듈

저장소에는 의도적으로 분리된 두 개의 시뮬레이션 모듈이 있습니다:

| 모듈 | 목적 | 회계 방식 |
|---|---|---|
| `snusmic_pipeline.backtest` | **전략 최적화** — Optuna 그리드 탐색, 다양한 weighting 비교, walk-forward sortino OOS-tail | Weight-based (포지션 = float, 합 = 1.0) |
| `snusmic_pipeline.sim` | **페르소나 비교** — 사용자가 실제 1억 굴렸을 때 얼마인지 | **Share-based** (정수 주식, 현금 원장, 수수료/세금 차감) |

이 README는 주로 `sim` 모듈에 대한 설명입니다. 두 모듈은 같은 `data/warehouse/` 데이터를 공유합니다.

---

## 3. 페르소나 시뮬레이션

5개 페르소나(+1 벤치마크)가 동일한 적립 스케줄과 동일한 KRW 가격판을 입력 받아, 서로 다른 매수/매도 정책으로 운용됩니다.

### 3-1. `oracle` — Prophet (예언자, 상한선)

미래의 가격 경로를 다 알고 있는 가상의 투자자.

- 입금이 들어올 때마다 **활성 SMIC 리포트 종목 중 사후 peak return이 최고인 종목**을 점수화
- 최고 종목의 peak return이 두 번째 종목 대비 `dominance_threshold` (기본 1.5배) 이상이면 **100% 집중**, 아니면 peak return 비례 분산 (캡 `max_weight`)
- 각 포지션은 자기 peak 날짜에 정확히 매도되도록 스케줄됨

이 페르소나는 **상한선** 입니다. 실거래로 베틸 수 없는 숫자.

### 3-2. `weak_oracle` — Weak Prophet (6개월 룩어헤드)

미래 6개월의 가격 경로만 보는 페르소나. 6개월 lookahead-bias가 있지만 그 외엔 정상.

- 매월 첫 영업일 (또는 quarterly), 활성 SMIC 종목 유니버스에서
- 향후 6개월간의 **실현 일별 수익률**로 평균/공분산 계산
- `scipy.optimize.minimize` (SLSQP) 로 **long-only max-Sharpe 포트폴리오** 풀이 (sum=1, 종목당 캡 `max_weight=0.40`, 무위험금리 3%)
- 결과 비중대로 share book 리밸런스

룩어헤드를 6→12개월로 늘리거나 max-Sharpe를 min-CVaR로 바꾸려면 `WeakProphetConfig` 한 곳만 고치면 됩니다.

### 3-3. `smic_follower` — SMIC Follower v1 (1/N 충신)

> 사라는 대로 사고 무조건 목표가에 도달할거라고 믿는 충신. 그래서 손실을 봐도 매도를 안함.

- **활성 리포트** = 발간일이 오늘 이전이고, 아직 목표가에 도달 안한 리포트
- 매월 첫 영업일 또는 입금 시: 활성 종목 전부에 **1/N 비중 리밸런스** (현금이 남지 않게)
- 일별 검사: 보유 종목의 종가가 `목표가 × target_hit_multiplier` 이상이면 매도, 다음 리밸런스에서 현금 재분배
- **목표가 미도달 종목은 절대 매도하지 않음** — 손실이 -50%여도 보유

### 3-4. `smic_follower_v2` — SMIC Follower v2 (손절 룰 추가)

v1과 동일하지만 **세 가지 손절 게이트**가 추가됨:

| 룰 | 조건 | 기본값 |
|---|---|---|
| `time_loss` | 1년 이상 보유 AND 평가손실 상태 | 365일 |
| `averaged_down_stop` | 물타기(buy_count ≥ 2) AND 평가손실 < -X% | -20% |
| `report_age_stop` | 리포트 발간 후 X일 경과 AND 목표가 미도달 | 730일 (2년) |

손절된 종목은 **새로운 리포트가 다시 나올 때까지** 활성 풀에서 제외됩니다. 동일 종목에 대한 새 리포트는 다시 매수 신호.

### 3-5. `all_weather` — All-Weather 벤치마크

투자자의 다른 선택지: SMIC 리포트와 무관하게 **분산형 ETF 적립**.

| 자산 | yfinance 심볼 | 비중 |
|---|---|---|
| Gold | `GLD` | 25% |
| NASDAQ-100 | `QQQ` | 25% |
| S&P 500 | `SPY` | 25% |
| KOSPI 200 | `069500.KS` | 25% |

- 입금 시 25/25/25/25 비중으로 자동 분배
- 매월 첫 영업일에 가격 변동으로 어긋난 비중을 다시 25%로 리밸런스
- USD ETF는 yfinance 일봉을 USD/KRW 환율로 환산 (`data/warehouse/fx_rates.csv` 캐시)

> **벤치마크의 의미**: SMIC 종목으로 1/N 굴리는 것이 단순한 글로벌 분산 ETF DCA를 이기는지 직접 비교 가능합니다. 위 결과 표에서 보이듯, 현재 SMIC 1/N (충신) 은 All-Weather 를 이기지 못하고 있습니다.

---

## 4. 현실적 수익률 계산 — share-based 증권 원장

가장 중요한 설계 결정은 모든 페르소나가 **공통 share-based 회계**를 쓴다는 것입니다.

### 4-1. 계좌 상태

```
holdings[symbol] = {
    qty:           int,    # 정수 주식 (반올림하지 않음, floor)
    avg_cost_krw:  float,  # 가중평균 원가 (Korean retail 표준)
    total_cost_krw: float, # 보유분의 누적 매수원가 (수수료 포함)
    first_buy_date: date,  # 시간-손절 룰 평가용
    buy_count:    int,     # 물타기 손절 룰 평가용
    realized_pnl_krw: float
}
cash_krw:         float
contributed_krw:  float   # 적립금 누적
realized_pnl_krw: float
```

### 4-2. 매수/매도 mechanics

```python
# 매수 5,000,000원어치 at 100,000원/주
fill_price = mid_price × (1 + slippage_bps/1e4)        # 100,050
affordable_qty = floor(budget / (fill_price × (1 + comm/1e4)))   # 49 주
gross = qty × fill_price                                # 4,902,450
commission = gross × commission_bps/1e4                # 735
cash -= gross + commission                              # 5,000,000 - 4,903,185 = 96,815
avg_cost = (avg_cost × prior_qty + gross + commission) / new_qty
```

```python
# 매도 49주 at 130,000원/주
fill_price = mid_price × (1 - slippage_bps/1e4)        # 129,935
gross = qty × fill_price                                # 6,366,815
commission = gross × commission_bps/1e4
sell_tax = gross × sell_tax_bps/1e4                    # 11,460  (KOSPI/KOSDAQ)
cash += gross - commission - sell_tax                   # +6,354,400
realized_pnl += (gross - commission - sell_tax) - avg_cost × qty
```

### 4-3. 기본 수수료 (변경 가능)

| 항목 | 기본값 | 단위 |
|---|---:|---|
| 매수/매도 수수료 | 1.5 | bps (0.015%) |
| 매도 거래세 | 18.0 | bps (0.18%, KOSPI/KOSDAQ) |
| 슬리피지 | 5.0 | bps (양방향) |

### 4-4. 리밸런스

`account.rebalance_to_weights({symbol: weight})` 호출 시:

1. 전체 보유 자산을 오늘 종가로 mark-to-market 해서 equity 계산
2. `target_value = equity × weight` 산출
3. **매도 우선**: 보유분이 target보다 큰 종목부터 차분만큼 정수 주식으로 매도 (현금 확보)
4. 그 다음 **매수**: 보유분이 target보다 작은 종목을 가용 현금 한도 내에서 정수 주식 매수

이 순서 덕분에 리밸런스 한 번에 cash가 음수로 가지 않고, 정수 주식의 한계로 ~1주 미만 자투리만 cash로 남습니다.

---

## 5. 적립식 시나리오 (1천만 + 월 100만 + 2년마다 +50만)

`SavingsPlan` 한 모델이 시나리오 전체를 표현합니다.

| 필드 | 기본값 | 의미 |
|---|---:|---|
| `initial_capital_krw` | 10,000,000 | 시뮬 첫 영업일 일시 입금 |
| `monthly_contribution_krw` | 1,000,000 | 매월 첫 영업일 정기 입금 |
| `escalation_step_krw` | 500,000 | 한 번의 에스컬레이션이 더하는 금액 |
| `escalation_period_years` | 2 | 몇 년마다 에스컬레이션할지 |
| `max_escalations` | 10 | 에스컬레이션 누적 횟수 한도 |

기본 설정에서의 적립금 추이:

| 기간 | 월 적립금 |
|---|---:|
| Year 0–1 | 1,000,000 |
| Year 2–3 | 1,500,000 |
| Year 4–5 | 2,000,000 |
| Year 6–7 | 2,500,000 |
| ... | ... |
| Year 20+ (cap) | 6,000,000 |

5년 3개월 시뮬에서 **누적 적립금 = 1억 KRW (정확히 100,000,000)** — 모든 페르소나가 같은 입금 스케줄을 받습니다.

월 첫 영업일 픽: 거래일 리스트에서 (year, month) 그룹의 최소값. 즉, 1월 1일이 휴일이면 1월 2일에 입금.

---

## 6. 데이터 설계 (SSOT/SDD/TDD)

세 가지 원칙이 코드 전반에 박혀 있습니다.

### 6-1. SSOT — Single Source of Truth

`src/snusmic_pipeline/sim/contracts.py` 가 **전체 시뮬레이션의 데이터 컨트랙트**를 가진 유일한 파일입니다. 모든 모델은:

- `pydantic.BaseModel` v2
- `ConfigDict(frozen=True, extra="forbid", validate_assignment=True)`
- `Annotated[..., Field(ge=..., le=...)]` 로 타입 + 범위 제약

```python
class SavingsPlan(_FrozenModel):
    initial_capital_krw:       Annotated[float, Field(ge=0)] = 10_000_000.0
    monthly_contribution_krw:  Annotated[float, Field(ge=0)] = 1_000_000.0
    escalation_step_krw:       Annotated[float, Field(ge=0)] = 500_000.0
    escalation_period_years:   Annotated[int, Field(ge=1, le=10)] = 2
    max_escalations:           Annotated[int, Field(ge=0, le=20)] = 10
```

새 파라미터 추가 = 모델 한 곳 수정. 시뮬 러너는 `SimulationConfig` 만 읽고 어떤 글로벌 상수도 참조하지 않습니다.

전체 컨트랙트 등록부:

| 모델 | 용도 |
|---|---|
| `SavingsPlan` | 적립금 + 에스컬레이션 |
| `BrokerageFees` | 수수료/세금/슬리피지 |
| `BenchmarkAsset` | 올웨더 슬롯 1개 (이름·심볼·비중) |
| `AllWeatherConfig` | 올웨더 4분할 + 리밸런스 주기 |
| `ProphetConfig` | 풀 룩어헤드 노브 |
| `WeakProphetConfig` | 6M 룩어헤드 + max-Sharpe 노브 |
| `SmicFollowerConfig` | 1/N 충신 노브 |
| `SmicFollowerV2Config` | 손절 룰 3종 + threshold |
| `SimulationConfig` | 루트 설정 (날짜·플랜·수수료·페르소나 튜플) |
| `Trade` | 체결 1건 (일자·종목·수량·체결가·수수료·세금·사유) |
| `EquityPoint` | 일별 mark-to-market 스냅샷 |
| `PersonaSummary` | 종합 통계 (평가금·IRR·MDD 등) |
| `SimulationResult` | 전체 결과 번들 |

### 6-2. SDD — Schema-Driven Design

데이터 보관 형식은 **두 단계**로 검증됩니다:

1. **In-process**: 모든 in-memory 객체는 frozen Pydantic 모델 — 잘못된 dict가 함수 인자로 들어가면 즉시 `ValidationError`.
2. **On-disk**: `src/snusmic_pipeline/backtest/schemas.py` 의 `TABLE_MODELS` registry로 CSV 읽기/쓰기 양쪽에서 행 단위 검증. 미상의 컬럼이 보이면 즉시 fail.

스키마 호환성 보장:

```bash
uv run python scripts/export_schemas.py --check          # JSON 스키마 추출
uv run python scripts/check_schema_compat.py             # main 대비 호환성 검증 (Principle 6)
```

### 6-3. TDD — Test-Driven Development

`tests/sim/` 41개 테스트 + `tests/` 95개 기존 테스트 = **136 passing**:

```
tests/sim/test_contracts.py     - 11 tests  (라운드트립, frozen, validator)
tests/sim/test_savings.py       -  7 tests  (에스컬레이션 산술, 월 첫영업일 픽)
tests/sim/test_brokerage.py     -  9 tests  (정수주, 가중평균, 수수료, 거래세)
tests/sim/test_personas.py      -  6 tests  (페르소나별 행동 검증)
tests/sim/test_all_weather.py   -  3 tests  (4분할, 리밸런스 정확도)
tests/sim/test_runner.py        -  4 tests  (E2E 결정성, JSON 직렬화)
tests/sim/test_visualize.py     -  1 test   (PNG 산출 정상)
```

대표 테스트:

```python
def test_contribution_amount_step_up_every_two_years():
    plan = SavingsPlan()
    assert contribution_amount(0, plan) == 1_000_000   # year 0
    assert contribution_amount(23, plan) == 1_000_000  # year 1
    assert contribution_amount(24, plan) == 1_500_000  # year 2 — +50만
    assert contribution_amount(48, plan) == 2_000_000  # year 4 — +100만

def test_smic_follower_holds_losers_and_sells_only_at_target(...):
    # LOSS 종목은 target 미도달 → 절대 매도 없음
    loss_sells = [t for t in sells if t.symbol == "LOSS"]
    assert loss_sells == []

def test_prophet_concentrates_on_realised_winner(...):
    # 사후 winner 한 종목에만 매수
    bought_symbols = {t.symbol for t in out.account.trades if t.side == "buy"}
    assert bought_symbols == {"WIN"}
```

---

## 7. 저장소 구조

```
.
├── README.md                              # ← 지금 보고 있는 문서
├── pyproject.toml                         # 의존성, ruff/mypy/pytest 설정
├── uv.lock                                # 잠긴 dependency 버전
│
├── data/
│   ├── extracted_reports.csv              # PDF 추출 원천
│   ├── extraction_quality.json            # 추출 품질 메트릭
│   ├── price_metrics.json                 # 리포트별 가격/목표가 메트릭
│   ├── manifest.json                      # PDF 다운로드 manifest
│   ├── pdfs/                              # 218개 PDF (gitignored 가능)
│   ├── markdown/                          # PDF → MD 변환 결과
│   ├── warehouse/                         # ── 정규화된 v3 warehouse ──
│   │   ├── reports.csv                    #     리포트 + KRW 환산 목표가
│   │   ├── daily_prices.csv               #     KRW 환산 OHLCV (전 종목)
│   │   ├── fx_rates.csv                   #     일별 환율
│   │   ├── benchmark_prices.csv           #     올웨더 ETF KRW 환산 캐시
│   │   ├── signals_daily.csv              #     MTT 시그널 (백테스트용)
│   │   ├── candidate_pool_events.csv      #     리포트 풀 이벤트
│   │   ├── execution_events.csv           #     백테스트 체결 원장
│   │   ├── positions_daily.csv            #     백테스트 일별 포지션
│   │   ├── equity_daily.csv               #     백테스트 일별 지분곡선
│   │   ├── strategy_runs.csv              #     백테스트 런 요약
│   │   └── snusmic.duckdb                 #     모든 CSV의 DuckDB 미러
│   ├── quant_v3/                          # JSON 미러 (서버 분석용)
│   └── sim/                               # ── 페르소나 시뮬 산출물 ──
│       ├── personas.json                  #     SimulationResult 전체
│       ├── summary.csv                    #     페르소나별 종합 통계
│       ├── equity_daily.csv               #     일별 mark-to-market
│       ├── trades.csv                     #     매수/매도 원장
│       ├── equity_curves.png              #     5개 페르소나 equity overlay
│       ├── net_profit_bar.png             #     순이익 막대 차트
│       └── drawdowns.png                  #     낙폭 곡선
│
├── docs/
│   ├── decisions/
│   │   ├── persona-simulation.md          # 페르소나 시뮬 설계 결정
│   │   ├── strategy-baselines.md          # 백테스트 baseline 컨트랙트
│   │   └── phase-2-objective.md           # OOS sortino objective 결정
│   └── schemas/                           # 공개 데이터 JSON 스키마
│
├── scripts/
│   ├── run_persona_sim.py                 # 페르소나 시뮬 CLI
│   ├── export_schemas.py                  # JSON 스키마 추출
│   └── check_schema_compat.py             # 스키마 호환성 검증
│
├── src/snusmic_pipeline/
│   ├── __main__.py                        # `python -m snusmic_pipeline ...`
│   ├── cli.py                             # 메인 CLI (refresh-market, build-warehouse, ...)
│   ├── download_pdfs.py                   # PDF 다운로더
│   ├── extract_pdf.py                     # opendataloader-pdf 래퍼
│   ├── extraction_quality.py              # 추출 품질 메트릭
│   ├── markdown_export.py                 # PDF → Markdown
│   ├── change_detection.py                # 인덱스 변화 감지
│   ├── currency.py                        # FX 환율 다운로드/변환
│   ├── fetch_index.py                     # SMIC 사이트 인덱스 fetch
│   ├── opendataloader_fallback.py         # OCR 폴백
│   ├── models.py                          # 메타 모델
│   ├── artifact_schemas.py                # 공통 artifact 스키마
│   ├── quant.py                           # legacy 백테스트 (단일 파일)
│   │
│   ├── backtest/                          # ── v3 walk-forward 엔진 ──
│   │   ├── schemas.py                     #     Pydantic 모델 + TABLE_MODELS
│   │   ├── warehouse.py                   #     read_table/write_table + Optuna
│   │   ├── engine.py                      #     event-driven backtest 엔진
│   │   ├── signals.py                     #     MTT 시그널
│   │   └── optimizers.py                  #     weighting 메소드들
│   │
│   └── sim/                               # ── 페르소나 시뮬레이션 (NEW) ──
│       ├── contracts.py                   #     SSOT pydantic 모델 전체
│       ├── savings.py                     #     적립금 스케줄 (에스컬레이션)
│       ├── brokerage.py                   #     share-based 증권 원장
│       ├── market.py                      #     PriceBoard + 올웨더 ETF 로더
│       ├── runner.py                      #     SimulationConfig 디스패치
│       ├── visualize.py                   #     matplotlib 3종 차트
│       └── personas/
│           ├── base.py                    #     공통 헬퍼 (IRR, MDD, snapshot)
│           ├── prophet.py                 #     Prophet
│           ├── weak_prophet.py            #     Weak Prophet (max-Sharpe)
│           ├── smic_follower.py           #     SMIC Follower v1 + 공통 엔진
│           ├── smic_follower_v2.py        #     SMIC Follower v2 (손절 추가)
│           └── all_weather.py             #     올웨더 벤치마크
│
└── tests/
    ├── test_*.py                          # 26개 기존 테스트 (PDF, 추출, 백테스트)
    └── sim/
        ├── conftest.py                    # 합성 가격/리포트 fixture
        ├── test_contracts.py              # SSOT 보장
        ├── test_savings.py                # 적립 산술
        ├── test_brokerage.py              # share-based 회계
        ├── test_personas.py               # 페르소나별 행동
        ├── test_all_weather.py            # 벤치마크
        ├── test_runner.py                 # E2E + 결정성
        └── test_visualize.py              # PNG 산출
```

---

## 8. 실행 방법

### 8-1. 환경 준비

```bash
uv sync --group dev
```

`uv` 가 없으면 `pip install uv` 한 번 실행. Python 3.11 이상.

### 8-2. 데이터 파이프라인 (PDF → warehouse)

PDF 다운로드부터 KRW 가격 warehouse 빌드까지:

```bash
uv run python -m snusmic_pipeline refresh-market    # PDF 인덱스 + 다운로드 + 추출
uv run python -m snusmic_pipeline build-warehouse   # data/warehouse/reports.csv
uv run python -m snusmic_pipeline refresh-prices    # data/warehouse/daily_prices.csv (yfinance)
```

### 8-3. 백테스트 (전략 최적화)

```bash
uv run python -m snusmic_pipeline run-backtest      # default config 5종 + Optuna
uv run python -m snusmic_pipeline export-dashboard  # data/quant_v3/*.json export
```

### 8-4. **페르소나 시뮬레이션 (이 README의 핵심)**

```bash
uv run python scripts/run_persona_sim.py \
    --start 2021-01-04 \
    --end 2026-04-15 \
    --warehouse data/warehouse \
    --out data/sim
```

옵션:

- `--refresh-benchmark`: 올웨더 ETF 가격 강제 재다운로드 (기본은 캐시 사용)
- `--start / --end`: 시뮬 기간 (기본 2021-01-04 → 2026-04-15)

콘솔에 페르소나별 종합 결과 표가 출력되고, `data/sim/` 에 모든 산출물이 저장됩니다.

### 8-5. 파라미터 변경 예시

`SimulationConfig` 만 바꾸면 시나리오 변경 가능. 예) 월 적립 50만, 손절 6개월:

```python
from datetime import date
from pathlib import Path
from snusmic_pipeline.sim.contracts import (
    SimulationConfig, SavingsPlan, ProphetConfig, SmicFollowerV2Config, AllWeatherConfig,
)
from snusmic_pipeline.sim.runner import run_simulation

cfg = SimulationConfig(
    start_date=date(2022, 1, 3),
    end_date=date(2026, 4, 15),
    savings_plan=SavingsPlan(monthly_contribution_krw=500_000),
    personas=(
        ProphetConfig(),
        SmicFollowerV2Config(time_loss_days=180, averaged_down_stop_pct=0.10),
        AllWeatherConfig(),
    ),
)
result = run_simulation(cfg, Path("data/warehouse"))
```

---

## 9. 산출물

### 9-0. SMIC 리포트 자체 통계 (페르소나 무관)

`data/sim/report_stats.json` + `report_performance.csv` 는 페르소나와 별개로
"리포트 발간 후 가격이 어떻게 움직였는가" 만 답하는 데이터입니다.

기본 시나리오 (2021-01-04 → 2026-04-15) 결과:

- 총 **211개** 리포트, 206개에 가격 데이터 매칭
- 목표가 도달: **127개 (61.7%)**
- 목표가 도달까지 걸린 시간: 평균 239일, 중앙값 46일 (긴 꼬리 분포)
- 발간 후 평균 누적 수익률: **+95.0%** (mean), +28.8% (median)
- 발간 시점 약속한 목표 상승률: 평균 **+62.6%**

Top 5 종목 (사후 수익률 기준):

| 순위 | 위너 (current return) | 루저 (current return) |
|---:|---|---|
| 1 | 이수페타시스 +2,105% | Chegg −94% |
| 2 | HD현대일렉트릭 +1,433% | 원티드랩 −91% |
| 3 | SNT에너지 +834% | 제이콘텐트리 −89% |
| 4 | SK하이닉스 +821% | 티와이홀딩스 −89% |
| 5 | Vertiv +794% | 카카오게임즈 −89% |

목표가에서 가장 멀리 어긋난 종목 (still open): Z-Holdings(−97%), 아이씨에이치(−95%),
원티드랩(−93%), 티와이홀딩스(−93%), 이지바이오(−92%).

`report_performance.csv` 에는 리포트별로 `entry_price_krw`,
`target_price_krw`, `target_upside_at_pub`, `target_hit`, `target_hit_date`,
`days_to_target`, `last_close_krw`, `current_return`, `peak_return`,
`trough_return`, `target_gap_pct` 가 모두 들어 있어, 자체 분석에 바로 사용 가능.

### 9-1. `data/sim/summary.csv` — 페르소나별 종합 통계

| 컬럼 | 의미 |
|---|---|
| `persona` | discriminator 키 (`oracle`, `weak_oracle`, ...) |
| `label` | 사람 친화 라벨 |
| `initial_capital_krw` | 초기 입금 (10M) |
| `total_contributed_krw` | 누적 입금 (~100M) |
| `final_equity_krw` | 마지막 영업일 평가금 |
| `final_cash_krw` / `final_holdings_value_krw` | 평가금의 cash/주식 분할 |
| `net_profit_krw` | 순이익 (= 평가금 − 누적입금) |
| `money_weighted_return` | 현금흐름 가중 IRR (annualised) |
| `time_weighted_return` | 시간가중 수익률 (Modified Dietz) |
| `cagr` | 단순 CAGR |
| `max_drawdown` | 최대 낙폭 (절대값, 0~1) |
| `realized_pnl_krw` | 실현 손익 누계 |
| `trade_count` | 매수+매도 체결 수 |
| `open_positions` | 마지막 날 보유 종목 수 |

### 9-2. `data/sim/equity_daily.csv` — 일별 시계열

각 페르소나의 매 영업일 mark-to-market. ~6,500행 (5 페르소나 × ~1,313 영업일).

```csv
persona,date,cash_krw,holdings_value_krw,equity_krw,contributed_capital_krw,net_profit_krw,open_positions
oracle,2021-01-04,6209282.59,3788651.96,9997934.55,10000000.0,-2065.45,2
oracle,2021-01-05,5841231.33,4156703.22,9997934.55,10000000.0,-2065.45,2
...
```

### 9-3. `data/sim/trades.csv` — 매수/매도 원장

각 체결의 정수 수량, 체결가(슬리피지 반영), 수수료, 거래세, 매도사유까지 모두 기록.

```csv
persona,date,symbol,side,qty,fill_price_krw,gross_krw,commission_krw,tax_krw,cash_after_krw,reason,report_id
oracle,2021-01-04,005930.KS,buy,18,89045.0,1602810.0,240.42,0.0,8397949.58,deposit_buy,r-...
smic_follower,2021-08-30,373220.KS,sell,5,422740.0,2113700.0,317.06,3804.66,...,target_hit,r-...
smic_follower_v2,2024-09-02,A.KS,sell,12,55310.0,663720.0,99.56,1194.70,...,stop_loss_time,r-...
```

`reason` 분류:

- `deposit_buy` — 입금 후 신규 매수
- `rebalance_buy` / `rebalance_sell` — 비중 재조정 체결
- `target_hit` — 목표가 도달 매도
- `stop_loss_time` — v2 시간 손절 (1년 보유 + 손실)
- `stop_loss_average_down` — v2 물타기 손절
- `stop_loss_report_age` — v2 리포트 노후 손절

### 9-4. 페르소나별 보유 종목 분석

세 가지 뷰가 추가로 생성됩니다:

#### `position_episodes.csv` — 종목별 라운드트립

`(persona, symbol)` 별로 보유 시작 → 종료(또는 still open)의 한 사이클을 한 행으로.

| 컬럼 | 의미 |
|---|---|
| `persona`, `symbol`, `company` | 누가, 어떤 종목 |
| `open_date`, `close_date`, `holding_days` | 보유 시작/종료/일수 (close_date=null이면 still open) |
| `buy_fills`, `sell_fills` | 분할 매수/매도 횟수 |
| `total_qty_bought`, `total_qty_sold` | 누적 매수/매도 주식수 |
| `avg_entry_price_krw`, `avg_exit_price_krw` | 가중평균 진입/청산가 |
| `realized_pnl_krw` | 이 라운드트립에서 실현된 손익 |
| `unrealized_pnl_krw`, `last_close_krw` | still open 일 때 |
| `status` | `"closed"` / `"open"` |
| `exit_reasons` | 매도 사유 모음 (`target_hit`, `stop_loss_time`, ...) |

#### `current_holdings.csv` — 현재 보유 (마지막 영업일 기준)

증권사 앱의 "내 보유 종목" 화면과 동일. 각 페르소나가 마지막 날 들고 있는 종목들.

| 컬럼 | 의미 |
|---|---|
| `persona`, `symbol`, `company`, `qty` | |
| `avg_cost_krw`, `last_close_krw` | 가중평균 매수원가 vs 최근 종가 |
| `market_value_krw` | qty × last_close (평가금) |
| `unrealized_pnl_krw`, `unrealized_return` | 평가손익 (KRW + %) |
| `holding_days`, `first_buy_date` | 얼마나 들고 있었나 |

샘플 (기본 시나리오 마지막 날):

- **Prophet**: 0 종목 (모두 peak에서 매도 완료)
- **All-Weather**: 4 종목 (GLD/QQQ/SPY/069500.KS 25/25/25/25)
- **SMIC Follower v1**: 77 종목 (목표가 미도달 종목들 그대로 보유)
- **SMIC Follower v2**: 14 종목 (손절 룰로 정리 후 남은 것)
- **Weak Prophet**: 20 종목 (max-Sharpe 결과로 분산, NE/에이피알/이지바이오 등)

#### `symbol_stats.csv` — 종목별 평생 누적

`(persona, symbol)` 별로 모든 라운드트립 합계: `episodes`, `total_holding_days`,
`total_realized_pnl_krw`, `is_currently_held`. 한 종목을 여러 번 매매한 경우의
누적 손익을 보기 좋습니다.

### 9-5. `data/sim/personas.json`

`SimulationResult.model_dump_json()` — 위 셋의 super-set, 그리고 `SimulationConfig` 까지 포함. 5MB 정도.

### 9-6. PNG 시각화

- `equity_curves.png` (1680×840): 5개 페르소나 + 누적 적립금 점선 overlay
- `net_profit_bar.png` (1400×770): 순이익 막대, 정렬된 가로 막대
- `drawdowns.png` (1680×700): 낙폭 곡선

---

## 10. 검증 / CI

### 10-1. 로컬 검증 풀세트

```bash
uv run pytest tests/ -q                                    # 136 passed, 1 skipped
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python scripts/export_schemas.py --check
uv run python scripts/check_schema_compat.py --base-ref origin/main
```

### 10-2. CI

GitHub Actions 는 위 검증 + warehouse refresh 만 수행합니다 (Node/npm/Vercel 빌드는 제거). 워크플로:

- `.github/workflows/ci.yml` — PR 단위 lint·type·test·schema 검증
- `.github/workflows/price-refresh.yml` — 매일 yfinance 가격 데이터 갱신
- `.github/workflows/sync.yml` — `workflow_dispatch` 로 SMIC 리포트 인덱스 + PDF 동기화
- `.github/workflows/budget-check.yml` — GitHub Actions 월 사용량 20% 잔량 시 트래킹 이슈 자동 생성 (러너 안전장치)

---

## 11. 참고 문서

- `docs/decisions/persona-simulation.md` — 본 시뮬 시스템 ADR
- `docs/decisions/strategy-baselines.md` — 백테스트 baseline 컨트랙트
- `docs/decisions/phase-2-objective.md` — OOS sortino objective 결정
- `docs/schemas/*.json` — 공개 데이터 스키마

---

## 면책

- **Prophet / Weak Prophet 결과는 lookahead-bias 가 들어간 상한선** 입니다. 실거래로 베틸 수 없습니다.
- SMIC Follower 결과는 **실제 SMIC가 발간한 리포트의 목표가**를 기반으로 하지만, 발간 후 시장에서 즉시 매수했을 때의 가상 시뮬레이션입니다. 실제 진입 시점·체결가·세금 효과는 다를 수 있습니다.
- 본 저장소는 SMIC 동아리의 리서치 품질을 평가하거나 매매 추천을 하지 않습니다. 단순히 "사라는 대로 사고 손실은 버티는 추종자가 글로벌 ETF DCA를 이기는가?" 라는 정량 질문에 답하는 도구입니다.
