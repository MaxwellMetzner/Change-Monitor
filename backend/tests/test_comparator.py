from io import BytesIO

from PIL import Image, ImageDraw

from app.comparator import evaluate_rules, hamming_hex, image_average_hash, normalize_text


def test_bad_state_disappearance_triggers_alert():
    result = evaluate_rules(
        old_text="Out of Stock.",
        new_text="$99.00 Add to Cart",
        old_visual_hash=None,
        new_visual_hash=None,
        rules=[
            {"type": "bad_text_absent", "config": {"bad_text": "Out of Stock"}, "enabled": True},
            {"type": "positive_phrase_present", "config": {"phrases": ["add to cart"]}, "enabled": True},
        ],
    )

    assert result.alert is True
    assert {rule["type"] for rule in result.triggered_rules} == {"bad_text_absent", "positive_phrase_present"}


def test_text_normalization_ignores_case_and_punctuation():
    assert normalize_text(" Out-of-stock!!! ") == "out of stock"


def test_minor_bad_text_punctuation_does_not_trigger():
    result = evaluate_rules(
        old_text="Out of Stock.",
        new_text="out-of-stock",
        old_visual_hash=None,
        new_visual_hash=None,
        rules=[{"type": "bad_text_absent", "config": {"bad_text": "Out of Stock"}, "enabled": True}],
    )

    assert result.alert is False


def _png_bytes(text: str) -> bytes:
    image = Image.new("RGB", (240, 80), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 220, 60), outline="black", width=2)
    draw.text((36, 34), text, fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_visual_hash_is_stable_for_identical_images():
    left = image_average_hash(_png_bytes("Out of Stock"))
    right = image_average_hash(_png_bytes("Out of Stock"))

    assert left.startswith("dhash-v1:")
    assert hamming_hex(left, right) == 0


def test_visual_hash_format_mismatch_is_not_compared():
    assert hamming_hex("ffffffffffffffff", image_average_hash(_png_bytes("Out of Stock"))) == 0
