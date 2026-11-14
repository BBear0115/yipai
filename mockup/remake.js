// 拍同款 — 照着一张喜欢的图，让模特穿上自己的商品拍 3 张。
// 参考图和商品各一张；商品从作品里选时沿用作品里的模特，否则用预设模特。
// 本文件先于 app.js 加载，因此不在顶层调用任何 app.js 的全局函数。

const REMAKE_MAX_BYTES = 20 * 1024 * 1024;
const REMAKE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

const remakeState = {
  reference: '',
  referencePost: null,
  product: '',
  productWork: null,
  model: 'male',
  submitting: false,
  error: '',
  pending: null,
  uploadVersion: 0
};

let remakeBound = false;

// 社区「做参考」：把这张效果图当参考图带进拍同款。
function useAsReference(post) {
  if (!post?.image) return;
  ++remakeState.uploadVersion;
  remakeState.reference = post.image;
  remakeState.referencePost = post.example ? null : post.id;
  remakeState.pending = null;
  remakeState.error = '';
  navigate('#remake');
  toast('已设为参考图，再选一件你的商品');
}

function remakeWorks() {
  return sortedJobs().filter(job => job.status === 'succeeded' && job.image).slice(0, 24);
}

function remakeSourceButtons(slot) {
  return `<div class="picker-sources"><button type="button" class="picker-source" data-remake-camera="${slot}">${icon('camera')}<span>拍照</span></button><button type="button" class="picker-source" data-remake-upload="${slot}">${icon('image')}<span>相册</span></button></div>`;
}

function remakeReferenceField() {
  const card = remakeState.reference
    ? `<div class="upload-card has-image"><div class="upload-thumb remake-thumb">${photo(remakeState.reference, '参考图')}</div><div class="upload-actions"><button type="button" class="secondary" data-remake-clear="reference">换一张 ${icon('refresh')}</button></div></div>`
    : `<div class="upload-card picker remake-picker">${remakeSourceButtons('reference')}<p class="remake-picker-note"><strong>电商截图就行</strong>界面、价格和文字<br>会自动忽略</p></div>`;
  return `<div class="studio-field"><div class="studio-field-label"><span>参考图</span><small>想拍成什么样</small></div>${card}</div>`;
}

function remakeProductField() {
  let card;
  if (remakeState.product) {
    card = `<div class="upload-card has-image"><div class="upload-thumb remake-thumb">${photo(remakeState.product, '商品图')}</div><div class="upload-actions"><button type="button" class="secondary" data-remake-clear="product">换一张 ${icon('refresh')}</button></div></div>`;
  } else {
    const works = remakeWorks();
    const workList = works.length
      ? works.map(job => `<button type="button" class="picker-work" data-remake-work="${escapeHtml(job.id)}" aria-label="使用作品：${escapeHtml(workflowJobName(job))}，${escapeHtml(job.date)}"><img src="${escapeHtml(job.image)}" alt="" loading="lazy" decoding="async"></button>`).join('')
      : `<p class="picker-empty">${jobsLoaded ? '生成过的作品会出现在这里，可直接拿来拍同款' : '正在加载作品…'}</p>`;
    card = `<div class="upload-card picker">${remakeSourceButtons('product')}<div class="picker-works" role="group" aria-label="从我的作品中选择">${workList}</div></div>`;
  }
  return `<div class="studio-field"><div class="studio-field-label"><span>商品</span><small>商品图，或从作品里选</small></div>${card}</div>`;
}

function remakeModelField() {
  if (remakeState.productWork) {
    return `<div class="studio-field"><div class="studio-field-label"><span>模特</span></div><p class="studio-hint">沿用这张作品里的模特。</p></div>`;
  }
  const chips = ['female', 'male'].map(value => `<div class="model-chip ${remakeState.model === value ? 'selected' : ''}" role="button" tabindex="0" data-remake-model="${value}" aria-pressed="${remakeState.model === value}">${photo(`assets/${value}-model.png`, `${modelName(value)}形象`)}<span class="model-label">${modelName(value)}<span class="model-check">${remakeState.model === value ? icon('check') : ''}</span></span></div>`).join('');
  return `<div class="studio-field"><div class="studio-field-label"><span>模特</span><small>参考图里的人不会出现在结果里</small></div><div class="compact-models">${chips}</div></div>`;
}

function renderRemake() {
  const ready = remakeState.reference && remakeState.product;
  const disabled = !ready || remakeState.submitting;
  app.innerHTML = `<section class="page detail-page variations-page remake-page">${subTop('拍同款', home)}<p class="variations-caption">照着喜欢的图，让模特穿上你的商品拍 3 张。</p><form id="remake-form" novalidate>${remakeReferenceField()}${remakeProductField()}${remakeModelField()}<p class="studio-hint">只学参考图的构图、姿势、场景和光线，不会照搬原图的模特、商品和品牌。</p><div class="inline-error" role="alert" ${remakeState.error ? '' : 'hidden'}>${escapeHtml(remakeState.error)}</div><div class="bottom-action"><button class="primary" type="submit" id="remake-generate" ${disabled ? 'disabled' : ''}>${remakeState.submitting ? '正在提交…' : `开始生成 ${icon('arrow')}`}</button><p class="helper">${ready ? '一次生成 3 张，完成后可在「我的」查看' : remakeState.reference ? '再选一件商品就可以开始' : '先放一张参考图'}</p></div></form><input id="remake-file" type="file" accept="image/jpeg,image/png,image/webp" hidden><input id="remake-camera" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden></section>`;
  bindHeader(home);
  bindRemake();
  watchImages();
  // Works arrive with the session; refresh the picker once they do.
  if (!jobsLoaded && !remakeState.product) sessionReady.then(() => { if (screen === 'remake' && jobsLoaded && !remakeState.product) renderRemake(); });
}

