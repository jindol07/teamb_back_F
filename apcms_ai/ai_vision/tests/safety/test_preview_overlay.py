import json,tempfile,unittest
from pathlib import Path
import numpy as np
from ai_vision.safety.preview_overlay import publish_overlay,draw_overlay


class PreviewOverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'overlay.json'
        self.frame=np.zeros((100,100,3),np.uint8)
        publish_overlay(self.path,self.frame,[dict(class_name='SMOKE',confidence=.8,bbox=[10,10,50,50])],
                        role='gate',camera_id='GATE_A',run_id='current',captured_monotonic=10)

    def draw(self,**kwargs):
        args=dict(path=self.path,role='gate',camera_id='GATE_A',run_id='current',clock=lambda:11)
        args.update(kwargs);return draw_overlay(self.frame,**args)

    def test_valid_overlay_draws_without_changing_source(self):
        result=self.draw();self.assertGreater(result.sum(),0);self.assertEqual(self.frame.sum(),0)

    def test_stale_future_wrong_run_and_other_camera_are_hidden(self):
        for kwargs in ({'clock':lambda:13},{'clock':lambda:9},{'run_id':'old'},{'role':'parking'},{'camera_id':'OTHER'}):
            with self.subTest(kwargs=kwargs):self.assertIs(self.draw(**kwargs),self.frame)

    def test_invalid_geometry_and_shape_are_hidden(self):
        data=json.loads(self.path.read_text())
        data['detections'][0]['bbox']=[0,0,1000,1000]
        self.path.write_text(json.dumps(data))
        self.assertIs(self.draw(),self.frame)
        data['shape']=[200,100,3];self.path.write_text(json.dumps(data))
        self.assertIs(self.draw(),self.frame)

    def test_missing_file_never_interrupts_parking_preview(self):
        self.path.unlink();self.assertIs(self.draw(),self.frame)

    def test_non_object_json_never_interrupts_preview(self):
        self.path.write_text('[]')
        self.assertIs(self.draw(),self.frame)
