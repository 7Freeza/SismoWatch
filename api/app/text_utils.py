import re
import unicodedata


def normalize_text(value):
    decomposed = unicodedata.normalize("NFKD", (value or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def sanitize_text(value, max_length=500):
    text = "".join(ch for ch in (value or "") if ch == " " or ch.isprintable())
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def extract_numbers(value):
    tokens = re.findall(r"\d+(?:[.,]\d+)?", str(value or ""))
    return [float(token.replace(",", ".")) for token in tokens]
