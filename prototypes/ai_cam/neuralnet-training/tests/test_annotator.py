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
            self.assertEqual(len(dataset.indices), 2)
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

    def test_extra_misses_are_recovered_and_only_confirmed_negatives_exported(self):
        from autolabel import export_dataset
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = []
            for i in range(5):
                cv2.imwrite(str(root/f'{i}.png'), np.full((12,16,3),i,np.uint8))
                rows.append(dict(image=f'{i}.png', boxes=[[.1,.1,.9,.9]] if i<3 else [],
                                 dataset_source='extra'))
            (root/'labels.json').write_text(json.dumps(rows[:3]))
            (root/'review_no_faces.json').write_text(json.dumps(rows[3:]+[rows[0]]))
            dataset = Dataset(root)
            self.assertEqual(len(dataset.indices),5)
            dataset.save(3, [])
            self.assertEqual(Dataset(root).row(3)['review_status'], 'reviewed')
            export_dataset(root/'labels.json',root/'dataset.json',test_count=1)
            manifest=json.loads((root/'dataset.json').read_text())
            exported=[r for split in ('train','val','test') for r in manifest[split]]
            self.assertEqual(len(exported),4)
            negative=next(r for r in exported if r['image']=='3.png')
            self.assertEqual(negative['boxes'],[])
            self.assertEqual(negative['annotation_source'],'human-reviewed')
            self.assertNotIn('4.png',[r['image'] for r in exported])

    def test_batch_review_is_atomic_and_preserves_existing_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cv2.imwrite(str(root/'ok.png'),np.zeros((12,16,3),np.uint8))
            rows=[dict(image='ok.png',boxes=[[.1,.1,.8,.8]],scores=[.9],dataset_source='real'),
                  dict(image='missing.png',boxes=[],dataset_source='extra')]
            path=root/'labels.json';path.write_text(json.dumps(rows))
            dataset=Dataset(root);original=path.read_bytes()
            with self.assertRaises(ValueError): dataset.review_remaining()
            self.assertEqual(path.read_bytes(),original)
            self.assertNotIn('review_status',dataset.row(0))
            cv2.imwrite(str(root/'missing.png'),np.zeros((12,16,3),np.uint8))
            self.assertEqual(dataset.review_remaining(),2)
            saved=json.loads(path.read_text())
            self.assertTrue(all(r['review_status']=='reviewed' for r in saved))
            self.assertEqual(saved[0]['boxes'],rows[0]['boxes'])
            self.assertEqual(saved[0]['scores'],rows[0]['scores'])
            self.assertEqual(saved[1]['boxes'],[])
            self.assertEqual(dataset.review_remaining(),0)
