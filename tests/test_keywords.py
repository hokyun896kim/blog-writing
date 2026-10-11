import base64
import hashlib
import hmac

import pytest

from blogwriter import keywords, naver
from blogwriter.keywords import KeywordStat


def test_signature_matches_searchad_spec():
    # 스펙: base64(HMAC-SHA256(secret, "{timestamp}.{method}.{uri}"))
    expected = base64.b64encode(
        hmac.new(b"secret", b"1700000000000.GET./keywordstool", hashlib.sha256).digest()
    ).decode()
    assert keywords.signature("secret", "1700000000000", "GET", "/keywordstool") == expected


def test_hint_keyword_removes_spaces():
    assert keywords.hint_keyword(" 제주 가족 여행 ") == "제주가족여행"


@pytest.mark.parametrize("raw, expected", [(1200, 1200), ("3,400", 3400), ("< 10", 0), ("", None), (None, None)])
def test_parse_count(raw, expected):
    assert keywords.parse_count(raw) == expected


def test_parse_keywordstool():
    data = {"keywordList": [
        {"relKeyword": "제주여행", "monthlyPcQcCnt": 10000, "monthlyMobileQcCnt": 50000, "compIdx": "높음"},
        {"relKeyword": "제주숨은명소", "monthlyPcQcCnt": "< 10", "monthlyMobileQcCnt": 30, "compIdx": "낮음"},
        {"relKeyword": ""},
    ]}
    a, b = keywords.parse_keywordstool(data)
    assert (a.keyword, a.monthly, a.competition) == ("제주여행", 60000, "높음")
    assert b.monthly == 30 and b.monthly_text == "약 30+"


@pytest.mark.parametrize("monthly, docs, code", [
    (1000, 100, "A"),      # 0.1
    (1000, 1500, "B"),     # 1.5
    (1000, 5000, "C"),     # 5
    (1000, 50000, "D"),    # 50
    (30, 1, "E"),          # 검색 적음
    (1000, None, "?"),     # 문서 수 미확인
])
def test_grade(monthly, docs, code):
    k = KeywordStat("k", pc=monthly, mobile=0, docs=docs)
    assert k.grade.code == code


def test_unknown_values_are_not_filled():
    k = KeywordStat("k")
    assert k.monthly is None and k.ratio is None
    assert k.monthly_text == "미확인" and k.grade.code == "?"
    assert keywords.fmt_ratio(k.ratio) == "미확인"
    assert KeywordStat("k", pc=0, mobile=0).monthly_text == "20 미만"


def test_searchad_requires_all_keys():
    with pytest.raises(naver.NaverError):
        keywords.SearchAd("123", "", "s")


def test_fill_docs_marks_failures_unknown(monkeypatch):
    def fake_total(q, *a):
        if q == "bad":
            raise naver.NaverError("boom")
        return 42
    monkeypatch.setattr(naver, "blog_total", fake_total)
    stats = [KeywordStat("good"), KeywordStat("bad")]
    errors = keywords.fill_docs(stats, "id", "secret")
    assert stats[0].docs == 42 and stats[1].docs is None
    assert len(errors) == 1 and "bad" in errors[0]
