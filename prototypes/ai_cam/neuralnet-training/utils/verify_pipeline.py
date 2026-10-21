"""Validate portable C preprocessing, integer graph and NMS against Python."""
import argparse
import ctypes as ct
import json
from pathlib import Path
import subprocess
import tempfile
import cv2
import numpy as np
from data import Faces
from model import preprocess, decode
from quantize import input_int8

class Box(ct.Structure):
    _fields_=[(name,ct.c_float) for name in ['x1','y1','x2','y2','score']]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',required=True)
    p.add_argument('--data',required=True)
    args=p.parse_args()
    out=Path(args.export).resolve();src=Path(__file__).resolve().parents[2]/'firmware'/'neuralnet'
    # NumPy fixtures are produced by quantize.py from the selected model.
    with tempfile.TemporaryDirectory() as d:
        d=Path(d)
        wrapper=d/'wrapper.c'
        wrapper.write_text('''#include "nn_model.h"
#include "nn_pipeline.h"
void run(int8_t *a,int8_t *b,int8_t *output) {
 int8_t *head=nn_run(nn_layers,NN_LAYER_COUNT,a,b,0);
 for(int i=0;i<960;i++) output[i]=head[i];
}
const float *scales(void) {return nn_output_scales;}
''')
        libpath=d/'pipeline.so'
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
                        '-I'+str(out),'-I'+str(src),str(wrapper),str(src/'nn_int8.c'),
                        str(src/'nn_pipeline.c'),'-lm','-o',str(libpath)],check=True)
        lib=ct.CDLL(str(libpath))
        array=np.ctypeslib.ndpointer(flags='C_CONTIGUOUS')
        lib.nn_preprocess_bgr.argtypes=[array,ct.c_int,ct.c_int,array]
        lib.run.argtypes=[array,array,array]
        lib.scales.restype=ct.POINTER(ct.c_float)
        scales=np.ctypeslib.as_array(lib.scales(),shape=(5,)).copy()
        lib.nn_decode.argtypes=[array,ct.POINTER(ct.c_float),ct.c_float,ct.c_float,ct.POINTER(Box),ct.POINTER(Box),ct.c_int]
        golden=np.load(out/'golden.npz');a=np.zeros(24576,np.int8);b=a.copy();head=np.zeros(960,np.int8)
        a[:12288]=golden['input'].reshape(-1);lib.run(a,b,head)
        last=max(int(k.split('_')[1]) for k in golden.files if k.startswith('layer_'))
        np.testing.assert_array_equal(head,golden[f'layer_{last}'].reshape(-1))
        dataset=Faces(Path(args.data)/'dataset.json',split='val')
        max_delta=0;changed=0;pixels=0;box_delta=0.;counts=[]
        for index,row in enumerate(dataset.records):
            image=cv2.imread(str(dataset.path.parent/row['image']))
            if image is None: raise ValueError('Unreadable validation image')
            # Firmware source is fixed QVGA; stress the exact supported geometry.
            image=cv2.resize(image,(320,240),interpolation=cv2.INTER_AREA)
            q=np.empty((1,96,128),np.int8)
            assert lib.nn_preprocess_bgr(image,320,240,q)==0
            expected=input_int8(preprocess(image))
            delta=np.abs(q.astype(int)-expected.astype(int));max_delta=max(max_delta,int(delta.max()))
            changed+=int(np.count_nonzero(delta));pixels+=delta.size
            if max_delta>1: raise AssertionError('Preprocessing differs by more than one INT8 unit')
            a[:12288]=q.reshape(-1);lib.run(a,b,head)
            # Compare decoder on identical logits to isolate postprocessing differences.
            import torch
            py=decode(torch.from_numpy(head.reshape(5,12,16).astype(np.float32)*scales[:,None,None]),.5)
            scratch=(Box*192)();boxes=(Box*192)()
            n=lib.nn_decode(head,lib.scales(),.5,.3,scratch,boxes,192)
            actual=np.array([[v.x1,v.y1,v.x2,v.y2,v.score] for v in boxes[:n]],np.float32).reshape(-1,5)
            np.testing.assert_allclose(actual,py,atol=2e-6,rtol=1e-5)
            if len(py):box_delta=max(box_delta,float(np.abs(actual-py).max()))
            counts.append(n)
        report=dict(images=len(counts),geometry='320x240 BGR',input_max_int8_delta=max_delta,
                    input_changed_fraction=changed/pixels,decoder_max_abs_delta=box_delta,
                    golden_head_exact=True,note='C vs OpenCV preprocessing rounding may differ by one unit; decoder tested on identical heads. Not an ESP32 timing test.')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
