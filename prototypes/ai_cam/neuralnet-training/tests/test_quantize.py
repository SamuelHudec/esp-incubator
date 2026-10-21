import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from model import TinyFace
from quantize import round_away, folded_layers, int_conv, install_model


class QuantizeTests(unittest.TestCase):
    def test_install_preserves_model_on_partial_copy_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root/'export.h', root/'model.h'
            source.write_bytes(b'new model')
            destination.write_bytes(b'previous model')
            def fail_copy(src, dst):
                dst.write(b'partial')
                raise OSError('Simulated write failure')
            with patch('quantize.shutil.copyfileobj', side_effect=fail_copy):
                with self.assertRaises(OSError):
                    install_model(source, destination)
            self.assertEqual(destination.read_bytes(), b'previous model')
            self.assertEqual(set(root.iterdir()), {source, destination})
            install_model(source, destination)
            self.assertEqual(destination.read_bytes(), source.read_bytes())

    def test_rounding(self):
        np.testing.assert_array_equal(round_away(np.array([-1.5,-.5,.5,1.5])),[-2,-1,1,2])

    def test_folding(self):
        torch.manual_seed(42)
        model=TinyFace().eval()
        x=torch.rand(1,1,96,128)
        with torch.no_grad():
            expected=model(x)
            for conv,relu in folded_layers(model):
                x=conv(x)
                if relu: x=x.relu()
        torch.testing.assert_close(x,expected,atol=1e-5,rtol=1e-5)

    def test_signed_requantization_and_clipping(self):
        layer=dict(kernel=1,stride=1,padding=0,groups=1,ci=1,co=1,relu=0,
                   weights=np.array([[[[1]]]],dtype=np.int8),bias=np.array([0],dtype=np.int32),
                   multiplier=np.array([1],dtype=np.int32),shift=np.array([1],dtype=np.int32))
        x=np.array([[[-3,-1,1,3]]],dtype=np.int8)
        np.testing.assert_array_equal(int_conv(x,layer),[[[-2,-1,1,2]]])
        layer['relu']=1
        np.testing.assert_array_equal(int_conv(x,layer),[[[0,0,1,2]]])
