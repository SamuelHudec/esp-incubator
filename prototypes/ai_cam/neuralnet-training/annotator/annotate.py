"""Small local browser editor for real-image records in labels.json."""
import argparse
import json
import math
import os
from pathlib import Path
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
import webbrowser

import cv2


class Dataset:
    def __init__(self, directory):
        self.path = directory.resolve() / 'labels.json'
        self.original = self.path.read_bytes()
        self.rows = json.loads(self.original)
        self.indices = [i for i, row in enumerate(self.rows) if row.get('dataset_source') == 'real']
        if not self.indices:
            raise ValueError('No real images in labels.json')

    def row(self, index):
        if not 0 <= index < len(self.indices):
            raise ValueError('Invalid image index')
        return self.rows[self.indices[index]]

    def image(self, index):
        row = self.row(index)
        image = cv2.imread(str(self.path.parent / row['image']))
        if image is None:
            raise ValueError(f'Cannot read {row["image"]}')
        success, encoded = cv2.imencode('.png', image)
        if not success:
            raise ValueError('Cannot encode image')
        return encoded.tobytes()

    def save(self, index, boxes):
        row = self.row(index)
        if not isinstance(boxes, list):
            raise ValueError('Invalid boxes')
        for box in boxes:
            if (not isinstance(box, list) or len(box) != 4
                    or not all(type(v) in (int, float) and math.isfinite(v) for v in box)
                    or not 0 <= box[0] < box[2] <= 1
                    or not 0 <= box[1] < box[3] <= 1):
                raise ValueError('Invalid normalized box')
        self.image(index)  # Never confirm an unreadable image as a negative.
        if self.path.read_bytes() != self.original:
            raise ValueError('labels.json changed outside this editor. Restart before saving.')
        backup = self.path.with_name('labels.before-review.json')
        if not backup.exists():
            with backup.open('xb') as stream:
                stream.write(self.original)
        updated = dict(row, boxes=boxes, scores=[1.0] * len(boxes), review_status='reviewed')
        updated.pop('error', None)
        rows = self.rows.copy()
        rows[self.indices[index]] = updated
        content = (json.dumps(rows, indent=2) + '\n').encode()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, delete=False) as stream:
                temporary = stream.name
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        self.rows, self.original = rows, content


def handler(dataset):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, body, content_type='application/json', status=200):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                if self.path == '/':
                    self.respond(Path(__file__).with_name('index.html').read_bytes(), 'text/html; charset=utf-8')
                elif self.path == '/records':
                    records = [dict(image=dataset.row(i)['image'], boxes=dataset.row(i)['boxes'],
                                    reviewed=dataset.row(i).get('review_status') == 'reviewed')
                               for i in range(len(dataset.indices))]
                    self.respond(json.dumps(records).encode())
                elif self.path.startswith('/image/'):
                    self.respond(dataset.image(int(self.path.removeprefix('/image/'))), 'image/png')
                else:
                    self.respond(b'Not found', 'text/plain', 404)
            except (ValueError, OSError, cv2.error) as exc:
                self.respond(str(exc).encode(), 'text/plain', 400)

        def do_POST(self):
            # Only same-origin browser requests may modify annotations.
            if self.headers.get('Origin') != f'http://127.0.0.1:{self.server.server_port}':
                self.respond(b'Invalid origin', 'text/plain', 403)
                return
            try:
                if self.path != '/save':
                    raise ValueError('Unknown endpoint')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 100000:
                    raise ValueError('Invalid request size')
                payload = json.loads(self.rfile.read(length))
                dataset.save(int(payload['index']), payload['boxes'])
                self.respond(b'{}')
            except (ValueError, OSError, KeyError, TypeError, cv2.error) as exc:
                self.respond(str(exc).encode(), 'text/plain', 400)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, type=Path)
    args = parser.parse_args()
    try:
        dataset = Dataset(args.data)
        server = HTTPServer(('127.0.0.1', 0), handler(dataset))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Annotator: {url}\nCtrl+C to stop.', flush=True)
    if (args.data / 'dataset.json').exists():
        print('Existing dataset.json is unchanged. Remove it and finalize again after review.', flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
