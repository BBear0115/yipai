"""Validate model availability through the actual API and input preparation."""
import base64
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from PIL import Image
import server


class ModelAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        data = Path(self.directory.name)
        self.data_patch = patch.object(server, 'DATA', data)
        self.db_patch = patch.object(server, 'DB', data / 'models.sqlite3')
        self.data_patch.start()
        self.db_patch.start()
        server.init_db()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.http.server_port}'
        image = BytesIO()
        Image.new('RGB', (600, 800), '#356da0').save(image, 'JPEG')
        self.image = image.getvalue()
        self.present, self.missing = 'a' * 32, 'b' * 32
        with server.connect() as db:
            for model_id in (self.present, self.missing):
                db.execute('INSERT INTO models (id,name,gender,image_path,is_preset,created) VALUES (?,?,?,?,?,?)',
                           (model_id, model_id, 'female', str(server.model_path(model_id)), 1, server.now()))
        server.model_path(self.present).write_bytes(self.image)

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.db_patch.stop()
        self.data_patch.stop()
        self.directory.cleanup()

    def test_models_api_filters_missing_files(self):
        with urlopen(self.base + '/api/models') as response:
            models = json.load(response)['models']
        self.assertEqual([model['id'] for model in models], [self.present])
        with urlopen(self.base + models[0]['image']) as response:
            self.assertEqual(response.read(), self.image)
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + f'/api/models/{self.missing}/image')
        self.assertEqual(error.exception.code, 404)

    def test_prepare_tryon_validates_model_file(self):
        payload = {'modelId': self.missing,
                   'workflowConfig': {'clothing_mode': 'multi'},
                   'inputImages': [{'role': 'upper', 'image': 'data:image/jpeg;base64,' + base64.b64encode(self.image).decode()}]}
        with self.assertRaisesRegex(ValueError, '所选模特不存在'):
            server.prepare_tryon_inputs(payload, 'visitor', 'remake')
        payload['modelId'] = self.present
        _, inputs = server.prepare_tryon_inputs(payload, 'visitor', 'remake')
        self.assertEqual([item['role'] for item in inputs], ['upper', 'model'])
        self.assertEqual(inputs[1]['bytes'], self.image)


if __name__ == '__main__':
    unittest.main()
