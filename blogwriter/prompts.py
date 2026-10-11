"""단계별 프롬프트. 각 함수는 (system, user) 튜플을 돌려준다."""

from __future__ import annotations

from .naver import Post

FINAL_MARKER = "=====최종본====="

BASE_SYSTEM = (
    "당신은 네이버 블로그 글쓰기를 돕는 한국어 편집자입니다. "
    "블로그 주인의 목소리를 지키고, 확인되지 않은 사실이나 겪지 않은 경험을 지어내지 않습니다. "
    "답변은 마크다운으로 작성합니다."
)


def _posts_block(posts: list[Post], body_chars: int) -> str:
    parts = []
    for i, p in enumerate(posts, 1):
        meta = " | ".join(x for x in (p.date, p.category, p.author, ", ".join(p.tags)) if x)
        body = (p.body or p.summary)[:body_chars]
        parts.append(f'<post index="{i}">\n제목: {p.title}\n정보: {meta}\n주소: {p.link}\n본문:\n{body}\n</post>')
    return "\n\n".join(parts)


def style_diagnosis(posts: list[Post]) -> tuple[str, str]:
    user = f"""아래는 한 사람이 쓴 네이버 블로그 글 {len(posts)}개입니다. 이 블로그의 스타일을 진단해 주세요.

{_posts_block(posts, 2500)}

다음 구성으로 작성하세요. 각 항목은 실제 글에서 근거 문장을 짧게 인용해 보여 주세요.

## 블로그 한 줄 요약
## 주요 주제와 카테고리
(비중이 큰 순서로, 대략적인 비율 포함)
## 예상 독자
## 어조와 어투
(존댓말/반말, 대표 종결어미, 감정 표현 정도, 1인칭 사용 방식)
## 글 구성 패턴
(도입 → 전개 → 마무리 방식, 소제목·목록 사용, 평균 분량 추정)
## 문장과 문단 습관
(문장 길이, 문단 길이, 줄바꿈, 이모티콘·특수문자)
## 자주 쓰는 표현
## 강점과 보완점
## 초안 작성 규칙
(이 블로그처럼 쓰기 위해 반드시 지킬 규칙 8~12개를 번호 목록으로. 이 부분은 이후 초안 작성에 그대로 쓰이니 구체적으로.)
"""
    return BASE_SYSTEM, user


def research(keyword: str, posts: list[Post], style: str) -> tuple[str, str]:
    style_block = f"\n<my_blog_style>\n{style}\n</my_blog_style>\n" if style else ""
    user = f"""키워드 「{keyword}」로 네이버 블로그 검색 상위에 있는 글 {len(posts)}개입니다.
이 키워드로 새 글을 쓰기 위한 준비 자료를 만들어 주세요. 상위 글의 문장을 베끼지 말고, 정보와 구조만 분석합니다.
{style_block}
{_posts_block(posts, 3500)}

다음 구성으로 작성하세요.

## 검색 의도
(이 키워드를 검색하는 사람이 정말 알고 싶은 것 2~4가지)
## 상위 글의 공통 구성
## 꼭 다뤄야 할 핵심 정보
(항목마다 근거가 된 글 번호를 [1], [3]처럼 표시. 가격·날짜·수치는 글마다 다르면 그 차이를 그대로 적고 '발행 전 확인 필요'로 표시)
## 상위 글이 놓친 부분 · 차별화 방향
(내 블로그 스타일이 있다면 그 강점을 살리는 방향으로)
## 함께 쓰면 좋은 연관 키워드
## 추천 제목 5개
## 추천 목차
"""
    return BASE_SYSTEM, user


REPEAT_WATCH = "'다만', '확인하세요', '~가 아니에요', '확정할 수 없어요', '~거든요', '정말', '꼭'"


def _context(style: str, prep: str, experience: str, request: str) -> str:
    return f"""<my_blog_style>
{style or "(진단된 스타일 없음: 친근한 존댓말의 정보형 블로그 글로 작성)"}
</my_blog_style>

<prepared_research>
{prep or "(준비 자료 없음)"}
</prepared_research>

<my_experience>
{experience or "(입력 없음)"}
</my_experience>

<my_request>
{request or "(없음)"}
</my_request>"""


def unique_sources(sources: list[dict]) -> list[dict]:
    """같은 주소는 한 번만 남긴다 (쿼리스트링·끝 슬래시 차이는 같은 글로 본다)."""
    seen, out = set(), []
    for s in sources:
        key = s.get("link", "").split("?")[0].rstrip("/")
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def _citable(sources: list[dict]) -> str:
    """본문에 출처로 달 수 있는 자료 (블로그 글은 제외: 다른 블로거 글을 출처로 달지 않는다)."""
    items = [s for s in unique_sources(sources) if "blog.naver.com" not in s.get("link", "")]
    if not items:
        return "(없음: 출처 링크를 달지 마세요)"
    return "\n".join(f"- {s['title']}: {s['link']}" for s in items)


