"""Independent annotation, review and repeatable training-dataset composition."""
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
from create_dataset import create_dataset
from data import Faces


def collection(root,name,kind,count,start=1,groups=False):
    directory=root/name;directory.mkdir()
    images=root/(name+'-raw');images.mkdir();rows=[]
    for i in range(count):
        image=images/f'{i}.png';cv2.imwrite(str(image),np.full((12,16,3),start+i,np.uint8))
        row=dict(image=str(image),boxes=[[.1,.1,.8,.8]],scores=[.9],dataset_source=kind,review_status='reviewed')
        if kind=='real': row['group']=f'session-{i//2}' if groups else '__root__'
        rows.append(row)
    (directory/'labels.json').write_text(json.dumps(rows))
    (directory/'collection.json').write_text(json.dumps(dict(format='face-annotations-v1',kind=kind)))
    return directory


class WorkflowTests(unittest.TestCase):
    def build(self,*args,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()): return create_dataset(*args,**kwargs)

    def test_annotation_review_and_reuse_without_teacher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';raw.mkdir()
            for i in range(6): cv2.imwrite(str(raw/f'{i}.png'),np.full((12,16,3),i,np.uint8))
            (raw/'broken.png').write_text('bad image');out=root/'annotations'
            with patch('annotate_data.load_detector',return_value=(object(),{'detector':'mock'})) as loader, \
                 patch('annotate_data.detect',return_value=([],[])),contextlib.redirect_stdout(io.StringIO()):
                annotate_collection(raw,out)
            loader.assert_called_once();self.assertFalse((out/'dataset.json').exists())
            rows=json.loads((out/'labels.json').read_text())
            self.assertTrue(all('dataset_source' not in r for r in rows))
            self.assertNotIn('kind', json.loads((out/'collection.json').read_text()))
            self.assertFalse((out/'summary.json').exists())
            self.assertFalse((out/'errors.json').exists())
            self.assertEqual(len(rows),7);self.assertEqual(sum(r['review_status']=='error' for r in rows),1)
            with self.assertRaisesRegex(ValueError,'reviewed images'): self.build(out,[],root/'not-ready',count=5)
            self.assertFalse((root/'not-ready').exists())
            cv2.imwrite(str(raw/'broken.png'),np.full((12,16,3),10,np.uint8))
            Dataset(out).review_remaining();before=(out/'labels.json').read_bytes()
            with patch('annotate_data.load_detector',side_effect=AssertionError('Teacher must not run')):
                a=self.build(out,[],root/'a',count=5,test_count=1)
                b=self.build(out,[],root/'b',count=7,test_count=1)
            self.assertEqual(sum(len(a[s]) for s in ('train','val','test')),5)
            self.assertEqual(sum(len(b[s]) for s in ('train','val','test')),7)
            self.assertEqual((out/'labels.json').read_bytes(),before)
            self.assertEqual(len(Faces(root/'a/dataset.json','train')[0][3]),0)

    def test_standalone_collection_role_is_chosen_only_when_mixing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old_extra=collection(root,'wider','extra',6)
            before=(old_extra/'labels.json').read_bytes()
            preferred=self.build(old_extra,[],root/'preferred',count=5,test_count=1)
            supplemental=self.build(None,[old_extra],root/'supplemental',count=5,test_count=1)
            self.assertTrue(all(r['dataset_source']=='real' for s in ('train','val','test') for r in preferred[s]))
            self.assertTrue(all(r['dataset_source']=='extra' for s in ('train','val','test') for r in supplemental[s]))
            self.assertEqual((old_extra/'labels.json').read_bytes(),before)

    def test_multiple_sources_priority_pending_negatives_and_repeatability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);real=collection(root,'camera','real',6)
            a=collection(root,'wider','extra',10,start=30);b=collection(root,'other','extra',8,start=60)
            rows=json.loads((b/'labels.json').read_text());rows[0]['review_status']='pending';rows[0]['boxes']=[]
            rows[1]['boxes']=[];(b/'labels.json').write_text(json.dumps(rows))
            for count,expected_real,total in [(4,4,4),(6,6,6),(15,6,15),(100,6,23),(None,6,23)]:
                m=self.build(real,[a,b],root/f'out-{count}',count=count,test_count=1)
                all_rows=[r for s in ('train','val','test') for r in m[s]]
                self.assertEqual(len(all_rows),total)
                self.assertEqual(sum(r['dataset_source']=='real' for r in all_rows),expected_real)
            first=self.build(real,[a,b],root/'repeat-a',count=15,test_count=1)
            second=self.build(real,[b,a],root/'repeat-b',count=15,test_count=1)
            for s in ('train','val','test'):
                self.assertEqual([r['image_sha256'] for r in first[s]],[r['image_sha256'] for r in second[s]])
            with self.assertRaisesRegex(ValueError,'already exists'): self.build(real,[a],root/'repeat-a',count=8)

    def test_capture_groups_stay_in_one_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);real=collection(root,'camera','real',6,groups=True)
            extra=collection(root,'wider','extra',30,start=30)
            dataset=self.build(real,[extra],root/'dataset',count=12,test_count=2,split_mode='group')
            owners={}
            for split in ('train','val','test'):
                camera_rows=[r for r in dataset[split] if r['dataset_source']=='real']
                self.assertTrue(camera_rows)
                for row in camera_rows:
                    self.assertEqual(owners.setdefault(row['group'],split),split)

    def test_group_constraints_and_deduplication_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);real=collection(root,'camera','real',6)
            extra=collection(root,'wider','extra',6,start=1)
            with self.assertRaisesRegex(ValueError,'three selected real groups'):
                self.build(real,[extra],root/'group',count=6,split_mode='group')
            m=self.build(real,[extra],root/'dedup',count=12,test_count=1)
            self.assertEqual(sum(len(m[s]) for s in ('train','val','test')),6)
            rows=json.loads((extra/'labels.json').read_text());rows[0]['boxes']=[]
            (extra/'labels.json').write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError,'Conflicting reviewed annotations'):
                self.build(real,[extra],root/'conflict',count=6)
            self.assertFalse((root/'conflict').exists())

    def test_legacy_mixed_collection_preserves_old_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);real=collection(root,'camera','real',4)
            extra=collection(root,'wider','extra',8,start=30);mixed=root/'old';mixed.mkdir()
            rows=json.loads((real/'labels.json').read_text())+json.loads((extra/'labels.json').read_text())
            (mixed/'labels.json').write_text(json.dumps(rows));(mixed/'dataset.json').write_text('existing experiment')
            before=(mixed/'labels.json').read_bytes()
            m=self.build(mixed,[mixed],root/'new',count=10,test_count=1)
            self.assertEqual(sum(r['dataset_source']=='real' for s in ('train','val','test') for r in m[s]),4)
            self.assertEqual((mixed/'labels.json').read_bytes(),before)
            self.assertEqual((mixed/'dataset.json').read_text(),'existing experiment')


if __name__=='__main__': unittest.main()
