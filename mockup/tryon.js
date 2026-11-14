const TRYON_MAX_REFERENCES = 8;
const TRYON_MAX_DETAILS = 4;
const TRYON_MAX_INPUT_BYTES = 20 * 1024 * 1024;
const TRYON_MAX_REQUEST_BYTES = 30 * 1024 * 1024 - 256 * 1024;
let tryonDraftState = freshTryonDraft();
let tryonDraftRevision = 0;

function freshTryonDraft(image = null) {
  return {
    clothingMode: 'multi',
    garments: {upper:image, lower:null, single:null},
    references: [],
    modelImage: null,
    modelFromWork: false,
    detailsEnabled: false,
    details: {upper:[], lower:[], single:[]},
    outputCount: 3,
    instruction: ''
  };
}

function resetTryonDraft(image) {
  tryonDraftState = freshTryonDraft(image);
  tryonDraftRevision++;
  pendingSubmission = null;
  if (typeof remakeReferencePosts !== 'undefined') remakeReferencePosts.clear();
}

function tryonPrimaryImages(state = tryonDraftState) {
  const roles = state.clothingMode === 'single' ? ['single'] : ['upper', 'lower'];
  return roles.filter(role => state.garments[role]).map(role => ({role, image:state.garments[role]}));
}

function collectTryonInputImages(state = tryonDraftState) {
  const garments = tryonPrimaryImages(state);
  const inputImages = [...garments];
  for (const image of state.references) inputImages.push({role:'reference', image});
  if (state.modelImage) inputImages.push({role:'model', image:state.modelImage});
  if (state.detailsEnabled) {
    for (const {role} of garments) {
      for (const image of state.details[role] || []) inputImages.push({role:'detail', image, garmentRole:role});
    }
  }
  return inputImages;
}

function buildTryonWorkflow(state = tryonDraftState) {
  const inputImages = collectTryonInputImages(state);
  const firstGarment = inputImages.find(image => ['upper','lower','single'].includes(image.role));
  return {
    workflowType:'remake',
    workflowConfig:{clothing_mode:state.clothingMode, output_count:state.outputCount, instruction:state.instruction.trim().slice(0,500)},
    inputImages,
    modelId:state.modelImage ? null : selectedModelId,
    source:firstGarment?.image || null,
    draftRevision:tryonDraftRevision
  };
}

function tryonImageBytes(image) {
  if (typeof image !== 'string' || !image.startsWith('data:')) return 0;
  const payload = image.slice(image.indexOf(',') + 1);
  return Math.floor(payload.length * 3 / 4) - (payload.endsWith('==') ? 2 : payload.endsWith('=') ? 1 : 0);
}

function tryonPayloadSizes(state = tryonDraftState) {
  const images=collectTryonInputImages(state);
  const firstGarment=images.find(item=>['upper','lower','single'].includes(item.role));
  const inputBytes=images.reduce((total,item)=>total+tryonImageBytes(item.image),0);
  const requestBytes=images.reduce((total,item)=>total+(item.image?.length||0),0)+(firstGarment?.image?.length||0)+8192+(state.instruction.length*2);
  return {inputBytes,requestBytes};
}

function tryonTotalOutputCount(state = tryonDraftState) {
  return Math.max(1, state.references.length) * state.outputCount;
}
function tryonDetailCount(state = tryonDraftState) { return Object.values(state.details).reduce((total,images)=>total+images.length,0); }

function tryonPreview(image, label, role, removeLabel = '移除') {
  if (!image) return `<div class="tryon-empty-slot"><span>${icon('image')}</span><span>${escapeHtml(label)}</span></div>`;
  return `<div class="tryon-thumb">${photo(image, label)}<span class="tryon-thumb-label">${escapeHtml(label)}</span><button class="tryon-remove" type="button" data-tryon-remove="${role}" aria-label="${removeLabel}${label}">${icon('close')}</button></div>`;
}

