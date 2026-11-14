import base64
from concurrent.futures import ThreadPoolExecutor
import http.cookiejar
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import zipfile
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request
from uuid import uuid4

from PIL import Image
import server


def source(size=(600, 800), color='#356da0'):
    output = BytesIO()
    Image.new('RGB', size, color).save(output, 'PNG')
    return output.getvalue()


class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        server.DATA = Path(cls.directory.name)
        server.DB = server.DATA / 'test.sqlite3'
        server.init_db()
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.http.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.directory.cleanup()

    def client(self):
        client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        client.open(self.base + '/api/session').read()
        return client

    def payload(self, **changes):
        body = {'image': 'data:image/png;base64,' + base64.b64encode(source()).decode(), 'model': 'female', 'idempotencyKey': str(uuid4())}
        return {**body, **changes}

    def post(self, client, body):
        return json.load(client.open(Request(self.base+'/api/jobs', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='POST')))

    def tryon_input(self, role, color='#356da0', size=(600, 800), **fields):
        return {'role': role, 'image': 'data:image/png;base64,' + base64.b64encode(source(size, color)).decode(), **fields}

    def tryon_payload(self, inputs=None, **changes):
        inputs = inputs if inputs is not None else [self.tryon_input('upper')]
        return self.payload(workflowType='tryon', workflowConfig={'clothing_mode': 'multi', 'output_count': 1}, inputImages=inputs, **changes)

    @patch.object(server, 'credentials', return_value=('test-key', None))
    def test_tryon_references_generate_separate_numbered_requests_and_keep_detail_ownership(self, credentials):
        owner = self.client()
        # Upload order deliberately differs from provider role order.
        inputs = [self.tryon_input('detail', 'orange', size=(160, 160), garmentRole='lower'),
                  self.tryon_input('lower', 'blue'), self.tryon_input('reference', 'red', size=(400, 600)),
                  self.tryon_input('model', 'purple', size=(400, 500)), self.tryon_input('upper', 'green'),
                  self.tryon_input('reference', 'yellow')]
        body = self.tryon_payload(inputs)
        body['workflowConfig'].update(output_count=2, instruction='奶油色搭配，棕色乐福鞋')
        with patch.object(server, 'generate'):
            job = self.post(owner, body)['job']
        self.assertEqual(len(job['inputImages']), 6)
        self.assertTrue(all(set(item) <= {'role', 'url', 'garmentRole'} for item in job['inputImages']))
        with server.connect() as db:
            stored = db.execute('SELECT * FROM jobs WHERE id=?', (job['id'],)).fetchone()
        self.assertNotIn('base64', stored['input_images'])
        self.assertNotIn('base64', stored['workflow_config'])
        requests = []
        def respond(request, **kwargs):
            requests.append(json.loads(request.data))
            return BytesIO(json.dumps({'output': [{'result': base64.b64encode(source()).decode()}]}).encode())
        with patch.object(server, 'urlopen', side_effect=respond):
            server.generate(job['id'], 'female', 'tryon', job['workflowConfig'])
        self.assertEqual(len(requests), 8)
        expected_order = ([2, 4, 1, 3, 0], [2, 4, 1, 3, 0], [5, 4, 1, 3, 0], [5, 4, 1, 3, 0])
        for request, order in zip(requests[::2], expected_order):
            content = request['input'][0]['content']
            expected = [server.image_data_url(server.parse_image(inputs[index]['image'], min_dimension=128)) for index in order]
            self.assertEqual([item['image_url'] for item in content[1:]], expected)
            self.assertIn('图1是画面参考；图2是上装商品；图3是下装商品；图4是模特身份；图5是服装细节', content[0]['text'])
            self.assertIn('图5只补充图3（下装商品）', content[0]['text'])
            self.assertIn('棕色乐福鞋', content[0]['text'])
            self.assertIn('只替换图1中与已上传商品冲突的服装', content[0]['text'])
            self.assertEqual(request['size'], '1024x1536')
        for request in requests[1::2]:
            content = request['input'][0]['content']
            self.assertEqual(len(content), 3)
            self.assertIn('必须保留图1已完成的所有商品', content[0]['text'])
            self.assertIn('图2是唯一的人脸和发型参考', content[0]['text'])
            self.assertEqual(content[2]['image_url'], server.image_data_url(server.parse_image(inputs[3]['image'], min_dimension=400)))
            self.assertEqual(content[1]['image_url'], server.image_data_url(server.watermark(source())))
        restored = json.load(owner.open(self.base + '/api/jobs/' + job['id']))['job']
        self.assertEqual(restored['status'], 'succeeded')
        self.assertEqual(len(restored['images']), 4)
        self.assertEqual(restored['image'], restored['images'][0])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    @patch.object(server, 'generate')
    def test_tryon_invalid_roles_config_and_reference_urls_do_not_create_jobs(self, generator, credentials):
        owner = self.client()
        invalid = [
            {'inputImages': []},
            {'inputImages': [self.tryon_input('unknown')]},
            {'inputImages': [self.tryon_input('upper'), self.tryon_input('upper')]},
            {'inputImages': [self.tryon_input('single')]},
            {'inputImages': [self.tryon_input('reference')]},
            {'inputImages': [self.tryon_input('upper'), self.tryon_input('detail', garmentRole='lower')]},
            {'inputImages': [self.tryon_input('upper'), self.tryon_input('detail')]},
            {'inputImages': [self.tryon_input('upper', garmentRole='upper')]},
            {'inputImages': [{'role': 'upper', 'image': '/api/jobs/another/input'}]},
            {'inputImages': [self.tryon_input('upper'), {'role': 'reference', 'image': 'https://example.com/image.jpg'}]},
            {'inputImages': [self.tryon_input('upper'), *[self.tryon_input('reference') for _ in range(9)]]},
            {'inputImages': [self.tryon_input('upper'), *[self.tryon_input('detail', garmentRole='upper') for _ in range(5)]]},
            {'inputImages': [self.tryon_input('upper'), self.tryon_input('model'), self.tryon_input('model')]},
            {'modelId': 'invalid'},
            {'modelId': uuid4().hex, 'inputImages': [self.tryon_input('upper'), self.tryon_input('model')]},
            {'workflowConfig': {'clothing_mode': 'auto'}},
            {'workflowConfig': {'clothing_mode': 'single'}},
            {'workflowConfig': {'clothing_mode': 'multi', 'output_count': True}},
            {'workflowConfig': {'clothing_mode': 'multi', 'output_count': 3}},
            {'workflowConfig': {'clothing_mode': 'multi', 'instruction': '长' * 501}},
            {'workflowConfig': {'clothing_mode': 'multi', 'instruction': []}},
        ]
        for change in invalid:
            with self.subTest(change=str(change)[:90]), self.assertRaises(HTTPError) as error:
                self.post(owner, {**self.tryon_payload(), **change})
            self.assertEqual(error.exception.code, 400)
        self.assertFalse(generator.called)
        self.assertEqual(json.load(owner.open(self.base + '/api/jobs'))['jobs'], [])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    @patch.object(server, 'generate')
    def test_tryon_accepts_single_or_only_lower_and_limits_combined_uploads(self, generator, credentials):
        owner = self.client()
        for mode, role in [('single', 'single'), ('multi', 'lower')]:
            body = self.tryon_payload([self.tryon_input(role)])
            body['workflowConfig']['clothing_mode'] = mode
            job = self.post(owner, body)['job']
            self.assertEqual(job['inputImages'][0]['role'], role)
            self.assertEqual(job['inputImages'][1]['role'], 'model')
            self.assertEqual(job['model'], 'female')
        with patch.object(server, 'MAX_INPUT', len(source()) + 10):
            with self.assertRaises(HTTPError) as error:
                self.post(owner, self.tryon_payload([self.tryon_input('upper'), self.tryon_input('lower')]))
            self.assertEqual(error.exception.code, 400)
            self.assertIn('合计', json.load(error.exception)['error'])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    @patch.object(server, 'generate')
    def test_tryon_accepts_small_product_pngs_and_keeps_original_dimensions(self, generator, credentials):
        for role, mode, size in [('upper', 'multi', (330, 502)), ('lower', 'multi', (480, 444)), ('single', 'single', (454, 454))]:
            with self.subTest(role=role, size=size):
                owner = self.client()
                body = self.tryon_payload([self.tryon_input(role, size=size)])
                body['workflowConfig']['clothing_mode'] = mode
                job = self.post(owner, body)['job']
                image = owner.open(self.base + job['inputImages'][0]['url']).read()
                self.assertEqual(Image.open(BytesIO(image)).size, size)
        owner = self.client()
        with self.assertRaises(HTTPError) as error:
            self.post(owner, self.tryon_payload([self.tryon_input('upper', size=(200, 240))]))
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(json.load(owner.open(self.base + '/api/jobs'))['jobs'], [])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    def test_tryon_library_model_snapshot_is_private_and_survives_model_deletion(self, credentials):
        owner = self.client(); stranger = self.client()
        created = json.load(owner.open(Request(self.base + '/api/models', data=json.dumps({
            'name': '专属模特', 'gender': 'female', 'image': self.tryon_input('model', 'purple', size=(400, 600))['image'],
        }).encode(), headers={'Content-Type': 'application/json'}, method='POST')))['model']
        model_id = created['id']
        body = self.tryon_payload(modelId=model_id)
        with patch.object(server, 'generate'):
            with self.assertRaises(HTTPError) as error:
                self.post(stranger, body)
            self.assertEqual(error.exception.code, 400)
            job = self.post(owner, body)['job']
            for item in job['inputImages']:
                self.assertEqual(owner.open(self.base + item['url']).status, 200)
                with self.assertRaises(HTTPError) as error:
                    stranger.open(self.base + item['url'])
                self.assertEqual(error.exception.code, 404)
            snapshot = owner.open(self.base + job['inputImages'][1]['url']).read()
            owner.open(Request(self.base + '/api/models/' + model_id, method='DELETE')).read()
            self.assertEqual(self.post(owner, body)['job']['id'], job['id'])
            # Regeneration re-uploads private stored inputs, independent of the deleted library item.
            inputs = [{**item, 'image': 'data:image/jpeg;base64,' + base64.b64encode(owner.open(self.base + item['url']).read()).decode()} for item in job['inputImages']]
            regenerated = self.post(owner, self.tryon_payload(inputs))['job']
        self.assertNotEqual(regenerated['id'], job['id'])
        with patch.object(server, 'request_image', return_value=server.watermark(source())) as request:
            server.generate(regenerated['id'], 'female', 'tryon', regenerated['workflowConfig'])
        self.assertEqual(request.call_args.args[1][1], server.image_data_url(server.parse_image('data:image/jpeg;base64,' + base64.b64encode(snapshot).decode(), min_dimension=400)))
        self.assertIn('只提供模特脸型、五官、发型和可识别身份', request.call_args.args[0])
        self.assertIn('不要机械地给所有商品搭配灰色长裤和白色运动鞋', request.call_args.args[0])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    @patch.object(server, 'generate')
    def test_tryon_maximum_sixteen_results_zip_and_all_inputs_are_private_and_deleted(self, generator, credentials):
        owner = self.client(); stranger = self.client()
        inputs = [self.tryon_input('upper'), *[self.tryon_input('reference') for _ in range(8)]]
        body = self.tryon_payload(inputs)
        body['workflowConfig']['output_count'] = 2
        job = self.post(owner, body)['job']
        self.assertEqual([item['role'] for item in job['inputImages']].count('model'), 0)
        for index in range(1, 17):
            server.data_path(job['id'], f'result-{index}').write_bytes(source())
        server.update_job(job['id'], status='succeeded')
        restored = json.load(owner.open(self.base + '/api/jobs/' + job['id']))['job']
        self.assertEqual(len(restored['images']), 16)
        for path in [restored['images'][-1], '/api/jobs/' + job['id'] + '/download.zip']:
            self.assertEqual(owner.open(self.base + path).status, 200)
            with self.assertRaises(HTTPError) as error:
                stranger.open(self.base + path)
            self.assertEqual(error.exception.code, 404)
        with zipfile.ZipFile(BytesIO(owner.open(self.base + '/api/jobs/' + job['id'] + '/download.zip').read())) as archive:
            self.assertEqual(len(archive.namelist()), 16)
            self.assertIn('yipai-tryon-16.jpg', archive.namelist())
            self.assertIsNone(archive.testzip())
        owner.open(Request(self.base + '/api/jobs/' + job['id'], method='DELETE')).read()
        self.assertFalse(any(server.DATA.glob(job['id'] + '.*')))

    def test_tryon_reference_and_identity_role_rules_keep_uncovered_outfit(self):
        inputs = [{'role': 'reference'}, {'role': 'lower'}]
        prompt = server.build_tryon_prompt('female', inputs, {'clothing_mode': 'multi'})
        self.assertIn('下装只替换下半身', prompt)
        self.assertIn('未被商品覆盖的原有上下装、鞋履、包与配饰自然保留', prompt)
        self.assertIn('保留图1人物的脸部身份', prompt)
        self.assertNotIn('成年女性', prompt)
        self.assertNotIn('智能搭配：', prompt)
        with_identity = server.build_tryon_prompt('female', [*inputs, {'role': 'model'}], {'clothing_mode': 'multi'})
        self.assertIn('最终画面必须是图3中的同一个人', with_identity)
        self.assertIn('完全忽略图1人物的人脸、五官、发型和身份', with_identity)

    @patch.object(server, 'credentials', return_value=('test-key', None))
    def test_legacy_tryon_snapshots_regenerate_with_original_identity_and_numbering(self, credentials):
        owner = self.client()
        with patch.object(server, 'generate'):
            original = self.post(owner, self.payload(model='male'))['job']
        self.assertEqual(original['workflowConfig']['clothing_mode'], 'auto')
        self.assertEqual([item['role'] for item in original['inputImages']], ['auto', 'model'])
        restored_inputs = []
        for item in original['inputImages']:
            data_url = 'data:image/jpeg;base64,' + base64.b64encode(owner.open(self.base + item['url']).read()).decode()
            restored_inputs.append({**item, 'image': data_url})
        body = self.payload(model='male', workflowType='tryon', workflowConfig=original['workflowConfig'], inputImages=restored_inputs)
        # Regeneration must use the supplied identity snapshot even if defaults disappear.
        with patch.object(server, 'STATIC', server.DATA / 'no-default-assets'), patch.object(server, 'generate'):
            regenerated = self.post(owner, body)['job']
        self.assertNotEqual(regenerated['id'], original['id'])
        self.assertEqual(regenerated['workflowConfig'], original['workflowConfig'])
        self.assertEqual([item['role'] for item in regenerated['inputImages']], ['auto', 'model'])
        with patch.object(server, 'STATIC', server.DATA / 'no-default-assets'), patch.object(server, 'request_image', return_value=source()) as request:
            server.generate(regenerated['id'], 'male', 'tryon', regenerated['workflowConfig'])
        expected = [server.image_data_url(server.parse_image(item['image'])) for item in restored_inputs]
        self.assertEqual(request.call_args.args[1], expected)
        self.assertIn('图1是目标商品；图2是模特身份', request.call_args.args[0])
        self.assertIn('鞋履展示上脚与完整鞋型', request.call_args.args[0])
        self.assertIn('成年男性', request.call_args.args[0])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    @patch.object(server, 'generate')
    def test_explicit_auto_mode_requires_one_auto_garment_and_keeps_role_limits(self, generator, credentials):
        owner = self.client()
        invalid = [
            [self.tryon_input('auto'), self.tryon_input('auto')],
            [self.tryon_input('auto'), self.tryon_input('upper')],
            [self.tryon_input('single')],
            [self.tryon_input('reference')],
            [self.tryon_input('auto'), self.tryon_input('detail', garmentRole='upper')],
            [self.tryon_input('auto'), *[self.tryon_input('reference') for _ in range(9)]],
            [self.tryon_input('auto'), self.tryon_input('model'), self.tryon_input('model')],
        ]
        for inputs in invalid:
            with self.subTest(roles=[item['role'] for item in inputs]), self.assertRaises(HTTPError) as error:
                self.post(owner, self.payload(workflowType='tryon', workflowConfig={'clothing_mode': 'auto'}, inputImages=inputs))
            self.assertEqual(error.exception.code, 400)
        valid = [self.tryon_input('auto'), self.tryon_input('detail', size=(160, 160), garmentRole='auto')]
        job = self.post(owner, self.payload(workflowType='tryon', workflowConfig={'clothing_mode': 'auto'}, inputImages=valid))['job']
        self.assertEqual(job['inputImages'][1]['garmentRole'], 'auto')

    def test_input_rejects_corrupt_small_and_nonimage(self):
        for value in ('hello', 'data:image/png;base64,aGVsbG8=', 'data:image/png;base64,'+base64.b64encode(source((100,100))).decode()):
            with self.assertRaises(ValueError):
                server.parse_image(value)
        output=server.parse_image(self.payload()['image'])
        self.assertEqual(Image.open(BytesIO(output)).size, (600,800))

    @patch.object(server,'credentials',return_value=('test-key','test-id'))
    def test_malformed_request_is_rejected_without_creating_job(self,credentials):
        client=self.client()
        for raw in (b'[]', b'null', b'{bad', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(HTTPError) as error:
                client.open(Request(self.base+'/api/jobs',data=raw,
                                    headers={'Content-Type':'application/json'},method='POST'))
            self.assertEqual(error.exception.code,400)
        self.assertEqual(json.load(client.open(self.base+'/api/jobs'))['jobs'],[])

    def test_watermark_is_in_exported_pixels(self):
        raw=source((900,1200))
        result=Image.open(BytesIO(server.watermark(raw)))
        self.assertEqual(result.format,'JPEG')
        self.assertEqual(result.size,(900,1200))
        self.assertNotEqual(result.getpixel((820,1150)),(53,109,160))

    def test_disguised_gif_is_rejected(self):
        output=BytesIO()
        Image.new('RGB',(600,800),'blue').save(output,'GIF')
        with self.assertRaises(ValueError):
            server.parse_image('data:image/png;base64,'+base64.b64encode(output.getvalue()).decode())

    @patch.object(server,'credentials',return_value=('test-key','test-id'))
    def test_invalid_options_and_oversize_body(self,credentials):
        client=self.client()
        for changes in ({'model':'unknown'},{'image':None},{'idempotencyKey':'bad'}):
            with self.assertRaises(HTTPError) as error:
                self.post(client,self.payload(**changes))
            self.assertEqual(error.exception.code,400)
        with self.assertRaises(HTTPError) as error:
            client.open(Request(self.base+'/api/jobs',data=b'{}',headers={
                'Content-Length':str(server.MAX_BODY+1),'Content-Type':'application/json'},method='POST'))
        self.assertEqual(error.exception.code,400)

    def test_configuration_and_private_data_not_served_as_static_files(self):
        client=self.client()
        for route in ('/.env.local','/../.env.local','/backend/data/jobs.sqlite3','/api/missing'):
            with self.subTest(route=route), self.assertRaises(HTTPError) as error:
                client.open(self.base+route)
            self.assertEqual(error.exception.code,404)

    def test_session_cookie_is_http_only_and_same_site(self):
        response=build_opener().open(self.base+'/api/session')
        cookie=response.headers.get('Set-Cookie','')
        self.assertIn('HttpOnly',cookie)
        self.assertIn('SameSite=Lax',cookie)

    @patch.object(server,'credentials',return_value=('test-key',None))
    @patch.object(server,'generate')
    def test_live_and_demo_jobs_keep_mode_and_scene_after_reload(self,generator,credentials):
        for mode in ('live','demo'):
            with self.subTest(mode=mode), patch.object(server.Handler,'generation_mode',mode):
                client=self.client()
                self.assertEqual(json.load(client.open(self.base+'/api/session'))['generationMode'],mode)
                job=self.post(client,self.payload(workflowType='background_change',workflowConfig={'scene_type':'cafe'}))['job']
                self.assertEqual(job['workflowType'],'background_change')
                self.assertEqual(job['workflowConfig'],{'scene_type':'cafe'})
                self.assertEqual(job['previewOnly'],mode=='demo')
            # A stored demo record stays a demo even after switching to the live server.
            restored=json.load(client.open(self.base+'/api/jobs/'+job['id']))['job']
            self.assertEqual(restored['previewOnly'],mode=='demo')
            self.assertEqual(restored['workflowConfig'],{'scene_type':'cafe'})

    def test_community_publish_read_and_withdraw(self):
        owner=self.client();other=self.client()
        job_id=uuid4().hex;timestamp=server.now()
        visitor=next(iter(next(handler.cookiejar for handler in owner.handlers if isinstance(handler, HTTPCookieProcessor)))).value
        import hashlib
        with server.connect() as db:
            db.execute('INSERT INTO jobs(id,visitor,idem,model,status,created,updated) VALUES(?,?,?,?,?,?,?)',
                       (job_id,hashlib.sha256(visitor.encode()).hexdigest(),str(uuid4()),'female','succeeded',timestamp,timestamp))
        server.data_path(job_id,'input').write_bytes(source())
        server.data_path(job_id,'result').write_bytes(server.watermark(source((900,1200))))
        body={'jobId':job_id,'nickname':'测试商家','productName':'蓝色上衣','note':'条纹清楚，已检查原图'}
        def publish(client,payload):
            return json.load(client.open(Request(self.base+'/api/posts',data=json.dumps(payload,ensure_ascii=False).encode(),
                headers={'Content-Type':'application/json'},method='POST')))
        with self.assertRaises(HTTPError) as error:
            publish(other,body)
        self.assertEqual(error.exception.code,404)
        post=publish(owner,body)['post']
        self.assertTrue(post['mine'])
        self.assertEqual(publish(owner,body)['post']['id'],post['id'])
        public=json.load(other.open(self.base+'/api/posts'))['posts']
        selected=next(item for item in public if item['id']==job_id)
        self.assertFalse(selected['mine'])
        self.assertEqual(selected['productName'],'蓝色上衣')
        self.assertEqual(Image.open(BytesIO(other.open(self.base+selected['image']).read())).size,(900,1200))
        self.assertEqual(Image.open(BytesIO(other.open(self.base+selected['productImage']).read())).size,(600,800))
        with self.assertRaises(HTTPError) as error:
            other.open(Request(self.base+'/api/posts/'+job_id,method='DELETE'))
        self.assertEqual(error.exception.code,404)
        owner.open(Request(self.base+'/api/jobs/'+job_id,method='DELETE')).read()
        self.assertEqual(other.open(self.base+selected['image']).status,200)
        owner.open(Request(self.base+'/api/posts/'+job_id,method='DELETE')).read()
        with self.assertRaises(HTTPError) as error:
            other.open(self.base+selected['image'])
        self.assertEqual(error.exception.code,404)

    def test_community_rejects_missing_fields_and_unfinished_job(self):
        owner=self.client()
        for payload in ({'jobId':uuid4().hex,'productName':'衣服','note':'好看'},
                        {'jobId':uuid4().hex,'productName':'','note':'好看'},
                        {'jobId':uuid4().hex,'productName':'衣服','note':'x'*301}):
            with self.assertRaises(HTTPError) as error:
                owner.open(Request(self.base+'/api/posts',data=json.dumps(payload).encode(),
                                   headers={'Content-Type':'application/json'},method='POST'))
            self.assertIn(error.exception.code,(400,404))

    def test_gateway_output_decode(self):
        self.assertEqual(server.extract_output({'output':[{'result':base64.b64encode(source()).decode()}]}),source())
        with self.assertRaises(RuntimeError):
            server.extract_output({'output':[{'result':'bad data'}]})

    @patch.object(server,'credentials',return_value=('test-key','test-id'))
    @patch.object(server,'generate')
    def test_idempotency_and_private_history(self, generator, credentials):
        client=self.client(); stranger=self.client(); body=self.payload()
        one=self.post(client,body)['job'];two=self.post(client,body)['job']
        self.assertEqual(one['id'],two['id'])
        self.assertEqual(generator.call_count,1)
        jobs=json.load(client.open(self.base+'/api/jobs'))['jobs']
        self.assertIn(one['id'],[j['id'] for j in jobs])
        for route in ('','/input','/result'):
            with self.assertRaises(HTTPError) as error:
                stranger.open(self.base+'/api/jobs/'+one['id']+route)
            self.assertEqual(error.exception.code,404)
        self.assertEqual(json.load(stranger.open(self.base+'/api/jobs'))['jobs'],[])
        original=client.open(self.base+'/api/jobs/'+one['id']+'/input').read()
        self.assertEqual(Image.open(BytesIO(original)).size,(600,800))

    @patch.object(server,'credentials',return_value=('test-key','test-id'))
    @patch.object(server,'generate')
    def test_concurrent_duplicate_and_delete(self,generator,credentials):
        client=self.client();body=self.payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.post(client,body),range(2)))
        job_id=results[0]['job']['id']
        self.assertEqual(results[1]['job']['id'],job_id)
        self.assertEqual(generator.call_count,1)
        with self.assertRaises(HTTPError) as error:
            client.open(Request(self.base+'/api/jobs/'+job_id,method='DELETE'))
        self.assertEqual(error.exception.code,409)
        server.update_job(job_id,status='failed',error='test')
        deleted=json.load(client.open(Request(self.base+'/api/jobs/'+job_id,method='DELETE')))
        self.assertTrue(deleted['deleted'])
        self.assertFalse(server.data_path(job_id,'input').exists())

    @patch.object(server,'credentials',return_value=(None,None))
    def test_unconfigured_service_fails_without_job(self,credentials):
        client=self.client()
        with self.assertRaises(HTTPError) as error:
            self.post(client,self.payload())
        self.assertEqual(error.exception.code,503)
        self.assertEqual(json.load(client.open(self.base+'/api/jobs'))['jobs'],[])

    @patch.object(server,'credentials',return_value=('test-key','test-id'))
    @patch.object(server,'generate')
    def test_restart_resolves_incomplete_task(self,generator,credentials):
        client=self.client();job=self.post(client,self.payload())['job']
        server.init_db()
        recovered=json.load(client.open(self.base+'/api/jobs/'+job['id']))['job']
        self.assertEqual(recovered['status'],'failed')
        self.assertIn('重启',recovered['error'])

    @patch.object(server,'credentials',return_value=('test-key',None))
    def test_generation_request_uses_product_and_model(self,credentials):
        job_id=uuid4().hex;timestamp=server.now()
        with server.connect() as db:
            db.execute('INSERT INTO jobs(id,visitor,idem,model,status,created,updated) VALUES(?,?,?,?,?,?,?)',(job_id,'test',str(uuid4()),'male','queued',timestamp,timestamp))
        server.data_path(job_id,'input').write_bytes(source())
        response=BytesIO(json.dumps({'output':[{'result':base64.b64encode(source((900,1200))).decode()}]}).encode())
        with patch.object(server,'urlopen',return_value=response) as call:
            server.generate(job_id,'male')
            req=call.call_args.args[0];payload=json.loads(req.data)
            self.assertEqual(payload['model'],'gpt-image-2.5-flare')
            self.assertIsNone(req.get_header('Uuap-id'))
            content=payload['input'][0]['content']
            self.assertEqual([item['type'] for item in content],['input_text','input_image','input_image'])
            self.assertIn('成年男性',content[0]['text'])
            self.assertTrue(all(item['image_url'].startswith('data:image/') for item in content[1:]))
            self.assertEqual(call.call_args.kwargs['timeout'],300)
        with server.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        self.assertEqual(row['status'],'succeeded')
        self.assertTrue(server.data_path(job_id,'result').is_file())

    @patch.object(server,'credentials',return_value=('test-key','test-id'))
    @patch.object(server,'generate')
    def test_queue_limit_and_wrong_origin(self,generator,credentials):
        client=self.client()
        for _ in range(10): self.post(client,self.payload())
        with self.assertRaises(HTTPError) as error:
            self.post(client,self.payload())
        self.assertEqual(error.exception.code,429)
        with self.assertRaises(HTTPError) as error:
            client.open(Request(self.base+'/api/jobs',data=b'{}',headers={'Origin':'https://unrelated.invalid'},method='POST'))
        self.assertEqual(error.exception.code,403)

    @patch.object(server,'credentials',return_value=('test-key',None))
    def test_background_change_workflow(self,credentials):
        job_id=uuid4().hex;timestamp=server.now()
        with server.connect() as db:
            db.execute('INSERT INTO jobs(id,visitor,idem,model,status,created,updated) VALUES(?,?,?,?,?,?,?)',(job_id,'test',str(uuid4()),'female','queued',timestamp,timestamp))
        server.data_path(job_id,'input').write_bytes(source())
        response=BytesIO(json.dumps({'output':[{'result':base64.b64encode(source((1024,1536))).decode()}]}).encode())
        with patch.object(server,'urlopen',return_value=response) as call:
            server.generate(job_id,'female','background_change',{'scene_type':'outdoor_street'})
            req=call.call_args.args[0];payload=json.loads(req.data)
            self.assertEqual(payload['model'],'gpt-image-2.5-flare')
            self.assertEqual(payload['size'],'1024x1536')
            content=payload['input'][0]['content']
            self.assertEqual([item['type'] for item in content],['input_text','input_image'])
            self.assertIn('城市街道背景',content[0]['text'])
            self.assertIn('保留图1同一张脸',content[0]['text'])
            self.assertIn('保持图1原始画幅比例',content[0]['text'])
            self.assertIn('服装固有色',content[0]['text'])
            self.assertTrue(content[1]['image_url'].startswith('data:image/'))
            self.assertEqual(content[1]['image_url'],server.image_data_url(server.data_path(job_id,'input').read_bytes()))
        with server.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        self.assertEqual(row['status'],'succeeded')
        self.assertTrue(server.data_path(job_id,'result').is_file())

    def test_background_scenes_have_valid_prompts(self):
        scenes = ('white','studio_gray','outdoor_street','indoor_minimal','beach','cafe')
        for scene in scenes:
            with self.subTest(scene=scene):
                prompt = server.build_background_change_prompt(scene)
                self.assertIn('只换背景硬规则',prompt)
                self.assertIn('只移除图1原背景',prompt)
                self.assertIn('场景',prompt)
                self.assertIn('不得把商品自动穿到模特身上',prompt)
        with self.assertRaises(ValueError):
            server.build_background_change_prompt('unknown')

    @patch.object(server,'credentials',return_value=('test-key',None))
    def test_pose_generates_each_photo_with_its_own_prompt(self,credentials):
        for count in (4,6,8):
            with self.subTest(count=count):
                job_id=uuid4().hex; timestamp=server.now()
                with server.connect() as db:
                    db.execute('INSERT INTO jobs(id,visitor,idem,model,status,created,updated,workflow_type,workflow_config) VALUES(?,?,?,?,?,?,?,?,?)',
                               (job_id,'test',str(uuid4()),'female','queued',timestamp,timestamp,'pose_variation',json.dumps({'pose_count':count})))
                original=source()
                server.data_path(job_id,'input').write_bytes(original)
                requests=[]
                def respond(request,**kwargs):
                    requests.append(json.loads(request.data))
                    return BytesIO(json.dumps({'output':[{'result':base64.b64encode(source((600,900))).decode()}]}).encode())
                with patch.object(server,'urlopen',side_effect=respond):
                    server.generate(job_id,'female','pose_variation',{'pose_count':count})
                self.assertEqual(len(requests),count)
                self.assertEqual(len({r['input'][0]['content'][0]['text'] for r in requests}),count)
                for request in requests:
                    self.assertEqual(request['size'],'1024x1536')
                    content=request['input'][0]['content']
                    self.assertEqual(content[1]['image_url'],server.image_data_url(original))
                    self.assertIn('一张完整的竖版',content[0]['text'])
                with server.connect() as db:
                    row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
                result=server.public_job(row)
                self.assertEqual(result['status'],'succeeded')
                self.assertEqual(len(result['images']),count)
                self.assertEqual(result['image'],result['images'][0])
                with Image.open(server.data_path(job_id,f'result-{count}')) as image:
                    self.assertEqual(image.size,(600,900))

    @patch.object(server,'credentials',return_value=('test-key',None))
    @patch.object(server,'generate')
    def test_pose_photos_zip_and_delete_are_private(self,generator,credentials):
        owner=self.client(); stranger=self.client()
        for value in (3,0,9,'4'):
            with self.assertRaises(HTTPError) as error:
                self.post(owner,self.payload(workflowType='pose_variation',workflowConfig={'pose_count':value}))
            self.assertEqual(error.exception.code,400)
        job=self.post(owner,self.payload(workflowType='pose_variation',workflowConfig={'pose_count':4}))['job']
        for index in range(1,5):
            server.data_path(job['id'],f'result-{index}').write_bytes(source())
        server.update_job(job['id'],status='succeeded')
        result=json.load(owner.open(self.base+'/api/jobs/'+job['id']))['job']
        for route in [*result['images'],'/api/jobs/'+job['id']+'/download.zip']:
            with self.assertRaises(HTTPError) as error:
                stranger.open(self.base+route)
            self.assertEqual(error.exception.code,404)
            self.assertEqual(owner.open(self.base+route).status,200)
        response=owner.open(self.base+'/api/jobs/'+job['id']+'/download.zip')
        self.assertEqual(response.headers['Content-Type'],'application/zip')
        with zipfile.ZipFile(BytesIO(response.read())) as archive:
            self.assertEqual(len(archive.namelist()),4)
            self.assertIsNone(archive.testzip())
        owner.open(Request(self.base+'/api/jobs/'+job['id'],method='DELETE')).read()
        self.assertFalse(any(server.data_path(job['id'],f'result-{index}').exists() for index in range(1,5)))

    def test_legacy_pose_sheet_is_split_once_and_original_is_preserved(self):
        job_id=uuid4().hex; timestamp=server.now()
        with server.connect() as db:
            db.execute('INSERT INTO jobs(id,visitor,idem,model,status,created,updated,workflow_type,workflow_config) VALUES(?,?,?,?,?,?,?,?,?)',
                       (job_id,'test',str(uuid4()),'female','succeeded',timestamp,timestamp,'pose_variation','{"pose_count":4}'))
        sheet=Image.new('RGB',(1200,1200))
        for box,color in [((0,0,600,600),'red'),((600,0,1200,600),'green'),((0,600,600,1200),'blue'),((600,600,1200,1200),'yellow')]:
            sheet.paste(color,box)
        sheet.save(server.data_path(job_id,'result'),'JPEG')
        original=server.data_path(job_id,'result').read_bytes()
        server.migrate_pose_results()
        samples=[Image.open(server.data_path(job_id,f'result-{index}')).getpixel((100,100)) for index in range(1,5)]
        self.assertEqual(len(set(samples)),4)
        self.assertEqual(server.data_path(job_id,'result').read_bytes(),original)
        first=server.data_path(job_id,'result-1').read_bytes()
        server.migrate_pose_results()
        self.assertEqual(server.data_path(job_id,'result-1').read_bytes(),first)

    @patch.object(server,'credentials',return_value=('test-key','test-id'))
    def test_gateway_failure_does_not_publish_raw_error(self,credentials):
        job_id=uuid4().hex;timestamp=server.now()
        with server.connect() as db:
            db.execute('INSERT INTO jobs(id,visitor,idem,model,status,created,updated) VALUES(?,?,?,?,?,?,?)',(job_id,'error-test',str(uuid4()),'male','queued',timestamp,timestamp))
        server.data_path(job_id,'input').write_bytes(source())
        with patch.object(server,'urlopen',side_effect=HTTPError(server.GATEWAY,500,'sensitive upstream text',{},None)):
            server.generate(job_id,'male')
        with server.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        self.assertEqual(row['status'],'failed')
        self.assertNotIn('sensitive',row['error'])
        self.assertFalse(server.data_path(job_id,'result').exists())

if __name__=='__main__':
    unittest.main()
