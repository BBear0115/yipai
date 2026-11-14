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
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../mockup/studio.js'),'utf8'),sandbox);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../mockup/app.js'),'utf8'),sandbox);
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

test('community posts overlay the product and remake bubble, with like, bookmark and share actions',async()=>{
  const ctx=await context();
  vm.runInContext("posts=[{id:'0123456789abcdef0123456789abcdef',nickname:'访客',productName:'衬衫',note:'好穿',image:'/image',productImage:'/input',created:new Date().toISOString()}];renderCommunity()",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/feed-product-thumb[\s\S]*feed-remake[^>]*>[\s\S]*?拍同款/);
  assert.match(html,/data-like="0123456789abcdef0123456789abcdef"[^>]*>[\s\S]*?<span>好看<\/span>/);
  const actions=html.slice(html.indexOf('feed-actions'));
  assert.ok(actions.indexOf('好看')<actions.indexOf('收藏')&&actions.indexOf('收藏')<actions.indexOf('分享'));
  assert.doesNotMatch(html,/查看详情|data-post=/);
});

test('retired post detail links fall back to the community feed',async()=>{
  const ctx=await context();
  vm.runInContext("location.hash='#post/example-dress'",ctx);
  await vm.runInContext('renderRoute()',ctx);
  assert.equal(vm.runInContext('location.hash',ctx),'#community');
});

test('navigation writes task routes to the URL hash',async()=>{
  const ctx=await context();
  vm.runInContext("navigate('#job/0123456789abcdef0123456789abcdef')",ctx);
  assert.equal(vm.runInContext('location.hash',ctx),'#job/0123456789abcdef0123456789abcdef');
});

test('create page keeps the immersive hero and the creation entries',async()=>{
  const ctx=await context();
  vm.runInContext("jobsLoaded=true;screen='home';renderCreate()",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/衣拍/);
  assert.match(html,/home-hero/);
  assert.match(html,/home-action-primary/);
  assert.match(html,/拍同款/);
  assert.match(html,/创意裂变/);
  assert.match(html,/home-slogan/);
  assert.doesNotMatch(html,/home-carousel|home-mini-actions|我的作品|社区灵感/);
  assert.doesNotMatch(html,/创作历史|一件商品，换种呈现|edit-profile/);
  assert.doesNotMatch(html,/把每一件单品|衣拍灵感|开始创作|官方穿搭灵感|看看示例/);
});

test('my page is a profile header with stats, a settings entry and works / saved tabs',async()=>{
  const ctx=await context();
  vm.runInContext("jobsLoaded=true;screen='my';renderMy()",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/edit-profile/);
  assert.match(html,/id="my-settings"/);
  assert.deepEqual(Array.from(vm.runInContext('[...app.innerHTML.matchAll(/data-my-tab="(\\w+)"/g)].map(match=>match[1])',ctx)),['works','saved']);
  assert.match(html,/作品[\s\S]*已发布[\s\S]*获赞/);
  assert.doesNotMatch(html,/home-hero|效果示例|tasks-link|batch-upload/);
});

test('dock routes 创作 to the create page and 我的 to its own page',async()=>{
  const ctx=await context();
  vm.runInContext("location.hash='#my'",ctx);
  await vm.runInContext('renderRoute()',ctx);
  assert.equal(vm.runInContext('screen',ctx),'my');
  vm.runInContext("location.hash='#home'",ctx);
  await vm.runInContext('renderRoute()',ctx);
  assert.equal(vm.runInContext('screen',ctx),'home');
});

test('开拍 offers camera and library choices, each opening its own file input',async()=>{
  const ctx=await context();
  vm.runInContext(`
    picked=[];input.click=()=>picked.push('library');cameraInput.click=()=>picked.push('camera');
    buttons={};layer={querySelectorAll:()=>['camera','library'].map(pick=>buttons[pick]={dataset:{pick}})};
    openOverlay=html=>{sheetHtml=html;return layer};
    pickImage();buttons.camera.onclick();buttons.library.onclick();
  `,ctx);
  assert.match(vm.runInContext('sheetHtml',ctx),/拍照[\s\S]*相册 \/ 文件/);
  assert.deepEqual(Array.from(vm.runInContext('picked',ctx)),['camera','library']);
  assert.match(fs.readFileSync(path.join(__dirname,'../mockup/index.html'),'utf8'),/id="camera-input"[^>]*capture="environment"/);
});

test('recreating an official example loads its product photo into the existing prepare flow',async()=>{
  const ctx=await context();
  vm.runInContext("prepared=false;prepare=()=>{prepared=true};toast=()=>{};recreatePost({productImage:'assets/community/floral-dress-product.jpg'})",ctx);
  assert.equal(vm.runInContext('draft',ctx),'assets/community/floral-dress-product.jpg');
  assert.equal(vm.runInContext('prepared',ctx),true);
});