function tryonUploadFeedbackMarkup(kind, role = '') {
  return `<p class="tryon-help" data-tryon-feedback="${kind}:${role}" role="status" hidden></p>`;
}

function tryonGarmentSlot(role, label, hint) {
  const image = tryonDraftState.garments[role];
  const details = tryonDraftState.details[role] || [];
  return `<article class="tryon-slot" data-garment-slot="${role}">
    <div class="tryon-slot-heading"><div><h3>${label}</h3><p>${hint}</p></div>${image ? `<button class="text-button" type="button" data-tryon-remove="${role}">移除</button>` : ''}</div>
    ${image ? `<div class="tryon-garment-preview">${photo(image, `${label}商品图`)}<span>${label}已上传</span></div>` : `<div class="tryon-empty-slot"><span>${icon('image')}</span><span>上传${label}商品图</span></div>`}
    <button class="secondary tryon-upload-button" type="button" data-tryon-upload="garment" data-role="${role}">${image ? '更换图片' : `上传${label}`} ${icon(image ? 'refresh' : 'plus')}</button>
    <div class="tryon-source-actions"><button class="text-button" type="button" data-tryon-camera="garment" data-role="${role}">拍照 ${icon('camera')}</button><button class="text-button" type="button" data-remake-work-picker="garment" data-role="${role}">从作品选择</button></div>
    ${tryonUploadFeedbackMarkup('garment', role)}
    <p class="tryon-help" data-tryon-resolution>支持 PNG / JPG / WebP；宽高至少 256 像素，单张不超过 20 MB。</p>
    ${tryonDraftState.detailsEnabled ? `<div class="tryon-slot-details"><div class="tryon-detail-heading"><strong>这件服装的细节图</strong><span>${details.length} / ${TRYON_MAX_DETAILS}</span></div><p>${image ? '仅补充面料、口袋、纽扣等局部，不会改变人物或场景。' : `先上传${label}商品图，再添加对应细节。`}</p><div class="tryon-thumbs">${details.map((detail,index)=>tryonPreview(detail, `${label}细节 ${index+1}`, `detail:${role}:${index}`, '移除')).join('')}</div><button class="text-button" type="button" data-tryon-upload="detail" data-role="${role}" ${!image || tryonDetailCount() >= TRYON_MAX_DETAILS ? 'disabled' : ''}>添加细节图 ${icon('plus')}</button>${tryonUploadFeedbackMarkup('detail', role)}</div>` : ''}
  </article>`;
}

