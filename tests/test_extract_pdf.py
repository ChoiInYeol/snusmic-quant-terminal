from snusmic_pipeline.extract_pdf import parse_money, parse_report_text


def test_parse_money_handles_commas_and_currency():
    assert parse_money("₩ 41,600") == 41600
    assert parse_money("$52.66") == 52.66


def test_parse_report_text_extracts_single_target_for_korean_report():
    text = """
    SK오션플랜트 (100090)
    Buy
    현재주가: 23,300 원
    목표주가: 41,600 원
    """

    parsed = parse_report_text(text)

    assert parsed["ticker"] == "100090"
    assert parsed["exchange"] == "KRX"
    assert parsed["googlefinance_symbol"] == "KRX:100090"
    assert parsed["report_current_price"] == 23300
    assert parsed["base_target"] == 41600
    assert parsed["target_currency"] == "KRW"
    assert parsed["status"] == "ok"


def test_parse_report_text_extracts_bear_base_bull():
    text = """
    Robotis (108490)
    Bear Case 250,900
    Base Case 355,800
    Bull Case 646,500
    """

    parsed = parse_report_text(text)

    assert parsed["ticker"] == "108490"
    assert parsed["bear_target"] == 250900
    assert parsed["base_target"] == 355800
    assert parsed["bull_target"] == 646500


def test_known_overseas_company_mapping_beats_noisy_parentheses():
    parsed = parse_report_text("JILPT (27E) noisy valuation text", fallback_company="JAC recruitment Co. Ltd")

    assert parsed["ticker"] == "2124"
    assert parsed["exchange"] == "TYO"
    assert parsed["googlefinance_symbol"] == "TYO:2124"
    assert parsed["target_currency"] == "JPY"
