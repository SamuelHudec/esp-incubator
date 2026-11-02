"""Real-first selection, review gate, and capture-group isolation."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from autolabel import select_mixed_images, export_dataset, finalize_run, main
from data import Faces


def image(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.full((12,16,3),value,np.uint8))


class MixedAutolabelTests(unittest.TestCase):
    def test_real_first_sampling_and_shortage(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); real=root/'real'; synthetic=root/'synthetic'
            for i in range(6): image(real/f'session-{i//2}/{i}.png',i)
            for i in range(10): image(synthetic/f'{i}.png',i+20)
            for count, expected in [(10,(6,4)),(6,(6,0)),(3,(3,0)),(30,(6,10)),(None,(6,10))]:
                rows,counts=select_mixed_images(real,synthetic,count,42)
                self.assertEqual((counts['real']['selected'],counts['synthetic']['selected']),expected)
                self.assertEqual(len({r['source'] for r in rows}),sum(expected))
                self.assertEqual(rows,select_mixed_images(real,synthetic,count,42)[0])
            self.assertNotEqual(select_mixed_images(real,synthetic,3,42)[0],
                                select_mixed_images(real,synthetic,3,43)[0])
            with self.assertRaises(ValueError): select_mixed_images(real,real,None,42)
            with self.assertRaises(ValueError): select_mixed_images(root,real,None,42)

    def test_review_group_split_and_negative_loading(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); records=[]
            for i in range(12):
                image(root/f'{i}.png',i)
                records.append(dict(image=f'{i}.png',boxes=[],scores=[],dataset_source='real',
                                    group=f'session-{i//3}',review_status='pending'))
            labels=root/'labels.json';labels.write_text(json.dumps(records))
            with self.assertRaisesRegex(ValueError,'Review every real'):
                export_dataset(labels,root/'dataset.json')
            self.assertFalse((root/'dataset.json').exists())
            for row in records: row['review_status']='reviewed'
            labels.write_text(json.dumps(records))
            export_dataset(labels,root/'dataset.json',test_count=2)
            dataset=json.loads((root/'dataset.json').read_text()); groups={}
            for split in ('train','val','test'):
                self.assertTrue(dataset[split])
                for row in dataset[split]:
                    self.assertNotIn(row['group'],{g for g,s in groups.items() if s!=split})
                    groups[row['group']]=split
                    self.assertEqual(row['annotation_source'],'human-reviewed')
                self.assertEqual(len(Faces(root/'dataset.json',split)[0][3]),0)
            self.assertGreater(len(dataset['test']),2)
            export_dataset(labels,root/'repeat.json',test_count=2)
            self.assertEqual(dataset,json.loads((root/'repeat.json').read_text()))
            for row in records: row['group']='one-burst'
            labels.write_text(json.dumps(records))
            with self.assertRaisesRegex(ValueError,'three selected real capture groups'):
                export_dataset(labels,root/'bad.json')
            self.assertFalse((root/'bad.json').exists())

    def test_duplicate_contents_cannot_leak_across_groups(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);records=[]
            for i in range(3):
                image(root/f'{i}.png',0)
                records.append(dict(image=f'{i}.png',boxes=[],dataset_source='real',
                                    group=str(i),review_status='reviewed'))
            labels=root/'labels.json';labels.write_text(json.dumps(records))
            with self.assertRaisesRegex(ValueError,'Identical image contents cross splits'):
                export_dataset(labels,root/'dataset.json')
            self.assertFalse((root/'dataset.json').exists())

    def test_mixed_cli_keeps_misses_and_errors_then_finalizes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);real=root/'real';synthetic=root/'synthetic';out=root/'run'
            for i in range(6): image(real/f'session-{i//2}/{i}.png',i+1)
            broken=real/'session-0/broken.png';broken.write_text('not an image')
            for i in range(8): image(synthetic/f'{i}.png',i+30)
            model=root/'teacher.onnx';model.write_bytes(b'mocked teacher')
            argv=['autolabel.py','--real-input',str(real),'--synthetic-input',str(synthetic),
                  '--count','10','--out',str(out),'--test-count','2']
            def fake_detect(detector, pixels, size):
                return ([],[]) if pixels[0,0,0]<10 else ([[.1,.1,.8,.8]],[.9])
            stream=io.StringIO()
            with patch('sys.argv',argv), patch('autolabel.download_model',return_value=model), \
                 patch('autolabel.cv2.FaceDetectorYN.create',return_value=object()), \
                 patch('autolabel.detect',side_effect=fake_detect), contextlib.redirect_stdout(stream):
                main()
            self.assertIn('real: selected 7 / available 7',stream.getvalue())
            self.assertIn('synthetic: selected 3 / available 8',stream.getvalue())
            self.assertFalse((out/'dataset.json').exists())
            labels=json.loads((out/'labels.json').read_text())
            self.assertEqual(sum(r['dataset_source']=='real' for r in labels),7)
            self.assertEqual(sum(r.get('review_status')=='unreadable' for r in labels),1)
            with self.assertRaisesRegex(ValueError,'Review every real'):
                finalize_run(out)
            for row in labels:
                if row['dataset_source']=='real': row['review_status']='reviewed'
            labels[0]['boxes']=[[.2,.2,.7,.7]]  # Correct a teacher miss; old scores stay empty.
            (out/'labels.json').write_text(json.dumps(labels))
            with self.assertRaisesRegex(ValueError,'Unreadable real'):
                finalize_run(out)
            image(broken,19)
            removed=labels.pop(0);(out/'labels.json').write_text(json.dumps(labels))
            with self.assertRaisesRegex(ValueError,'retain every selected real'):
                finalize_run(out)
            labels.append(removed);(out/'labels.json').write_text(json.dumps(labels))
            with contextlib.redirect_stdout(io.StringIO()): finalize_run(out)
            dataset=json.loads((out/'dataset.json').read_text())
            self.assertEqual(sum(len(dataset[k]) for k in ('train','val','test')),10)
            real_rows=[r for k in ('train','val','test') for r in dataset[k]
                       if r['dataset_source']=='real']
            self.assertEqual(sum(bool(r['boxes']) for r in real_rows),1)
            self.assertEqual(next(r['scores'] for r in real_rows if r['boxes']),[1.0])
            self.assertTrue(json.loads((out/'summary.json').read_text())['finalized'])
            with self.assertRaises(FileExistsError): finalize_run(out)

    def test_empty_real_pool_and_flat_capture_group(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);real=root/'real';real.mkdir();synthetic=root/'synthetic'
            for i in range(4): image(synthetic/f'{i}.png',i)
            rows,counts=select_mixed_images(real,synthetic,3,42)
            self.assertEqual(counts['real']['selected'],0)
            self.assertTrue(all(r['dataset_source']=='synthetic' for r in rows))
            for i in range(3): image(real/f'{i}.png',i+20)
            rows,_=select_mixed_images(real,synthetic,3,42)
            self.assertEqual({r['group'] for r in rows},{'__root__'})


if __name__=='__main__': unittest.main()