function renderTryonStudio() {
  setScreen('remake');
  const state = tryonDraftState;
  const isMulti = state.clothingMode === 'multi';
  const refs = state.references;
  const directModel = Boolean(state.modelImage);
  const chosenLibraryModel = selectedModelId ? allModels.find(item => item.id === selectedModelId) : null;
  const activeGarments = isMulti ? ['upper','lower'] : ['single'];
  const garmentImages = tryonPrimaryImages(state);
  const detailsCount = tryonDetailCount(state);
  const modelContent = directModel
    ? `<div class="tryon-model-preview">${photo(state.modelImage, '自定义模特照片')}<div><strong>${state.modelFromWork?'沿用作品中的人物':'自定义人物参考'}</strong><p>只用于人物身份，不决定服装或场景。</p></div><button class="text-button" type="button" data-tryon-remove="model">移除</button></div>`
    : chosenLibraryModel
      ? `<div class="tryon-model-preview">${photo(chosenLibraryModel.image, chosenLibraryModel.name)}<div><strong>${escapeHtml(chosenLibraryModel.name)}</strong><p>模特照片只用于人物身份。</p></div><button class="text-button" type="button" data-clear-library-model>取消选择</button></div>`
      : `<div class="tryon-identity-note">默认使用所选性别的模特；参考照片只提供拍法，不会照搬其中的人物。</div>`;
  const refsMarkup = refs.length
    ? `<div class="tryon-thumbs">${refs.map((image,index)=>tryonPreview(image, `参考图 ${index+1}`, `reference:${index}`)).join('')}</div>`
    : `<div class="tryon-empty-slot tryon-reference-empty"><span>${icon('image')}</span><span>先添加一张喜欢的参考照片，或从已有作品选择</span></div>`;
  app.innerHTML = `<section class="page detail-page tryon-page">
    ${subTop('拍同款', home)}
    <p class="tryon-page-caption">照着喜欢的照片，让模特穿上你的商品。参考照片用于构图、姿势、场景和光线，每张分别输出独立成片。</p>
    <div class="tryon-layout">
      <div class="tryon-main-column">
        <section class="tryon-card tryon-garments-card">
          <div class="tryon-section-heading"><div><span class="eyebrow">商品输入</span><h2>选择服装类型</h2><p>上下装可只传一件；也可切换为连体/全身服装。</p></div></div>
          <div class="tryon-mode-switch" role="group" aria-label="服装类型">
            <button type="button" data-clothing-mode="multi" class="${isMulti?'selected':''}" aria-pressed="${isMulti}">上装 / 下装</button>
            <button type="button" data-clothing-mode="single" class="${!isMulti?'selected':''}" aria-pressed="${!isMulti}">连体 / 全身</button>
          </div>
          <div class="tryon-garment-grid">${activeGarments.map(role => role === 'upper' ? tryonGarmentSlot(role,'上装','上衣、外套等') : role === 'lower' ? tryonGarmentSlot(role,'下装','裤子、裙装等') : tryonGarmentSlot(role,'连体 / 全身','连衣裙、连体衣等')).join('')}</div>
        </section>
        <section class="tryon-card">
          <div class="tryon-section-heading"><div><span class="eyebrow">画面控制</span><h2>参考照片 <span class="tryon-count">${refs.length} / ${TRYON_MAX_REFERENCES}</span></h2><p>先分析参考照片的构图、姿势、场景与光线，再结合你的商品重拍。截图中的界面、价格和文字会被忽略。</p></div><button class="secondary" type="button" data-tryon-upload="reference" ${refs.length>=TRYON_MAX_REFERENCES?'disabled':''}>添加参考图 ${icon('plus')}</button></div>
          ${refsMarkup}
          <div class="tryon-source-actions"><button class="text-button" type="button" data-tryon-camera="reference">拍摄参考照 ${icon('camera')}</button><button class="text-button" type="button" data-remake-work-picker="reference">从作品选择 ${icon('image')}</button></div>
          ${tryonUploadFeedbackMarkup('reference')}
        </section>
        <section class="tryon-card">
          <div class="tryon-section-heading"><div><span class="eyebrow">模特身份</span><h2>人物参考 <span class="tryon-optional">可选</span></h2><p>人物照片只用于身份；与拍摄参考同时使用时会单独校准人物，耗时稍长。建议上传清晰正脸或上半身照。</p></div></div>
          <div class="tryon-gender-switch" role="group" aria-label="默认模特性别">${['female','male'].map(value=>`<button type="button" data-model="${value}" class="${model===value?'selected':''}" aria-pressed="${model===value}">${modelName(value)}</button>`).join('')}</div>
          ${modelContent}
          <div class="tryon-model-actions"><button class="secondary" type="button" data-tryon-upload="model">上传人物照片 ${icon('plus')}</button><button class="text-button" type="button" data-open-picker>从模特库选择</button></div>
          ${tryonUploadFeedbackMarkup('model')}
        </section>
      </div>
      <aside class="tryon-side-column">
        <section class="tryon-card">
          <div class="tryon-section-heading"><div><span class="eyebrow">商品细节</span><h2>服装细节参考</h2></div><label class="tryon-switch"><input type="checkbox" id="tryon-details-toggle" ${state.detailsEnabled?'checked':''}><span></span><b>${state.detailsEnabled?'开启':'关闭'}</b></label></div>
          <p class="tryon-help">开启后最多添加 4 张细节图，并绑定到对应服装。关闭时已选细节会保留在草稿中，但不会提交。</p>
          ${state.detailsEnabled ? `<p class="tryon-detail-total">已添加 ${detailsCount} / ${TRYON_MAX_DETAILS} 张</p>` : ''}
        </section>
        <section class="tryon-card">
          <div class="tryon-section-heading"><div><span class="eyebrow">生成方案</span><h2>每组输出</h2></div></div>
          <div class="tryon-count-options">${[1,2,3].map(count=>`<button type="button" data-output-count="${count}" class="${state.outputCount===count?'selected':''}" aria-pressed="${state.outputCount===count}">${count} 张</button>`).join('')}</div>
          <p class="tryon-help">${refs.length ? `${refs.length} 张参考图 × 每组 ${state.outputCount} 张` : '先添加参考照片'}；预计共 ${tryonTotalOutputCount(state)} 张。</p>
        </section>
        <section class="tryon-card">
          <label class="field-label" for="tryon-instruction">补充搭配要求 <span class="tryon-optional">可选 · 最多 500 字</span></label>
          <textarea id="tryon-instruction" class="field-input" maxlength="500" placeholder="例如：搭配简洁的浅色鞋履，整体适合春季通勤。">${escapeHtml(state.instruction)}</textarea>
          <p class="tryon-help">参考照片提供拍摄气质，其余穿搭会围绕你的商品协调搭配。商品本身的颜色、图案与结构优先保留。</p>
          <p class="tryon-character-count"><span id="tryon-instruction-count">${state.instruction.length}</span> / 500</p>
        </section>
        <div class="tryon-submit-error" id="tryon-submit-error" role="alert" hidden></div>
        <div class="bottom-action tryon-bottom-action"><button id="generate" class="primary" type="button" ${garmentImages.length && refs.length?'':'disabled'}>生成 ${tryonTotalOutputCount(state)} 张图片 ${icon('arrow')}</button><p class="helper">${refs.length ? '商品、参考和细节图片会按用途分别处理。' : '请先添加参考照片，再上传至少一件商品。'}</p></div>
      </aside>
    </div>
    ${errorSlot}
  </section>`;
  bindHeader(home);
  app.querySelectorAll('[data-clothing-mode]').forEach(button=>button.onclick=()=>{state.clothingMode=button.dataset.clothingMode; tryonDraftRevision++; pendingSubmission=null; renderTryonStudio();});
  app.querySelectorAll('[data-output-count]').forEach(button=>button.onclick=()=>{state.outputCount=Number(button.dataset.outputCount); tryonDraftRevision++; pendingSubmission=null; renderTryonStudio();});
  app.querySelectorAll('[data-tryon-upload]').forEach(button=>button.onclick=()=>openTryonFilePicker(button.dataset.tryonUpload,button.dataset.role));
  app.querySelectorAll('[data-tryon-camera]').forEach(button=>button.onclick=()=>openTryonFilePicker(button.dataset.tryonCamera,button.dataset.role,true));
  app.querySelectorAll('[data-remake-work-picker]').forEach(button=>button.onclick=()=>openRemakeWorkPicker(button.dataset.remakeWorkPicker,button.dataset.role));
  app.querySelectorAll('[data-tryon-remove]').forEach(button=>button.onclick=()=>removeTryonInput(button.dataset.tryonRemove));
  app.querySelector('#tryon-details-toggle').onchange=event=>{state.detailsEnabled=event.target.checked; tryonDraftRevision++; pendingSubmission=null; renderTryonStudio();};
  app.querySelector('[data-open-picker]').onclick=openModelPicker;
  app.querySelector('[data-clear-library-model]')?.addEventListener('click',()=>{selectedModelId=null; try{localStorage.removeItem('yipai-selected-model-id');}catch{} renderTryonStudio();});
  app.querySelectorAll('[data-model]').forEach(button=>button.onclick=()=>{state.modelImage=null;state.modelFromWork=false;selectModel(button.dataset.model);});
  app.querySelector('#tryon-instruction').oninput=event=>{
    state.instruction=event.target.value.slice(0,500);
    tryonDraftRevision++; pendingSubmission=null;
    app.querySelector('#tryon-instruction-count').textContent=String(state.instruction.length);
  };
  app.querySelector('#generate').onclick=submitTryon;
  watchImages();
  app.querySelectorAll('[data-garment-slot]').forEach(slot=>{
    const image=slot.querySelector('.tryon-garment-preview img');
    if (!image) return;
    const showResolution=()=>{
      if (image.naturalWidth && Math.min(image.naturalWidth,image.naturalHeight)<512) {
        slot.querySelector('[data-tryon-resolution]').textContent=`已上传 ${image.naturalWidth} × ${image.naturalHeight} 像素，可继续生成；图片较小，建议使用更清晰的原图保留服装细节。`;
      }
    };
    if (image.complete) showResolution(); else image.addEventListener('load',showResolution,{once:true});
  });
}

