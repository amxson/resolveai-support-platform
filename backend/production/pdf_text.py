"""Isolated PDF extraction process. No links, scripts, images or tools execute."""

import io
import sys

if sys.platform != "win32":
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (6, 6))

from pypdf import PdfReader


def main():
    payload = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
    if len(payload) > 5 * 1024 * 1024:
        raise ValueError("File too large")
    reader = PdfReader(io.BytesIO(payload), strict=True)
    if reader.is_encrypted or len(reader.pages) > 100:
        raise ValueError("Encrypted or oversized PDF")
    text = ""
    for page in reader.pages:
        contents = page.get_contents()
        if contents and len(contents.get_data()) > 2 * 1024 * 1024:
            raise ValueError("PDF page stream too large")
        text += (page.extract_text() or "") + "\n"
        if len(text) > 100000:
            raise ValueError("Extracted text too long")
    if not text.strip():
        raise ValueError("No extractable text; OCR is not configured")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(2)
