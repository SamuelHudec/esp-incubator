"""Imported boxes must remain pending until human review."""
import json
from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np
from import_coco import import_coco
from annotator.annotate import Dataset
from create_dataset import read_collection

class CocoTests(unittest.TestCase):
    def test_import_review_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve(); raw=root/'raw'; out=root/'out'
            for split in ('train','valid','test'):
                folder=raw/split; folder.mkdir(parents=True)
                for name in ('face','empty'):
                    cv2.imwrite(str(folder/f'{name}.png'),np.zeros((100,200,3),np.uint8))
                data=dict(images=[dict(id=i,file_name=f'{name}.png',width=200,height=100) for i,name in enumerate(('face','empty'))],
                          categories=[dict(id=1,name='Face'),dict(id=2,name='hand')],
                          annotations=[dict(image_id=0,category_id=1,bbox=[20,10,40,30]),
                                       dict(image_id=0,category_id=1,bbox=[100,50,100,50]),
                                       dict(image_id=1,category_id=2,bbox=[0,0,10,10])])
                (folder/'_annotations.coco.json').write_text(json.dumps(data))
            before={p:p.read_bytes() for p in raw.rglob('*') if p.is_file()}
            rows=import_coco(raw,out)
            self.assertEqual(len(rows),6)
            self.assertEqual(len({r['image'] for r in rows}),6)
            self.assertTrue(all(r['review_status']=='pending' for r in rows))
            self.assertEqual(rows[0]['boxes'],[[.1,.1,.3,.4],[.5,.5,1.,1.]])
            self.assertEqual(rows[1]['boxes'],[])
            self.assertEqual(read_collection(out,'extra')[0],[])
            editor=Dataset(out); editor.save(0,rows[0]['boxes']); editor.save(1,[])
            self.assertEqual(len(read_collection(out,'extra')[0]),2)
            self.assertTrue(all(p.read_bytes()==content for p,content in before.items()))
            with self.assertRaises(ValueError): import_coco(raw,out)
            path=raw/'train/_annotations.coco.json'
            for mutation in ('bounds','dimensions','reference','missing','category'):
                modified=json.loads(json.dumps(data))
                if mutation=='bounds': modified['annotations'][0]['bbox']=[190,0,20,10]
                if mutation=='dimensions': modified['images'][0]['width']=201
                if mutation=='reference': modified['annotations'][0]['image_id']=999
                if mutation=='missing': modified['images'][0]['file_name']='missing.png'
                if mutation=='category': modified['categories'][0]['name']='person'
                path.write_text(json.dumps(modified))
                with self.assertRaises(ValueError): import_coco(path,root/mutation)
                self.assertFalse((root/mutation).exists())
            path.write_text(json.dumps(data))
            hands=import_coco(path,root/'hands',category='hand')
            self.assertEqual(hands[1]['boxes'],[[0.,0.,.05,.1]])