function openTryonFilePicker(kind, role, camera = false) {
  const revision=tryonDraftRevision;
  const route=currentRoute;
  const viewVersion=routeVersion;
  const picker = document.createElement('input');
  picker.type='file'; picker.accept='image/jpeg,image/png,image/webp';
  picker.multiple=!camera && (kind==='reference' || kind==='detail');
  if (camera) picker.setAttribute('capture','environment');
  picker.onchange=async()=>{
    const files=Array.from(picker.files||[]);
    picker.remove();
    if (!files.length) return;
    showTryonUploadFeedback(kind,role,'正在读取图片…');
    try {
      const added=await addTryonFiles(kind,role,files,revision,route,viewVersion);
      if (added && currentRoute===route && routeVersion===viewVersion) renderTryonStudio();
      else if (currentRoute===route && routeVersion===viewVersion) showTryonUploadFeedback(kind,role,'');
    }
    catch(error) { if(currentRoute===route && routeVersion===viewVersion) showTryonUploadFeedback(kind,role,error.message || '图片无法读取，请重试',true); else toast(error.message || '图片无法读取，请重试'); }
  };
  picker.addEventListener('cancel',()=>picker.remove(),{once:true});
  document.body.appendChild(picker); picker.click();
}

function showTryonUploadFeedback(kind, role = '', message, error = false) {
  const box=app.querySelector(`[data-tryon-feedback="${kind}:${role}"]`);
  if (box) {
    box.hidden=!message; box.textContent=message;
    box.classList.toggle('inline-error',error && Boolean(message));
    box.setAttribute('role',error?'alert':'status');
  }
  if (error) toast(message);
}

