"""RetinaFace ResNet50 ONNX adapter using OpenCV DNN on CPU.

Model: clibdev/Pytorch_Retinaface release 1.0.0 (biubug6 weights).
Preprocessing and anchor decoding follow that project's detect.py and PriorBox.
"""
import hashlib
import math
from pathlib import Path
import urllib.request

import cv2
import numpy as np

REVISION = '1.0.0'
MODEL = 'retinaface-resnet-50.onnx'
SHA256 = 'a903411b598d92ccc6af5660d875f38783a93031be13643ed4c87851ec165898'
BASE = f'https://github.com/clibdev/Pytorch_Retinaface/releases/download/{REVISION}/'


def download_model(cache):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / MODEL
    if not target.exists():
        temporary = target.with_suffix('.partial')
        try:
            with urllib.request.urlopen(BASE + MODEL, timeout=60) as response, temporary.open('wb') as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != SHA256:
                raise ValueError('RetinaFace download checksum mismatch')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    if hashlib.sha256(target.read_bytes()).hexdigest() != SHA256:
        raise ValueError(f'RetinaFace checksum mismatch: {target}; remove it and retry')
    return target


def priors(width, height):
    return np.asarray([
        [(x+.5)*stride/width, (y+.5)*stride/height, size/width, size/height]
        for stride, sizes in ((8,(16,32)), (16,(64,128)), (32,(256,512)))
        for y in range(math.ceil(height/stride))
        for x in range(math.ceil(width/stride)) for size in sizes
    ], dtype=np.float32)


class RetinaFace:
    def __init__(self, model, threshold):
        self.net = cv2.dnn.readNetFromONNX(str(model))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self.threshold = threshold

    def predict(self, image, size):
        if size != 640:
            raise ValueError('This RetinaFace ONNX export requires --size 640')
        h,w = image.shape[:2]
        scale = size/max(h,w)
        nw,nh = max(1,round(w*scale)), max(1,round(h*scale))
        resized = cv2.resize(image,(nw,nh),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_LINEAR)
        # This export has fixed 640x640 pyramid resize shapes; preserve aspect ratio with padding.
        width = height = 640
        padded = np.empty((height,width,3),np.float32)
        padded[:] = (104,117,123)
        padded[:nh,:nw] = resized
        self.net.setInput(cv2.dnn.blobFromImage(padded, mean=(104,117,123), swapRB=False))
        outputs = self.net.forward(self.net.getUnconnectedOutLayersNames())
        loc = next(v.reshape(-1,4) for v in outputs if v.shape[-1] == 4)
        scores = next(v.reshape(-1,2)[:,1] for v in outputs if v.shape[-1] == 2)
        anchors = priors(width,height)
        if len(loc) != len(anchors):
            raise ValueError('RetinaFace output/anchor count mismatch')
        keep = np.flatnonzero(scores >= self.threshold)
        keep = keep[np.argsort(scores[keep])[::-1][:5000]]
        if not len(keep):
            return [], []
        loc, anchors, scores = loc[keep], anchors[keep], scores[keep]
        centers = anchors[:,:2] + loc[:,:2]*.1*anchors[:,2:]
        sizes = anchors[:,2:]*np.exp(loc[:,2:]*.2)
        boxes = np.concatenate((centers-sizes/2, centers+sizes/2),axis=1)
        boxes *= np.asarray([width/nw,height/nh,width/nw,height/nh])
        boxes = np.clip(boxes,0,1)
        valid = np.isfinite(boxes).all(axis=1) & (boxes[:,2]>boxes[:,0]) & (boxes[:,3]>boxes[:,1])
        boxes,scores = boxes[valid],scores[valid]
        rectangles = np.concatenate((boxes[:,:2],boxes[:,2:]-boxes[:,:2]),axis=1)
        selected = cv2.dnn.NMSBoxes(rectangles.tolist(),scores.tolist(),self.threshold,.3)
        selected = np.asarray(selected,dtype=int).reshape(-1)
        return boxes[selected].tolist(),scores[selected].tolist()
