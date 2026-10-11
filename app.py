"""블로그 글쓰기 도우미 (Streamlit).

실행: streamlit run app.py
"""

from __future__ import annotations

import os

import streamlit as st

from blogwriter import llm, naver, prompts, storage

st.set_page_config(page_title="블로그 글쓰기 도우미", page_icon="✍️", layout="wide")

SS = st.session_state
for key, default in {
    "style": "", "style_blog": "", "keyword": "", "prep": "", "sources": [],
    "experience": "", "request": "", "plan": "", "draft": "", "review": "", "final": "",
}.items():
    SS.setdefault(key, default)

# 저장된 스타일 진단은 앱을 다시 켜도 이어서 쓴다.
if not SS.style:
    saved = storage.load("style", {})
    SS.style, SS.style_blog = saved.get("text", ""), saved.get("blog_id", "")


# ---------------------------------------------------------------- 연결 설정

settings = storage.load("settings", {})
with st.sidebar:
    st.header("⚙️ 연결 설정")
    claude_key = st.text_input(
        "Claude API 키", type="password",
        value=settings.get("claude_key", os.environ.get("ANTHROPIC_API_KEY", "")),
        help="console.anthropic.com 에서 발급. 비워 두면 ANTHROPIC_API_KEY 환경변수를 씁니다.",
    )
    model_label = st.selectbox("모델", list(llm.MODELS), index=0)
    model = llm.MODELS[model_label]
    naver_id = st.text_input(
        "네이버 Client ID", value=settings.get("naver_id", os.environ.get("NAVER_CLIENT_ID", "")),
        help="developers.naver.com → 애플리케이션 등록 → 사용 API: 검색",
    )
    naver_secret = st.text_input(
        "네이버 Client Secret", type="password",
        value=settings.get("naver_secret", os.environ.get("NAVER_CLIENT_SECRET", "")),
    )
    remember = st.checkbox("이 PC에 저장 (data/settings.json)", value=bool(settings))

    c1, c2 = st.columns(2)
    if c1.button("연결 확인", use_container_width=True):
        try:
            llm.check_connection(llm.make_client(claude_key), model)
            st.success("Claude 연결 OK")
        except Exception as e:  # 사용자에게 원인을 그대로 보여 준다
            st.error(f"Claude: {e}")
        try:
            naver.check_search_api(naver_id, naver_secret)
            st.success("네이버 검색 API OK")
        except Exception as e:
            st.error(f"네이버: {e}")
    if c2.button("저장", use_container_width=True):
        if remember:
            storage.save("settings", {"claude_key": claude_key, "naver_id": naver_id, "naver_secret": naver_secret})
            st.success("저장했습니다.")
        else:
            storage.save("settings", {})
            st.info("저장된 키를 지웠습니다.")

    st.divider()
    st.caption("진행 상황")
    for label, done in [
        ("① 스타일 진단", SS.style), ("② 글 작성 준비", SS.prep),
        ("③ 초안", SS.draft), ("④ 최종 검수", SS.final),
    ]:
        st.write(("✅ " if done else "⬜ ") + label)


def client():
    return llm.make_client(claude_key)


def run_stream(system_user: tuple[str, str], effort: str = "high") -> str | None:
    """Claude 응답을 화면에 흘려 보여 주고 전체 텍스트를 돌려준다. 실패하면 None."""
    system, user = system_user
    try:
        return st.write_stream(llm.stream_text(client(), system, user, model=model, effort=effort))
    except llm.LLMError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"예상하지 못한 오류: {e}")
    return None


PROJECT_KEYS = ("prep", "sources", "experience", "request", "plan", "draft", "review", "final")


def save_current_project():
    if SS.keyword:
        storage.save_project(SS.keyword, {
            k: SS[k] for k in PROJECT_KEYS
        })


st.title("✍️ 블로그 글쓰기 도우미")
st.caption("내 블로그 스타일 진단 → 상위 글 분석 → 초안 작성 → 최종 검수. AI 결과는 발행 전에 꼭 직접 확인하세요.")

tab_style, tab_prep, tab_draft, tab_review, tab_saved = st.tabs(
    ["① 내 블로그 스타일 진단", "② 글 작성 준비", "③ 초안 작성", "④ 최종 검수", "📁 저장된 작업"]
)

# ---------------------------------------------------------------- ① 스타일 진단

