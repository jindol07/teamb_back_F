import tempfile
import unittest
from pathlib import Path
from ai_vision.safety.run_class_specific_shared import parse_config


class ClassSpecificSharedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.model=self.root/'model.pt';self.model.write_bytes(b'model')
        self.args=['--shared-run-dir',str(self.root),'--shared-role','gate','--shared-camera-id','GATE_A',
                   '--fire-model',str(self.model),'--smoke-model',str(self.model),'--output',str(self.root/'out')]

    def test_shared_only_config_has_no_video_or_production_send(self):
        args,config=parse_config(self.args+['--show'])
        self.assertEqual(config.shared_camera_id,'GATE_A')
        self.assertIsNone(config.video_path)
        self.assertFalse(config.production_camera)
        self.assertFalse(config.publish_alert_session)
        self.assertTrue(config.show)
        self.assertFalse(args.output.exists())

    def test_unbounded_and_excessive_durations_are_rejected(self):
        for seconds in ('0','-1','301','nan'):
            with self.subTest(seconds=seconds),self.assertRaises(ValueError):
                parse_config(self.args+['--max-seconds',seconds])

    def test_existing_output_is_preserved(self):
        (self.root/'out').mkdir()
        with self.assertRaises(FileExistsError):parse_config(self.args)
