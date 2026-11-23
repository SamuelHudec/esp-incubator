"""Appending camera captures must preserve review work and survive interruptions."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from annotate_data import annotate_collection
from annotator.annotate import Dataset


def photo(path,value=1):
    cv2.imwrite(str(path),np.full((12,16,3),value,np.uint8))


class IncrementalTests(unittest.TestCase):
    def run_annotation(self,raw,out,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()): return annotate_collection(raw,out,**kwargs)

    def test_append_preserves_reviewed_boxes_and_skips_empty_successes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';raw.mkdir();out=root/'out'
            photo(raw/'a.png');photo(raw/'b.png',2)
            with patch('annotate_data.load_detector',return_value=(object(),{})),patch('annotate_data.detect',return_value=([],[])) as detector:
                self.run_annotation(raw,out);self.assertEqual(detector.call_count,2)
            Dataset(out).save(0,[[.1,.1,.8,.8]])
            before=json.loads((out/'labels.json').read_text())
            photo(raw/'c.png',3)
            with patch('annotate_data.load_detector',return_value=(object(),{})),patch('annotate_data.detect',return_value=([],[])) as detector:
                rows=self.run_annotation(raw,out);self.assertEqual(detector.call_count,1)
            self.assertEqual(rows[:2],before)
            self.assertEqual(rows[2]['review_status'],'pending')
            original=(out/'labels.json').read_bytes()
            with patch('annotate_data.load_detector',side_effect=AssertionError('No model load for a no-op')):
                self.run_annotation(raw,out)
            self.assertEqual((out/'labels.json').read_bytes(),original)

    def test_retry_errors_and_resume_interrupted_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';raw.mkdir();out=root/'out'
            for i in range(3): photo(raw/f'{i}.png',i)
            with patch('annotate_data.load_detector',return_value=(object(),{})),patch('annotate_data.detect',side_effect=[([],[]),KeyboardInterrupt()]):
                with self.assertRaises(KeyboardInterrupt): self.run_annotation(raw,out)
            self.assertEqual(len(json.loads((out/'labels.json').read_text())),1)
            with patch('annotate_data.load_detector',return_value=(object(),{})),patch('annotate_data.detect',return_value=([],[])) as detector:
                self.run_annotation(raw,out);self.assertEqual(detector.call_count,2)
            (raw/'broken.png').write_text('bad')
            with patch('annotate_data.load_detector',return_value=(object(),{})):
                rows=self.run_annotation(raw,out)
            self.assertEqual(rows[-1]['review_status'],'error')
            photo(raw/'broken.png',7)
            with patch('annotate_data.load_detector',return_value=(object(),{})),patch('annotate_data.detect',return_value=([],[])) as detector:
                rows=self.run_annotation(raw,out);self.assertEqual(detector.call_count,1)
            self.assertEqual(rows[-1]['review_status'],'pending')

    def test_review_of_repaired_error_updates_content_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';raw.mkdir();out=root/'out'
            (raw/'broken.png').write_text('bad')
            with patch('annotate_data.load_detector',return_value=(object(),{})):
                self.run_annotation(raw,out)
            photo(raw/'broken.png')
            Dataset(out).save(0,[])
            before=(out/'labels.json').read_bytes()
            with patch('annotate_data.load_detector',side_effect=AssertionError('Reviewed repairs are complete')):
                self.run_annotation(raw,out)
            self.assertEqual((out/'labels.json').read_bytes(),before)

    def test_crash_journal_recovery_preserves_editor_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';raw.mkdir();out=root/'out';photo(raw/'a.png')
            with patch('annotate_data.load_detector',return_value=(object(),{})),patch('annotate_data.detect',return_value=([],[])):
                self.run_annotation(raw,out)
            photo(raw/'b.png',2)
            def during_detection(*args):
                Dataset(out).save(0,[[.2,.2,.7,.7]])
                return [],[]
            with patch('annotate_data.load_detector',return_value=(object(),{})),patch('annotate_data.detect',side_effect=during_detection):
                with self.assertRaisesRegex(ValueError,'changed in the editor'):
                    self.run_annotation(raw,out)
            with (out/'detections.jsonl').open('ab') as log: log.write(b'{"image":')
            with patch('annotate_data.load_detector',side_effect=AssertionError('Recover journal without rerunning teacher')):
                rows=self.run_annotation(raw,out)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['boxes'],[[.2,.2,.7,.7]])
            self.assertEqual(rows[0]['review_status'],'reviewed')

    def test_input_settings_and_replaced_completed_images_are_not_silently_mixed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';raw.mkdir();out=root/'out';photo(raw/'a.png')
            with patch('annotate_data.load_detector',return_value=(object(),{})),patch('annotate_data.detect',return_value=([],[])):
                self.run_annotation(raw,out)
            before=(out/'labels.json').read_bytes()
            other=root/'other';other.mkdir();photo(other/'a.png')
            with self.assertRaisesRegex(ValueError,'different input'): self.run_annotation(other,out)
            with self.assertRaisesRegex(ValueError,'same detector'): self.run_annotation(raw,out,threshold=.6)
            photo(raw/'a.png',9)
            with self.assertRaisesRegex(ValueError,'contents changed'): self.run_annotation(raw,out)
            self.assertEqual((out/'labels.json').read_bytes(),before)


if __name__=='__main__': unittest.main()