with tab_style:
    st.subheader("내 블로그 스타일 진단")
    st.write("최근 글을 읽어 주제·어조·글 구성·자주 쓰는 표현을 분석하고, 초안에 쓸 **작성 규칙**을 만듭니다.")
    c1, c2 = st.columns([3, 1])
    blog_input = c1.text_input("내 네이버 블로그 주소 또는 아이디", value=SS.style_blog, placeholder="https://blog.naver.com/내아이디")
    count = c2.number_input("분석할 글 수", 5, 50, 20, step=5)

    if st.button("스타일 진단 시작", type="primary", disabled=not blog_input):
        try:
            blog_id = naver.normalize_blog_id(blog_input)
            with st.status("내 블로그 글 수집 중…", expanded=True) as status:
                posts = naver.fetch_rss(blog_id, limit=int(count))
                if not posts:
                    raise naver.NaverError("RSS에 공개 글이 없습니다.")
                st.write(f"글 {len(posts)}개 확인, 본문 읽는 중…")
                errors = naver.fill_bodies(posts, max_chars=2500)
                if errors:
                    st.write(f"본문을 못 읽은 글 {len(errors)}개는 요약으로 대신합니다.")
                status.update(label=f"글 {len(posts)}개 수집 완료", state="complete", expanded=False)
        except Exception as e:
            st.error(f"수집 실패: {e}")
        else:
            text = run_stream(prompts.style_diagnosis(posts))
            if text:
                SS.style, SS.style_blog = text, blog_id
                storage.save("style", {"blog_id": blog_id, "text": text})
                st.success("진단 결과를 저장했습니다. 아래에서 직접 다듬을 수 있어요.")

    if SS.style:
        st.divider()
        st.markdown("**진단 결과** (수정 가능 — 이 내용이 초안 작성에 그대로 쓰입니다)")
        edited = st.text_area("style", SS.style, height=420, label_visibility="collapsed")
        if st.button("수정 내용 저장", key="save_style"):
            SS.style = edited
            storage.save("style", {"blog_id": SS.style_blog, "text": edited})
            st.success("저장했습니다.")

# ---------------------------------------------------------------- ② 글 작성 준비

with tab_prep:
    st.subheader("글 작성 준비와 상위 글 분석")
    c1, c2 = st.columns([3, 1])
    keyword = c1.text_input("작성할 키워드", value=SS.keyword, placeholder="예: 제주 3박4일 가족여행 코스")
    top_n = c2.number_input("분석할 상위 글 수", 3, 10, 5)
    extra_urls = st.text_area(
        "추가로 참고할 글 주소 (선택, 한 줄에 하나 — 뉴스·공식 자료 등)", height=80,
    )

    if st.button("상위 글 분석", type="primary", disabled=not keyword):
        try:
            with st.status("상위 글 수집 중…", expanded=True) as status:
                posts = naver.search_blog(keyword, naver_id, naver_secret, display=int(top_n))
                for url in filter(None, (u.strip() for u in extra_urls.splitlines())):
                    posts.append(naver.Post(title=url, link=url))
                if not posts:
                    raise naver.NaverError("검색 결과가 없습니다.")
                errors = naver.fill_bodies(posts, max_chars=3500)
                for i, p in enumerate(posts, 1):
                    st.write(f"[{i}] {p.title} — {len(p.body):,}자")
                if errors:
                    st.write(f"본문을 못 읽은 글 {len(errors)}개는 요약으로 대신합니다.")
                status.update(label=f"글 {len(posts)}개 수집 완료", state="complete", expanded=False)
        except Exception as e:
            st.error(f"수집 실패: {e}")
        else:
            text = run_stream(prompts.research(keyword, posts, SS.style))
            if text:
                SS.keyword, SS.prep = keyword, text
                SS.sources = prompts.unique_sources([{"title": p.title, "link": p.link} for p in posts])
                SS.plan = SS.draft = SS.review = SS.final = ""
                save_current_project()

    if SS.prep:
        st.divider()
        if SS.sources:
            with st.expander("분석한 글 목록"):
                for i, s in enumerate(SS.sources, 1):
                    st.markdown(f"[{i}] [{s['title']}]({s['link']})")
        st.markdown("**준비 자료** (확인 후 필요하면 고치세요 — 초안은 이 내용을 기준으로 씁니다)")
        edited = st.text_area("prep", SS.prep, height=420, label_visibility="collapsed")
        if st.button("준비 자료 승인·저장", key="save_prep"):
            SS.prep = edited
            save_current_project()
            st.success("승인했습니다. ③ 초안 작성 탭으로 이동하세요.")

# ---------------------------------------------------------------- ③ 초안 작성

