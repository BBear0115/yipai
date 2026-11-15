const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {webcrypto} = require('node:crypto');

async function context(initialHash = '') {
  const location = {hash:initialHash};
  const listeners = {};
  const classList = {add(){},remove(){},toggle(){}};
  const element = {style:{setProperty(){}},classList,setAttribute(){},addEventListener(){},querySelector(){return {...element};},querySelectorAll(){return [];},focus(){},appendChild(){},insertBefore(){},replaceWith(){},remove(){},click(){},getAttribute(){return '';},setAttribute(){},removeAttribute(){},children:[],innerHTML:'',textContent:'',dataset:{},inert:false};
  const window = {scrollTo(){},addEventListener(name,fn){listeners[name]=fn;},history:{pushState(_state,_title,hash){location.hash=hash;},replaceState(_state,_title,hash){location.hash=hash;}}};
  const document = {body:{classList,appendChild(){}},querySelector:()=>({...element}),querySelectorAll:()=>[],getElementById:()=>({...element}),addEventListener(name,fn){listeners[`document:${name}`]=fn;},removeEventListener(){},createElement(tag){if(tag==='template')return {content:{firstElementChild:{...element}},set innerHTML(_value){}};return {...element};}};
  const sandbox = vm.createContext({
    document,window,location,localStorage:{getItem(){},setItem(){},removeItem(){}},crypto:webcrypto,
    setTimeout(){return 1;},clearTimeout(){},setInterval(){return 1;},clearInterval(){},
    fetch:async()=>({ok:true,json:async()=>({ready:true,jobs:[],posts:[]})})
  });
  // Load the same modules, in the same order, as the browser entry point.
  const html = fs.readFileSync(path.join(__dirname,'../mockup/index.html'),'utf8');
  for (const [,src] of html.matchAll(/<script src="([^"?]+)(?:\?[^\"]*)?"><\/script>/g)) {
    vm.runInContext(fs.readFileSync(path.join(__dirname,'../mockup',src),'utf8'),sandbox,{filename:src});
  }
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

test('community posts overlay the product and a 做参考 bubble, with like, bookmark and share actions',async()=>{
  const ctx=await context();
  vm.runInContext("posts=[{id:'0123456789abcdef0123456789abcdef',nickname:'访客',productName:'衬衫',note:'好穿',image:'/image',productImage:'/input',created:new Date().toISOString()}];renderCommunity()",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/feed-product-thumb[\s\S]*feed-remake[^>]*data-reference="0123456789abcdef0123456789abcdef"[^>]*>[\s\S]*?做参考/);
  assert.doesNotMatch(html,/拍同款/);
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

test('published works show a badge in 我的 and their post details and stats on the result page',async()=>{
  const ctx=await context();
  vm.runInContext("history=[{id:'a',status:'succeeded',image:'/a',date:'11/14',created:'2026-11-14T00:00:00Z',post:{productName:'碎花裙',note:'花色还原好',created:'2026-11-14T00:00:00Z',likes:3,saves:2,remakes:1}},{id:'b',status:'succeeded',image:'/b',date:'11/14',created:'2026-11-14T00:00:00Z',post:null}]",ctx);
  assert.match(vm.runInContext("historyCard(history[0])",ctx),/status-badge published">已发布/);
  assert.doesNotMatch(vm.runInContext("historyCard(history[1])",ctx),/已发布/);
  vm.runInContext("renderResult(history[0])",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/id="delete-job"/);
  assert.match(html,/碎花裙[\s\S]*花色还原好/);
  assert.match(html,/<dd>3<\/dd><dt>觉得好看[\s\S]*<dd>2<\/dd><dt>收藏[\s\S]*<dd>1<\/dd><dt>做参考/);
});

test('deleting a published work asks a second time before removing the post',async()=>{
  const ctx=await context();
  vm.runInContext(`
    titles=[];calls=[];sheet=(title,body,buttons)=>{titles.push(title);lastButtons=buttons};
    api=async(path,options)=>{calls.push(path+' '+options.method);return {deleted:true,postDeleted:true}};
    myPage=()=>{};toast=()=>{};
    history=[{id:'a',status:'succeeded',post:{productName:'碎花裙',likes:1,saves:0}}];posts=[{id:'a'}];
    confirmDelete(history[0]);
    lastButtons[1].action();
  `,ctx);
  assert.deepEqual(Array.from(vm.runInContext('titles',ctx)),['删除这张作品？','这张作品已发布到社区']);
  assert.equal(vm.runInContext('calls.length',ctx),0);
  await vm.runInContext('lastButtons[1].action()',ctx);
  assert.deepEqual(Array.from(vm.runInContext('calls',ctx)),['/api/jobs/a DELETE']);
  assert.equal(vm.runInContext('history.length+posts.length',ctx),0);
  vm.runInContext("titles=[];calls=[];history=[{id:'b',status:'succeeded',post:null}];confirmDelete(history[0])",ctx);
  await vm.runInContext('lastButtons[1].action()',ctx);
  assert.deepEqual(Array.from(vm.runInContext('titles',ctx)),['删除这张作品？']);
  assert.deepEqual(Array.from(vm.runInContext('calls',ctx)),['/api/jobs/b DELETE']);
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

test('the library option advertises multi-select and hands several photos to batch creation',async()=>{
  const ctx=await context();
  vm.runInContext(`
    layer={querySelectorAll:()=>[]};openOverlay=html=>{sheetHtml=html;return layer};pickImage();
    batched=null;openBatchUpload=files=>{batched=files};
    input.files=[{name:'a.jpg'},{name:'b.jpg'}];
  `,ctx);
  assert.match(vm.runInContext('sheetHtml',ctx),/相册 \/ 文件[\s\S]*最多 10 张/);
  await vm.runInContext('input.onchange({target:input})',ctx);
  assert.deepEqual(Array.from(vm.runInContext('batched.map(file=>file.name)',ctx)),['a.jpg','b.jpg']);
  const html=fs.readFileSync(path.join(__dirname,'../mockup/index.html'),'utf8');
  assert.match(html,/id="file-input"[^>]*multiple/);
  assert.doesNotMatch(html,/id="camera-input"[^>]*multiple/);
});

test('settings no longer offer the task list or batch upload',async()=>{
  const ctx=await context();
  vm.runInContext("sheet=(title,body,buttons)=>{labels=buttons.map(button=>button.label)};mySettings()",ctx);
  const labels=Array.from(vm.runInContext('labels',ctx));
  assert.ok(!labels.includes('任务列表')&&!labels.includes('批量上传'));
  assert.ok(!fs.existsSync(path.join(__dirname,'../mockup/tasks.js')));
});

test('做参考 carries a post\'s effect photo into 拍同款 as the reference, without touching the 开拍 draft',async()=>{
  const ctx=await context();
  vm.runInContext("reacted=[];react=async(post,kind)=>{reacted.push(kind)};useAsReference({id:'example-dress',image:'assets/community/floral-dress-result.jpg',productImage:'assets/community/floral-dress-product.jpg',example:true})",ctx);
  assert.equal(vm.runInContext('tryonDraftState.references[0]',ctx),'assets/community/floral-dress-result.jpg');
  assert.equal(vm.runInContext('remakeReferencePosts.size',ctx),0);
  assert.equal(vm.runInContext('location.hash',ctx),'#remake');
  assert.equal(vm.runInContext('draft',ctx),null);
  // Choosing it is not a remake yet; the count only rises once a job is submitted.
  assert.equal(vm.runInContext('reacted.length',ctx),0);
});

test('home 拍同款 exposes reference, garment roles, model, detail and work source controls',async()=>{
  const ctx=await context('#remake');
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.equal(vm.runInContext('screen',ctx),'remake');
  assert.match(html,/上装 \/ 下装/);
  assert.match(html,/连体 \/ 全身/);
  assert.match(html,/参考照片/);
  assert.match(html,/人物参考/);
  assert.match(html,/服装细节参考/);
  assert.match(html,/data-tryon-camera="reference"/);
  assert.match(html,/data-remake-work-picker="garment"/);
  assert.match(html,/data-remake-work-picker="reference"/);
  assert.match(html,/id="generate"[^>]*disabled/);
  assert.equal(vm.runInContext('tryonDraftState.outputCount',ctx),3);
});

test('picking a finished work preserves its garment and identity as distinct inputs',async()=>{
  const ctx=await context();
  vm.runInContext("jobsLoaded=true;screen='remake';history=[{id:'done',status:'succeeded',image:'/api/jobs/done/result',model:'female',date:'11/14'}];tryonDraftState.references=['data:image/jpeg;base64,ref'];remakeUseWork('done')",ctx);
  assert.equal(vm.runInContext('tryonDraftState.garments.upper',ctx),'/api/jobs/done/result');
  assert.equal(vm.runInContext('tryonDraftState.modelImage',ctx),'/api/jobs/done/result');
  assert.match(vm.runInContext('app.innerHTML',ctx),/沿用作品中的人物/);
  const payload=JSON.parse(JSON.stringify(vm.runInContext('remakePayload()',ctx)));
  assert.equal(payload.workflowType,'remake');
  assert.deepEqual(payload.inputImages.map(item=>item.role),['upper','reference','model']);
  assert.equal(payload.workflowConfig.output_count,3);
});

test('拍同款 submits role inputs, records 做参考 after success, and preserves the 开拍 draft',async()=>{
  const ctx=await context();
  vm.runInContext(`
    screen='remake';currentRoute='#remake';navigate=route=>{location.hash=route};
    draft='data:image/jpeg;base64,basic';
    posts=[{id:'0123456789abcdef0123456789abcdef',image:'/api/posts/0123456789abcdef0123456789abcdef/result'}];
    reacted=[];react=async(post,kind,active)=>{reacted.push([post.id,kind,active])};
    sourceData=async source=>source.startsWith('data:')?source:'data:image/jpeg;base64,reference';
    useAsReference(posts[0]);
    tryonDraftState.garments.upper='data:image/jpeg;base64,product';model='female';
    calls=[];api=async(path,options)=>{calls.push(JSON.parse(options.body));return {job:{id:'fedcba9876543210fedcba9876543210',status:'queued',created:'2026-11-14T00:00:00Z',workflowType:'remake'}}};
  `,ctx);
  await vm.runInContext('submitTryon()',ctx);
  const body=JSON.parse(JSON.stringify(vm.runInContext('calls[0]',ctx)));
  assert.equal(body.workflowType,'remake');
  assert.equal(body.workflowConfig.output_count,3);
  assert.equal(body.image,'data:image/jpeg;base64,product');
  assert.deepEqual(body.inputImages.map(item=>item.role),['upper','reference']);
  assert.equal(body.inputImages[1].image,'data:image/jpeg;base64,reference');
  assert.ok(body.idempotencyKey.length>0);
  assert.deepEqual(JSON.parse(JSON.stringify(vm.runInContext('reacted',ctx))),[['0123456789abcdef0123456789abcdef','remake',true]]);
  assert.equal(vm.runInContext('location.hash',ctx),'#job/fedcba9876543210fedcba9876543210');
  assert.equal(vm.runInContext('tryonDraftState.references.length',ctx),0);
  assert.equal(vm.runInContext('draft',ctx),'data:image/jpeg;base64,basic');
});

test('拍同款 results show three photos, the reference, and regenerate with the same reference',async()=>{
  const ctx=await context();
  vm.runInContext(`
    sent=[];generate=async(source,model,workflow)=>{sent.push({source,model,workflow})};
    job={id:'remake',model:'male',status:'succeeded',created:new Date().toISOString(),image:'/r-1',images:['/r-1','/r-2','/r-3'],original:'/input',reference:'/api/jobs/remake/reference',workflowType:'remake',workflowConfig:{model_source:'preset',model:'male'}};
    renderResult(job);
  `,ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.equal((html.match(/data-pose-image=/g)||[]).length,3);
  assert.match(html,/共 3 张独立图片/);
  assert.match(html,/拍同款第 1 张/);
  assert.match(html,/id="result-reference"[\s\S]*参考图/);
  assert.match(html,/商品原图/);
  assert.equal(vm.runInContext('poseProgress({workflowType:"remake",images:["/r-1"]})',ctx),'已生成 1 / 3 张');
});

test('model library initializes only after app APIs and toast are available',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../mockup/index.html'),'utf8');
  assert.ok(html.indexOf('app.js')<html.indexOf('models.js'));
});

test('directly opening remake renders the advanced workspace before the model library loads',async()=>{
  const ctx=await context('#remake');
  assert.equal(vm.runInContext('screen',ctx),'remake');
  assert.match(vm.runInContext('app.innerHTML',ctx),/服装细节参考/);
  assert.equal(vm.runInContext('selectedModelId',ctx),null);
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

test('comparison modes restore image opening and dispose sliders when leaving the result',async()=>{
  const ctx=await context();
  vm.runInContext(`
    controls={};
    originalQuery=document.querySelector;
    document.querySelector=selector=>controls[selector]||=(originalQuery(selector));
    modeButtons=['side-by-side','slider'].map(mode=>({dataset:{mode},classList:{toggle(){}}}));
    document.querySelectorAll=selector=>selector==='[data-mode]'?modeButtons:[];
    destroyed=0;
    createCompareSlider=()=>({destroy(){destroyed++}});
    viewed=[];openViewer=item=>viewed.push(item.image);
    renderResult({id:'result',model:'female',status:'succeeded',image:'/effect',original:'/input'});
    modeButtons[1].onclick();
  `,ctx);
  assert.equal(vm.runInContext("controls['#result-primary'].onclick",ctx),null);
  vm.runInContext(`
    modeButtons[0].onclick();
    controls['#result-primary'].onclick();
    controls['#result-primary'].onkeydown({key:'Enter',preventDefault(){}});
    modeButtons[1].onclick();
    setScreen('home',true);
  `,ctx);
  assert.deepEqual(Array.from(vm.runInContext('viewed',ctx)),['/effect','/effect']);
  assert.equal(vm.runInContext('destroyed',ctx),2);
});

test('single image export omits an absent image index and retains explicit gallery indices',async()=>{
  const ctx=await context();
  vm.runInContext(`
    links=[];
    document.createElement=()=>({click(){links.push(this)},remove(){}});
    exportJob={image:'/effect',workflowType:'background_change',workflowConfig:{scene_type:'beach'},created:'2026-11-15T00:00:00Z'};
    downloadSingleImage(exportJob);
    downloadSingleImage(exportJob,'/effect-2',2);
  `,ctx);
  const files=Array.from(vm.runInContext('links.map(link=>link.download)',ctx));
  assert.match(files[0],/^衣拍_背景替换_海边_\d{8}_\d{6}\.jpg$/);
  assert.match(files[1],/^衣拍_背景替换_海边_\d{8}_\d{6}_2\.jpg$/);
});

test('batch queue saturation preserves unsubmitted pictures and their idempotency keys for retry',async()=>{
  const ctx=await context();
  vm.runInContext(`
    controls={};
    originalQuery=document.querySelector;
    layer=originalQuery('layer');
    layer.querySelector=selector=>controls[selector]||=(originalQuery(selector));
    openOverlay=()=>layer;closeOverlay=()=>{};watchImages=()=>{};
    revoked=[];URL={revokeObjectURL:url=>revoked.push(url)};
    batchFiles=['one','two','three'].map(id=>({name:id,preview:'blob:'+id,data:'image:'+id,idempotencyKey:id}));
    calls=[];
    api=async(path,options)=>{
      calls.push(JSON.parse(options.body));
      if(calls.length>1)throw Error('排队任务已达上限');
      return {job:{id:'submitted',model:'female',status:'queued',created:new Date().toISOString()},queueCount:1};
    };
    openBatchResults=(jobs,message)=>{batchNotice=message};
    openBatchUpload([],true);
  `,ctx);
  await vm.runInContext("controls['#batch-submit'].onclick()",ctx);
  assert.deepEqual(Array.from(vm.runInContext('batchFiles.map(file=>file.idempotencyKey)',ctx)),['two','three']);
  assert.deepEqual(Array.from(vm.runInContext('revoked',ctx)),['blob:one']);
  assert.match(vm.runInContext('batchNotice',ctx),/2 张未提交/);
  assert.equal(vm.runInContext('batchSubmitting',ctx),false);
});

test('leaving generation cleans up its progress animation',async()=>{
  const ctx=await context();
  const code=fs.readFileSync(path.join(__dirname,'../mockup/app.js'),'utf8');
  vm.runInContext(code.slice(code.indexOf('function waiting()'),code.indexOf('function renderJob(')),ctx);
  vm.runInContext(`
    destroyed=0;createProgressStage=()=>({destroy(){destroyed++}});
    active={id:'job',model:'female',status:'queued'};
    waiting();
    navigate('#home');
  `,ctx);
  assert.equal(vm.runInContext('destroyed',ctx),1);
  assert.equal(vm.runInContext('progressStage',ctx),null);
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

test('try-on lower-only submission keeps gender separate from library model ID',async()=>{
  const ctx=await context();
  vm.runInContext(`
    tryonDraftState={clothingMode:'multi',garments:{upper:null,lower:'data:image/jpeg;base64,lower',single:null},references:[],modelImage:null,detailsEnabled:false,details:{upper:[],lower:[],single:[]},outputCount:1,instruction:''};
    selectedModelId='0123456789abcdef0123456789abcdef';
    currentRoute='#remake';screen='remake';
    calls=[];navigate=route=>{location.hash=route};
    api=async(path,options)=>{calls.push({path,options});return {job:{id:'abcdef0123456789abcdef0123456789',status:'queued',created:new Date().toISOString()}}};
  `,ctx);
  const source=vm.runInContext('buildTryonWorkflow()',ctx);
  assert.equal(vm.runInContext('tryonTotalOutputCount()',ctx),1);
  ctx.workflowForTest=source;
  await vm.runInContext("generate(workflowForTest.source,'male',workflowForTest)",ctx);
  const body=JSON.parse(vm.runInContext('calls[0].options.body',ctx));
  assert.equal(body.model,'male');
  assert.equal(body.modelId,'0123456789abcdef0123456789abcdef');
  assert.equal(body.workflowType,'remake');
  assert.deepEqual(body.workflowConfig,{clothing_mode:'multi',output_count:1,instruction:''});
  assert.equal(body.image,'data:image/jpeg;base64,lower');
  assert.deepEqual(body.inputImages.map(item=>item.role),['lower']);
  assert.ok(!body.inputImages.some(item=>item.role==='model'));
});

test('try-on single garment and uploaded model photos submit as separate roles',async()=>{
  const ctx=await context();
  vm.runInContext(`
    tryonDraftState={clothingMode:'single',garments:{upper:'data:image/jpeg;base64,inactive-upper',lower:null,single:'data:image/jpeg;base64,dress'},references:[],modelImage:'data:image/jpeg;base64,face',detailsEnabled:false,details:{upper:[],lower:[],single:[]},outputCount:1,instruction:''};
    selectedModelId='';currentRoute='#remake';screen='remake';calls=[];navigate=route=>{location.hash=route};
    api=async(path,options)=>{calls.push({path,options});return {job:{id:'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',status:'queued',created:new Date().toISOString()}}};
  `,ctx);
  const workflow=vm.runInContext('buildTryonWorkflow()',ctx);
  ctx.workflowForTest=workflow;
  await vm.runInContext("generate(workflowForTest.source,'female',workflowForTest)",ctx);
  const body=JSON.parse(vm.runInContext('calls[0].options.body',ctx));
  assert.equal(body.workflowConfig.clothing_mode,'single');
  assert.deepEqual(body.inputImages.map(item=>item.role),['single','model']);
  assert.equal(body.modelId,undefined);
  assert.equal(body.image,'data:image/jpeg;base64,dress');
});

test('开拍 prepares one product while 拍同款 contains the garment workbench',async()=>{
  const ctx=await context();
  vm.runInContext("draft='data:image/png;base64,product';location.hash='#prepare';currentRoute='';renderRoute()",ctx);
  assert.equal(vm.runInContext('location.hash',ctx),'#prepare');
  assert.match(vm.runInContext('app.innerHTML',ctx),/商品原图/);
  assert.doesNotMatch(vm.runInContext('app.innerHTML',ctx),/服装细节参考|data-clothing-mode|data-tryon-upload/);
  vm.runInContext("location.hash='#remake';renderRoute()",ctx);
  assert.equal(vm.runInContext('location.hash',ctx),'#remake');
  assert.match(vm.runInContext('app.innerHTML',ctx),/上装 \/ 下装/);
  assert.match(vm.runInContext('app.innerHTML',ctx),/连体 \/ 全身/);
  assert.match(vm.runInContext('app.innerHTML',ctx),/上传上装/);
  assert.match(vm.runInContext('app.innerHTML',ctx),/上传下装/);
  assert.equal(vm.runInContext("tryonDraftState.clothingMode",ctx),'multi');
});

test('开拍 submits only its product and model, preserving the advanced remake draft',async()=>{
  const ctx=await context();
  vm.runInContext(`
    screen='prepare';currentRoute='#prepare';draft='data:image/jpeg;base64,basic';
    tryonDraftState.garments.upper='data:image/jpeg;base64,advanced';
    tryonDraftState.references=['data:image/jpeg;base64,reference'];
    selectedModelId='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
    controls={};document.querySelector=selector=>controls[selector]||={classList:{toggle(){}},setAttribute(){},addEventListener(){},querySelector(){return {innerHTML:''}}};
    document.querySelectorAll=()=>[];
    navigate=()=>{};api=async(path,options)=>{sent=JSON.parse(options.body);return {job:{id:'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',status:'queued',created:new Date().toISOString()}}};
    renderPrepare();controls['#generate'].onclick();
  `,ctx);
  await new Promise(resolve=>setImmediate(resolve));
  const body=JSON.parse(JSON.stringify(vm.runInContext('sent',ctx)));
  assert.equal(body.image,'data:image/jpeg;base64,basic');
  assert.equal(body.modelId,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
  assert.equal(body.inputImages,undefined);
  assert.equal(body.workflowConfig,undefined);
  assert.equal(body.reference,undefined);
  assert.equal(vm.runInContext('tryonDraftState.garments.upper',ctx),'data:image/jpeg;base64,advanced');
  assert.equal(vm.runInContext('tryonDraftState.references.length',ctx),1);
});

test('拍同款 still blocks submission without an active garment',async()=>{
  const ctx=await context();
  vm.runInContext(`tryonDraftState.references=['data:image/jpeg;base64,reference'];calls=0;generate=async()=>{calls++};showTryonError=message=>lastError=message;`,ctx);
  await vm.runInContext('submitTryon()',ctx);
  assert.equal(vm.runInContext('calls',ctx),0);
  assert.match(vm.runInContext('lastError',ctx),/主商品图/);
});

test('拍同款 enables and submits upper, lower, paired or single garments without a reference',async t=>{
  for (const [mode,roles] of [['multi',['upper']],['multi',['lower']],['multi',['upper','lower']],['single',['single']]]) {
    await t.test(roles.join('+'),async()=>{
      const ctx=await context('#remake');
      ctx.clothingModeForTest=mode;ctx.rolesForTest=roles;
      vm.runInContext(`
        tryonDraftState.clothingMode=clothingModeForTest;
        for(const role of rolesForTest) tryonDraftState.garments[role]='data:image/jpeg;base64,'+role;
        draft='data:image/jpeg;base64,basic';model='male';
        renderTryonStudio();calls=[];navigate=route=>{location.hash=route};
        api=async(path,options)=>{calls.push(JSON.parse(options.body));return {job:{id:'new',status:'queued',created:new Date().toISOString()}}};
      `,ctx);
      const html=vm.runInContext('app.innerHTML',ctx);
      assert.doesNotMatch(html,/id="generate"[^>]*disabled/);
      assert.match(html,/<h2>生成数量<\/h2>/);
      await vm.runInContext('submitTryon()',ctx);
      const body=JSON.parse(JSON.stringify(vm.runInContext('calls[0]',ctx)));
      assert.equal(body.workflowType,'remake');
      assert.equal(body.workflowConfig.clothing_mode,mode);
      assert.equal(body.workflowConfig.output_count,3);
      assert.equal(body.workflowConfig.shooting_style,'auto');
      assert.match(html,/<h2>拍摄方向<\/h2>/);
      assert.deepEqual(body.inputImages.map(item=>item.role),roles);
      assert.equal(body.image,`data:image/jpeg;base64,${roles[0]}`);
      assert.equal(body.model,'male');
      assert.equal(body.reference,undefined);
      assert.equal(vm.runInContext('location.hash',ctx),'#job/new');
      assert.equal(vm.runInContext('tryonPrimaryImages().length',ctx),0);
      assert.equal(vm.runInContext('draft',ctx),'data:image/jpeg;base64,basic');
    });
  }
});

test('拍同款 carries a selected no-reference shooting style into the job',async()=>{
  const ctx=await context('#remake');
  vm.runInContext(`
    resetTryonDraft('data:image/jpeg;base64,upper');
    tryonDraftState.shootingStyle='lookbook';draft='data:image/jpeg;base64,basic';
    renderTryonStudio();calls=[];navigate=route=>{location.hash=route};
    api=async(path,options)=>{calls.push(JSON.parse(options.body));return {job:{id:'new',status:'queued',created:new Date().toISOString()}}};
  `,ctx);
  assert.match(vm.runInContext('app.innerHTML',ctx),/城市 Lookbook/);
  await vm.runInContext('submitTryon()',ctx);
  assert.equal(vm.runInContext('calls[0].workflowConfig.shooting_style',ctx),'lookbook');
});

test('adding and removing optional references updates output totals while keeping garment generation available',async()=>{
  const ctx=await context('#remake');
  vm.runInContext(`
    resetTryonDraft('data:image/jpeg;base64,upper');tryonDraftState.outputCount=2;
    normalizeTryonFile=async file=>file.image;renderTryonStudio();
  `,ctx);
  assert.equal(vm.runInContext('tryonTotalOutputCount()',ctx),2);
  await vm.runInContext(`addTryonFiles('reference',undefined,[{image:'data:image/jpeg;base64,ref1'},{image:'data:image/jpeg;base64,ref2'}])`,ctx);
  vm.runInContext('renderTryonStudio()',ctx);
  assert.equal(vm.runInContext('tryonTotalOutputCount()',ctx),4);
  assert.match(vm.runInContext('app.innerHTML',ctx),/<h2>每张参考生成<\/h2>/);
  vm.runInContext("removeTryonInput('reference:0')",ctx);
  assert.equal(vm.runInContext('tryonTotalOutputCount()',ctx),2);
  vm.runInContext("removeTryonInput('reference:0')",ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.doesNotMatch(html,/id="generate"[^>]*disabled/);
  assert.match(html,/<h2>生成数量<\/h2>/);
  const workflow=JSON.parse(JSON.stringify(vm.runInContext('buildTryonWorkflow()',ctx)));
  assert.equal(workflow.workflowConfig.output_count,2);
  assert.deepEqual(workflow.inputImages.map(item=>item.role),['upper']);
});

test('returning to remake preserves its garment and references independently of the basic draft',async()=>{
  const ctx=await context();
  vm.runInContext("screen='remake';currentRoute='#remake';routeVersion=1;normalizeTryonFile=async file=>file.image",ctx);
  await vm.runInContext("addTryonFiles('garment','lower',[{image:'data:image/jpeg;base64,lower'}])",ctx);
  await vm.runInContext("addTryonFiles('reference',null,[{image:'data:image/jpeg;base64,reference'}])",ctx);
  vm.runInContext("screen='home';currentRoute='#home';draft='data:image/jpeg;base64,basic';navigate('#remake')",ctx);
  assert.equal(vm.runInContext('tryonDraftState.garments.lower',ctx),'data:image/jpeg;base64,lower');
  assert.equal(vm.runInContext('tryonDraftState.references[0]',ctx),'data:image/jpeg;base64,reference');
  assert.equal(vm.runInContext('location.hash',ctx),'#remake');
  assert.equal(vm.runInContext('draft',ctx),'data:image/jpeg;base64,basic');
});

test('selecting a library model updates gender separately and persists the library ID',async()=>{
  const ctx=await context();
  vm.runInContext("allModels=[{id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',name:'专属男模',gender:'male',image:'/model'}];selectedModelId=null;tryonDraftState=freshTryonDraft()",ctx);
  vm.runInContext("selectLibraryModel('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')",ctx);
  assert.equal(vm.runInContext('model',ctx),'male');
  assert.equal(vm.runInContext('selectedModelId',ctx),'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
  assert.equal(vm.runInContext('tryonDraftState.modelImage',ctx),null);
  assert.equal(vm.runInContext('buildTryonWorkflow().modelId',ctx),'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
});

test('starting a new try-on draft clears references, details, and instruction',async()=>{
  const ctx=await context();
  vm.runInContext(`tryonDraftState={clothingMode:'single',garments:{upper:null,lower:null,single:'data:image/jpeg;base64,old'},references:['data:image/jpeg;base64,ref'],modelImage:null,detailsEnabled:true,details:{upper:[],lower:[],single:['data:image/jpeg;base64,detail']},outputCount:2,instruction:'old instruction'};resetTryonDraft()`,ctx);
  const state=vm.runInContext('tryonDraftState',ctx);
  assert.equal(state.clothingMode,'multi');
  assert.equal(state.garments.single,null);
  assert.deepEqual(Array.from(state.references),[]);
  assert.deepEqual(Array.from(state.details.single),[]);
  assert.equal(state.detailsEnabled,false);
  assert.equal(state.instruction,'');
  assert.equal(state.outputCount,3);
});

test('try-on expands reference count by per-reference output count and preserves separate refs',async()=>{
  const ctx=await context();
  vm.runInContext(`
    tryonDraftState={clothingMode:'multi',garments:{upper:'data:image/jpeg;base64,upper',lower:null,single:null},references:['data:image/jpeg;base64,ref1','data:image/jpeg;base64,ref2'],modelImage:null,detailsEnabled:false,details:{upper:[],lower:[],single:[]},outputCount:2,instruction:'春季通勤'};
  `,ctx);
  const output=vm.runInContext('buildTryonWorkflow()',ctx);
  assert.equal(vm.runInContext('tryonTotalOutputCount()',ctx),4);
  assert.deepEqual(Array.from(output.inputImages,item=>item.role),['upper','reference','reference']);
  assert.deepEqual(Array.from(output.inputImages.filter(item=>item.role==='reference'),item=>item.image),['data:image/jpeg;base64,ref1','data:image/jpeg;base64,ref2']);
  assert.deepEqual(JSON.parse(JSON.stringify(output.workflowConfig)),{clothing_mode:'multi',output_count:2,instruction:'春季通勤'});
});

test('try-on details are bound to their garment and excluded while the detail switch is off',async()=>{
  const ctx=await context();
  vm.runInContext(`
    tryonDraftState={clothingMode:'multi',garments:{upper:'data:image/jpeg;base64,upper',lower:'data:image/jpeg;base64,lower',single:null},references:[],modelImage:null,detailsEnabled:false,details:{upper:['data:image/jpeg;base64,collar'],lower:['data:image/jpeg;base64,pocket'],single:[]},outputCount:1,instruction:''};
  `,ctx);
  assert.deepEqual(Array.from(vm.runInContext('buildTryonWorkflow().inputImages',ctx),item=>item.role),['upper','lower']);
  vm.runInContext('tryonDraftState.detailsEnabled=true',ctx);
  const images=vm.runInContext('buildTryonWorkflow().inputImages',ctx);
  assert.deepEqual(Array.from(images,item=>item.role),['upper','lower','detail','detail']);
  assert.deepEqual(Array.from(images.filter(item=>item.role==='detail'),item=>item.garmentRole),['upper','lower']);
});

test('try-on garment mode changes retain both drafts and submit only the active mode',async()=>{
  const ctx=await context();
  vm.runInContext(`tryonDraftState={clothingMode:'multi',garments:{upper:'data:image/jpeg;base64,upper',lower:'data:image/jpeg;base64,lower',single:'data:image/jpeg;base64,single'},references:[],modelImage:null,detailsEnabled:true,details:{upper:['data:image/jpeg;base64,upper-detail'],lower:[],single:['data:image/jpeg;base64,single-detail']},outputCount:1,instruction:''}`,ctx);
  assert.deepEqual(Array.from(vm.runInContext('buildTryonWorkflow().inputImages',ctx),item=>item.role),['upper','lower','detail']);
  vm.runInContext("tryonDraftState.clothingMode='single'",ctx);
  let images=vm.runInContext('buildTryonWorkflow().inputImages',ctx);
  assert.deepEqual(Array.from(images,item=>item.role),['single','detail']);
  assert.equal(vm.runInContext('tryonDraftState.garments.upper',ctx),'data:image/jpeg;base64,upper');
  vm.runInContext("tryonDraftState.clothingMode='multi'",ctx);
  images=vm.runInContext('buildTryonWorkflow().inputImages',ctx);
  assert.deepEqual(Array.from(images,item=>item.role),['upper','lower','detail']);
});

test('try-on idempotency includes every input and retries reuse the same key',async()=>{
  const ctx=await context();
  vm.runInContext(`screen='home';keys=[];api=async(_path,options)=>{keys.push(JSON.parse(options.body).idempotencyKey);throw Error('network')}`,ctx);
  const first={workflowType:'tryon',workflowConfig:{clothing_mode:'multi',output_count:1,instruction:''},inputImages:[{role:'lower',image:'data:image/jpeg;base64,lower'},{role:'reference',image:'data:image/jpeg;base64,ref'}]};
  ctx.workflowForTest=first;
  await vm.runInContext("generate('data:image/jpeg;base64,lower','female',workflowForTest)",ctx);
  await vm.runInContext("generate('data:image/jpeg;base64,lower','female',workflowForTest)",ctx);
  const changed={...first,inputImages:[...first.inputImages,{role:'detail',garmentRole:'lower',image:'data:image/jpeg;base64,detail'}]};
  ctx.workflowForTest=changed;
  await vm.runInContext("generate('data:image/jpeg;base64,lower','female',workflowForTest)",ctx);
  assert.equal(vm.runInContext('keys[0]===keys[1]',ctx),true);
  assert.equal(vm.runInContext('keys[1]!==keys[2]',ctx),true);
});

test('slow try-on upload does not overwrite a newer draft',async()=>{
  const ctx=await context();
  vm.runInContext(`screen='remake';currentRoute='#remake';routeVersion=3;normalizeTryonFile=async()=>new Promise(resolve=>finishUpload=resolve)`,ctx);
  const pending=vm.runInContext("addTryonFiles('garment','upper',[{name:'old'}],tryonDraftRevision,currentRoute,routeVersion)",ctx);
  await new Promise(resolve=>setImmediate(resolve));
  vm.runInContext("resetTryonDraft('data:image/jpeg;base64,new-draft')",ctx);
  vm.runInContext("finishUpload('data:image/jpeg;base64,late-old')",ctx);
  assert.equal(await pending,false);
  assert.equal(vm.runInContext('tryonDraftState.garments.upper',ctx),'data:image/jpeg;base64,new-draft');
});

test('try-on upload failure appears beside its control and preserves the existing image',async()=>{
  const ctx=await context();
  vm.runInContext(`
    screen='remake';currentRoute='#remake';routeVersion=3;
    tryonDraftState.garments.upper='data:image/jpeg;base64,existing';
    uploadFeedback={hidden:true,textContent:'',classList:{toggle(){}},setAttribute(){}};
    submitFeedback={hidden:true,textContent:''};
    app.querySelector=selector=>selector==='[data-tryon-feedback="garment:upper"]'?uploadFeedback:submitFeedback;
    testPicker={files:[{name:'small.png'}],addEventListener(){},click(){},remove(){}};
    document.body.appendChild=()=>{};document.createElement=()=>testPicker;
    toast=message=>lastToast=message;
    normalizeTryonFile=async()=>{throw Error('这张图片为 200 × 240 像素，商品图宽和高都需至少 256 像素。')};
    openTryonFilePicker('garment','upper');
  `,ctx);
  await vm.runInContext('testPicker.onchange()',ctx);
  assert.equal(vm.runInContext('uploadFeedback.hidden',ctx),false);
  assert.match(vm.runInContext('uploadFeedback.textContent',ctx),/200 × 240/);
  assert.match(vm.runInContext('lastToast',ctx),/256/);
  assert.equal(vm.runInContext('tryonDraftState.garments.upper',ctx),'data:image/jpeg;base64,existing');
});

test('try-on size validation reports the actual PNG dimensions',async()=>{
  const ctx=await context();
  vm.runInContext(`URL={createObjectURL:()=>'/small.png',revokeObjectURL(){}};loadImage=async()=>({width:200,height:240})`,ctx);
  await assert.rejects(
    vm.runInContext("normalizeTryonFile({name:'small.png',size:1024},'garment')",ctx),
    /200 × 240.*256/
  );
});

test('try-on accepts small product PNGs without enlarging their pixels',async()=>{
  const ctx=await context();
  vm.runInContext(`
    URL={createObjectURL:file=>file,revokeObjectURL(){}};
    loadImage=async file=>({width:file.width,height:file.height});
    testCanvas={getContext:()=>({drawImage(){}}),toDataURL:()=> 'data:image/jpeg;base64,small'};
    document.createElement=()=>testCanvas;
  `,ctx);
  for (const [width,height] of [[330,502],[480,444],[454,454]]) {
    ctx.fileForTest={name:'product.png',type:'image/png',size:1024,width,height};
    const image=await vm.runInContext("normalizeTryonFile(fileForTest,'garment')",ctx);
    assert.equal(image,'data:image/jpeg;base64,small');
    assert.equal(vm.runInContext('testCanvas.width',ctx),width);
    assert.equal(vm.runInContext('testCanvas.height',ctx),height);
  }
});

test('try-on regeneration resends every saved input URL and workflow setting',async()=>{
  const ctx=await context();
  vm.runInContext(`
    sourceData=async url=>` + "`data:image/jpeg;base64,${url.split('/').pop()}`" + `;
    calls=[];currentRoute='#job/abcdef0123456789abcdef0123456789';screen='result';navigate=route=>{location.hash=route};
    api=async(path,options)=>{calls.push({path,options});return {job:{id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',status:'queued',created:new Date().toISOString()}}};
  `,ctx);
  const job={id:'abcdef0123456789abcdef0123456789',original:'/api/jobs/x/input',model:'female',workflowType:'tryon',workflowConfig:{clothing_mode:'multi',output_count:2,instruction:'keep outfit'},inputImages:[{role:'lower',url:'/api/jobs/x/input-1'},{role:'reference',url:'/api/jobs/x/input-2'},{role:'detail',url:'/api/jobs/x/input-3',garmentRole:'lower'}]};
  ctx.jobForTest=job;
  const workflow=vm.runInContext('regenerationWorkflow(jobForTest)',ctx);
  ctx.workflowForTest=workflow;
  await vm.runInContext("generate('/api/jobs/x/input','female',workflowForTest)",ctx);
  const body=JSON.parse(vm.runInContext('calls[0].options.body',ctx));
  assert.deepEqual(body.workflowConfig,{clothing_mode:'multi',output_count:2,instruction:'keep outfit'});
  assert.deepEqual(body.inputImages.map(item=>item.role),['lower','reference','detail']);
  assert.equal(body.inputImages[2].garmentRole,'lower');
  assert.deepEqual(body.inputImages.map(item=>item.image),['data:image/jpeg;base64,input-1','data:image/jpeg;base64,input-2','data:image/jpeg;base64,input-3']);
});

test('拍同款 without a reference shows its gallery and regenerates all garment, model and detail snapshots',async()=>{
  const ctx=await context();
  ctx.savedJobForTest={
    id:'abcdef0123456789abcdef0123456789',original:'/api/jobs/old/input',image:'/out-1',images:['/out-1','/out-2','/out-3'],
    model:'male',workflowType:'remake',status:'succeeded',date:'today',reference:null,
    workflowConfig:{clothing_mode:'multi',output_count:3,instruction:'棕色皮鞋'},
    inputImages:[{role:'upper',url:'/api/jobs/old/input-1'},{role:'lower',url:'/api/jobs/old/input-2'},
      {role:'model',url:'/api/jobs/old/input-3'},{role:'detail',garmentRole:'lower',url:'/api/jobs/old/input-4'}]
  };
  vm.runInContext(`
    regenerateButton={};const defaultQuery=document.querySelector;
    document.querySelector=selector=>selector==='#regenerate'?regenerateButton:defaultQuery(selector);
    sourceData=async url=>'data:image/jpeg;base64,'+url.split('/').pop();
    calls=[];navigate=route=>{location.hash=route};
    api=async(path,options)=>{calls.push(JSON.parse(options.body));return {job:{id:'regenerated',status:'queued',created:new Date().toISOString()}}};
    renderResult(savedJobForTest);
  `,ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.equal((html.match(/data-pose-image=/g)||[]).length,3);
  assert.match(html,/下载全部 3 张/);
  assert.doesNotMatch(html,/id="result-reference"|src="(?:null|undefined)"/);
  assert.equal(vm.runInContext('poseProgress({...savedJobForTest,images:["/out-1"]})',ctx),'已生成 1 / 3 张');
  vm.runInContext('regenerateButton.onclick()',ctx);
  await new Promise(resolve=>setImmediate(resolve));
  const body=JSON.parse(JSON.stringify(vm.runInContext('calls[0]',ctx)));
  assert.equal(body.workflowType,'remake');
  assert.deepEqual(body.workflowConfig,{clothing_mode:'multi',output_count:3,instruction:'棕色皮鞋'});
  assert.deepEqual(body.inputImages.map(item=>item.role),['upper','lower','model','detail']);
  assert.deepEqual(body.inputImages.map(item=>item.image),['data:image/jpeg;base64,input-1','data:image/jpeg;base64,input-2','data:image/jpeg;base64,input-3','data:image/jpeg;base64,input-4']);
  assert.equal(body.inputImages[3].garmentRole,'lower');
  assert.equal(body.model,'male');
  assert.equal(body.reference,undefined);
  assert.equal(vm.runInContext('location.hash',ctx),'#job/regenerated');
});

test('try-on gallery is labeled as try-on rather than pose variation',async()=>{
  const ctx=await context();
  vm.runInContext(`renderResult({id:'job',workflowType:'tryon',workflowConfig:{clothing_mode:'multi',output_count:2},inputImages:[{role:'lower',url:'/lower'}],images:['/out-1','/out-2'],image:'/out-1',original:'/lower',model:'female',date:'today',status:'succeeded'})`,ctx);
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/虚拟试穿图片/);
  assert.match(html,/虚拟试穿第 1 张/);
  assert.match(html,/选择虚拟试穿图片/);
  assert.doesNotMatch(html,/姿势裂变/);
  assert.match(html,/下装原图/);
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

test('studio demo routes load matching samples on refresh without creating private jobs',async()=>{
  const ctx=await context('#demo/pose/4');
  const html=vm.runInContext('app.innerHTML',ctx);
  assert.match(html,/演示样例/);
  assert.match(html,/assets\/demo\/pose-original-1\.svg/);
  assert.match(html,/assets\/demo\/pose-result-1d\.svg/);
  assert.equal((html.match(/data-pose-image=/g)||[]).length,4);
  assert.equal(vm.runInContext('history.length',ctx),0);
  assert.doesNotMatch(html,/Invalid Date|mockup\/assets/);
  vm.runInContext(`api=async()=>{throw Error('demo must not call the job API')};location.hash='#demo/background/beach'`,ctx);
  await vm.runInContext('renderRoute()',ctx);
  assert.match(vm.runInContext('app.innerHTML',ctx),/assets\/demo\/bg-result-beach\.svg/);
  assert.equal(vm.runInContext("getDemoResult('pose',8)",ctx),null);
  assert.equal(vm.runInContext("getDemoResult('background','cafe')",ctx),null);
});

test('studio presets keep their mode in the URL and preserve a server demo notice',async()=>{
  const ctx=await context();
  vm.runInContext(`
    notice={hidden:true};
    originalGet=document.getElementById;
    document.getElementById=id=>id==='service-mode-notice'?notice:originalGet(id);
    serverGenerationMode='demo';
    setDemoMode(false);
    applyStudioPreset('ecommerce');
  `,ctx);
  assert.equal(vm.runInContext('location.hash',ctx),'#variations/background');
  assert.equal(vm.runInContext('notice.hidden',ctx),false);
  assert.equal(vm.runInContext('studioState.scene',ctx),'white');
});

test('settings and studio share the demo switch without leaving the current page',async()=>{
  const ctx=await context();
  vm.runInContext(`
    demoStorage=new Map([['yipai-demo-mode','true']]);
    localStorage.getItem=key=>demoStorage.get(key)??null;
    localStorage.setItem=(key,value)=>demoStorage.set(key,value);
    screen='my';
    toggleDemoMode();
  `,ctx);
  assert.equal(vm.runInContext('isDemoMode()',ctx),false);
  assert.equal(vm.runInContext('screen',ctx),'my');
  vm.runInContext('toggleDemoMode()',ctx);
  assert.equal(vm.runInContext('isDemoMode()',ctx),true);
  vm.runInContext("location.hash='#variations/pose'",ctx);
  await vm.runInContext('renderRoute()',ctx);
  assert.doesNotMatch(vm.runInContext('app.innerHTML',ctx),/id="studio-generate" disabled/);
  assert.equal(vm.runInContext('studioState.upload',ctx),'');
});
