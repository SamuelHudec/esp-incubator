import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from autolabel import select_images, detect, render_montage


class AutolabelTests(unittest.TestCase):
    def test_seeded_selection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(30):
                (root/f'{i}.jpg').touch()
            first,total=select_images(root,10,42)
            second,_=select_images(root,10,42)
            self.assertEqual(first,second)
            self.assertEqual(len(set(first)),10)
            self.assertEqual(total,30)
            self.assertEqual(len(select_images(root,100,42)[0]),30)

    def test_coordinate_mapping_and_preview(self):
        class Detector:
            def setInputSize(self,size):
                self.size=size
            def detect(self,image):
                return None,np.array([[64,32,128,64,0,0,0,0,0,0,0,0,0,0,.95]])
        image=np.zeros((200,400,3),np.uint8)
        detector=Detector()
        boxes,scores=detect(detector,image,640)
        self.assertEqual(detector.size,(640,320))
        np.testing.assert_allclose(boxes,[[.1,.1,.3,.3]])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'image.png';cv2.imwrite(str(path),image)
            output=Path(d)/'preview.jpg'
            render_montage([dict(source=str(path),boxes=boxes,scores=scores)],output)
            self.assertEqual(cv2.imread(str(output)).shape,(280,320,3))


if __name__=='__main__':
    unittest.main()
