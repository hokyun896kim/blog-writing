"""외부 API를 가짜로 바꿔 전체 흐름(진단 → 준비 → 초안 → 검수)을 돌려 본다."""

import pytest
from streamlit.testing.v1 import AppTest

from blogwriter import llm, naver, prompts


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOGWRITER_DATA", str(tmp_path))
    import importlib
    from blogwriter import storage
    importlib.reload(storage)

    def fake_stream(client, system, user, **kw):
        if "스타일을 진단" in user:
            yield "## 초안 작성 규칙\n1. 해요체"
        elif "준비 자료를 만들어" in user:
            yield "## 검색 의도\n코스"
        elif "작성 계획을 세워" in user:
            yield "| 1 | 도입 | … | 경험 |"
        elif "초안을 써 주세요" in user:
            assert "<approved_plan>" in user
            yield "# 제목\n본문 초안"
        else:
            yield f"## 검수 결과\n✅ 문제 없음\n{prompts.FINAL_MARKER}\n# 제목\n최종 본문 [확인 필요: 가격]"

    monkeypatch.setattr(llm, "stream_text", fake_stream)
    monkeypatch.setattr(naver, "fetch_rss", lambda blog_id, limit: [naver.Post("내 글", "https://blog.naver.com/me/1")])
    monkeypatch.setattr(naver, "search_blog", lambda *a, **k: [naver.Post("상위 글", "https://blog.naver.com/x/2")])
    monkeypatch.setattr(naver, "fill_bodies", lambda posts, max_chars: [])
    return AppTest.from_file("../app.py", default_timeout=30)


def field(at, label):
    return next(t for t in at.text_input if t.label == label)


def click(at, label):
    next(b for b in at.button if b.label == label).click()
    at.run()
    assert not at.exception, at.exception


def test_full_flow(app):
    at = app.run()
    assert not at.exception

    field(at, "내 네이버 블로그 주소 또는 아이디").set_value("https://blog.naver.com/me")
    at.run()
    click(at, "스타일 진단 시작")
    assert "해요체" in at.session_state.style

    field(at, "작성할 키워드").set_value("제주 여행")
    at.run()
    click(at, "상위 글 분석")
    assert at.session_state.keyword == "제주 여행"
    assert "검색 의도" in at.session_state.prep

    click(at, "작성 계획 만들기")
    assert "도입" in at.session_state.plan

    next(sl for sl in at.slider if sl.label.startswith("이미지 프롬프트 수")).set_value(8)
    at.run()
    click(at, "초안 작성")
    from blogwriter import storage
    assert storage.load("prefs")["image_count"] == 8
    assert "본문 초안" in at.session_state.draft

    click(at, "검수 시작")
    assert "문제 없음" in at.session_state.review
    assert at.session_state.final.startswith("# 제목")
    assert any("[확인 필요]" in w.value for w in at.warning)


def test_keyword_cards(app, monkeypatch):
    from blogwriter import keywords
    from blogwriter.keywords import KeywordStat

    monkeypatch.setattr(keywords.SearchAd, "related", lambda self, seeds: [
        KeywordStat("제주숨은명소", pc=200, mobile=800, competition="낮음"),
        KeywordStat("제주여행", pc=10000, mobile=50000, competition="높음"),
        KeywordStat("아무도안찾음", pc=0, mobile=0),
    ])
    monkeypatch.setattr(naver, "blog_total", lambda q, *a: {"제주여행": 300000, "제주숨은명소": 300}[q])

    at = app.run()
    for label, value in [("고객 ID (CUSTOMER_ID)", "1"), ("액세스 라이선스", "k"), ("비밀키", "s")]:
        field(at, label).set_value(value)
    field(at, "기준 키워드 (쉼표로 최대 5개)").set_value("제주여행")
    at.run()
    click(at, "키워드 탐색")

    stats = at.session_state.kw_stats
    assert [k.keyword for k in stats] == ["제주여행", "제주숨은명소"]  # 검색량순, 검색 적음 숨김
    assert stats[0].grade.code == "C" and stats[1].grade.code == "A"
    html = "".join(m.value for m in at.markdown)
    assert "60,000" in html and "300,000" in html and "C 보통" in html

    click(at, "이 키워드로 글 준비 →")
    assert at.session_state.keyword == "제주여행"
    assert field(at, "작성할 키워드").value == "제주여행"

    click(at, "⭐ 보관")
    from blogwriter import storage
    assert storage.load("saved_keywords")[0]["keyword"] == "제주여행"
