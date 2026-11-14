const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {webcrypto} = require('node:crypto');

async function context() {
  const location = {hash:''};
  const listeners = {};
  const classList = {add(){},remove(){},toggle(){}};
  const element = {style:{},classList,setAttribute(){},addEventListener(){},querySelector(){return {...element};},querySelectorAll(){return [];},focus(){},appendChild(){},insertBefore(){},replaceWith(){},remove(){},click(){},getAttribute(){return '';},setAttribute(){},removeAttribute(){},children:[],innerHTML:'',textContent:'',dataset:{},inert:false};
  const window = {scrollTo(){},addEventListener(name,fn){listeners[name]=fn;},history:{pushState(_state,_title,hash){location.hash=hash;},replaceState(_state,_title,hash){location.hash=hash;}}};
  const document = {body:{classList},querySelector:()=>({...element}),querySelectorAll:()=>[],getElementById:()=>({...element}),addEventListener(name,fn){listeners[`document:${name}`]=fn;},createElement(tag){if(tag==='template')return {content:{firstElementChild:{...element}},set innerHTML(_value){}};return {...element};}};
  const sandbox = vm.createContext({
    document,window,location,localStorage:{getItem(){},setItem(){}},crypto:webcrypto,
    setTimeout(){return 1;},clearTimeout(){},setInterval(){return 1;},
    fetch:async()=>({ok:true,json:async()=>({ready:true,jobs:[],posts:[]})})
  });
  vm.runInContext('openBatchUpload=()=>{}',sandbox);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../mockup/community.js'),'utf8'),sandbox);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../mockup/app.js'),'utf8'),sandbox);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../mockup/workflows.js'),'utf8'),sandbox);
  await vm.runInContext('sessionReady',sandbox);
  vm.runInContext('waiting=()=>{};prepare=()=>{};toast=()=>{};pollJobs=async()=>{};',sandbox);
  return sandbox;
}

test('in-flight submission remains locked when history sync finishes', async()=>{
  const ctx=await context();
  vm.runInContext("calls=0; api=async(path,opts)=>{if(!opts)return {jobs:[]};calls++;return new Promise(resolve=>release=resolve)}",ctx);
  const pending=vm.runInContext("generate('data:image/jpeg;base64,test','male')",ctx);
  await new Promise(resolve=>setImmediate(resolve));
  await vm.runInContext('syncJobs()',ctx);
  assert.equal(vm.runInContext('busy',ctx),true);
  await vm.runInContext("generate('data:image/jpeg;base64,test','male')",ctx);
  assert.equal(vm.runInContext('calls',ctx),1);
  vm.runInContext("release({job:{id:'job',created:new Date().toISOString()}})",ctx);
  await pending;
});

test('ambiguous network failure reuses idempotency key and selected model',async()=>{
  const ctx=await context();
  vm.runInContext("keys=[];api=async(path,opts)=>{keys.push(JSON.parse(opts.body).idempotencyKey);throw Error('network')}",ctx);
  await vm.runInContext("generate('data:image/jpeg;base64,test','male')",ctx);
  await vm.runInContext("generate('data:image/jpeg;base64,test','male')",ctx);
  assert.equal(vm.runInContext('keys[0]===keys[1]',ctx),true);
  assert.equal(vm.runInContext('model',ctx),'male');
  assert.equal(vm.runInContext('submitting',ctx),false);
});

test('regeneration sends the original image and original model',async()=>{
  const ctx=await context();
  vm.runInContext("sourceData=async(source)=>{sourceUsed=source;return 'data:image/jpeg;base64,original'}; api=async(path,opts)=>{sent=JSON.parse(opts.body);return {job:{id:'new',created:new Date().toISOString()}}}",ctx);
  await vm.runInContext("generate('/api/jobs/old/input','male')",ctx);
  assert.equal(vm.runInContext('sourceUsed',ctx),'/api/jobs/old/input');
  assert.equal(vm.runInContext('sent.model',ctx),'male');
  assert.equal(vm.runInContext('sent.image',ctx),'data:image/jpeg;base64,original');
});

test('unsupported native sharing opens save-and-forward fallback',async()=>{
  const ctx=await context();
  vm.runInContext("navigator={};File=class{};fetch=async()=>({ok:true,blob:async()=>({})});sheet=(title,body,buttons)=>{fallback=title;fallbackButtons=buttons}",ctx);
  await vm.runInContext("share({image:'/result',id:'one'})",ctx);
  assert.equal(vm.runInContext('fallback',ctx),'分享图片');
  assert.equal(vm.runInContext('fallbackButtons[1].label',ctx),'保存图片');
});

