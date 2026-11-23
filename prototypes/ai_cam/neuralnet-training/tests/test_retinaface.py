"""Check RetinaFace decoding and normalization independently of downloaded weights."""
import unittest
import numpy as np
from utils.retinaface import RetinaFace, priors


class FakeNet:
    def __init__(self, positive):
        self.positive = positive

    def setInput(self, blob):
        self.height, self.width = blob.shape[2:]

    def getUnconnectedOutLayersNames(self):
        return ['loc', 'conf', 'landmarks']

    def forward(self, names):
        count = len(priors(self.width,self.height))
        loc = np.zeros((1,count,4),np.float32)
        conf = np.zeros((1,count,2),np.float32)
        if self.positive:
            conf[0,0,1] = .95
        return [loc,conf,np.zeros((1,count,10),np.float32)]


class RetinaFaceTests(unittest.TestCase):
    def test_padding_is_removed_from_normalized_coordinates(self):
        detector = RetinaFace.__new__(RetinaFace)
        detector.threshold = .8
        detector.net = FakeNet(True)
        for height,width in ((100,200),(200,100)):
            boxes,scores=detector.predict(np.zeros((height,width,3),np.uint8),640)
            nw,nh=width*3.2,height*3.2
            # First prior has center (4,4), size 16: clipped pixel bounds (0,0,12,12).
            np.testing.assert_allclose(boxes,[[0,0,12/nw,12/nh]],atol=1e-6)
            self.assertAlmostEqual(scores[0],.95,places=6)

    def test_empty_predictions(self):
        detector=RetinaFace.__new__(RetinaFace)
        detector.threshold=.8
        detector.net=FakeNet(False)
        self.assertEqual(detector.predict(np.zeros((100,200,3),np.uint8),640),([],[]))
