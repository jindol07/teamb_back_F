import json,tempfile,unittest
from pathlib import Path
from ai_vision.safety.region_review_manifest import load_regions
from ai_vision.safety.model_review_manifest import file_sha256


class RegionManifestTests(unittest.TestCase):
    def test_changed_original_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);image=root/'image.png';image.write_bytes(b'original')
            case=dict(id='case',path=str(image),sha256=file_sha256(image),positives=[],negatives=[])
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps(dict(purpose='manual_smoke_region_diagnostic',cases=[case])),encoding='utf-8')
            self.assertEqual(len(load_regions(manifest)),1)
            image.write_bytes(b'changed')
            with self.assertRaises(ValueError):load_regions(manifest)