test('cancelled native share does not trigger an error or download',async()=>{
  const ctx=await context();
  vm.runInContext("navigator={canShare:()=>true,share:async()=>{const e=Error();e.name='AbortError';throw e}};File=class{};fetch=async()=>({ok:true,blob:async()=>({})});fallback=false;shareFallback=()=>{fallback=true};",ctx);
  await vm.runInContext("share({image:'/result',id:'one'})",ctx);
  assert.equal(vm.runInContext('fallback',ctx),false);
});

test('community text is escaped and examples are clearly identified',async()=>{
  const ctx=await context();
  vm.runInContext("posts=[{id:'safe',nickname:'<script>name</script>',productName:'<img src=x onerror=alert(1)>',note:'<b>note</b>',image:'/image',productImage:'/input'}];renderCommunity()",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.ok(html.includes('&lt;script&gt;'));
  assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
  assert.ok(!html.includes('<script>name'));
  assert.ok(html.includes('官方示例'));
});

test('navigation writes task routes to the URL hash',async()=>{
  const ctx=await context();
  vm.runInContext("navigate('#job/0123456789abcdef0123456789abcdef')",ctx);
  assert.equal(vm.runInContext('location.hash',ctx),'#job/0123456789abcdef0123456789abcdef');
});

test('home workbench foregrounds upload and keeps example content clearly marked',async()=>{
  const ctx=await context();
  vm.runInContext('jobsLoaded=true;renderMy()',ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/衣拍/);
  assert.match(html,/start-card/);
  assert.match(html,/创作历史/);
  assert.match(html,/效果示例/);
  assert.doesNotMatch(html,/my-stats|profile-card/);
});

test('model library initializes only after app APIs and toast are available',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../mockup/index.html'),'utf8');
  assert.ok(html.indexOf('app.js')<html.indexOf('models.js'));
});

