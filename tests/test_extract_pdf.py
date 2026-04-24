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
    assert parsed["rating"] == "Buy"
    assert parsed["report_current_price"] == 23300
    assert parsed["base_target"] == 41600
    assert parsed["target_currency"] == "KRW"
    assert parsed["status"] == "ok"


def test_parse_report_text_extracts_non_buy_rating_without_failing_target_parse():
    text = """
    Chewy (CHWY)
    Rating: Attention
    Current Price: $42
    Target Price: $36
    """

    parsed = parse_report_text(text)

    assert parsed["ticker"] == "CHWY"
    assert parsed["rating"] == "Attention"
    assert parsed["base_target"] == 36
    assert parsed["status"] == "ok"
    assert "Non-buy rating" in parsed["note"]


def test_parse_report_text_extracts_markdown_heading_rating():
    parsed = parse_report_text("##### Rating\n## Strong Buy\n목표주가: 12,000원\nSample (123456)")

    assert parsed["rating"] == "Strong Buy"
    assert parsed["base_target"] == 12000


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
    assert parsed["target_currency"] == "JPY"


def test_target_price_before_korean_label_beats_following_year_noise():
    text = "8,100원을 Base case 목표주가로 제시한다. 동사는 22년 코스닥으로 이전 상장했다."

    parsed = parse_report_text(text, fallback_company="인카금융서비스")

    assert parsed["base_target"] == 8100


def test_current_price_before_target_label_does_not_become_target():
    text = "현재주가: 23,300 원 목표주가: 41,600 원 상승여력: 78.5%"

    parsed = parse_report_text(text, fallback_company="SK오션플랜트")

    assert parsed["report_current_price"] == 23300
    assert parsed["base_target"] == 41600


def test_equal_current_and_target_candidate_uses_next_target_candidate():
    text = "현재주가 : 238.30 위안 목표주가 238.30\n현재주가 : 238.30 위안 목표주가 : 331.70 위안 상승여력: 39%"

    parsed = parse_report_text(text, fallback_company="BYD")

    assert parsed["report_current_price"] == 238.30
    assert parsed["base_target"] == 331.70
    assert "selected next target" in parsed["note"]


def test_case_price_table_sets_median_base_and_marks_ambiguity():
    text = """
    Example Corp (123456)
    투자의견: Sell
    Case 1 가격 8,000원
    Case 2 가격 10,000원
    Case 3 가격 15,000원
    """

    parsed = parse_report_text(text)

    assert parsed["rating"] == "Sell"
    assert parsed["base_target"] == 10000
    assert "case_1=8000" in parsed["target_price_detail"]
    assert "case_3=15000" in parsed["target_price_detail"]
    assert "median case value" in parsed["note"]


def test_base_case_number_is_not_misread_as_target_price():
    text = """
    Doximity (DOCS)
    Rating: Buy
    Base Case 1: slower penetration
    Case 1 target price $75.40
    Case 2 target price $131.16
    """

    parsed = parse_report_text(text)

    assert parsed["base_target"] == 103.28
    assert parsed["base_target"] != 1


def test_bear_bull_without_base_uses_median_scenario_value():
    text = """
    Chewy (CHWY)
    Rating: Sell
    Bear Case $25.05
    Bull Case $51.60
    """

    parsed = parse_report_text(text)

    assert parsed["ticker"] == "CHWY"
    assert parsed["exchange"] == "NYSE"
    assert parsed["base_target"] == 38.325
    assert "No explicit Base target" in parsed["note"]
