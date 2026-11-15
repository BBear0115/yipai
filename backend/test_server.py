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

from PIL import Image, ImageChops
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
        for size, color in [((900,1200),'#356da0'), ((1600,900),'#d0d0d0'),
                            ((400,600),'black')]:
            with self.subTest(size=size,color=color):
                raw=source(size,color)
                result=Image.open(BytesIO(server.watermark(raw)))
                self.assertEqual(result.format,'JPEG')
                self.assertEqual(result.size,size)
                baseline=BytesIO()
                Image.open(BytesIO(raw)).save(baseline,'JPEG',quality=92)
                # Compare equally encoded files so JPEG rounding alone cannot pass this check.
                changed=ImageChops.difference(result,Image.open(BytesIO(baseline.getvalue()))).convert('L')
                changed=changed.point(lambda value:255 if value>12 else 0)
                bounds=changed.getbbox()
                self.assertIsNotNone(bounds)
                left,top,right,bottom=bounds
                self.assertGreaterEqual(left,size[0]//3)
                self.assertGreaterEqual(top,int(size[1]*0.8))
                self.assertLess(right,size[0]-2)
                self.assertLess(bottom,size[1]-2)

    def test_watermark_has_no_background_or_shadow(self):
        white=Image.open(BytesIO(server.watermark(source((900,1200),'white'))))
        self.assertTrue(all(low>=253 for low,high in white.getextrema()))
        for color in ('#888888','#202020'):
            with self.subTest(color=color):
                result=Image.open(BytesIO(server.watermark(source((900,1200),color))))
                original=int(color[1:3],16)
                # White artwork may brighten its backdrop; JPEG ringing gets a small tolerance.
                self.assertTrue(all(low>=original-12 for low,high in result.getextrema()))

    def test_watermark_without_chinese_font_still_exports(self):
        with patch.object(server,'watermark_font',return_value=None):
            result=Image.open(BytesIO(server.watermark(source((900,1200)))))
        self.assertEqual(result.format,'JPEG')
        self.assertEqual(result.size,(900,1200))
        self.assertGreater(result.crop((600,1000,900,1200)).convert('L').getextrema()[1],180)

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
        owner.open(Request(self.base+'/api/posts/'+job_id,method='DELETE')).read()
        with self.assertRaises(HTTPError) as error:
            other.open(self.base+selected['image'])
        self.assertEqual(error.exception.code,404)
        jobs=json.load(owner.open(self.base+'/api/jobs'))['jobs']
        self.assertIsNone(next(job for job in jobs if job['id']==job_id)['post'])

    def test_published_work_carries_post_stats_and_deleting_it_removes_the_post(self):
        owner,other=self.client(),self.client()
        job_id=uuid4().hex;timestamp=server.now()
        visitor=next(iter(next(handler.cookiejar for handler in owner.handlers if isinstance(handler, HTTPCookieProcessor)))).value
        import hashlib
        with server.connect() as db:
            db.execute('INSERT INTO jobs(id,visitor,idem,model,status,created,updated) VALUES(?,?,?,?,?,?,?)',
                       (job_id,hashlib.sha256(visitor.encode()).hexdigest(),str(uuid4()),'female','succeeded',timestamp,timestamp))
        server.data_path(job_id,'input').write_bytes(source())
        server.data_path(job_id,'result').write_bytes(server.watermark(source((900,1200))))
        def send(client,path,payload,method='POST'):
            return json.load(client.open(Request(self.base+path,data=json.dumps(payload,ensure_ascii=False).encode(),
                headers={'Content-Type':'application/json'},method=method)))
        send(owner,'/api/posts',{'jobId':job_id,'productName':'蓝色上衣','note':'条纹清楚'})
        for kind in ('like','save','remake'):
            send(other,f'/api/posts/{job_id}/reactions',{'kind':kind})
        send(other,f'/api/posts/{job_id}/reactions',{'kind':'like'})
        stats=send(owner,f'/api/posts/{job_id}/reactions',{'kind':'like'})['stats']
        self.assertEqual((stats['likes'],stats['saves'],stats['remakes'],stats['liked']),(2,1,1,True))
        stats=send(owner,f'/api/posts/{job_id}/reactions',{'kind':'like','active':False})['stats']
        self.assertEqual((stats['likes'],stats['liked']),(1,False))
        with self.assertRaises(HTTPError) as error:
            send(other,f'/api/posts/{job_id}/reactions',{'kind':'remake','active':False})
        self.assertEqual(error.exception.code,400)
        post=json.load(owner.open(self.base+'/api/jobs/'+job_id))['job']['post']
        self.assertEqual((post['productName'],post['note'],post['likes'],post['saves'],post['remakes']),('蓝色上衣','条纹清楚',1,1,1))
        self.assertNotIn(job_id,[job['id'] for job in json.load(other.open(self.base+'/api/jobs'))['jobs']])
        self.assertTrue(json.load(owner.open(Request(self.base+'/api/jobs/'+job_id,method='DELETE')))['postDeleted'])
        self.assertNotIn(job_id,[item['id'] for item in json.load(other.open(self.base+'/api/posts'))['posts']])
        with self.assertRaises(HTTPError) as error:
            other.open(self.base+f'/api/posts/{job_id}/result')
        self.assertEqual(error.exception.code,404)
        with server.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM post_reactions WHERE post_id=?',(job_id,)).fetchone())

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
            self.assertEqual(payload['model'],'gpt-image-2.5-sunburst')
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
            self.assertEqual(payload['model'],'gpt-image-2.5-sunburst')
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
        for value in (3,0,9,'4',4.0,True):
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

    @patch.object(server,'credentials',return_value=('test-key',None))
    @patch.object(server,'generate')
    def test_remake_requires_reference_and_model_choice(self,generator,credentials):
        client=self.client()
        reference='data:image/png;base64,'+base64.b64encode(source()).decode()
        for changes in ({'workflowConfig':{'model_source':'preset','model':'female'}},
                        {'reference':reference,'workflowConfig':{'model_source':'preset','model':'robot'}},
                        {'reference':reference,'workflowConfig':{'model_source':'elsewhere'}},
                        {'reference':reference}):
            with self.subTest(changes=changes), self.assertRaises(HTTPError) as error:
                self.post(client,self.payload(workflowType='remake',**changes))
            self.assertEqual(error.exception.code,400)
        job=self.post(client,self.payload(workflowType='remake',reference=reference,workflowConfig={'model_source':'preset','model':'male','extra':'x'}))['job']
        self.assertEqual(job['workflowConfig'],{'model_source':'preset','model':'male'})
        self.assertEqual(job['reference'],f'/api/jobs/{job["id"]}/reference')
        self.assertEqual(Image.open(BytesIO(client.open(self.base+job['reference']).read())).size,(600,800))
        with self.assertRaises(HTTPError) as error:
            self.client().open(self.base+job['reference'])
        self.assertEqual(error.exception.code,404)

    def analysis_reply(self,**changes):
        analysis={'original_category':'连帽卫衣','product_note':'图2里只有格纹长裤是商品。','shot':'全身竖构图','pose':'正面站立',
                  'styling':'纯黑卫衣','scene':'夜晚街头','lighting':'闪光灯直打','color':'高对比','mood':'街拍',
                  'variants':['照原姿势','侧身走动','蹲坐路边'],'reference_box':[0,100,1000,600],'product_box':[0,0,1000,1000],**changes}
        text=json.dumps(analysis,ensure_ascii=False)
        events=[{'type':'response.output_text.delta','delta':text[:40]},{'type':'response.output_text.delta','delta':text[40:]},{'type':'response.completed'}]
        return BytesIO(''.join(f'data: {json.dumps(event,ensure_ascii=False)}\n\n' for event in events).encode()+b'data: [DONE]\n\n')

    @patch.object(server, 'credentials', return_value=('test-key', None))
    def test_role_remake_analyzes_each_reference_and_generates_three_with_all_garments(self, credentials):
        owner = self.client()
        inputs = [self.tryon_input('upper', 'red', size=(330, 502)), self.tryon_input('lower', 'blue', size=(480, 444)),
                  self.tryon_input('reference', 'green'), self.tryon_input('reference', 'yellow'),
                  self.tryon_input('model', 'purple'), self.tryon_input('detail', 'orange', size=(160, 160), garmentRole='lower')]
        body = self.payload(workflowType='remake', workflowConfig={'clothing_mode':'multi', 'instruction':'棕色乐福鞋'}, inputImages=inputs)
        with patch.object(server, 'generate'):
            job = self.post(owner, body)['job']
        self.assertEqual(job['workflowConfig']['output_count'], 3)
        self.assertEqual(len(job['inputImages']), 6)
        self.assertEqual(job['reference'], job['inputImages'][2]['url'])
        with patch.object(server, 'analysis_credentials', return_value=('key', 'http://analyze.invalid/v1', 'vision')):
            with patch.object(server, 'urlopen', return_value=self.analysis_reply()) as request:
                analysis = server.request_analysis(source(), [{'role':'upper','bytes':source()}, {'role':'lower','bytes':source()}], 'test')
            content = json.loads(request.call_args.args[0].data)['input'][0]['content']
            self.assertEqual(len(content), 4)
            self.assertIn('图2是上装商品；图3是下装商品', content[0]['text'])
        with patch.object(server, 'request_analysis', return_value=analysis) as analyze, patch.object(server, 'request_image', return_value=source()) as image:
            server.generate(job['id'], 'female', 'remake', job['workflowConfig'])
        self.assertEqual(analyze.call_count, 2)
        self.assertEqual([item['role'] for item in analyze.call_args.args[1]], ['upper', 'lower'])
        self.assertEqual(image.call_count, 12)  # six photos, each followed by identity calibration
        prompt = image.call_args_list[0].args[0]
        self.assertIn('图1是画面参考；图2是上装商品；图3是下装商品；图4是模特身份；图5是服装细节', prompt)
        self.assertIn('图5只补充图3（下装商品）', prompt)
        self.assertIn('本张拍法：照原姿势', prompt)
        self.assertIn('棕色乐福鞋', prompt)
        self.assertNotIn('保持其人物姿势', prompt)
        self.assertIn('本张拍法：侧身走动', image.call_args_list[2].args[0])
        restored = json.load(owner.open(self.base + '/api/jobs/' + job['id']))['job']
        self.assertEqual(restored['status'], 'succeeded')
        self.assertEqual(len(restored['images']), 6)
        with server.connect() as db:
            row = db.execute('SELECT workflow_config,input_images FROM jobs WHERE id=?', (job['id'],)).fetchone()
        self.assertNotIn('base64', row['workflow_config'] + row['input_images'])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    @patch.object(server, 'generate')
    def test_role_remake_twenty_four_results_and_snapshots_are_private_and_deleted(self, generator, credentials):
        owner = self.client(); stranger = self.client()
        inputs = [self.tryon_input('single'), *[self.tryon_input('reference') for _ in range(8)]]
        body = self.payload(workflowType='remake', workflowConfig={'clothing_mode':'single'}, inputImages=inputs)
        job = self.post(owner, body)['job']
        self.assertEqual(job['inputImages'][-1]['role'], 'model')
        for item in job['inputImages']:
            self.assertEqual(owner.open(self.base + item['url']).status, 200)
            with self.assertRaises(HTTPError) as error:
                stranger.open(self.base + item['url'])
            self.assertEqual(error.exception.code, 404)
        for index in range(1, 25):
            server.data_path(job['id'], f'result-{index}').write_bytes(source())
        server.update_job(job['id'], status='succeeded')
        server.analysis_path(job['id']).write_text('{}')
        restored = json.load(owner.open(self.base + '/api/jobs/' + job['id']))['job']
        self.assertEqual(len(restored['images']), 24)
        for path in [restored['images'][-1], '/api/jobs/' + job['id'] + '/download.zip']:
            self.assertEqual(owner.open(self.base + path).status, 200)
            with self.assertRaises(HTTPError) as error:
                stranger.open(self.base + path)
            self.assertEqual(error.exception.code, 404)
        with zipfile.ZipFile(BytesIO(owner.open(self.base + '/api/jobs/' + job['id'] + '/download.zip').read())) as archive:
            self.assertEqual(len(archive.namelist()), 24)
            self.assertIn('yipai-remake-24.jpg', archive.namelist())
        owner.open(Request(self.base + '/api/jobs/' + job['id'], method='DELETE')).read()
        self.assertFalse(any(server.DATA.glob(job['id'] + '.*')))

    @patch.object(server, 'credentials', return_value=('test-key', None))
    @patch.object(server, 'generate')
    def test_role_remake_validates_garment_config_detail_ownership_and_identity_source(self, generator, credentials):
        owner = self.client()
        good = [self.tryon_input('upper'), self.tryon_input('reference')]
        invalid = [({'clothing_mode':'multi'}, good[1:]),
                   ({'clothing_mode':'multi','output_count':4}, good),
                   ({'clothing_mode':'multi'}, [*good, self.tryon_input('detail', garmentRole='lower')]),
                   ({'clothing_mode':'multi'}, [self.tryon_input('upper', size=(200,240)), good[1]]),
                   ({'clothing_mode':'multi','model_source':'work'}, [*good, self.tryon_input('model')])]
        for config, inputs in invalid:
            with self.subTest(config=config, roles=[item['role'] for item in inputs]), self.assertRaises(HTTPError) as error:
                self.post(owner, self.payload(workflowType='remake', workflowConfig=config, inputImages=inputs))
            self.assertEqual(error.exception.code, 400)
        self.assertFalse(generator.called)
        self.assertEqual(json.load(owner.open(self.base + '/api/jobs'))['jobs'], [])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    def test_no_reference_remake_scene_and_pose_reach_provider(self, credentials):
        from backend.workflows.shooting_plans import SCENE_CONFIGS, POSE_MODIFIERS
        owner = self.client()
        for scene_id, scene in SCENE_CONFIGS.items():
            with self.subTest(scene=scene_id):
                body = self.payload(workflowType='remake', model='male',
                                    workflowConfig={'clothing_mode':'multi', 'output_count':1,
                                                    'shooting_style':scene_id, 'pose_preference':'side'},
                                    inputImages=[self.tryon_input('upper'), self.tryon_input('lower')])
                with patch.object(server, 'generate'):
                    job = self.post(owner, body)['job']
                self.assertEqual(job['workflowConfig']['shooting_style'], scene_id)
                self.assertEqual(job['workflowConfig']['pose_preference'], 'side')
                with patch.object(server, 'request_analysis') as analyze, patch.object(server, 'request_image', return_value=source()) as image:
                    server.generate(job['id'], 'male', 'remake', job['workflowConfig'])
                analyze.assert_not_called()
                image.assert_called_once()
                prompt = image.call_args.args[0]
                self.assertIn(scene['name'], prompt)
                self.assertIn(POSE_MODIFIERS['side'], prompt)
                self.assertIn('图1是上装商品；图2是下装商品；图3是模特身份', prompt)
                self.assertIn('已上传的商品必须同时穿在同一位模特身上', prompt)

    @patch.object(server, 'credentials', return_value=('test-key', None))
    @patch.object(server, 'generate')
    def test_remake_rejects_invalid_scene_and_pose_before_creating_jobs(self, generator, credentials):
        owner = self.client()
        invalid = [{'shooting_style': value} for value in ('unknown', [], {}, 1, None)]
        invalid += [{'pose_preference': value} for value in ('unknown', [], {}, 1, None)]
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(HTTPError) as error:
                self.post(owner, self.payload(workflowType='remake',
                          workflowConfig={'clothing_mode':'multi', **fields},
                          inputImages=[self.tryon_input('upper')]))
            self.assertEqual(error.exception.code, 400)
        generator.assert_not_called()
        self.assertEqual(json.load(owner.open(self.base + '/api/jobs'))['jobs'], [])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    def test_role_remake_without_reference_generates_three_with_both_garments_and_private_snapshots(self, credentials):
        owner = self.client(); stranger = self.client()
        # Keep upload order different from the numbered image roles sent to the provider.
        inputs = [self.tryon_input('detail', 'orange', size=(160, 160), garmentRole='lower'),
                  self.tryon_input('lower', 'blue', size=(480, 444)),
                  self.tryon_input('model', 'purple'), self.tryon_input('upper', 'red', size=(330, 502))]
        body = self.payload(workflowType='remake', workflowConfig={'clothing_mode':'multi', 'instruction':'搭配棕色皮鞋'}, inputImages=inputs)
        with patch.object(server, 'generate'):
            job = self.post(owner, body)['job']
        self.assertEqual(job['workflowConfig']['output_count'], 3)
        self.assertIsNone(job['reference'])
        snapshots = []
        for item in job['inputImages']:
            snapshots.append(owner.open(self.base + item['url']).read())
            with self.assertRaises(HTTPError) as error:
                stranger.open(self.base + item['url'])
            self.assertEqual(error.exception.code, 404)
        requests = []
        def respond(request, **kwargs):
            requests.append(json.loads(request.data))
            return BytesIO(json.dumps({'output':[{'result':base64.b64encode(source()).decode()}]}).encode())
        with patch.object(server, 'request_analysis') as analyze, patch.object(server, 'urlopen', side_effect=respond):
            server.generate(job['id'], 'female', 'remake', job['workflowConfig'])
        analyze.assert_not_called()
        self.assertEqual(len(requests), 3)  # No separate identity calibration without a pose reference.
        expected = [server.image_data_url(snapshots[index]) for index in (3, 1, 2, 0)]
        prompts = []
        for request in requests:
            content = request['input'][0]['content']
            self.assertEqual([item['image_url'] for item in content[1:]], expected)
            prompt = content[0]['text']; prompts.append(prompt)
            self.assertIn('图1是上装商品；图2是下装商品；图3是模特身份；图4是服装细节', prompt)
            self.assertIn('图4只补充图2（下装商品）', prompt)
            self.assertIn('智能搭配：', prompt)
            self.assertIn('已上传的商品必须同时穿在同一位模特身上', prompt)
            self.assertIn('搭配棕色皮鞋', prompt)
            self.assertNotIn('画面参考', prompt)
        self.assertEqual(len(set(prompts)), 3)
        self.assertFalse(server.analysis_path(job['id']).exists())
        restored = json.load(owner.open(self.base + '/api/jobs/' + job['id']))['job']
        self.assertEqual(restored['status'], 'succeeded')
        self.assertEqual(len(restored['images']), 3)
        self.assertIsNone(restored['reference'])
        with self.assertRaises(HTTPError) as error:
            owner.open(self.base + '/api/jobs/' + job['id'] + '/reference')
        self.assertEqual(error.exception.code, 404)
        # Regeneration reuses all private role snapshots without introducing a reference.
        regenerated_inputs = [{**item, 'image':'data:image/jpeg;base64,' + base64.b64encode(raw).decode()}
                              for item, raw in zip(restored['inputImages'], snapshots)]
        with patch.object(server, 'generate'):
            regenerated = self.post(owner, self.payload(workflowType='remake', workflowConfig=restored['workflowConfig'],
                                                       inputImages=regenerated_inputs))['job']
        self.assertNotEqual(regenerated['id'], restored['id'])
        self.assertEqual([item['role'] for item in regenerated['inputImages']], [item['role'] for item in restored['inputImages']])
        self.assertEqual(regenerated['inputImages'][0]['garmentRole'], 'lower')
        self.assertIsNone(regenerated['reference'])
        with patch.object(server, 'request_analysis') as analyze, patch.object(server, 'request_image', return_value=source()) as image:
            server.generate(regenerated['id'], 'female', 'remake', regenerated['workflowConfig'])
        analyze.assert_not_called()
        self.assertEqual(image.call_count, 3)

    @patch.object(server, 'credentials', return_value=('test-key', None))
    def test_role_remake_without_reference_accepts_single_garments_and_selected_output_count(self, credentials):
        owner = self.client()
        for mode, role, count in [('multi', 'upper', 1), ('multi', 'lower', 2), ('single', 'single', 3)]:
            with self.subTest(role=role, count=count):
                body = self.payload(model='male', workflowType='remake',
                                    workflowConfig={'clothing_mode':mode, 'output_count':count}, inputImages=[self.tryon_input(role)])
                with patch.object(server, 'generate'):
                    job = self.post(owner, body)['job']
                self.assertEqual([item['role'] for item in job['inputImages']], [role, 'model'])
                with patch.object(server, 'request_analysis') as analyze, patch.object(server, 'request_image', return_value=source()) as image:
                    server.generate(job['id'], 'male', 'remake', job['workflowConfig'])
                analyze.assert_not_called()
                self.assertEqual(image.call_count, count)
                restored = json.load(owner.open(self.base + '/api/jobs/' + job['id']))['job']
                self.assertEqual(restored['status'], 'succeeded')
                self.assertEqual(len(restored['images']), count)
                self.assertIsNone(restored['reference'])

    @patch.object(server, 'credentials', return_value=('test-key', None))
    def test_role_remake_without_reference_reports_generation_failure_and_resumes_remaining_outputs(self, credentials):
        owner = self.client()
        body = self.payload(workflowType='remake', workflowConfig={'clothing_mode':'multi'},
                            inputImages=[self.tryon_input('upper'), self.tryon_input('lower')])
        with patch.object(server, 'generate'):
            job = self.post(owner, body)['job']
        with patch.object(server, 'request_analysis') as analyze, patch.object(server, 'request_image', side_effect=[source(), ValueError('sensitive upstream text')]) as image:
            server.generate(job['id'], 'female', 'remake', job['workflowConfig'])
        analyze.assert_not_called()
        self.assertEqual(image.call_count, 2)
        failed = json.load(owner.open(self.base + '/api/jobs/' + job['id']))['job']
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['error'], '图片生成失败，请重新生成')
        self.assertEqual(len(failed['images']), 1)
        original_result = server.data_path(job['id'], 'result-1').read_bytes()
        with patch.object(server, 'request_analysis') as analyze, patch.object(server, 'request_image', return_value=source(color='blue')) as image:
            server.generate(job['id'], 'female', 'remake', job['workflowConfig'])
        analyze.assert_not_called()
        self.assertEqual(image.call_count, 2)
        self.assertEqual(server.data_path(job['id'], 'result-1').read_bytes(), original_result)
        restored = json.load(owner.open(self.base + '/api/jobs/' + job['id']))['job']
        self.assertEqual(restored['status'], 'succeeded')
        self.assertEqual(len(restored['images']), 3)

    @patch.object(server, 'credentials', return_value=('test-key', None))
    def test_role_remake_from_existing_work_keeps_its_identity_without_default_model(self, credentials):
        owner = self.client()
        body = self.payload(workflowType='remake', workflowConfig={'clothing_mode':'auto','model_source':'work','output_count':1},
                            inputImages=[self.tryon_input('auto'), self.tryon_input('reference')])
        with patch.object(server, 'generate'):
            job = self.post(owner, body)['job']
        self.assertEqual([item['role'] for item in job['inputImages']], ['auto', 'reference'])
        with patch.object(server, 'analysis_credentials', return_value=('key', 'http://analyze.invalid/v1', 'vision')):
            with patch.object(server, 'urlopen', return_value=self.analysis_reply()):
                analysis = server.request_analysis(source(), source(), 'test')
        with patch.object(server, 'request_analysis', return_value=analysis), patch.object(server, 'request_image', return_value=source()) as image:
            server.generate(job['id'], 'female', 'remake', job['workflowConfig'])
        self.assertEqual(image.call_count, 1)
        self.assertIn('出镜人物沿用图2商品作品中的模特', image.call_args.args[0])
        self.assertNotIn('保留图1人物的脸部身份', image.call_args.args[0])

    @patch.object(server, 'credentials', return_value=('image-only-key', None))
    @patch.object(server, 'analysis_credentials', return_value=(None, 'http://analysis.invalid/v1', 'vision'))
    def test_role_remake_without_analyzer_uses_only_the_configured_image_provider(self, analyzer, credentials):
        owner = self.client()
        body = self.payload(workflowType='remake', workflowConfig={'clothing_mode':'multi'},
                            inputImages=[self.tryon_input('lower'), self.tryon_input('reference')])
        with patch.object(server, 'generate'):
            job = self.post(owner, body)['job']
        urls = []; prompts = []
        def respond(request, **kwargs):
            urls.append(request.full_url)
            prompts.append(json.loads(request.data)['input'][0]['content'][0]['text'])
            self.assertEqual(request.get_header('Authorization'), 'image-only-key')
            return BytesIO(json.dumps({'output':[{'result':base64.b64encode(source()).decode()}]}).encode())
        with patch.object(server, 'urlopen', side_effect=respond):
            server.generate(job['id'], 'female', 'remake', job['workflowConfig'])
        self.assertEqual(urls, [server.GATEWAY] * 6)
        self.assertIn('本张拍法：尽量复现参考照片的构图和姿势', prompts[0])
        self.assertIn('改为自然走动或侧身抓拍', prompts[2])
        self.assertIn('换一个机位和自然姿势', prompts[4])
        self.assertEqual(json.loads(server.analysis_path(job['id']).read_text())['references'][0]['_source'], 'direct-reference')
        restored = json.load(owner.open(self.base + '/api/jobs/' + job['id']))['job']
        self.assertEqual(restored['status'], 'succeeded')
        self.assertEqual(len(restored['images']), 3)

    def remake_job(self,config):
        job_id=uuid4().hex;timestamp=server.now()
        with server.connect() as db:
            db.execute('INSERT INTO jobs(id,visitor,idem,model,status,created,updated,workflow_type,workflow_config) VALUES(?,?,?,?,?,?,?,?,?)',
                       (job_id,'test',str(uuid4()),config.get('model','female'),'queued',timestamp,timestamp,'remake',json.dumps(config)))
        server.data_path(job_id,'input').write_bytes(source())
        server.data_path(job_id,'reference').write_bytes(source((600,1200)))
        return job_id

    @patch.object(server,'analysis_credentials',return_value=('analyze-key','http://analyze.invalid/v1','vision-model'))
    @patch.object(server,'credentials',return_value=('test-key',None))
    def test_remake_reads_the_reference_then_generates_three_photos(self,credentials,analysis_credentials):
        job_id=self.remake_job({'model_source':'preset','model':'male'})
        requests=[]
        def respond(request,**kwargs):
            body=json.loads(request.data);requests.append((request.full_url,body,request.get_header('Authorization')))
            if body.get('stream'):
                return self.analysis_reply()
            return BytesIO(json.dumps({'output':[{'result':base64.b64encode(source((600,900))).decode()}]}).encode())
        with patch.object(server,'urlopen',side_effect=respond):
            server.generate(job_id,'male','remake',{'model_source':'preset','model':'male'})
        url,analysis,auth=requests[0]
        self.assertEqual(url,'http://analyze.invalid/v1/responses')
        self.assertEqual((analysis['model'],auth),('vision-model','Bearer analyze-key'))
        self.assertEqual([item['type'] for item in analysis['input'][0]['content']],['input_text','input_image','input_image'])
        generations=[body for _,body,_ in requests[1:]]
        self.assertEqual(len(generations),3)
        prompts=[body['input'][0]['content'][0]['text'] for body in generations]
        for prompt,variant in zip(prompts,['照原姿势','侧身走动','蹲坐路边']):
            self.assertIn(variant,prompt)
            self.assertIn('图2的模特',prompt)
            self.assertIn('忽略此人的长相',prompt)
            self.assertIn('图2里只有格纹长裤是商品',prompt)
        content=generations[0]['input'][0]['content']
        self.assertEqual(len(content),4)
        # The reference is cropped to the photo region the analysis reported before generation sees it.
        reference=Image.open(BytesIO(base64.b64decode(content[3]['image_url'].split(',',1)[1])))
        self.assertEqual(reference.size,(600,600))
        with server.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        result=server.public_job(row)
        self.assertEqual(result['status'],'succeeded')
        self.assertEqual(len(result['images']),3)
        self.assertTrue(server.analysis_path(job_id).is_file())

    @patch.object(server,'analysis_credentials',return_value=('analyze-key','http://analyze.invalid/v1','vision-model'))
    @patch.object(server,'credentials',return_value=('test-key',None))
    def test_remake_from_a_work_keeps_its_model_and_resumes_after_a_failure(self,credentials,analysis_credentials):
        job_id=self.remake_job({'model_source':'work','model':'female'})
        calls=[]
        def respond(request,**kwargs):
            body=json.loads(request.data);calls.append(body)
            if body.get('stream'):
                return self.analysis_reply()
            if len(calls)==3:
                raise HTTPError(server.GATEWAY,500,'upstream',{},None)
            return BytesIO(json.dumps({'output':[{'result':base64.b64encode(source((600,900))).decode()}]}).encode())
        with patch.object(server,'urlopen',side_effect=respond):
            server.generate(job_id,'female','remake',{'model_source':'work'})
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?',(job_id,)).fetchone()['status'],'failed')
        first=calls[1]['input'][0]['content']
        self.assertEqual(len(first),3)
        self.assertIn('图1中的模特就是出镜模特',first[0]['text'])
        calls.clear()
        with patch.object(server,'urlopen',side_effect=respond):
            server.generate(job_id,'female','remake',{'model_source':'work'})
        # The saved analysis and the finished first photo are reused; only photos 2 and 3 are requested.
        self.assertFalse(any(body.get('stream') for body in calls))
        self.assertEqual(len(calls),2)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?',(job_id,)).fetchone()['status'],'succeeded')

    @patch.object(server,'analysis_credentials',return_value=('analyze-key','http://analyze.invalid/v1','vision-model'))
    @patch.object(server,'credentials',return_value=('test-key',None))
    def test_unreadable_reference_fails_with_a_clear_message(self,credentials,analysis_credentials):
        job_id=self.remake_job({'model_source':'preset','model':'female'})
        with patch.object(server,'urlopen',return_value=self.analysis_reply(variants=['只有一条'])):
            server.generate(job_id,'female','remake',{'model_source':'preset','model':'female'})
        with server.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        self.assertEqual(row['status'],'failed')
        self.assertIn('参考图',row['error'])
        self.assertFalse(server.analysis_path(job_id).exists())

    def test_analysis_boxes_ignore_implausible_regions(self):
        fields={key:'x' for key in ('original_category','product_note','shot','pose','styling','scene','lighting','color','mood')}
        text=json.dumps({**fields,'variants':['a','b','c'],'reference_box':[0,0,100,100],'product_box':[-50,0,2000,1000]})
        analysis=server.parse_analysis('好的：'+text)
        self.assertIsNone(analysis['reference_box'])
        self.assertEqual(analysis['product_box'],[0,0,1000,1000])

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