with tab_draft:
    st.subheader("초안 작성")
    if not SS.keyword:
        st.info("먼저 ② 글 작성 준비에서 키워드를 분석하세요. (준비 없이 쓰려면 아래에 키워드를 입력)")
    kw = st.text_input("키워드", value=SS.keyword)
    if not SS.style:
        st.warning("스타일 진단이 없어 기본 어조로 작성합니다. ① 탭에서 먼저 진단하면 내 말투로 써 줍니다.")
    SS.experience = st.text_area(
        "내 경험·관점 (가장 중요! 실제로 겪은 일, 사진 찍은 장면, 느낀 점을 메모처럼)",
        SS.experience, height=150,
        placeholder="예: 10월 둘째 주 아이 둘과 다녀옴. 첫날 비 와서 실내 위주로 바꿈. 렌터카는 공항 셔틀이 20분 걸렸음…",
    )
    SS.request = st.text_area("나만의 작성 요청 (선택)", SS.request, height=80, placeholder="예: 비용 정리 표를 넣어 줘, 마지막에 체크리스트")
    c1, c2 = st.columns(2)
    length = c1.select_slider("분량", ["짧게 (1,500자 내외)", "보통 (2,500자 내외)", "길게 (4,000자 이상)"], value="보통 (2,500자 내외)")
    prefs = storage.load("prefs", {})
    images = c2.slider("이미지 프롬프트 수 (대표 이미지 포함)", 5, 10, prefs.get("image_count", 6))

    with st.expander("📝 문단별 작성 계획 (선택 — 먼저 계획을 보고 고친 뒤 초안을 쓰면 요청·경험이 빠지지 않아요)", expanded=bool(SS.plan)):
        if st.button("작성 계획 만들기", disabled=not kw):
            text = run_stream(prompts.plan(kw, SS.style, SS.prep, SS.experience, SS.request, length), effort="medium")
            if text:
                SS.keyword, SS.plan = kw, text
                save_current_project()
        if SS.plan:
            SS.plan = st.text_area("plan", SS.plan, height=300, label_visibility="collapsed")
            st.caption("이 계획대로 초안을 씁니다. 필요 없으면 내용을 모두 지우세요.")

    if st.button("초안 작성", type="primary", disabled=not kw):
        storage.save("prefs", {**prefs, "image_count": images})
        text = run_stream(prompts.draft(
            kw, SS.style, SS.prep, SS.experience, SS.request, length, images,
            plan_text=SS.plan, sources=SS.sources,
        ))
        if text:
            SS.keyword, SS.draft = kw, text
            SS.review = SS.final = ""
            save_current_project()

    if SS.draft:
        st.divider()
        st.markdown("**초안** (직접 고친 뒤 ④ 최종 검수로 넘어가세요)")
        SS.draft = st.text_area("draft", SS.draft, height=520, label_visibility="collapsed")
        c1, c2 = st.columns(2)
        if c1.button("초안 저장", key="save_draft"):
            save_current_project()
            st.success("저장했습니다.")
        c2.download_button("초안 내려받기 (.md)", SS.draft, file_name=f"{storage.slug(SS.keyword)}_초안.md")

# ---------------------------------------------------------------- ④ 최종 검수

with tab_review:
    st.subheader("최종 검수")
    if not SS.draft:
        st.info("③ 초안 작성을 먼저 진행하세요.")
    else:
        st.write("사실·수치, 지어낸 경험, 요청·경험 반영, 스타일 일치, 반복 표현, 검색 의도, 키워드 배치, 가독성·출처를 점검하고 반영한 최종본을 만듭니다.")
        if st.button("검수 시작", type="primary"):
            text = run_stream(prompts.review(SS.keyword, SS.style, SS.prep, SS.experience, SS.draft, SS.request))
            if text:
                SS.review, SS.final = prompts.split_review(text)
                save_current_project()
                st.rerun()

        if SS.review:
            with st.expander("검수 결과", expanded=not SS.final):
                st.markdown(SS.review)
        if SS.final:
            st.markdown("**최종본** — 아래 박스 오른쪽 위 복사 버튼으로 복사하세요.")
            view = st.radio("보기", ["미리보기", "복사용 원문"], horizontal=True, label_visibility="collapsed")
            if view == "미리보기":
                st.markdown(SS.final)
            else:
                st.code(SS.final, language=None, wrap_lines=True)
            st.download_button("최종본 내려받기 (.md)", SS.final, file_name=f"{storage.slug(SS.keyword)}_최종.md")
            if "[확인 필요" in SS.final:
                st.warning("최종본에 [확인 필요] 표시가 남아 있습니다. 발행 전에 직접 확인해 채우세요.")

# ---------------------------------------------------------------- 저장된 작업

with tab_saved:
    st.subheader("저장된 작업")
    projects = storage.list_projects()
    if not projects:
        st.info("아직 저장된 작업이 없습니다.")
    for i, p in enumerate(projects):
        stage = "최종본" if p.get("final") else "초안" if p.get("draft") else "준비 자료"
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{p['keyword']}** · {stage} · {p.get('updated', '')}")
        if c2.button("불러오기", key=f"load_{i}"):
            SS.keyword = p["keyword"]
            for k in PROJECT_KEYS:
                SS[k] = p.get(k, [] if k == "sources" else "")
            st.rerun()
