from blogwriter import naver, prompts

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>내 블로그</title>
<item><title><![CDATA[가을 캠핑 준비물 정리]]></title>
<link>https://blog.naver.com/myid/223000000001?fromRss=true</link>
<description><![CDATA[<p>올해도 캠핑 &amp; 여행</p>]]></description>
<category>캠핑</category><tag>캠핑,가을캠핑, 준비물</tag>
<pubDate>Mon, 06 Oct 2026 10:00:00 +0900</pubDate></item>
<item><title>두 번째 글</title><link>https://blog.naver.com/myid/2</link></item>
</channel></rss>""".encode()

SE_ONE = """<html><body><script>var x=1;</script>
<div class="se-main-container">
  <div class="se-module"><p class="se-text-paragraph"><span>안녕하세요&#8203; 여러분</span></p></div>
  <div class="se-module"><p class="se-text-paragraph"><span>오늘은 캠핑 이야기예요.</span></p></div>
</div></body></html>"""


def test_parse_rss():
    posts = naver.parse_rss(RSS)
    assert len(posts) == 2
    assert posts[0].title == "가을 캠핑 준비물 정리"
    assert posts[0].summary == "올해도 캠핑 & 여행"
    assert posts[0].tags == ["캠핑", "가을캠핑", "준비물"]
    assert posts[1].category == ""


def test_parse_search_response():
    data = {"items": [{"title": "<b>제주</b> 여행 &amp; 코스", "link": "https://blog.naver.com/a/1",
                       "description": "<b>제주</b> 3박", "bloggername": "아무개", "postdate": "20261001"}]}
    [p] = naver.parse_search_response(data)
    assert p.title == "제주 여행 & 코스"
    assert p.summary == "제주 3박"
    assert p.author == "아무개" and p.date == "20261001"


def test_parse_post_url():
    assert naver.parse_post_url("https://blog.naver.com/myid/223000000001") == ("myid", "223000000001")
    assert naver.parse_post_url("https://blog.naver.com/PostView.naver?blogId=myid&logNo=42") == ("myid", "42")
    assert naver.parse_post_url("https://m.blog.naver.com/PostView.naver?logNo=42&blogId=my-id") == ("my-id", "42")
    assert naver.parse_post_url("https://news.example.com/article/1") is None


def test_normalize_blog_id():
    assert naver.normalize_blog_id("snscheol") == "snscheol"
    assert naver.normalize_blog_id("https://blog.naver.com/snscheol/") == "snscheol"
    assert naver.normalize_blog_id("https://blog.naver.com/PostList.naver?blogId=snscheol") == "snscheol"


def test_extract_body_smart_editor():
    assert naver.extract_body(SE_ONE) == "안녕하세요 여러분\n오늘은 캠핑 이야기예요."


def test_extract_body_fallback():
    assert "본문" in naver.extract_body("<html><body><article><p>기사 본문</p></article></body></html>")


def test_split_review():
    report, final = prompts.split_review(f"## 검수 결과\n문제 없음\n{prompts.FINAL_MARKER}\n# 제목\n본문")
    assert report == "## 검수 결과\n문제 없음"
    assert final == "# 제목\n본문"
    assert prompts.split_review("검수만")[1] == ""


def test_prompts_include_inputs():
    post = naver.Post(title="t", link="l", body="본문내용")
    _, user = prompts.research("키워드X", [post], "스타일Y")
    assert "키워드X" in user and "스타일Y" in user and "본문내용" in user
    _, user = prompts.draft("k", "", "", "경험Z", "", "보통", 7)
    assert "경험Z" in user and "총 7장" in user
