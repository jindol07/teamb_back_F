import unittest
from ai_vision.safety.region_review import evaluate_regions


class RegionReviewTests(unittest.TestCase):
    def detection(self,box):return dict(class_name='SMOKE',confidence=.8,bbox=box)
    def test_hand_box_does_not_satisfy_visible_smoke(self):
        result=evaluate_regions([self.detection([10,0,30,20])],[[10,40,40,70]],[[0,0,40,30]])
        self.assertEqual(result['missing_positive_regions'],1)
        self.assertEqual(len(result['negative_region_detections']),1)
    def test_one_detection_cannot_match_two_positive_regions(self):
        result=evaluate_regions([self.detection([0,0,20,20])],[[0,0,20,20],[0,0,20,20]],[])
        self.assertEqual(result['matched_positive_regions'],1)
        self.assertEqual(result['missing_positive_regions'],1)
    def test_bad_boxes_are_rejected(self):
        with self.assertRaises(ValueError):evaluate_regions([],[[1,1,0,0]],[])