async function normalizeTryonFile(file, kind) {
  if (file.size > 20 * 1024 * 1024) throw new Error('单张图片不能超过 20 MB。');
  const url=URL.createObjectURL(file);
  let image;
  try { image=await loadImage(url); } finally { URL.revokeObjectURL(url); }
  const minSide=kind==='detail'?128:kind==='garment'?256:400;
  if (Math.min(image.width,image.height)<minSide) throw new Error(`这张图片为 ${image.width} × ${image.height} 像素，${kind==='garment'?'商品图':kind==='detail'?'细节图':'参考图'}宽和高都需至少 ${minSide} 像素。`);
  const shortSide=Math.min(image.width,image.height), longSide=Math.max(image.width,image.height);
  const scale=Math.min(1,Math.max(1200/longSide,minSide/shortSide));
  const canvas=document.createElement('canvas'); canvas.width=Math.round(image.width*scale); canvas.height=Math.round(image.height*scale);
  canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
  return canvas.toDataURL('image/jpeg',.82);
}

async function addTryonFiles(kind, role, files, expectedRevision=tryonDraftRevision, expectedRoute=currentRoute, expectedViewVersion=routeVersion) {
  const state=tryonDraftState;
  if (kind==='reference' && state.references.length+files.length>TRYON_MAX_REFERENCES) throw new Error(`参考图最多 ${TRYON_MAX_REFERENCES} 张。`);
  if (kind==='detail' && tryonDetailCount(state)+files.length>TRYON_MAX_DETAILS) throw new Error(`服装细节图最多 ${TRYON_MAX_DETAILS} 张。`);
  if (['garment','model'].includes(kind) && files.length!==1) throw new Error('请一次选择一张图片。');
  const normalized=[];
  for (const file of files) normalized.push(await normalizeTryonFile(file,kind));
  if (expectedRevision!==tryonDraftRevision || expectedRoute!==currentRoute || expectedViewVersion!==routeVersion || screen!=='remake' || state!==tryonDraftState) return false;
  const next={...state, garments:{...state.garments}, references:[...state.references], details:{upper:[...state.details.upper],lower:[...state.details.lower],single:[...state.details.single]}};
  if (kind==='garment') { next.garments[role]=normalized[0]; if (role==='single') next.details.single=[]; else next.details[role]=[]; }
  if (kind==='reference') next.references.push(...normalized);
  if (kind==='detail') next.details[role].push(...normalized);
  if (kind==='model') {next.modelImage=normalized[0];next.modelFromWork=false;}
  const sizes=tryonPayloadSizes(next);
  if (sizes.inputBytes>TRYON_MAX_INPUT_BYTES) throw new Error('所选图片压缩后总大小仍超过 20 MB，请减少图片数量或使用更小的图片。');
  if (sizes.requestBytes>TRYON_MAX_REQUEST_BYTES) throw new Error('图片总请求体超过 30 MB，请减少图片数量或使用更小的图片。');
  if (kind==='model') { selectedModelId=null; try{localStorage.removeItem('yipai-selected-model-id');}catch{} }
  tryonDraftState=next; tryonDraftRevision++; pendingSubmission=null;
  return true;
}