test('pose workflow offers 4, 6, and 8 image counts',async()=>{
  const ctx=await context();
  vm.runInContext('renderPoseVariationPage()',ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.deepEqual(Array.from(vm.runInContext('[...app.innerHTML.matchAll(/data-count="(\\d+)"/g)].map(match=>Number(match[1]))',ctx)),[4,6,8]);
});

test('background workflow exposes the six supported scene IDs',async()=>{
  const ctx=await context();
  assert.deepEqual(Array.from(vm.runInContext('sceneTypes.map(scene=>scene.id)',ctx)),['white','studio_gray','outdoor_street','indoor_minimal','beach','cafe']);
  vm.runInContext('renderBackgroundChangePage()',ctx);
  assert.match(vm.runInContext('app.innerHTML',ctx),/accept="image\/jpeg,image\/png,image\/webp"/);
});

test('background result keeps the chosen scene visible and labels mock output honestly',async()=>{
  const ctx=await context();
  vm.runInContext("renderResult({id:'bg',model:'female',status:'succeeded',created:new Date().toISOString(),image:'/result',original:'/input',workflowType:'background_change',workflowConfig:{scene_type:'beach'},previewOnly:true})",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/背景替换 · 海边/);
  assert.match(html,/本地界面预览使用固定样例图/);
});

test('recent task image retry controls are not nested inside the task link',async()=>{
  const ctx=await context();
  vm.runInContext("history=[{id:'recent',model:'female',status:'succeeded',created:new Date().toISOString(),image:'/api/jobs/recent/result'}]",ctx);
  const html=vm.runInContext('renderWorkflowHistory()',ctx);
  assert.match(html,/<article class="workflow-recent-item">/);
  assert.equal((html.match(/<button\b/g)||[]).length,2);
  assert.match(html,/<button class="workflow-recent-open"[^>]+data-recent-job="recent"/);
});

test('workflow submission sends typed config with an idempotency key and opens its returned job',async()=>{
  const ctx=await context();
  vm.runInContext(`
    currentRoute='#workflow/pose-variation';
    navigate=route=>{location.hash=route};
    workflowUpload='data:image/jpeg;base64,test';
    calls=[];
    api=async(path,options)=>{
      calls.push({path,options});
      return {job:{id:'0123456789abcdef0123456789abcdef',status:'queued',created:'2026-11-11T00:00:00Z'}};
    };
  `,ctx);
  await vm.runInContext("submitWorkflow('pose_variation',{pose_count:6})",ctx);
  const body=JSON.parse(vm.runInContext('calls[0].options.body',ctx));
  assert.equal(vm.runInContext('calls[0].path',ctx),'/api/jobs');
  assert.equal(vm.runInContext('calls[0].options.method',ctx),'POST');
  assert.equal(body.workflowType,'pose_variation');
  assert.deepEqual(body.workflowConfig,{pose_count:6});
  assert.ok(typeof body.idempotencyKey==='string'&&body.idempotencyKey.length>0);
  assert.equal(vm.runInContext('location.hash',ctx),'#job/0123456789abcdef0123456789abcdef');
});

test('refreshing a task route reads the existing task and never posts generation',async()=>{
  const ctx=await context();
  vm.runInContext(`history=[];reads=[];renderResult=job=>{restoredId=job.id};api=async(path,options)=>{reads.push({path,method:options?.method||'GET'});return {job:{id:'0123456789abcdef0123456789abcdef',model:'female',created:'2026-11-11T00:00:00Z',status:'succeeded',image:'/result',original:'/input'}}};location.hash='#job/0123456789abcdef0123456789abcdef'`,ctx);
  await vm.runInContext('renderRoute()',ctx);
  assert.equal(vm.runInContext('restoredId',ctx),'0123456789abcdef0123456789abcdef');
  assert.equal(vm.runInContext('reads.length',ctx),1);
  assert.equal(vm.runInContext('reads[0].method',ctx),'GET');
});

test('polling does not rebuild a publish form or discard its draft',async()=>{
  const ctx=await context();
  vm.runInContext(`screen='publish';publishDrafts.set('one',{productName:'条纹上衣',note:'保留输入'});renders=0;renderPublish=()=>{renders++};api=async()=>({jobs:[{id:'pending',model:'female',created:'2026-11-11T00:00:00Z',status:'succeeded'}]})`,ctx);
  // Restore the actual poll implementation because the shared helper isolates it for submission tests.
  const source=fs.readFileSync(path.join(__dirname,'../mockup/app.js'),'utf8');
  const actualPoll=source.slice(source.indexOf('async function pollJobs()'),source.indexOf('function loadImage('));
  vm.runInContext(actualPoll,ctx);
  await vm.runInContext('pollJobs()',ctx);
  assert.equal(vm.runInContext('renders',ctx),0);
  assert.equal(vm.runInContext("publishDrafts.get('one').note",ctx),'保留输入');
});

test('pending history sorts before completed jobs, then by descending creation time',async()=>{
  const ctx=await context();
  vm.runInContext(`history=[{id:'new',status:'succeeded',created:'2026-11-11T03:00:00Z'},{id:'pending',status:'queued',created:'2026-11-11T01:00:00Z'},{id:'old',status:'failed',created:'2026-11-11T02:00:00Z'}]`,ctx);
  assert.equal(vm.runInContext("sortedJobs().map(job=>job.id).join(',')",ctx),'pending,new,old');
});

test('image retry reloads the same file without creating a task',async()=>{
  const ctx=await context();
  vm.runInContext(`
    const retryImage={complete:false,src:'/recorded.jpg',getAttribute(){return this.src},removeAttribute(){this.src=''},setAttribute(_name,value){this.src=value}};
    const retryButton={};const failure={hidden:true};
    const frame={classList:{add(){},remove(){}},querySelector(selector){return selector==='img'?retryImage:selector==='.image-error'?failure:retryButton}};
    postCount=0;api=async()=>{postCount++};watchImages({querySelectorAll(){return [frame]}});
    retryImage.onerror();failureShown=!failure.hidden;retryButton.onclick({stopPropagation(){}});
  `,ctx);
  assert.equal(vm.runInContext('failureShown',ctx),true);
  assert.equal(vm.runInContext('retryImage.src',ctx),'/recorded.jpg');
  assert.equal(vm.runInContext('postCount',ctx),0);
});

test('submission completing after navigation preserves the new draft and current route',async()=>{
  const ctx=await context();
  vm.runInContext(`currentRoute='#prepare';draft='data:image/jpeg;base64,old';api=async()=>new Promise(resolve=>release=resolve)`,ctx);
  const pending=vm.runInContext('generate()',ctx);
  await new Promise(resolve=>setImmediate(resolve));
  vm.runInContext(`currentRoute='#community';location.hash='#community';screen='community';draft='data:image/jpeg;base64,new';release({job:{id:'0123456789abcdef0123456789abcdef',status:'queued',created:new Date().toISOString()}})`,ctx);
  await pending;
  assert.equal(vm.runInContext('draft',ctx),'data:image/jpeg;base64,new');
  assert.equal(vm.runInContext('location.hash',ctx),'#community');
  assert.equal(vm.runInContext('busy',ctx),true);
});
