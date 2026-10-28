import unittest
from unittest.mock import Mock
import numpy as np
from ultralytics.engine.results import Results
from ai_vision.safety.class_specific_model import ClassSpecificModel
from ai_vision.safety.live_fire_smoke import detect_frame


class ClassSpecificModelTests(unittest.TestCase):
    def test_reversed_model_labels_select_only_the_owned_class(self):
        frame = np.zeros((40, 40, 3), np.uint8)
        fire = Mock(names={0:'SMOKE',1:'FIRE'})
        smoke = Mock(names={0:'FIRE',1:'SMOKE'})
        boxes = np.array([[1,1,20,20,.8,1],[2,2,25,25,.9,0]],np.float32)
        for model in (fire,smoke):
            model.predict.return_value = [Results(frame,'',model.names,boxes=boxes)]
        detections, _ = detect_frame(ClassSpecificModel(fire,smoke),frame)
        self.assertEqual([row['class_name'] for row in detections],['FIRE','SMOKE'])
        for model in (fire,smoke):
            self.assertEqual(model.predict.call_args.kwargs['classes'],[1])

    def test_missing_class_and_failed_inference_are_not_hidden(self):
        with self.assertRaises(ValueError):
            ClassSpecificModel(Mock(names={0:'SMOKE'}),Mock(names={0:'SMOKE'}))
        a=Mock(names={0:'FIRE'});b=Mock(names={0:'SMOKE'})
        a.predict.return_value=[]
        with self.assertRaises(RuntimeError):
            ClassSpecificModel(a,b).predict(source=np.zeros((40,40,3),np.uint8))
