"""LLM client (Dify + OpenAI-compatible) bound to Personal Hotspot interface."""

from __future__ import annotations

import http.client
import json
import re
import ssl
import urllib.parse
from typing import Callable, Optional

from .network import BoundHTTPConnection, ensure_default_hotspot, find_hotspot_bind_address


class LLMError(Exception):
    pass


BUGFIND_PROMPT = (
    "You are a C/C++ code reviewer for Dev-C++ 5.11. "
    "ALWAYS reply in Thai only. List bugs as numbered points with short fixes. "
    "Do not rewrite the whole file unless asked. "
    "If you show sample code, use ```cpp and never put comments in code."
)

CHATBOT_PROMPT = (
    "You are a C/C++ coding assistant for Dev-C++ 5.11. "
    "ALWAYS reply in Thai only (except code identifiers/keywords inside code). "
    "Put code in ```cpp only, with no comments (no // or /* */). "
    "Put explanations outside code blocks only."
)

SYSTEM_PROMPT = CHATBOT_PROMPT

CODE_FENCE_RE = re.compile(r"```(?:cpp|c|c\+\+)?\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_code_blocks(text: str) -> list[str]:
    blocks = [m.group(1).strip("\n") for m in CODE_FENCE_RE.finditer(text or "")]
    return [b for b in blocks if b.strip()]


def _is_dify(base_url: str, provider: str = "") -> bool:
    p = (provider or "").strip().lower()
    if p == "dify":
        return True
    u = base_url.lower()
    return "dify.ai" in u or ("dify" in u and u.rstrip("/").endswith("/v1"))


def _http_json(
    *,
    method: str,
    url: str,
    headers: dict,
    body: bytes,
    local_ip: str,
    timeout: float,
) -> tuple[int, dict | str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise LLMError(f"base_url ไม่ถูกต้อง: {url}")
    host = parsed.hostname
    if not host:
        raise LLMError("base_url ไม่มี hostname")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    headers = dict(headers)
    headers.setdefault("Host", host)
    headers.setdefault("Connection", "close")
    headers.setdefault("Content-Length", str(len(body)))
    headers.setdefault("User-Agent", "DevCpp-AI/1.0")

    binder = BoundHTTPConnection(local_ip)
    context = ssl.create_default_context() if parsed.scheme == "https" else None

    if parsed.scheme == "https":
        conn: http.client.HTTPConnection = http.client.HTTPSConnection(
            host, port, timeout=timeout, context=context
        )
    else:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)

    def bound_connect() -> None:
        sock = binder.connect(host, port, timeout=timeout)
        if context is not None:
            sock = context.wrap_socket(sock, server_hostname=host)
        conn.sock = sock

    conn.connect = bound_connect  # type: ignore[method-assign]

    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
        if resp.status >= 400:
            raise LLMError(f"API error {resp.status}: {raw[:800]}")
        try:
            return resp.status, json.loads(raw)
        except json.JSONDecodeError:
            return resp.status, raw
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _require_hotspot(on_status: Optional[Callable[[str], None]]):
    ok, msg = ensure_default_hotspot()
    if on_status:
        on_status(msg)
    bind = find_hotspot_bind_address()
    if bind is None:
        raise LLMError(
            "ไม่พบเน็ตที่ใช้ได้\n"
            f"{msg}\n"
            "ต่อ Hotspot (hah) หรือสาย LAN แล้วลองใหม่"
        )
    if on_status:
        label = "LAN" if bind.reason == "lan_fallback" else "Hotspot/Wi-Fi"
        on_status(f"ใช้เน็ตผ่าน {label}: {bind.iface_name} ({bind.ip})")
    return bind


def chat_dify(
    query: str,
    *,
    api_key: str,
    base_url: str,
    conversation_id: str = "",
    user: str = "devcpp-ai",
    timeout: float = 120.0,
    on_status: Optional[Callable[[str], None]] = None,
) -> tuple[str, str]:
    bind = _require_hotspot(on_status)
    base = base_url.rstrip("/")
    url = base + "/chat-messages"

    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "blocking",
        "conversation_id": conversation_id or "",
        "user": user,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        _, data = _http_json(
            method="POST",
            url=url,
            headers=headers,
            body=body,
            local_ip=bind.ip,
            timeout=timeout,
        )
    except LLMError:
        raise
    except OSError as e:
        raise LLMError(f"เชื่อมต่อ Dify ไม่สำเร็จผ่าน Hotspot: {e}") from e

    if not isinstance(data, dict):
        raise LLMError(f"ตอบกลับไม่ใช่ JSON object: {str(data)[:200]}")

    answer = data.get("answer")
    if not answer:
        raise LLMError(f"Dify ไม่ได้ส่งคำตอบ (answer ว่าง): {json.dumps(data)[:400]}")
    new_cid = str(data.get("conversation_id") or conversation_id or "")
    return str(answer), new_cid


def chat_openai_compatible(
    messages: list[dict],
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float = 120.0,
    on_status: Optional[Callable[[str], None]] = None,
) -> str:
    bind = _require_hotspot(on_status)
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        url = base + "/chat/completions"
    else:
        url = base + "/v1/chat/completions"

    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        _, data = _http_json(
            method="POST",
            url=url,
            headers=headers,
            body=body,
            local_ip=bind.ip,
            timeout=timeout,
        )
    except LLMError:
        raise
    except OSError as e:
        raise LLMError(f"เชื่อมต่อ LLM ไม่สำเร็จผ่าน Hotspot: {e}") from e

    if not isinstance(data, dict):
        raise LLMError("ตอบกลับไม่ใช่ JSON")
    choices = data.get("choices") or []
    if not choices:
        raise LLMError("API ไม่ได้ส่งคำตอบกลับมา")
    content = (choices[0].get("message") or {}).get("content")
    if not content:
        raise LLMError("คำตอบว่างจาก API")
    return str(content)


def chat_completion(
    messages: list[dict],
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float = 120.0,
    provider: str = "dify",
    conversation_id: str = "",
    on_status: Optional[Callable[[str], None]] = None,
) -> tuple[str, str]:
    if _is_dify(base_url, provider):
        parts: list[str] = []
        for m in messages:
            role = m.get("role")
            content = str(m.get("content") or "")
            if role == "system":
                continue
            if role in ("user", "assistant"):
                parts.append(content)
        query = parts[-1] if parts else ""
        answer, cid = chat_dify(
            query,
            api_key=api_key,
            base_url=base_url,
            conversation_id=conversation_id,
            timeout=timeout,
            on_status=on_status,
        )
        return answer, cid

    answer = chat_openai_compatible(
        messages,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        on_status=on_status,
    )
    return answer, conversation_id
