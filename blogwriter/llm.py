"""Claude 호출. 긴 글을 다루므로 항상 스트리밍으로 받는다."""

from __future__ import annotations

from collections.abc import Iterator

import anthropic

DEFAULT_MODEL = "claude-opus-5-5"
MODELS = {
    "Claude Opus 5.5 (기본·고품질)": "claude-opus-5-5",
    "Claude Sonnet 5.5 (빠르고 저렴)": "claude-sonnet-5-5",
}
# 안전 분류기가 요청을 거절하면 서버가 다른 모델로 이어서 처리한다.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(RuntimeError):
    pass


def make_client(api_key: str) -> anthropic.Anthropic:
    # 키를 비워 두면 ANTHROPIC_API_KEY 환경변수 등 SDK 기본 인증을 쓴다.
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def stream_text(
    client: anthropic.Anthropic,
    system: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    max_tokens: int = 32000,
) -> Iterator[str]:
    """본문 텍스트 조각을 순서대로 내보낸다. 끝까지 소비해야 오류 검사가 끝난다."""
    try:
        with client.beta.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            yield from stream.text_stream
            final = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise LLMError("Claude API 키가 올바르지 않습니다. 연결 설정을 확인하세요.") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Claude API 사용 한도에 걸렸습니다. 잠시 후 다시 시도하세요.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API 오류 ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Claude API에 연결하지 못했습니다. 네트워크를 확인하세요.") from e

    if final.stop_reason == "refusal":
        raise LLMError("요청이 안전 정책으로 거절되었습니다. 주제나 표현을 바꿔 다시 시도하세요.")
    if final.stop_reason == "max_tokens":
        yield "\n\n> ⚠️ 출력 길이 한도에 도달해 글이 중간에 끊겼습니다."


def complete(client: anthropic.Anthropic, system: str, prompt: str, **kw) -> str:
    return "".join(stream_text(client, system, prompt, **kw))


def check_connection(client: anthropic.Anthropic, model: str = DEFAULT_MODEL) -> str:
    """짧은 실제 호출로 키와 모델을 확인한다 (사용량이 아주 조금 든다)."""
    return complete(client, "짧게 답하세요.", "'연결 성공'이라고만 답하세요.", model=model, effort="low", max_tokens=2000)
