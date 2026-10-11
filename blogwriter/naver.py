"""네이버 블로그 수집: 검색 API, 내 블로그 RSS, 글 본문 추출."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://openapi.naver.com/v1/search/blog.json"
RSS_URL = "https://rss.blog.naver.com/{blog_id}.xml"
MOBILE_POST_URL = "https://m.blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
TIMEOUT = 15


class NaverError(RuntimeError):
    pass


@dataclass
class Post:
    title: str
    link: str
    summary: str = ""
    date: str = ""
    author: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    body: str = ""


def strip_tags(text: str) -> str:
    """검색 결과의 <b> 태그와 HTML 엔티티를 제거한다."""
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def parse_post_url(url: str) -> tuple[str, str] | None:
    """네이버 블로그 글 주소에서 (blogId, logNo)를 뽑는다. 네이버 블로그가 아니면 None."""
    blog_id = re.search(r"[?&]blogId=([\w-]+)", url)
    log_no = re.search(r"[?&]logNo=(\d+)", url)
    if blog_id and log_no:
        return blog_id.group(1), log_no.group(1)
    m = re.search(r"blog\.naver\.com/([\w-]+)/(\d+)", url)
    if m:
        return m.group(1), m.group(2)
    return None


def normalize_blog_id(value: str) -> str:
    """'https://blog.naver.com/abc' 같은 주소나 'abc' 아이디를 모두 받아 아이디만 돌려준다."""
    value = value.strip().rstrip("/")
    m = re.search(r"blogId=([\w-]+)", value) or re.search(r"blog\.naver\.com/([\w-]+)", value)
    if m:
        return m.group(1)
    if not re.fullmatch(r"[\w-]+", value):
        raise NaverError(f"블로그 아이디를 알아볼 수 없습니다: {value!r}")
    return value


# ---------------------------------------------------------------- 검색 API

def _search_raw(query: str, client_id: str, client_secret: str, display: int) -> dict:
    if not (client_id and client_secret):
        raise NaverError("네이버 검색 API Client ID / Secret을 먼저 입력하세요.")
    resp = requests.get(
        SEARCH_URL,
        params={"query": query, "display": display, "sort": "sim"},
        headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        try:
            msg = resp.json().get("errorMessage", resp.text)
        except ValueError:
            msg = resp.text
        raise NaverError(f"네이버 검색 API 오류 ({resp.status_code}): {msg}")
    return resp.json()


def search_blog(query: str, client_id: str, client_secret: str, display: int = 10) -> list[Post]:
    """네이버 블로그 검색 API(정확도순) 상위 글 목록."""
    return parse_search_response(_search_raw(query, client_id, client_secret, display))


def blog_total(query: str, client_id: str, client_secret: str) -> int:
    """이 검색어로 나오는 블로그 문서 수 (검색 API의 total)."""
    return int(_search_raw(query, client_id, client_secret, display=1).get("total", 0))


def parse_search_response(data: dict) -> list[Post]:
    return [
        Post(
            title=strip_tags(it.get("title", "")),
            link=it.get("link", ""),
            summary=strip_tags(it.get("description", "")),
            date=it.get("postdate", ""),
            author=it.get("bloggername", ""),
        )
        for it in data.get("items", [])
    ]


def check_search_api(client_id: str, client_secret: str) -> int:
    """연결 확인용: '블로그' 검색 결과 수를 돌려준다."""
    return len(search_blog("블로그", client_id, client_secret, display=1))


# ---------------------------------------------------------------- RSS

def fetch_rss(blog_id: str, limit: int = 30) -> list[Post]:
    """내 블로그 RSS에서 최근 글 목록을 가져온다 (보통 최근 50개까지 제공)."""
    blog_id = normalize_blog_id(blog_id)
    resp = requests.get(RSS_URL.format(blog_id=blog_id), headers={"User-Agent": UA}, timeout=TIMEOUT)
    if resp.status_code != 200:
        raise NaverError(f"RSS를 가져오지 못했습니다 ({resp.status_code}). 블로그 아이디와 공개 설정을 확인하세요.")
    return parse_rss(resp.content)[:limit]


def parse_rss(xml_bytes: bytes) -> list[Post]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise NaverError(f"RSS 형식을 읽지 못했습니다: {e}") from e
    posts = []
    for item in root.iter("item"):
        def text(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None else ""

        tags = [t.strip() for t in text("tag").split(",") if t.strip()]
        posts.append(
            Post(
                title=strip_tags(text("title")),
                link=text("link"),
                summary=strip_tags(text("description")),
                date=text("pubDate"),
                category=text("category"),
                tags=tags,
            )
        )
    return posts


# ---------------------------------------------------------------- 본문

def fetch_post_body(url: str, max_chars: int = 6000) -> str:
    """네이버 블로그 글의 본문 텍스트. 네이버 블로그가 아니면 일반 페이지 본문을 추린다."""
    ids = parse_post_url(url)
    target = MOBILE_POST_URL.format(blog_id=ids[0], log_no=ids[1]) if ids else url
    resp = requests.get(target, headers={"User-Agent": UA}, timeout=TIMEOUT)
    resp.raise_for_status()
    return extract_body(resp.text)[:max_chars]


def extract_body(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # 스마트에디터 ONE: 문단 단위로 줄바꿈을 살린다.
    container = soup.select_one("div.se-main-container")
    if container:
        paras = [
            p.get_text(" ", strip=True)
            for p in container.select(".se-text-paragraph, .se-quote, .se-table")
        ]
        text = "\n".join(p for p in paras if p)
        if text:
            return _clean(text)

    # 구 에디터 / 일반 페이지
    for selector in ("#postViewArea", "div.post-view", "article", "main", "body"):
        node = soup.select_one(selector)
        if node:
            return _clean(node.get_text("\n", strip=True))
    return ""


def _clean(text: str) -> str:
    text = text.replace("​", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fill_bodies(posts: list[Post], max_chars: int = 6000) -> list[str]:
    """posts의 body를 채운다. 실패한 글은 요약으로 대신하고, 실패 메시지를 모아 돌려준다."""
    errors = []
    for p in posts:
        try:
            p.body = fetch_post_body(p.link, max_chars=max_chars) or p.summary
        except requests.RequestException as e:
            p.body = p.summary
            errors.append(f"{p.title}: {e}")
    return errors
