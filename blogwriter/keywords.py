"""키워드 탐색: 네이버 검색광고 API(월 검색량) + 블로그 검색 API(문서 수) → 키워드 카드."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import time
from dataclasses import dataclass

import requests

from . import naver

SEARCHAD_BASE = "https://api.searchad.naver.com"
KEYWORDS_TOOL = "/keywordstool"
TIMEOUT = 15


@dataclass
class KeywordStat:
    keyword: str
    pc: int | None = None          # 월간 PC 검색수 (None = 미확인)
    mobile: int | None = None      # 월간 모바일 검색수
    competition: str = ""          # 검색광고 경쟁정도: 높음/중간/낮음
    docs: int | None = None        # 블로그 문서 수 (None = 아직 조회 안 함·실패)

    @property
    def monthly(self) -> int | None:
        if self.pc is None or self.mobile is None:
            return None
        return self.pc + self.mobile

    @property
    def monthly_text(self) -> str:
        """화면 표시용. API가 '< 10'으로 준 값은 0으로 저장되므로 '10 미만'으로 보여 준다."""
        if self.monthly is None:
            return "미확인"
        parts = [self.pc, self.mobile]
        if all(p == 0 for p in parts):
            return "20 미만"
        if any(p == 0 for p in parts):
            return f"약 {self.monthly:,}+"
        return f"{self.monthly:,}"

    @property
    def ratio(self) -> float | None:
        """문서 수 ÷ 월 검색량. 낮을수록 검색하는 사람에 비해 글이 적다는 뜻."""
        if self.monthly is None or self.docs is None or self.monthly == 0:
            return None
        return self.docs / self.monthly

    @property
    def grade(self) -> Grade:
        return grade_of(self.monthly, self.ratio)


@dataclass(frozen=True)
class Grade:
    code: str
    label: str
    color: str  # 카드 테두리·배지 색
    hint: str


GRADES = {
    "A": Grade("A", "A 기회", "#16a34a", "검색량에 비해 글이 적어요"),
    "B": Grade("B", "B 좋음", "#2563eb", "도전해 볼 만해요"),
    "C": Grade("C", "C 보통", "#ca8a04", "차별화가 필요해요"),
    "D": Grade("D", "D 포화", "#dc2626", "이미 글이 아주 많아요"),
    "E": Grade("E", "E 검색 적음", "#6b7280", "찾는 사람이 거의 없어요"),
    "?": Grade("?", "미확인", "#9ca3af", "수치를 확인하지 못했어요"),
}
MIN_MONTHLY = 50
RATIO_CUTS = (("A", 0.5), ("B", 2.0), ("C", 10.0))


def grade_of(monthly: int | None, ratio: float | None) -> Grade:
    if monthly is None:
        return GRADES["?"]
    if monthly < MIN_MONTHLY:
        return GRADES["E"]
    if ratio is None:
        return GRADES["?"]
    for code, cut in RATIO_CUTS:
        if ratio < cut:
            return GRADES[code]
    return GRADES["D"]


# ---------------------------------------------------------------- 검색광고 API

class SearchAd:
    def __init__(self, customer_id: str, api_key: str, secret_key: str):
        if not (customer_id and api_key and secret_key):
            raise naver.NaverError("검색광고 API 고객 ID / 액세스 라이선스 / 비밀키를 모두 입력하세요.")
        self.customer_id, self.api_key, self.secret_key = customer_id.strip(), api_key.strip(), secret_key.strip()

    def _headers(self, method: str, uri: str) -> dict:
        timestamp = str(int(time.time() * 1000))
        return {
            "X-Timestamp": timestamp,
            "X-API-KEY": self.api_key,
            "X-Customer": self.customer_id,
            "X-Signature": signature(self.secret_key, timestamp, method, uri),
        }

    def related(self, seeds: list[str]) -> list[KeywordStat]:
        """시드 키워드(최대 5개)와 연관 키워드의 월 검색량."""
        hints = [hint_keyword(s) for s in seeds if hint_keyword(s)][:5]
        if not hints:
            raise naver.NaverError("키워드를 입력하세요.")
        resp = requests.get(
            SEARCHAD_BASE + KEYWORDS_TOOL,
            params={"hintKeywords": ",".join(hints), "showDetail": "1"},
            headers=self._headers("GET", KEYWORDS_TOOL),
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            try:
                msg = resp.json().get("title") or resp.json().get("message") or resp.text
            except ValueError:
                msg = resp.text
            raise naver.NaverError(f"검색광고 API 오류 ({resp.status_code}): {msg}")
        return parse_keywordstool(resp.json())


def signature(secret_key: str, timestamp: str, method: str, uri: str) -> str:
    message = f"{timestamp}.{method}.{uri}"
    digest = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def hint_keyword(text: str) -> str:
    """검색광고 API는 띄어쓰기가 있는 키워드를 받지 않는다 (네이버 검색량도 띄어쓰기 무시)."""
    return re.sub(r"\s+", "", text)


def parse_count(value) -> int | None:
    """월간 검색수: 숫자 또는 '< 10' 같은 문자열. '< 10'은 임의로 어림하지 않고 0으로 둔다 (표시는 monthly_text)."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        if value.strip().startswith("<"):
            return 0
        digits = value.replace(",", "").strip()
        if digits.isdigit():
            return int(digits)
    return None


def parse_keywordstool(data: dict) -> list[KeywordStat]:
    return [
        KeywordStat(
            keyword=item.get("relKeyword", ""),
            pc=parse_count(item.get("monthlyPcQcCnt")),
            mobile=parse_count(item.get("monthlyMobileQcCnt")),
            competition=item.get("compIdx", "") or "",
        )
        for item in data.get("keywordList", [])
        if item.get("relKeyword")
    ]


def fill_docs(stats: list[KeywordStat], client_id: str, client_secret: str, on_progress=None) -> list[str]:
    """블로그 문서 수를 채운다. 실패한 키워드는 None(미확인)으로 두고 오류를 모아 돌려준다."""
    errors = []
    for i, s in enumerate(stats):
        try:
            s.docs = naver.blog_total(s.keyword, client_id, client_secret)
        except (naver.NaverError, requests.RequestException) as e:
            s.docs = None
            errors.append(f"{s.keyword}: {e}")
        if on_progress:
            on_progress(i + 1, len(stats))
    return errors


def fmt_int(value: int | None) -> str:
    return "미확인" if value is None else f"{value:,}"


def fmt_ratio(value: float | None) -> str:
    return "미확인" if value is None else f"{value:,.2f}"