test('model library initializes only after app APIs and toast are available',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../mockup/index.html'),'utf8');
  assert.ok(html.indexOf('app.js')<html.indexOf('models.js'));
});

test('创意裂变 offers 4, 6, and 8 pose counts and only the two variation modes',async()=>{
  const ctx=await context();
  vm.runInContext("screen='variations';renderVariations()",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.deepEqual(Array.from(vm.runInContext('[...app.innerHTML.matchAll(/data-studio-count="(\\d+)"/g)].map(match=>Number(match[1]))',ctx)),[4,6,8]);
  assert.deepEqual(Array.from(vm.runInContext('[...app.innerHTML.matchAll(/data-studio-mode="(\\w+)"/g)].map(match=>match[1])',ctx)),['pose','background']);
  assert.match(html,/每个姿势输出一张独立图片/);
  assert.doesNotMatch(html,/虚拟试穿|服装上身|创作历史|最近作品|最近任务|edit-profile|从左侧/);
});

test('pose result displays each output separately and offers all-image download',async()=>{
  const ctx=await context();
  vm.runInContext("renderResult({id:'poses',model:'female',status:'succeeded',created:new Date().toISOString(),image:'/pose-1',images:['/pose-1','/pose-2','/pose-3','/pose-4'],original:'/input',workflowType:'pose_variation',workflowConfig:{pose_count:4}})",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.equal((html.match(/data-pose-image=/g)||[]).length,4);
  assert.match(html,/第 <span id="pose-result-index">1<\/span> 张 \/ 共 4 张独立图片/);
  assert.match(html,/下载全部 4 张/);
  assert.match(html,/data-pose-image="3" aria-label="查看第 4 张图片"/);
  assert.doesNotMatch(html,/宫格/);
});

test('pose thumbnail selection controls the large image, viewer, sharing, and saved output',async()=>{
  const ctx=await context();
  vm.runInContext(`
    controls={};
    originalQuery=document.querySelector;
    document.querySelector=selector=>controls[selector]||=(originalQuery(selector));
    poseButtons=Array.from({length:4},(_,index)=>({dataset:{poseImage:String(index)},classList:{toggle(){}},setAttribute(name,value){this[name]=value}}));
    document.querySelectorAll=selector=>selector==='[data-pose-image]'?poseButtons:[];
    save=result=>{saved=result};
    openViewer=result=>{viewed=result};
    shareOptions=result=>{shared=result};
    renderResult({id:'poses',model:'female',status:'succeeded',image:'/pose-1',images:['/pose-1','/pose-2','/pose-3','/pose-4'],original:'/input',workflowType:'pose_variation'});
    poseButtons[1].onclick();
    controls['#save'].onclick();
    controls['#result-primary'].onclick();
    controls['#share'].onclick();
  `,ctx);
  assert.match(vm.runInContext("controls['#result-primary'].innerHTML",ctx),/src="\/pose-2"/);
  assert.equal(vm.runInContext('saved.image',ctx),'/pose-2');
  assert.equal(vm.runInContext('saved.imageIndex',ctx),2);
  assert.equal(vm.runInContext('viewed.image',ctx),'/pose-2');
  assert.equal(vm.runInContext('shared.image',ctx),'/pose-2');
  assert.equal(vm.runInContext("poseButtons[1]['aria-pressed']",ctx),'true');
  assert.equal(vm.runInContext("controls['#pose-result-index'].textContent",ctx),'2');
});

test('pose progress advances as individual image files complete',async()=>{
  const ctx=await context();
  const code=fs.readFileSync(path.join(__dirname,'../mockup/app.js'),'utf8');
  vm.runInContext(code.slice(code.indexOf('function waiting()'),code.indexOf('function renderJob(')),ctx);
  vm.runInContext(code.slice(code.indexOf('async function pollJobs()'),code.indexOf('function loadImage(')),ctx);
  vm.runInContext(`
    controls={};
    originalQuery=document.querySelector;
    document.querySelector=selector=>controls[selector]||=(originalQuery(selector));
    active={id:'poses',model:'female',status:'running',workflowType:'pose_variation',workflowConfig:{pose_count:4},images:['/pose-1']};
    history=[active];
    waiting();
    api=async()=>({jobs:[{...active,images:['/pose-1','/pose-2','/pose-3']}]});
  `,ctx);
  assert.match(vm.runInContext('app.innerHTML',ctx),/已生成 1 \/ 4 张/);
  await vm.runInContext('pollJobs()',ctx);
  assert.equal(vm.runInContext("controls['#task-progress'].textContent",ctx),'已生成 3 / 4 张');
  assert.equal(vm.runInContext("controls['#task-progress'].hidden",ctx),false);
});

test('换背景 exposes the six supported scene IDs',async()=>{
  const ctx=await context();
  vm.runInContext("screen='variations';renderVariations('background')",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.deepEqual(Array.from(vm.runInContext('[...app.innerHTML.matchAll(/data-studio-scene="(\\w+)"/g)].map(match=>match[1])',ctx)),['white','studio_gray','outdoor_street','indoor_minimal','beach','cafe']);
  assert.match(html,/accept="image\/jpeg,image\/png,image\/webp"/);
});

test('background result keeps the chosen scene visible and labels mock output honestly',async()=>{
  const ctx=await context();
  vm.runInContext("renderResult({id:'bg',model:'female',status:'succeeded',created:new Date().toISOString(),image:'/result',original:'/input',workflowType:'background_change',workflowConfig:{scene_type:'beach'},previewOnly:true})",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/背景替换 · 海边/);
  assert.match(html,/旧的演示样例记录/);
});

test('real background output has no sample notice',async()=>{
  const ctx=await context();
  vm.runInContext("renderResult({id:'live-bg',model:'female',status:'succeeded',created:new Date().toISOString(),image:'/result',original:'/input',workflowType:'background_change',workflowConfig:{scene_type:'cafe'},previewOnly:false})",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/背景替换 · 咖啡馆/);
  assert.doesNotMatch(html,/preview-output-notice/);
});

test('old workbench links redirect to the matching page',async()=>{
  const ctx=await context();
  for (const [from,to] of [['#workflows','#variations'],['#workflow/pose-variation','#variations'],['#workflow/background-change','#variations/background'],['#create','#home'],['#create/background','#variations/background']]) {
    vm.runInContext(`location.hash='${from}'`,ctx);
    await vm.runInContext('renderRoute()',ctx);
    assert.equal(vm.runInContext('location.hash',ctx),to,from);
  }
});

test('创意裂变 picker offers camera, album and finished works, and a picked work becomes the upload',async()=>{
  const ctx=await context();
  vm.runInContext(`
    jobsLoaded=true;
    history=[{id:'done',status:'succeeded',image:'/api/jobs/done/result',model:'female',date:'11/14',created:'2026-11-14T00:00:00Z'},{id:'running',status:'running',model:'female',date:'11/14',created:'2026-11-14T01:00:00Z'}];
    screen='variations';studioState.upload='';renderVariations('pose');
  `,ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/data-studio-camera/);
  assert.match(html,/data-studio-upload/);
  assert.match(html,/capture="environment"/);
  assert.deepEqual(Array.from(vm.runInContext('[...app.innerHTML.matchAll(/data-studio-work="(\\w+)"/g)].map(match=>match[1])',ctx)),['done']);
  vm.runInContext("studioUseWork('done')",ctx);
  assert.equal(vm.runInContext('studioState.upload',ctx),'/api/jobs/done/result');
});

test('创意裂变 submission sends typed config with an idempotency key and opens its returned job',async()=>{
  const ctx=await context();
  vm.runInContext(`
    screen='variations';
    currentRoute='#variations';
    navigate=route=>{location.hash=route};
    renderVariations=()=>{};
    studioState.mode='pose';studioState.poseCount=6;
    studioState.upload='data:image/jpeg;base64,test';
    calls=[];
    api=async(path,options)=>{
      calls.push({path,options});
      return {job:{id:'0123456789abcdef0123456789abcdef',status:'queued',created:'2026-11-11T00:00:00Z'}};
    };
  `,ctx);
  await vm.runInContext('studioSubmit()',ctx);
  const body=JSON.parse(vm.runInContext('calls[0].options.body',ctx));
  assert.equal(vm.runInContext('calls[0].path',ctx),'/api/jobs');
  assert.equal(vm.runInContext('calls[0].options.method',ctx),'POST');
  assert.equal(body.workflowType,'pose_variation');
  assert.deepEqual(body.workflowConfig,{pose_count:6});
  assert.ok(typeof body.idempotencyKey==='string'&&body.idempotencyKey.length>0);
  assert.equal(vm.runInContext('location.hash',ctx),'#job/0123456789abcdef0123456789abcdef');
  assert.equal(vm.runInContext('history[0].workflowType',ctx),'pose_variation');
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

 test('创意裂变 and history routes coexist with the current home navigation',async()=>{
  const ctx=await context();
  vm.runInContext("location.hash='#variations/background'",ctx);
  await vm.runInContext('renderRoute()',ctx);
  assert.equal(vm.runInContext('screen',ctx),'variations');
  assert.equal(vm.runInContext('studioState.mode',ctx),'background');
  vm.runInContext("location.hash='#history'",ctx);
  await vm.runInContext('renderRoute()',ctx);
  assert.equal(vm.runInContext('screen',ctx),'my');
  assert.match(vm.runInContext('app.innerHTML',ctx),/data-my-tab="works"/);
});
