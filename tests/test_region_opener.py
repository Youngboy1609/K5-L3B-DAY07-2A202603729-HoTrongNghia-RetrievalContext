import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ingest_bonus import make_region_opener


class FakeRenderedPage:
    width = 576
    height = 756

    def crop(self, bbox):
        self.bbox = bbox
        return self

    def to_image(self, resolution):
        self.resolution = resolution
        return self

    @property
    def original(self):
        return self

    def save(self, stream, format, optimize):
        stream.write(b"png")


class FakePdf:
    def __init__(self):
        self.pages = [FakeRenderedPage() for _ in range(49)]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RegionOpenerTests(unittest.TestCase):
    def test_text_chunk_resolves_to_full_page_visual_region(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"pdf")
            regions = root / "regions.jsonl"
            regions.write_text(json.dumps({
                "id": "wdr-p049-page-visual", "page": 49, "bbox": [0, 0, 576, 756],
                "crop": None, "modality": "page_visual", "rights_status": "reviewed_local_only",
            }) + "\n", encoding="utf-8")
            page = FakePdf()
            with patch("pdfplumber.open", return_value=page):
                opener = make_region_opener(pdf, regions, root / "crops",
                                            page_by_id={"wdr-p049-text-00": 49})
                result = opener("wdr-p049-text-00")

        self.assertEqual(result["id"], "wdr-p049-text-00")
        self.assertEqual(result["page"], 49)
        self.assertEqual(result["modality"], "page_visual")
        self.assertTrue(result["image_url"].startswith("data:image/png;base64,"))
        self.assertEqual(page.pages[48].resolution, 220)

    def test_page_scope_ignores_region_crop_and_renders_full_physical_page(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"pdf")
            regions = root / "regions.jsonl"
            regions.write_text(json.dumps({
                "id": "figure", "page": 3, "bbox": [10, 20, 100, 120],
                "crop": None, "modality": "figure", "rights_status": "reviewed_local_only",
            }) + "\n", encoding="utf-8")
            page = FakePdf()
            with patch("pdfplumber.open", return_value=page):
                opener = make_region_opener(pdf, regions, root / "crops", page_by_id={"figure": 3})
                result = opener("figure", scope="page")
        self.assertEqual(result["scope"], "page")
        self.assertEqual(result["physical_page"], 3)
        self.assertEqual(result["bbox"], [0, 0, 576.0, 756.0])


if __name__ == "__main__":
    unittest.main()
