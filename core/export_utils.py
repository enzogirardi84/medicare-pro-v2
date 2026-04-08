import io
import json
import re
import unicodedata


def _repair_mojibake(text):
    if not text:
        return text
    sospechoso = ("Ã", "Â", "â", "ð", "�")
    if not any(token in text for token in sospechoso):
        return text
    try:
        reparado = text.encode("latin-1", "ignore").decode("utf-8", "ignore")
        return reparado or text
    except Exception:
        return text


def safe_text(value):
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", "replace")
    elif isinstance(value, (list, tuple, set)):
        text = ", ".join(safe_text(item) for item in value if item not in [None, ""])
    elif isinstance(value, dict):
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            text = str(value)
    else:
        text = str(value)

    text = _repair_mojibake(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if ch == "\n" or (ord(ch) >= 32 and ch != "\x7f"))
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    parts = []
    for token in text.split(" "):
        if len(token) > 40:
            token = " ".join(token[i : i + 32] for i in range(0, len(token), 32))
        parts.append(token)
    text = " ".join(parts)
    return text.encode("latin-1", "replace").decode("latin-1")


def pdf_output_bytes(pdf):
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", "replace")
    return bytes(out)


def sanitize_filename_component(value, fallback="archivo"):
    text = unicodedata.normalize("NFKD", str(value or fallback))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")
    return text or fallback


def dataframe_csv_bytes(df):
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)
    return buffer.getvalue()