def plan(keyword: str, style: str, prep: str, experience: str, request: str, length: str) -> tuple[str, str]:
    user = f"""키워드 「{keyword}」 글을 쓰기 전에 문단별 작성 계획을 세워 주세요. 본문은 아직 쓰지 않습니다.

{_context(style, prep, experience, request)}

분량: {length}

다음 형식의 표로 작성하세요.

| 순서 | 소제목 | 이 문단에서 할 말 (2~3줄) | 쓰는 자료 (준비 자료 항목·경험·요청) |

표 아래에 짧게 덧붙이세요.
- **제목 후보 3개**
- **요청 반영 계획**: <my_request>의 각 요청이 몇 번 문단에 들어가는지 (요청이 없으면 생략)
- **경험 배치**: <my_experience>의 각 경험이 몇 번 문단에 들어가는지 (경험이 없으면 '정보형으로 작성')
"""
    return BASE_SYSTEM, user


def draft(
    keyword: str,
    style: str,
    prep: str,
    experience: str,
    request: str,
    length: str,
    image_count: int,
    plan_text: str = "",
    sources: list[dict] | None = None,
) -> tuple[str, str]:
    plan_block = f"\n<approved_plan>\n{plan_text}\n</approved_plan>\n" if plan_text else ""
    plan_rule = "- <approved_plan>의 문단 순서와 문단별 내용을 따릅니다.\n" if plan_text else ""
    user = f"""키워드 「{keyword}」로 네이버 블로그 글 초안을 써 주세요.

{_context(style, prep, experience, request)}
{plan_block}
<citable_sources>
{_citable(sources or [])}
</citable_sources>

작성 원칙
{plan_rule}- 「초안 작성 규칙」과 어조·어투를 그대로 따라, 블로그 주인이 직접 쓴 것처럼 씁니다.
- 경험담은 <my_experience>에 있는 내용만 1인칭 경험으로 씁니다. 없는 경험(구매·방문·사용)을 지어내지 마세요.
- 경험이 있으면 정보를 나열하지 말고 '그때 상황 → 본 것 → 그래서 내린 판단' 흐름으로 풀어 씁니다.
- 준비 자료의 핵심 정보와 차별화 방향을 빠짐없이 반영하고, <my_request>의 요청은 하나도 빠뜨리지 않습니다.
- 근거가 있는 내용은 돌려 말하지 말고 구체적으로 바로 설명합니다. {REPEAT_WATCH} 같은 표현이 반복되지 않게 합니다. (가격·날짜·안전 조건 같은 꼭 필요한 주의는 유지)
- 확실하지 않은 가격·날짜·수치는 [확인 필요: 무엇을] 으로 표시합니다.
- 키워드는 제목과 도입부에 자연스럽게 넣고, 본문에 억지로 반복하지 않습니다.
- 사진이 들어갈 자리에 [사진: 어떤 장면] 을 넣습니다.
- 출처는 <citable_sources>에 있는 것만, 처음 사용한 위치에 한 번만 링크합니다. 같은 링크를 두 번 달지 않습니다.
- 분량: {length}

출력 형식
# (제목)
(본문, 소제목은 ## 사용)

---
**태그**: #태그1 #태그2 … (8~15개)

**이미지 생성 프롬프트** (대표 이미지 포함 정확히 총 {image_count}장, 번호 목록, 각 줄은 이미지 생성 AI에 바로 붙여 넣을 수 있는 한 문장)
"""
    return BASE_SYSTEM, user


def review(
    keyword: str, style: str, prep: str, experience: str, draft_text: str, request: str = ""
) -> tuple[str, str]:
    user = f"""키워드 「{keyword}」 글의 초안을 발행 전에 검수해 주세요.

{_context(style, prep, experience, request)}

<draft>
{draft_text}
</draft>

먼저 아래 항목으로 검수 결과를 쓰세요. 각 항목은 ✅/⚠️ 로 표시하고, 문제는 해당 문장을 인용해 고칠 방향을 적습니다.

## 검수 결과
1. 사실·수치: 준비 자료와 다르거나 근거 없는 내용, [확인 필요] 목록
2. 경험의 진실성: <my_experience>에 없는 경험을 지어낸 부분
3. 요청·경험 반영: <my_request>의 요청과 <my_experience>의 경험이 각각 본문 어디에 들어갔는지, 빠진 것
4. 스타일 일치: 어조·종결어미·문단 습관이 내 블로그와 맞는지
5. 반복 표현: 같은 어미·접속사·표현이 반복되는 곳 ({REPEAT_WATCH} 등)
6. 검색 의도 충족: 독자가 궁금한 것을 다 답했는지, 빠진 핵심 정보
7. 키워드 배치: 제목·도입부·소제목, 과도한 반복 여부
8. 가독성·출처: 너무 긴 문단·문장, 소제목 흐름, 중복된 출처 링크

그다음 한 줄에 정확히 {FINAL_MARKER} 라고 쓰고, 검수 결과를 모두 반영한 최종본 전체를 초안과 같은 형식(제목, 본문, 태그, 이미지 프롬프트)으로 쓰세요.
3번에서 빠진 요청·경험은 준비 자료와 입력 범위 안에서 채워 넣습니다.
확인되지 않은 사실은 지어내서 채우지 말고 [확인 필요] 표시를 남겨 두세요.
"""
    return BASE_SYSTEM, user


def split_review(text: str) -> tuple[str, str]:
    """검수 응답을 (검수 결과, 최종본)으로 나눈다. 구분선이 없으면 최종본은 빈 문자열."""
    if FINAL_MARKER in text:
        report, final = text.split(FINAL_MARKER, 1)
        return report.strip(), final.strip()
    return text.strip(), ""
