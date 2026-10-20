"""Draw detections on an image, video, webcam or MJPEG URL (q to quit)."""
import argparse
import time
from pathlib import Path
import cv2
import torch
from model import load_model, preprocess, decode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--source', required=True, help='Image/video path, URL or webcam index')
    parser.add_argument('--output', help='Annotated image path (image inputs only)')
    parser.add_argument('--device', choices=['cpu','mps','cuda'], default='cpu')
    parser.add_argument('--threshold', type=float, default=.5)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if args.threads < 1 or not 0 < args.threshold < 1:
        parser.error('threads must be positive; threshold in (0,1)')
    torch.set_num_threads(args.threads)
    model = load_model(args.checkpoint, args.device)
    is_image = Path(args.source).suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.webp'} and not args.source.startswith(('http:', 'https:'))
    if args.output and not is_image:
        parser.error('--output supports still images only')

    @torch.inference_mode()
    def annotate(frame):
        start = time.perf_counter()
        output = model(preprocess(frame).unsqueeze(0).to(args.device))[0]
        boxes = decode(output, args.threshold)  # CPU transfer synchronizes accelerator.
        elapsed = (time.perf_counter()-start)*1000
        h,w = frame.shape[:2]
        for x1,y1,x2,y2,score in boxes:
            a = (min(w-1,int(x1*w)), min(h-1,int(y1*h)))
            b = (min(w-1,int(x2*w)), min(h-1,int(y2*h)))
            cv2.rectangle(frame, a,b, (0,255,0), 2)
            cv2.putText(frame, f'{score:.2f}', a, cv2.FONT_HERSHEY_SIMPLEX, .5,(0,255,0),1)
        cv2.putText(frame, f'Python detect {elapsed:.1f} ms | faces {len(boxes)}',
                    (8,20),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,255,0),1)
        return frame

    if is_image:
        frame = cv2.imread(args.source)
        if frame is None:
            raise ValueError('Cannot read image')
        frame = annotate(frame)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(args.output, frame):
                raise RuntimeError('Cannot save output')
        else:
            cv2.imshow('TinyFace',frame); cv2.waitKey(0); cv2.destroyAllWindows()
        return
    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError('Cannot open source; close other ESP32 stream viewers')
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            cv2.imshow('TinyFace', annotate(frame))
            if cv2.waitKey(1) & 0xff == ord('q'):
                break
    finally:
        cap.release(); cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
