"""Unit tests for bcgpt.utils.security.file_signature — all deterministic, stdlib only."""

import pytest
from bcgpt.utils.security.file_signature import (
    detect_file_type,
    validate_file_signature,
)


# ---------------------------------------------------------------------------
# 1. Real PNG bytes
# ---------------------------------------------------------------------------
class TestPNG:
    PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

    def test_detect(self):
        assert detect_file_type(self.PNG_MAGIC) == "png"

    def test_validate_ok(self):
        ok, msg = validate_file_signature(self.PNG_MAGIC, "logo.png")
        assert ok is True
        assert "png" in msg


# ---------------------------------------------------------------------------
# 2. Executable (MZ header) disguised as PNG
# ---------------------------------------------------------------------------
class TestExecutableAsPNG:
    MZ = b"MZ\x90\x00" + b"\x00" * 60

    def test_validate_rejects(self):
        ok, msg = validate_file_signature(self.MZ, "evil.png")
        assert ok is False
        # Should say "no recognizable signature" or "signature mismatch"
        assert "signature" in msg or "no recognizable" in msg


# ---------------------------------------------------------------------------
# 3. WebP dual-offset check
# ---------------------------------------------------------------------------
class TestWebP:
    WEBP = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 8
    FAKE_AVI = b"RIFF" + b"\x00" * 4 + b"AVI " + b"\x00" * 8

    def test_detect_webp(self):
        assert detect_file_type(self.WEBP) == "webp"

    def test_validate_webp_ok(self):
        ok, msg = validate_file_signature(self.WEBP, "x.webp")
        assert ok is True

    def test_fake_avi_not_webp(self):
        assert detect_file_type(self.FAKE_AVI) != "webp"

    def test_fake_avi_named_webp_rejected(self):
        ok, _ = validate_file_signature(self.FAKE_AVI, "x.webp")
        assert ok is False


# ---------------------------------------------------------------------------
# 4. WAV dual-offset check
# ---------------------------------------------------------------------------
class TestWAV:
    WAV = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 8

    def test_detect_wav(self):
        assert detect_file_type(self.WAV) == "wav"

    def test_validate_wav_ok(self):
        ok, _ = validate_file_signature(self.WAV, "sound.wav")
        assert ok is True


# ---------------------------------------------------------------------------
# 5. PDF checks
# ---------------------------------------------------------------------------
class TestPDF:
    PDF = b"%PDF-1.7\n" + b"\x00" * 20

    def test_detect(self):
        assert detect_file_type(self.PDF) == "pdf"

    def test_validate_pdf_ok(self):
        ok, _ = validate_file_signature(self.PDF, "doc.pdf")
        assert ok is True

    def test_pdf_named_png_rejected(self):
        ok, msg = validate_file_signature(self.PDF, "doc.png")
        assert ok is False
        assert "mismatch" in msg


# ---------------------------------------------------------------------------
# 6. DOCX / XLSX both accept ZIP magic
# ---------------------------------------------------------------------------
class TestZIPBased:
    ZIP_MAGIC = b"PK\x03\x04" + b"\x00" * 20

    def test_detect_zip(self):
        assert detect_file_type(self.ZIP_MAGIC) == "zip"

    def test_validate_docx(self):
        ok, _ = validate_file_signature(self.ZIP_MAGIC, "report.docx")
        assert ok is True

    def test_validate_xlsx(self):
        ok, _ = validate_file_signature(self.ZIP_MAGIC, "sheet.xlsx")
        assert ok is True

    def test_validate_pptx(self):
        ok, _ = validate_file_signature(self.ZIP_MAGIC, "slides.pptx")
        assert ok is True

    def test_validate_zip(self):
        ok, _ = validate_file_signature(self.ZIP_MAGIC, "archive.zip")
        assert ok is True

    def test_pk0506(self):
        assert detect_file_type(b"PK\x05\x06" + b"\x00" * 20) == "zip"

    def test_pk0708(self):
        assert detect_file_type(b"PK\x07\x08" + b"\x00" * 20) == "zip"


# ---------------------------------------------------------------------------
# 7. Fail-secure edge cases
# ---------------------------------------------------------------------------
class TestFailSecure:
    def test_empty_bytes(self):
        ok, msg = validate_file_signature(b"", "x.png")
        assert ok is False
        assert msg  # some message present

    def test_none_contents(self):
        ok, msg = validate_file_signature(None, "x.png")  # type: ignore[arg-type]
        assert ok is False

    def test_non_bytes(self):
        ok, msg = validate_file_signature("string data", "x.png")  # type: ignore[arg-type]
        assert ok is False

    def test_no_extension(self):
        ok, msg = validate_file_signature(b"some bytes", "noext")
        assert ok is False
        assert "extension" in msg

    def test_empty_extension(self):
        ok, msg = validate_file_signature(b"some bytes", "trailing.")
        assert ok is False
        assert "extension" in msg


