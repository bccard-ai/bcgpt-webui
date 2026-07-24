#!/usr/bin/env python3
"""A simple script that generates a QR code image from text.

Usage:
    python qr_generator.py "https://example.com"
    python qr_generator.py "안녕하세요" -o hello.png
"""

import argparse

import qrcode


def generate_qr(text: str, output: str = "qr.png") -> str:
    """Create a QR code from the given text, save it as an image, and return its path."""
    img = qrcode.make(text)
    img.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="텍스트로 QR 코드 이미지를 생성합니다."
    )
    parser.add_argument("text", help="QR 코드에 담을 텍스트 (URL, 문자열 등)")
    parser.add_argument(
        "-o", "--output", default="qr.png", help="저장할 이미지 경로 (기본값: qr.png)"
    )
    args = parser.parse_args()

    path = generate_qr(args.text, args.output)
    print(f"QR 코드를 저장했습니다: {path}")


if __name__ == "__main__":
    main()
