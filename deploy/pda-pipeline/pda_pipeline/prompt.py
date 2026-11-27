"""T3 Code が ACP で渡す依頼から、オーナーの依頼の文を取り出す。"""
import hashlib
import re

_USER_REQUEST = re.compile(r"<user_request>(.*?)</user_request>", re.S)
_T3_MARK = re.compile(r"^\s*\[T3 Code:[^\]]*\]\s*")
_HANDOFF = "User message:"


def extract_request(blocks):
    """session/prompt の prompt の配列を取り、(依頼の文, T3 Code の道具経由か) を返す。"""
    raw = "\n".join(b.get("text", "") for b in blocks or [] if b.get("type") == "text")
    m = _USER_REQUEST.search(raw)
    body = m.group(1) if m else raw
    if body.lstrip().startswith("Context handoff") and _HANDOFF in body:
        body = body[body.rindex(_HANDOFF) + len(_HANDOFF):]
    via_tools = bool(_T3_MARK.match(body))
    return _T3_MARK.sub("", body).strip(), via_tools


def text_key(text):
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()