function removeTryonInput(key) {
  const state=tryonDraftState;
  if (key==='model') {state.modelImage=null;state.modelFromWork=false;}
  else if (key.startsWith('reference:')) {const [removed]=state.references.splice(Number(key.split(':')[1]),1);remakeReferencePosts.delete(removed);}
  else if (key.startsWith('detail:')) {const [,role,index]=key.split(':'); state.details[role].splice(Number(index),1);}
  else {state.garments[key]=null; state.details[key]=[];}
  tryonDraftRevision++; pendingSubmission=null; renderTryonStudio();
}

function showTryonError(message) {
  const box=app.querySelector('#tryon-submit-error');
  if (!box) { pageError(message); return; }
  box.hidden=!message; box.textContent=message;
}

async function submitTryon() {
  const workflow=buildTryonWorkflow();
  if (!tryonDraftState.references.length) {showTryonError('请先添加至少一张参考照片。');return;}
  if (!workflow.source) {showTryonError('请至少上传一张主商品图：上装、下装或连体/全身服装。');return;}
  const sizes=tryonPayloadSizes();
  if (sizes.inputBytes>TRYON_MAX_INPUT_BYTES) {showTryonError('图片压缩后总大小超过 20 MB，请减少图片数量或重新选择较小的图片。');return;}
  if (sizes.requestBytes>TRYON_MAX_REQUEST_BYTES) {showTryonError('图片总请求体超过 30 MB，请减少图片数量或重新选择较小的图片。');return;}
  showTryonError('');
  const referencePostIds=workflow.inputImages.filter(item=>item.role==='reference').map(item=>remakeReferencePosts.get(item.image)).filter(Boolean);
  const job=await generate(workflow.source,model,workflow);
  if (job) await recordRemakeReferences(referencePostIds);
}
