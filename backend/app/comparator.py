from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from io import BytesIO
from typing import Any

from PIL import Image, ImageFilter


DEFAULT_POSITIVE_PHRASES = [
    "add to cart",
    "buy now",
    "in stock",
    "available",
    "reserve",
    "pre-order",
    "checkout",
    "select seats",
    "tickets available",
    "register",
    "book now",
    "available appointments",
    "select time",
    "open slot",
]

LIKELY_BAD_PHRASES = [
    "out of stock",
    "sold out",
    "unavailable",
    "currently unavailable",
    "not available",
    "no appointments",
    "coming soon",
    "notify me",
]


def normalize_text(value: str, *, lowercase: bool = True) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\s?(?:am|pm)?\b", " ", text, flags=re.I)
    text = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", " ", text)
    text = re.sub(r"[\u2018\u2019]", "'", text)
    text = re.sub(r"[\u201c\u201d]", '"', text)
    text = re.sub(r"[^0-9A-Za-z$%.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower() if lowercase else text


def text_similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def changed_char_count(left: str, right: str) -> int:
    matcher = SequenceMatcher(None, left, right)
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal")


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def image_average_hash(contents: bytes, hash_size: int = 8) -> str:
    image = Image.open(BytesIO(contents)).convert("L")
    image = image.filter(ImageFilter.GaussianBlur(radius=0.75))
    image = image.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = list(image.getdata())
    bits = []
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for column in range(hash_size):
            left = pixels[offset + column]
            right = pixels[offset + column + 1]
            bits.append("1" if left > right else "0")
    return f"dhash-v1:{int(''.join(bits), 2):0{hash_size * hash_size // 4}x}"


def _split_visual_hash(value: str) -> tuple[str, str]:
    if ":" not in value:
        return "legacy-ahash", value
    prefix, digest = value.split(":", 1)
    return prefix, digest


def hamming_hex(left: str | None, right: str | None) -> int:
    if not left or not right:
        return 0
    left_prefix, left_digest = _split_visual_hash(left)
    right_prefix, right_digest = _split_visual_hash(right)
    if left_prefix != right_prefix:
        return 0
    try:
        return bin(int(left_digest, 16) ^ int(right_digest, 16)).count("1")
    except ValueError:
        return 0


def extract_bad_phrase(text: str) -> str:
    normalized = normalize_text(text)
    for phrase in LIKELY_BAD_PHRASES:
        if phrase in normalized:
            return phrase
    words = normalized.split()
    return " ".join(words[:12]) if words else ""


def phrase_present(phrase: str, text: str) -> bool:
    normalized_phrase = normalize_text(phrase)
    normalized_text = normalize_text(text)
    if not normalized_phrase:
        return False
    if normalized_phrase in normalized_text:
        return True
    return SequenceMatcher(None, normalized_phrase, normalized_text[: max(len(normalized_phrase) * 2, 1)]).ratio() > 0.92


@dataclass
class RuleEvaluation:
    alert: bool
    changed: bool
    change_score: float
    triggered_rules: list[dict[str, Any]]
    summary: str
    deduplication_state: str


def evaluate_rules(
    *,
    old_text: str,
    new_text: str,
    old_visual_hash: str | None,
    new_visual_hash: str | None,
    rules: list[dict[str, Any]],
    selector_found: bool = True,
) -> RuleEvaluation:
    old_norm = normalize_text(old_text)
    new_norm = normalize_text(new_text)
    similarity = text_similarity(old_norm, new_norm)
    score = round(1 - similarity, 4)
    changed_chars = changed_char_count(old_norm, new_norm)
    triggered: list[dict[str, Any]] = []
    alert = False
    changed = score > 0.0
    summary = "No meaningful change detected."

    enabled_rules = [rule for rule in rules if rule.get("enabled", True)]
    if not enabled_rules:
        enabled_rules = [{"type": "any_text_change", "config": {"threshold": 0.12, "minimum_changed_characters": 8}}]

    for rule in enabled_rules:
        rule_type = rule["type"]
        config = rule.get("config") or {}

        if rule_type == "selector_missing" and not selector_found:
            triggered.append({"type": rule_type, "reason": "The selector did not match any element."})
            alert = True
            changed = True
            summary = "The monitored selector is missing from the page."

        if rule_type == "bad_text_absent":
            bad_text = config.get("bad_text", "")
            if bad_text and phrase_present(bad_text, old_text) and not phrase_present(bad_text, new_text):
                triggered.append({"type": rule_type, "reason": "Unavailable text disappeared.", "bad_text": bad_text})
                alert = True
                changed = True
                summary = "Unavailable text disappeared from the monitored area."

        if rule_type == "positive_phrase_present":
            phrases = config.get("phrases") or DEFAULT_POSITIVE_PHRASES
            matches = [phrase for phrase in phrases if phrase_present(phrase, new_text) and not phrase_present(phrase, old_text)]
            if matches:
                triggered.append({"type": rule_type, "reason": "Positive phrase appeared.", "matches": matches})
                alert = True
                changed = True
                summary = f"Purchase/availability phrase appeared: {', '.join(matches[:3])}."

        if rule_type == "any_text_change":
            threshold = float(config.get("threshold", 0.12))
            minimum_changed_characters = int(config.get("minimum_changed_characters", 8))
            if score >= threshold and changed_chars >= minimum_changed_characters:
                triggered.append(
                    {
                        "type": rule_type,
                        "reason": "Text changed above threshold.",
                        "change_score": score,
                        "changed_characters": changed_chars,
                    }
                )
                alert = True
                changed = True
                summary = f"Text changed materially ({int(score * 100)}% difference)."

        if rule_type == "any_visual_change":
            threshold = int(config.get("hamming_threshold", 8))
            distance = hamming_hex(old_visual_hash, new_visual_hash)
            if distance >= threshold:
                triggered.append({"type": rule_type, "reason": "Screenshot hash changed.", "distance": distance})
                alert = True
                changed = True
                summary = f"Visual area changed (hash distance {distance})."

    old_preview = old_text.strip().replace("\n", " ")[:160]
    new_preview = new_text.strip().replace("\n", " ")[:160]
    if alert and old_preview and new_preview:
        summary = f"{summary} Old: {old_preview} New: {new_preview}"

    return RuleEvaluation(
        alert=alert,
        changed=changed,
        change_score=score,
        triggered_rules=triggered,
        summary=summary,
        deduplication_state=text_hash(new_norm),
    )


def unified_text_diff(from_text: str, to_text: str) -> str:
    from_lines = from_text.splitlines()
    to_lines = to_text.splitlines()
    return "\n".join(
        difflib.unified_diff(from_lines, to_lines, fromfile="baseline", tofile="snapshot", lineterm="")
    )
