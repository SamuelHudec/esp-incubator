import json
from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np
from autolabel import export_dataset
from data import Faces


class DatasetManifestTests(unittest.TestCase):
    def test_split_paths_and_repeatability(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            records = []
            for i in range(10):
                cv2.imwrite(str(root/f'{i}.png'), np.zeros((96,128,3),np.uint8))
                records.append(dict(image=f'{i}.png',boxes=[[.2,.2,.6,.6]]))
            labels=root/'labels.json'; labels.write_text(json.dumps(records))
            output=root/'nested/dataset.json'
            self.assertEqual(export_dataset(labels,output,test_count=2), (6,2,2))
            train=Faces(output,split='train');val=Faces(output,split='val')
            self.assertFalse(train.image_paths() & val.image_paths())
            test=Faces(output,split='test')
            self.assertFalse(test.image_paths() & (train.image_paths() | val.image_paths()))
            self.assertEqual(len(train.image_paths() | val.image_paths() | test.image_paths()),10)
            self.assertEqual(tuple(train[0][0].shape),(1,96,128))
            other=root/'nested/repeat.json';export_dataset(labels,other,test_count=2)
            self.assertEqual(json.loads(output.read_text()),json.loads(other.read_text()))
            with self.assertRaises(FileExistsError):
                export_dataset(labels,output)

    def test_insufficient_labels(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'labels.json';p.write_text('[]')
            with self.assertRaises(ValueError):
                export_dataset(p,Path(d)/'dataset.json')
