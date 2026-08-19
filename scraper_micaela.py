from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PRICE_PATTERN = re.compile(
    r"(?:[$€£]\s*\d[\d.,]*|\d[\d.,]*\s*(?:[$€£]|USD|ARS|MXN)|(?:USD|ARS|MXN)\s*\d[\d.,]*)"
)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._hidden_tag: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._hidden_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == self._hidden_tag:
            self._hidden_tag = None

    def handle_data(self, data: str) -> None:
        if self._hidden_tag is not None:
            return

        text = " ".join(data.split())
        if text:
            self._chunks.append(text)

    @property
    def chunks(self) -> list[str]:
        return self._chunks


def fetch_html(url: str, timeout: int = 10) -> str:
    request = Request(url, headers={"User-Agent": "scraper-micaela/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_products(html: str) -> list[dict[str, str]]:
    parser = _VisibleTextParser()
    parser.feed(html)
    return _products_from_chunks(parser.chunks)


def scrape(source: str) -> list[dict[str, str]]:
    parsed_source = urlparse(source)
    if parsed_source.scheme in {"http", "https"}:
        html = fetch_html(source)
    else:
        html = Path(source).read_text(encoding="utf-8")
    return extract_products(html)


def _products_from_chunks(chunks: Iterable[str]) -> list[dict[str, str]]:
    products: list[dict[str, str]] = []
    current_name: str | None = None

    for chunk in chunks:
        matches = list(PRICE_PATTERN.finditer(chunk))
        if not matches:
            current_name = chunk
            continue

        inline_name = PRICE_PATTERN.sub("", chunk)
        inline_name = inline_name.strip(" -:\t")
        name = inline_name or current_name or "Sin nombre"

        for match in matches:
            products.append({"name": name, "price": _normalize_price(match.group(0))})

        current_name = name

    return products


def _normalize_price(price: str) -> str:
    return " ".join(price.split())


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper de precios para Micaela.")
    parser.add_argument("source", help="URL HTTP/HTTPS o ruta a un archivo HTML local.")
    args = parser.parse_args()
    print(json.dumps(scrape(args.source), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
