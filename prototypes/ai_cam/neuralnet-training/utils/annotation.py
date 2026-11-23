"""Desktop teacher adapters and reference-image rendering, independent of dataset splits."""
import hashlib
import math
from pathlib import Path
import urllib.request
import cv2
import numpy as np

REVISION = '3cc26e7f1014a5ee5d74a42acee58bafc9d0a310'
BASE = f'https://huggingface.co/opencv/face_detection_yunet/resolve/{REVISION}/'
MODEL = 'face_detection_yunet_2023mar.onnx'
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

def download_model(cache):
    cache.mkdir(parents=True, exist_ok=True)
    for name in (MODEL, 'LICENSE'):
        target = cache / name
        if not target.exists():
            temporary = target.with_suffix(target.suffix + '.partial')
            try:
                with urllib.request.urlopen(BASE+name, timeout=60) as response:
                    temporary.write_bytes(response.read())
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    return cache / MODEL

def detect(detector, image, size):
    if hasattr(detector, "predict"):
        return detector.predict(image, size)
    h,w = image.shape[:2]
    scale = size/max(h,w)
    nw,nh = max(1,round(w*scale)), max(1,round(h*scale))
    resized = cv2.resize(image,(nw,nh),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_LINEAR)
    detector.setInputSize((nw,nh))
    _, faces = detector.detect(resized)
    boxes, scores = [], []
    for face in faces if faces is not None else []:
        x,y,bw,bh = map(float,face[:4])
        box = np.clip([x/nw,y/nh,(x+bw)/nw,(y+bh)/nh],0,1).tolist()
        if box[2]>box[0] and box[3]>box[1]:
            boxes.append(box); scores.append(float(face[-1]))
    return boxes,scores

def render_montage(rows, output=None):
    chosen = rows
    if not chosen:
        raise ValueError('Cannot render an empty montage')
    tiles=[]
    for row in chosen:
        image=cv2.imread(row['source'])
        if image is None:
            raise ValueError(f"Cannot read montage image: {row['source']}")
        h,w=image.shape[:2]
        scale=min(320/w,240/h)
        tile=np.full((280,320,3),32,np.uint8)
        nw,nh=max(1,round(w*scale)),max(1,round(h*scale))
        small=cv2.resize(image,(nw,nh))
        for box,score in zip(row['boxes'],row['scores']):
            x1,y1,x2,y2=box
            a=(int(x1*nw),int(y1*nh)); b=(min(nw-1,int(x2*nw)),min(nh-1,int(y2*nh)))
            cv2.rectangle(small,a,b,(0,255,0),2)
            cv2.putText(small,f'{score:.2f}',a,cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,0),1)
        tile[:nh,:nw]=small
        cv2.putText(tile,Path(row['source']).name[:38],(4,257),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
        cv2.putText(tile,f"faces={len(row['boxes'])}",(4,274),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,255,255),1)
        tiles.append(tile)
    if tiles:
        cols=min(4,len(tiles)); grid=np.full((math.ceil(len(tiles)/cols)*280,cols*320,3),32,np.uint8)
        for i,tile in enumerate(tiles):
            y,x=divmod(i,cols);grid[y*280:(y+1)*280,x*320:(x+1)*320]=tile
        if output is not None and not cv2.imwrite(str(output),grid):
            raise RuntimeError('Failed to write preview')
    return grid


def load_detector(name, threshold, size, cache=None):
    if not 0 < threshold < 1 or size < 32:
        raise ValueError('Require threshold in (0,1) and size >= 32')
    if name == 'yunet':
        model = download_model(Path(cache or ('data/models/yunet/'+REVISION)))
        detector = cv2.FaceDetectorYN.create(str(model), '', (size,size), threshold, .3, 5000)
        model_name, revision = 'opencv/face_detection_yunet', REVISION
    elif name == 'retinaface':
        if size != 640:
            raise ValueError('RetinaFace requires --size 640')
        from utils import retinaface
        model = retinaface.download_model(Path(cache or ('data/models/retinaface/'+retinaface.REVISION)))
        detector = retinaface.RetinaFace(model, threshold)
        model_name, revision = 'clibdev/Pytorch_Retinaface/ResNet50', retinaface.REVISION
    else:
        raise ValueError(f'Unknown detector: {name}')
    return detector, dict(detector=name, model=model_name, revision=revision,
                         model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                         threshold=threshold, input_size=size, opencv=cv2.__version__)