# ---------------------------------------------------------------------------
# 8. Text passthrough (unverifiable text extensions)
# ---------------------------------------------------------------------------
class TestTextPassthrough:
    def test_csv(self):
        ok, msg = validate_file_signature(b"col1,col2\n1,2", "data.csv")
        assert ok is True
        assert "text" in msg

    def test_json(self):
        ok, msg = validate_file_signature(b'{"key": "value"}', "data.json")
        assert ok is True

    def test_md(self):
        ok, msg = validate_file_signature(b"# Heading", "notes.md")
        assert ok is True

    def test_markdown(self):
        ok, msg = validate_file_signature(b"# Heading", "notes.markdown")
        assert ok is True

    def test_txt(self):
        ok, msg = validate_file_signature(b"hello world", "readme.txt")
        assert ok is True

    def test_yaml(self):
        ok, msg = validate_file_signature(b"key: value", "config.yaml")
        assert ok is True

    def test_yml(self):
        ok, msg = validate_file_signature(b"key: value", "config.yml")
        assert ok is True

    def test_html(self):
        ok, _ = validate_file_signature(b"<html></html>", "page.html")
        assert ok is True

    def test_htm(self):
        ok, _ = validate_file_signature(b"<html></html>", "page.htm")
        assert ok is True

    def test_xml(self):
        ok, _ = validate_file_signature(b"<root/>", "data.xml")
        assert ok is True

    def test_log(self):
        ok, _ = validate_file_signature(b"2026-01-01 INFO msg", "app.log")
        assert ok is True

    def test_tsv(self):
        ok, _ = validate_file_signature(b"a\tb\n1\t2", "data.tsv")
        assert ok is True


# ---------------------------------------------------------------------------
# 9. JPEG checks
# ---------------------------------------------------------------------------
class TestJPEG:
    JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 12

    def test_detect(self):
        assert detect_file_type(self.JPEG) == "jpeg"

    def test_validate_jpg(self):
        ok, _ = validate_file_signature(self.JPEG, "p.jpg")
        assert ok is True

    def test_validate_jpeg(self):
        ok, _ = validate_file_signature(self.JPEG, "p.jpeg")
        assert ok is True

    def test_jpeg_named_png_rejected(self):
        ok, msg = validate_file_signature(self.JPEG, "p.png")
        assert ok is False
        assert "mismatch" in msg


# ---------------------------------------------------------------------------
# Additional: OLE, RTF, BMP, MP3, GIF
# ---------------------------------------------------------------------------
class TestOtherFormats:
    def test_ole_doc(self):
        ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 20
        assert detect_file_type(ole) == "ole"
        ok, _ = validate_file_signature(ole, "old.doc")
        assert ok is True

    def test_ole_xls(self):
        ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 20
        ok, _ = validate_file_signature(ole, "old.xls")
        assert ok is True

    def test_rtf(self):
        rtf = b"{\\rtf1 hello}"
        assert detect_file_type(rtf) == "rtf"
        ok, _ = validate_file_signature(rtf, "doc.rtf")
        assert ok is True

    def test_bmp(self):
        bmp = b"BM" + b"\x00" * 20
        assert detect_file_type(bmp) == "bmp"
        ok, _ = validate_file_signature(bmp, "img.bmp")
        assert ok is True

    def test_mp3_id3(self):
        mp3 = b"ID3" + b"\x00" * 10
        assert detect_file_type(mp3) == "mp3"
        ok, _ = validate_file_signature(mp3, "track.mp3")
        assert ok is True

    def test_mp3_sync(self):
        mp3 = b"\xff\xfb" + b"\x00" * 10
        assert detect_file_type(mp3) == "mp3"

    def test_gif87a(self):
        gif = b"GIF87a" + b"\x00" * 10
        assert detect_file_type(gif) == "gif"
        ok, _ = validate_file_signature(gif, "anim.gif")
        assert ok is True

    def test_gif89a(self):
        gif = b"GIF89a" + b"\x00" * 10
        assert detect_file_type(gif) == "gif"

    def test_unknown_extension(self):
        # Extension not in either table -> pass-through
        ok, msg = validate_file_signature(b"\x00\x01\x02", "file.xyz")
        assert ok is True
        assert "not subject" in msg

    def test_detect_none_for_random_bytes(self):
        assert detect_file_type(b"\x00\x01\x02\x03\x04") is None

    def test_detect_none_for_empty(self):
        assert detect_file_type(b"") is None

    def test_detect_none_for_non_bytes(self):
        assert detect_file_type(None) is None  # type: ignore[arg-type]
