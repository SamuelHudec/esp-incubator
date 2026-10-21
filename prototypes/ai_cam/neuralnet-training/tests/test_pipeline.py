"""Numerical and end-to-end smoke tests; synthetic shapes are not face validation."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from model import TinyFace, targets, decode, loss_fn, load_model


class PipelineTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(42)

    def test_target_decode_roundtrip_and_empty(self):
        boxes = [[.2,.2,.5,.6],[.7,.7,.72,.72]]
        score, distances = targets(boxes)
        pred = torch.cat([(score*40-20)[None], distances])
        result = decode(pred)
        self.assertEqual(len(result),2)
        for box in boxes:
            self.assertTrue(any(np.allclose(row[:4],box,atol=1e-6) for row in result))
        self.assertEqual(len(decode(torch.full((5,12,16),-20.))),0)

    def test_negative_loss_and_checkpoint(self):
        model = TinyFace()
        output = model(torch.zeros(2,1,96,128))
        self.assertEqual(tuple(output.shape),(2,5,12,16))
        loss = loss_fn(output,torch.zeros(2,12,16),torch.zeros(2,4,12,16))
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'test.pt'
            torch.save(dict(architecture='tinyface-v1',model=model.state_dict()),path)
            restored = load_model(path)
            model.eval()
            self.assertTrue(torch.equal(model(torch.zeros(1,1,96,128)),restored(torch.zeros(1,1,96,128))))

    def test_synthetic_overfit(self):
        model = TinyFace()
        x = torch.zeros(2,1,96,128)
        x[0,0,24:60,32:64] = 1
        s,b = targets([[.25,.25,.5,.625]])
        score = torch.stack([s,torch.zeros_like(s)])
        boxes = torch.stack([b,torch.zeros_like(b)])
        optimizer = torch.optim.Adam(model.parameters(),lr=.005)
        first = loss_fn(model(x),score,boxes).item()
        for _ in range(100):
            optimizer.zero_grad()
            loss = loss_fn(model(x),score,boxes)
            loss.backward(); optimizer.step()
        model.eval()
        final = loss_fn(model(x),score,boxes).item()
        self.assertLess(final,first*.3)
        self.assertGreater(len(decode(model(x)[0],.3)),0)
        self.assertEqual(len(decode(model(x)[1],.3)),0)


if __name__ == '__main__':
    unittest.main()
