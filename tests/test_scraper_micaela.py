import tempfile
import unittest
from pathlib import Path

from scraper_micaela import extract_products, scrape


class ExtractProductsTests(unittest.TestCase):
    def test_extracts_inline_name_and_price(self) -> None:
        html = """
        <html>
          <body>
            <div>Yerba Playadito $ 3.499</div>
            <div>Café molido ARS 8500</div>
          </body>
        </html>
        """

        self.assertEqual(
            extract_products(html),
            [
                {"name": "Yerba Playadito", "price": "$ 3.499"},
                {"name": "Café molido", "price": "ARS 8500"},
            ],
        )

    def test_reuses_previous_label_and_ignores_hidden_text(self) -> None:
        html = """
        <html>
          <head>
            <style>.price { color: red; }</style>
            <script>console.log('9999');</script>
          </head>
          <body>
            <h2>Leche entera</h2>
            <span>$1200</span>
          </body>
        </html>
        """

        self.assertEqual(
            extract_products(html),
            [{"name": "Leche entera", "price": "$1200"}],
        )

    def test_scrape_reads_local_file(self) -> None:
        html = "<p>Galletitas</p><p>MXN 42</p>"

        with tempfile.TemporaryDirectory() as tmp_dir:
            html_path = Path(tmp_dir) / "micaela.html"
            html_path.write_text(html, encoding="utf-8")

            self.assertEqual(
                scrape(str(html_path)),
                [{"name": "Galletitas", "price": "MXN 42"}],
            )


if __name__ == "__main__":
    unittest.main()
