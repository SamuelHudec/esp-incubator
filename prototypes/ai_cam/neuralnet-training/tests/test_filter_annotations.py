"""Size filtering preserves review work and uses the largest face only."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest

from filter_annotations import filter_annotations, parse_ratio


class FilterTests(unittest.TestCase):
    def test_largest_face_threshold_and_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root/'source'
            source.mkdir()
            boxes = [
                [[0, 0, 1/3, 1/10]],
                [[0, 0, 0.1, 0.1]],
                [[0, 0, 0.01, 0.01], [0, 0, 0.5, 0.5]],
                [[0, 0, 0.15, 0.15], [0.5, 0.5, 0.65, 0.65]],
                [], [],
            ]
            rows = []
            for i, face_boxes in enumerate(boxes):
                (source/f'{i}.jpg').write_bytes(b'fixture')
                rows.append(dict(image=f'{i}.jpg', boxes=face_boxes,
                                 review_status='pending' if i == 5 else 'reviewed', group='session'))
            original = json.dumps(rows)
            (source/'labels.json').write_text(original)
            (source/'collection.json').write_text(json.dumps(dict(format='face-annotations-v1')))
            out = root/'filtered'
            kept, report = filter_annotations(source, out)
            self.assertEqual(report['removed_images'], 2)
            self.assertEqual(report['without_boxes_kept'], 2)
            for actual, index in zip(kept, [0, 2, 4, 5]):
                self.assertEqual((out/actual['image']).resolve(), source/f'{index}.jpg')
                self.assertEqual({k:v for k,v in actual.items() if k != 'image'},
                                 {k:v for k,v in rows[index].items() if k != 'image'})
            self.assertEqual((source/'labels.json').read_text(), original)
            self.assertEqual(json.loads((out/'collection.json').read_text())['filtered_from'], str(source))
            with self.assertRaises(ValueError):
                filter_annotations(source, out)
            larger, _ = filter_annotations(source, root/'larger', min_face_ratio=0.005)
            self.assertEqual(len(larger), 6)
            nonempty, report = filter_annotations(source, root/'nonempty', exclude_empty=True)
            self.assertEqual(len(nonempty), 2)
            self.assertTrue(all(row['boxes'] for row in nonempty))
            self.assertEqual(report['without_boxes_kept'], 0)
            self.assertEqual(report['without_boxes_removed'], 2)
            self.assertEqual(report['removed_images'], 4)
            self.assertTrue(report['exclude_empty'])

    def test_fraction_and_decimal_thresholds(self):
        self.assertEqual(parse_ratio('1/30'), 1/30)
        self.assertEqual(parse_ratio('0.05'), 0.05)
        for value in ['1/0', 'nan', 'inf', '-0.1', '2', 'abc']:
            with self.assertRaises(argparse.ArgumentTypeError):
                parse_ratio(value)

    def test_validation_and_legacy_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'source'
            source.mkdir()
            (source/'labels.json').write_text('[]')
            for threshold in [-1, 1.1, float('nan'), float('inf')]:
                with self.assertRaises(ValueError):
                    filter_annotations(source, Path(tmp)/'invalid', threshold)
            with self.assertRaises(ValueError):
                filter_annotations(source, source/'nested')
            out = Path(tmp)/'legacy'
            filter_annotations(source, out)
            self.assertFalse((out/'collection.json').exists())


if __name__ == '__main__':
    unittest.main()
