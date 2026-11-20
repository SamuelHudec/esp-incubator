"""Annotation persistence must preserve other records and reject unsafe saves."""
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
from annotator.annotate import Dataset


class AnnotatorTests(unittest.TestCase):
    def test_review_preserves_sources_and_rejects_external_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cv2.imwrite(str(root/'photo.png'), np.zeros((12,16,3), np.uint8))
            rows = [dict(image='photo.png', boxes=[[.1,.1,.9,.9]], scores=[.8],
                         dataset_source='real', group='session', review_status='pending'),
                    dict(image='photo.png', boxes=[], dataset_source='synthetic')]
            labels = root/'labels.json'
            labels.write_text(json.dumps(rows))
            original = labels.read_bytes()
            dataset = Dataset(root)
            self.assertEqual(len(dataset.indices), 1)
            dataset.save(0, [])
            saved = json.loads(labels.read_text())
            self.assertEqual(saved[0]['review_status'], 'reviewed')
            self.assertEqual(saved[0]['boxes'], [])
            self.assertEqual(saved[0]['group'], 'session')
            self.assertEqual(saved[1], rows[1])
            self.assertEqual((root/'labels.before-review.json').read_bytes(), original)
            dataset.save(0, [[.2,.2,.8,.8]])
            self.assertEqual(json.loads(labels.read_text())[0]['scores'], [1.0])
            before = labels.read_bytes()
            for boxes in ([[0,0,0,1]], [[0,0,2,1]], [[0,0,float('nan'),1]]):
                with self.assertRaises(ValueError): dataset.save(0, boxes)
                self.assertEqual(labels.read_bytes(), before)
            labels.write_text('[]')
            with self.assertRaisesRegex(ValueError, 'changed outside'): dataset.save(0, [])
            self.assertEqual(labels.read_text(), '[]')

    def test_unreadable_image_cannot_be_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            labels = root/'labels.json'
            labels.write_text(json.dumps([dict(image='missing.png', boxes=[], dataset_source='real')]))
            dataset = Dataset(root)
            before = labels.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Cannot read'): dataset.save(0, [])
            self.assertEqual(labels.read_bytes(), before)
