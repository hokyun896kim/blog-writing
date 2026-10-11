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
        elif "초안을 써 주세요" in user:
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

    click(at, "초안 작성")
    assert "본문 초안" in at.session_state.draft

    click(at, "검수 시작")
    assert "문제 없음" in at.session_state.review
    assert at.session_state.final.startswith("# 제목")
    assert any("[확인 필요]" in w.value for w in at.warning)
