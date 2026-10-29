"""Lớp gọi LLM dùng chung: thử lần lượt Gemini, Groq, OpenRouter và tự chuyển khi lỗi hoặc hết hạn mức."""
import json
import re
import time

import requests

from .config import env


class LLMError(RuntimeError):
    pass


def _post(url, headers, body, retries=3):
    """POST có thử lại khi gặp 429/5xx (chờ 2s, 4s, ...)."""
    last = None
    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=120)
        except requests.RequestException as exc:
            last = f"lỗi mạng: {exc.__class__.__name__}"
        else:
            if resp.status_code == 200:
                return resp.json()
            last = f"HTTP {resp.status_code}"
            if resp.status_code not in (429, 500, 502, 503, 504):
                raise LLMError(last)
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
    raise LLMError(last or "không rõ lỗi")


def _gemini(prompt, system, json_mode):
    key = env("GEMINI_API_KEY")
    model = env("GEMINI_MODEL", "gemini-2.5-flash")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    data = _post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {"x-goog-api-key": key, "Content-Type": "application/json"},
        body,
    )
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError):
        raise LLMError("Gemini trả về phản hồi rỗng hoặc bị chặn")


def _openai_compatible(url, key, model, prompt, system, extra_headers=None):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    headers.update(extra_headers or {})
    data = _post(url, headers, {"model": model, "messages": messages, "temperature": 0.4})
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise LLMError("phản hồi rỗng")


def _groq(prompt, system, json_mode):
    return _openai_compatible(
        "https://api.groq.com/openai/v1/chat/completions",
        env("GROQ_API_KEY"),
        env("GROQ_MODEL", "llama-3.3-70b-versatile"),
        prompt,
        system,
    )


def _openrouter(prompt, system, json_mode):
    model = env("OPENROUTER_MODEL")
    if not model:
        raise LLMError("chưa đặt OPENROUTER_MODEL (chọn một model có đuôi :free)")
    return _openai_compatible(
        "https://openrouter.ai/api/v1/chat/completions",
        env("OPENROUTER_API_KEY"),
        model,
        prompt,
        system,
    )


PROVIDERS = {
    "gemini": ("GEMINI_API_KEY", _gemini),
    "groq": ("GROQ_API_KEY", _groq),
    "openrouter": ("OPENROUTER_API_KEY", _openrouter),
}


def call_llm(prompt, system=None, json_mode=False):
    order = [n.strip() for n in env("LLM_ORDER", "gemini,groq,openrouter").split(",") if n.strip()]
    problems = []
    for name in order:
        if name not in PROVIDERS:
            continue
        key_name, fn = PROVIDERS[name]
        if not env(key_name):
            problems.append(f"{name}: chưa có khoá")
            continue
        try:
            return fn(prompt, system, json_mode)
        except LLMError as exc:
            problems.append(f"{name}: {exc}")
    raise LLMError("Không nhà cung cấp nào dùng được: " + "; ".join(problems))


def parse_json(text):
    """Tách JSON ra khỏi phản hồi, kể cả khi model bọc trong ```json ... ```."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("không thấy JSON trong phản hồi")
    candidate = text[min(starts):]
    end = max(candidate.rfind("}"), candidate.rfind("]"))
    return json.loads(candidate[: end + 1])