function bindRemake() {
  if (remakeBound) return;
  remakeBound = true;
  app.addEventListener('click', remakeClick);
  app.addEventListener('change', remakeChange);
  app.addEventListener('submit', remakeSubmitEvent);
}

let remakeSlot = 'reference';
function remakeClick(event) {
  if (screen !== 'remake') return;
  const target = event.target.closest('[data-remake-upload],[data-remake-camera],[data-remake-work],[data-remake-clear],[data-remake-model]');
  if (!target) return;
  const data = target.dataset;
  if (data.remakeUpload || data.remakeCamera) {
    remakeSlot = data.remakeUpload || data.remakeCamera;
    app.querySelector(data.remakeUpload ? '#remake-file' : '#remake-camera')?.click();
  } else if (data.remakeWork) remakeUseWork(data.remakeWork);
  else if (data.remakeClear) remakeSet(data.remakeClear, '');
  else if (data.remakeModel && remakeState.model !== data.remakeModel) { remakeState.model = data.remakeModel; remakeState.pending = null; renderRemake(); }
}

function remakeChange(event) {
  if (event.target.id !== 'remake-file' && event.target.id !== 'remake-camera') return;
  const file = event.target.files?.[0];
  event.target.value = '';
  if (file) void remakeReadFile(file, remakeSlot);
}

function remakeSubmitEvent(event) {
  if (event.target.id !== 'remake-form') return;
  event.preventDefault();
  void remakeSubmit();
}

function remakeSet(slot, value, work = null) {
  ++remakeState.uploadVersion;
  remakeState[slot] = value;
  if (slot === 'product') remakeState.productWork = work;
  else remakeState.referencePost = null;
  remakeState.pending = null;
  remakeState.error = '';
  renderRemake();
}

// A picked work stays a server URL for the preview; remakeSubmit turns it into image data.
function remakeUseWork(id) {
  const job = history.find(item => item.id === id);
  if (job?.image) remakeSet('product', job.image, job.id);
}

async function remakeReadFile(file, slot) {
  if (!REMAKE_TYPES.includes(file.type)) { remakeState.error = '请上传 JPG、PNG 或 WebP 图片'; renderRemake(); return; }
  if (file.size > REMAKE_MAX_BYTES) { remakeState.error = '图片不能超过 20 MB'; renderRemake(); return; }
  const version = ++remakeState.uploadVersion;
  try {
    const url = URL.createObjectURL(file);
    let image;
    try { image = await loadImage(url); }
    finally { URL.revokeObjectURL(url); }
    if (version !== remakeState.uploadVersion) return;
    // Phone screenshots are tall; keep enough height that the photo region stays sharp.
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 1600 / Math.max(image.width, image.height));
    canvas.width = Math.round(image.width * scale);
    canvas.height = Math.round(image.height * scale);
    if (Math.min(canvas.width, canvas.height) < 512) throw new Error('图片尺寸过小，请换一张清楚的图片');
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
    remakeSet(slot, canvas.toDataURL('image/jpeg', .88));
  } catch (error) {
    if (version !== remakeState.uploadVersion) return;
    remakeState.error = error.message || '无法读取图片，请换一张清楚的 JPG、PNG 或 WebP 图片';
    if (screen === 'remake') renderRemake();
  }
}

// 同一组参考图、商品和模特复用同一把 idempotencyKey，任一项变化换新 key。
function remakePayload() {
  const config = remakeState.productWork ? {model_source: 'work'} : {model_source: 'preset', model: remakeState.model};
  const signature = JSON.stringify([remakeState.reference, remakeState.product, config]);
  if (!remakeState.pending || remakeState.pending.signature !== signature) {
    remakeState.pending = {signature, idempotencyKey: crypto.randomUUID()};
  }
  return {image: remakeState.product, reference: remakeState.reference, model: config.model || 'female', idempotencyKey: remakeState.pending.idempotencyKey, workflowType: 'remake', workflowConfig: config};
}

async function remakeSubmit() {
  if (remakeState.submitting) return;
  if (!remakeState.reference || !remakeState.product) { remakeState.error = '请先放好参考图和商品'; renderRemake(); return; }
  if (busy || submitting) { remakeState.error = '已有图片正在生成，请完成后再提交。'; renderRemake(); return; }
  const submissionRoute = currentRoute;
  remakeState.submitting = true; submitting = true;
  remakeState.error = '';
  renderRemake();
  try {
    await sessionReady;
    const payload = remakePayload();
    const referencePost = remakeState.referencePost;
    [payload.image, payload.reference] = await Promise.all([sourceData(payload.image), sourceData(payload.reference)]);
    const data = await api('/api/jobs', {method: 'POST', body: JSON.stringify(payload)});
    remakeState.submitting = false; submitting = false;
    Object.assign(remakeState, {reference: '', referencePost: null, product: '', productWork: null, pending: null});
    // Only count a 做参考 once the remake was actually submitted.
    const post = referencePost && findPost(referencePost);
    if (post) void react(post, 'remake', true).catch(() => {});
    const job = mergeJob(data.job);
    toast('拍同款任务已提交');
    if (currentRoute === submissionRoute) { active = job; navigate(`#job/${job.id}`); }
    schedulePoll();
  } catch (error) {
    remakeState.submitting = false; submitting = false;
    busy = history.some(isPending);
    remakeState.error = error.message || '提交失败，请重试';
    if (screen === 'remake') renderRemake();
    else toast(remakeState.error);
  }
}
