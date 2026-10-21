"""Compare native fast paths with independent Python/OpenCV references."""
import ctypes as ct
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from quantize import int_conv, input_int8
from model import preprocess


class Layer(ct.Structure):
    _fields_ = [(k, ct.c_int) for k in
                ('ci','co','hi','wi','ho','wo','kernel','stride','padding','groups','relu')] + [
                    ('weights',ct.POINTER(ct.c_int8)),
                    *[(k,ct.POINTER(ct.c_int32)) for k in ('bias','multiplier','shift')]]


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        src = Path(__file__).resolve().parents[2]/'firmware/neuralnet'
        lib = Path(cls.directory.name)/'native.so'
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
                        str(src/'nn_int8.c'),str(src/'nn_pipeline.c'),'-lm','-o',str(lib)],check=True)
        cls.lib = ct.CDLL(str(lib))
        array = np.ctypeslib.ndpointer(flags='C_CONTIGUOUS')
        cls.lib.nn_conv.argtypes = [ct.POINTER(Layer),array,array]
        cls.lib.nn_preprocess_bgr.argtypes = [array,ct.c_int,ct.c_int,array]

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_convolutions(self):
        rng = np.random.default_rng(71)
        for ci,co,h,w,k,stride,pad,groups in [
                (1,5,1,1,1,1,0,1),(3,5,3,5,1,1,0,1),
                (32,32,12,16,1,1,0,1),(3,4,7,9,3,2,1,1),
                (4,4,7,9,3,1,1,4),(3,5,7,9,1,2,0,1)]:
            for relu in (0,1):
                x=rng.integers(-127,128,(ci,h,w),dtype=np.int8)
                layer=dict(ci=ci,co=co,hi=h,wi=w,ho=(h+2*pad-k)//stride+1,
                           wo=(w+2*pad-k)//stride+1,kernel=k,stride=stride,padding=pad,
                           groups=groups,relu=relu,
                           weights=rng.integers(-127,128,(co,ci//groups,k,k),dtype=np.int8),
                           bias=rng.integers(-1000,1001,co,dtype=np.int32),
                           multiplier=np.full(co,123456789,dtype=np.int32),
                           shift=np.array([0,24,31,40,62]*((co+4)//5),dtype=np.int32)[:co].copy())
                native=Layer(*[layer[name] for name,_ in Layer._fields_[:11]],
                             *[layer[name].ctypes.data_as(typ) for name,typ in Layer._fields_[11:]])
                out=np.empty((co,layer['ho'],layer['wo']),np.int8)
                self.lib.nn_conv(ct.byref(native),x,out)
                np.testing.assert_array_equal(out,int_conv(x,layer))

    def test_qvga_preprocessing(self):
        rng=np.random.default_rng(8)
        images=[np.full((240,320,3),v,np.uint8) for v in (0,1,127,128,254,255)]
        images += [rng.integers(0,256,(240,320,3),dtype=np.uint8) for _ in range(20)]
        images += [np.repeat(((np.indices((240,320)).sum(axis=0)%2)*255).astype(np.uint8)[...,None],3,axis=2)]
        for image in images:
            output=np.empty((1,96,128),np.int8)
            self.assertEqual(self.lib.nn_preprocess_bgr(image,320,240,output),0)
            np.testing.assert_array_equal(output,input_int8(preprocess(image)))
