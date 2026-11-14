// 衣拍创作台 — 单页三栏（服装上身 / 换姿势 / 换背景）。
// 通过 window.renderStudio / window.openStudioMode 暴露给 app.js。
// 本文件先于 app.js 加载，因此不在顶层调用任何 app.js 的全局函数。

const STUDIO_MODES = {
  tryon: {
    label: '服装上身',
    tab: '服装上身',
    title: '服装上身',
    caption: '上传平铺图或挂拍图，生成模特上身效果。',
    uploadTitle: '上传商品平铺图',
    uploadNote: '平铺图、挂拍图都可以',
    hint: '商品完整、细节清楚，上身效果更好。',
    icon: 'user'
  },
  pose: {
    label: '换姿势',
    tab: '换姿势',
    title: '姿势裂变',
    caption: '同一模特多姿势，每个姿势单独成片。',
    uploadTitle: '上传已生成的上身效果图',
    uploadNote: '建议使用清晰的竖版上身图',
    hint: '一次生成一组独立姿势图，支持逐张查看和保存。',
    icon: 'refresh'
  },
  background: {
    label: '换背景',
    tab: '换背景',
    title: '换背景',
    caption: '给上身效果图换上新的拍摄场景。',
    uploadTitle: '上传上身效果图',
    uploadNote: '人物与服装主体完整',
    hint: '背景会替换为所选场景，人物与服装保持不变。',
    icon: 'image'
  }
};

const STUDIO_SCENES = [
  {value: 'white', label: '白底', dot: 'white'},
  {value: 'studio_gray', label: '灰底', dot: 'gray'},
  {value: 'outdoor_street', label: '街拍', dot: 'street'},
  {value: 'indoor_minimal', label: '室内', dot: 'indoor'},
  {value: 'beach', label: '海边', dot: 'beach'},
  {value: 'cafe', label: '咖啡馆', dot: 'cafe'}
];

const STUDIO_POSE_COUNTS = [4, 6, 8];
const STUDIO_MAX_BYTES = 20 * 1024 * 1024;
const STUDIO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

const studioState = {
  mode: 'tryon',
  upload: '',
  model: 'female',
  poseCount: 4,
  scene: 'white',
  submitting: false,
  error: '',
  pending: null,
  uploadVersion: 0,
  recentVersion: 0
};

let studioBound = false;
let studioWorks = [];
let studioWorksLoaded = false;

function studioModeOf(value) {
  return STUDIO_MODES[value] ? value : 'tryon';
}

function openStudioMode(mode) {
  studioState.mode = studioModeOf(mode);
  studioState.error = '';
  const route = studioState.mode === 'tryon' ? '#create' : `#create/${studioState.mode}`;
  if (location.hash === route || (studioState.mode === 'tryon' && location.hash === '#home')) renderStudio();
  else navigate(route);
}

// 同一张图 + 同一配置复用同一把 idempotencyKey，配置变化换新 key。
function studioSignature() {
  const config = studioState.mode === 'pose' ? studioState.poseCount
    : studioState.mode === 'background' ? studioState.scene
    : studioState.model;
  return JSON.stringify([studioState.mode, studioState.upload, config]);
}

function studioPayload() {
  const signature = studioSignature();
  if (!studioState.pending || studioState.pending.signature !== signature) {
    studioState.pending = {signature, idempotencyKey: crypto.randomUUID()};
  }
  const payload = {image: studioState.upload, model: studioState.mode === 'tryon' ? studioState.model : 'female', idempotencyKey: studioState.pending.idempotencyKey};
  if (studioState.mode === 'pose') Object.assign(payload, {workflowType: 'pose_variation', workflowConfig: {pose_count: studioState.poseCount}});
  if (studioState.mode === 'background') Object.assign(payload, {workflowType: 'background_change', workflowConfig: {scene_type: studioState.scene}});
  return payload;
}

function studioConfigSummary() {
  if (studioState.mode === 'tryon') return studioState.model === 'male' ? '男模特' : '女模特';
  if (studioState.mode === 'pose') return `${studioState.poseCount} 个姿势`;
  const scene = STUDIO_SCENES.find(item => item.value === studioState.scene);
  return scene ? scene.label : '白底';
}

function studioRail() {
  const tools = Object.entries(STUDIO_MODES).map(([key, mode]) => `<button class="rail-tool ${studioState.mode === key ? 'active' : ''}" type="button" data-studio-mode="${key}" aria-pressed="${studioState.mode === key}">${icon(mode.icon)}<span>${mode.label}</span></button>`).join('');
  return `<aside class="studio-rail"><div class="rail-brand"><span class="rail-brand-icon">${icon('camera')}</span><strong>衣拍</strong></div><div class="rail-tools">${tools}</div><div class="rail-links"><a href="#history">作品历史</a><a href="#community">社区</a></div><div class="rail-foot">AI 商品摄影台</div></aside>`;
}

function studioTabs() {
  const tabs = Object.entries(STUDIO_MODES).map(([key, mode]) => `<button class="mode-tab ${studioState.mode === key ? 'active' : ''}" type="button" data-studio-mode="${key}" aria-pressed="${studioState.mode === key}">${mode.tab}</button>`).join('');
  return `<div class="mode-tabs" role="group" aria-label="创作模式">${tabs}</div>`;
}

function studioUploadField(mode) {
  const card = studioState.upload
    ? `<div class="upload-card has-image"><div class="upload-thumb">${photo(studioState.upload, mode.uploadTitle, '', true)}</div><div class="upload-actions"><button type="button" data-studio-upload>换一张 ${icon('refresh')}</button><button type="button" class="remove" data-studio-remove>移除 ${icon('close')}</button></div></div>`
    : `<div class="upload-card"><button type="button" class="upload-dropzone" data-studio-upload>${icon('image')}<strong>${escapeHtml(mode.uploadTitle)}</strong><small>JPG、PNG 或 WebP，最大 20 MB</small><span class="secondary">浏览图片 ${icon('plus')}</span></button></div>`;
  return `<div class="studio-field"><div class="studio-field-label"><span>${studioState.mode === 'pose' ? '输入图片' : '图片'}</span><small>${escapeHtml(mode.uploadNote)}</small></div>${card}<input id="studio-file" type="file" accept="image/jpeg,image/png,image/webp" hidden></div>`;
}

function studioOptions() {
  if (studioState.mode === 'tryon') {
    return `<div class="studio-field"><div class="studio-field-label"><span>模特性别</span><small>默认女模特</small></div><div class="option-grid">${[['female', '女模特'], ['male', '男模特']].map(([value, label]) => `<button class="option-chip ${studioState.model === value ? 'active' : ''}" type="button" data-studio-model="${value}" aria-pressed="${studioState.model === value}"><strong>${label}</strong></button>`).join('')}</div></div>`;
  }
  if (studioState.mode === 'pose') {
    return `<div class="studio-field"><div class="studio-field-label"><span>姿势数量</span><small>每个姿势输出一张独立图片</small></div><div class="option-grid three">${STUDIO_POSE_COUNTS.map(count => `<button class="option-chip ${studioState.poseCount === count ? 'active' : ''}" type="button" data-studio-count="${count}" aria-pressed="${studioState.poseCount === count}"><strong>${count} 个姿势</strong></button>`).join('')}</div></div>`;
  }
  const chips = STUDIO_SCENES.map(scene => `<button class="option-chip ${studioState.scene === scene.value ? 'active' : ''}" type="button" data-studio-scene="${scene.value}" aria-pressed="${studioState.scene === scene.value}"><span class="chip-dot ${scene.dot}"></span><strong>${scene.label}</strong></button>`).join('');
  return `<div class="studio-field"><div class="studio-field-label"><span>场景</span><small>背景替换</small></div><div class="option-grid">${chips}</div></div>`;
}

function studioPreview(mode) {
  const ready = Boolean(studioState.upload);
  const stage = ready
    ? photo(studioState.upload, '上传的创作素材', 'studio-preview-image')
    : `<div class="preview-empty">${icon(mode.icon)}<strong>还没有上传图片</strong><p>${escapeHtml(mode.uploadTitle)}，这里会显示预览。</p></div>`;
  return `<section class="studio-preview"><div class="preview-head"><h2>效果预览</h2><span class="preview-badge ${ready ? 'ready' : ''}">${ready ? '已就绪' : '等待上传'}</span></div><div class="preview-stage">${stage}</div><div class="preview-foot">${escapeHtml(studioConfigSummary())}${ready ? ' · 图片已压缩，提交时使用' : ' · 上传图片后即可生成'}</div></section>`;
}

function studioWorksGrid() {
  if (!studioWorksLoaded) return '<div class="recent-empty">正在加载最近作品…</div>';
  if (!studioWorks.length) return '<div class="recent-empty">还没有作品，生成的第一张会出现在这里。</div>';
  return studioWorks.map(job => {
    const succeeded = job.status === 'succeeded';
    const tag = succeeded ? '' : `<span class="recent-tag">${job.status === 'failed' ? '失败' : '生成中'}</span>`;
    return `<button class="recent-card" type="button" data-studio-job="${escapeHtml(job.id)}" aria-label="查看作品">${photo(succeeded ? job.image : job.original, '最近作品', '', true)}${tag}</button>`;
  }).join('');
}

function renderStudio(routeMode) {
  if (routeMode) studioState.mode = studioModeOf(routeMode);
  const mode = STUDIO_MODES[studioState.mode];
  const disabled = !studioState.upload || studioState.submitting;
  app.innerHTML = `<section class="studio"><div class="studio-shell">${studioRail()}<section class="studio-panel"><div class="studio-panel-head"><h1>${mode.title}</h1><p>${mode.caption}</p></div>${studioTabs()}<form id="studio-form" novalidate>${studioUploadField(mode)}${studioOptions()}<div class="studio-hint">${escapeHtml(mode.hint)}</div><div class="studio-actions"><button class="generate-btn" type="submit" id="studio-generate" ${disabled ? 'disabled' : ''}>${studioState.submitting ? '正在提交…' : `开始生成 ${icon('arrow')}`}</button></div><div class="studio-error" role="alert" ${studioState.error ? '' : 'hidden'}>${escapeHtml(studioState.error)}</div></form></section>${studioPreview(mode)}</div><div class="recent-block"><div class="recent-head"><h2>最近作品</h2><button type="button" data-studio-refresh aria-label="刷新最近作品">${icon('refresh')} 刷新</button></div><div class="recent-grid">${studioWorksGrid()}</div></div></section>`;
  bindStudio();
  watchImages();
  void loadStudioWorks();
}

function bindStudio() {
  const root = app.querySelector('.studio');
  if (!root) return;
  if (!studioBound) {
    studioBound = true;
    app.addEventListener('click', studioClick);
    app.addEventListener('change', studioChange);
    app.addEventListener('submit', studioSubmitEvent);
    app.addEventListener('dragover', studioDragover);
    app.addEventListener('dragleave', studioDragleave);
    app.addEventListener('drop', studioDrop);
  }
  root.classList.toggle('dragover', false);
}

function studioClick(event) {
  const target = event.target.closest('[data-studio-mode],[data-studio-upload],[data-studio-remove],[data-studio-model],[data-studio-count],[data-studio-scene],[data-studio-refresh],[data-studio-job]');
  if (!target) return;
  if (target.hasAttribute('data-studio-mode')) { openStudioMode(target.dataset.studioMode); return; }
  if (target.hasAttribute('data-studio-upload')) { app.querySelector('#studio-file')?.click(); return; }
  if (target.hasAttribute('data-studio-remove')) { studioResetUpload(); return; }
  if (target.hasAttribute('data-studio-model')) { studioChoose('model', target.dataset.studioModel); return; }
  if (target.hasAttribute('data-studio-count')) { studioChoose('poseCount', Number(target.dataset.studioCount)); return; }
  if (target.hasAttribute('data-studio-scene')) { studioChoose('scene', target.dataset.studioScene); return; }
  if (target.hasAttribute('data-studio-refresh')) { void loadStudioWorks(true); return; }
  if (target.hasAttribute('data-studio-job')) {
    const job = studioWorks.find(item => item.id === target.dataset.studioJob);
    if (job) openJob(job);
  }
}

function studioChange(event) {
  if (event.target.id !== 'studio-file') return;
  const file = event.target.files?.[0];
  event.target.value = '';
  if (file) void studioReadFile(file);
}

function studioSubmitEvent(event) {
  if (event.target.id !== 'studio-form') return;
  event.preventDefault();
  void studioSubmit();
}

function studioDragover(event) {
  const card = event.target.closest?.('.upload-card');
  if (!card) return;
  event.preventDefault();
  card.classList.add('dragover');
}

function studioDragleave(event) {
  const card = event.target.closest?.('.upload-card');
  if (!card || card.contains(event.relatedTarget)) return;
  card.classList.remove('dragover');
}

function studioDrop(event) {
  const card = event.target.closest?.('.upload-card');
  if (!card) return;
  event.preventDefault();
  card.classList.remove('dragover');
  const file = event.dataTransfer?.files?.[0];
  if (file) void studioReadFile(file);
}

function studioResetUpload() {
  studioState.upload = '';
  studioState.pending = null;
  studioState.error = '';
  renderStudio();
}

function studioChoose(key, value) {
  if (studioState[key] === value) return;
  studioState[key] = value;
  studioState.pending = null;
  renderStudio();
}

async function studioReadFile(file) {
  if (!STUDIO_TYPES.includes(file.type)) { studioState.error = '请上传 JPG、PNG 或 WebP 图片'; renderStudio(); return; }
  if (file.size > STUDIO_MAX_BYTES) { studioState.error = '图片不能超过 20 MB'; renderStudio(); return; }
  const version = ++studioState.uploadVersion;
  try {
    const url = URL.createObjectURL(file);
    let image;
    try { image = await new Promise((resolve, reject) => { const img = new Image(); img.onload = () => resolve(img); img.onerror = reject; img.src = url; }); }
    finally { URL.revokeObjectURL(url); }
    if (version !== studioState.uploadVersion) return;
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 1200 / Math.max(image.width, image.height));
    canvas.width = Math.round(image.width * scale);
    canvas.height = Math.round(image.height * scale);
    if (Math.min(canvas.width, canvas.height) < 512) throw new Error('图片尺寸过小，请换一张清楚的图片');
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
    studioState.upload = canvas.toDataURL('image/jpeg', .85);
    studioState.pending = null;
    studioState.error = '';
    renderStudio();
  } catch (error) {
    if (version !== studioState.uploadVersion) return;
    studioState.error = error.message || '无法读取图片，请换一张清楚的 JPG、PNG 或 WebP 图片';
    renderStudio();
  }
}

async function studioSubmit() {
  if (studioState.submitting) return;
  if (!studioState.upload) { studioState.error = '请先上传图片'; renderStudio(); return; }
  studioState.submitting = true;
  studioState.error = '';
  const button = app.querySelector('#studio-generate');
  if (button) { button.disabled = true; button.textContent = '正在提交…'; }
  try {
    await sessionReady;
    const data = await api('/api/jobs', {method: 'POST', body: JSON.stringify(studioPayload())});
    studioState.submitting = false;
    studioState.upload = '';
    studioState.pending = null;
    toast('任务已提交');
    navigate(`#job/${data.job.id}`);
    void loadStudioWorks(true);
  } catch (error) {
    studioState.submitting = false;
    studioState.error = error.message || '提交失败，请重试';
    const box = app.querySelector('.studio-error');
    if (box) { box.hidden = false; box.textContent = studioState.error; }
    if (button) { button.disabled = false; button.innerHTML = `开始生成 ${icon('arrow')}`; }
  }
}

async function loadStudioWorks(refresh = false) {
  if (refresh) { studioWorksLoaded = false; const grid = app.querySelector('.recent-grid'); if (grid) grid.innerHTML = '<div class="recent-empty">正在加载最近作品…</div>'; }
  const version = ++studioState.recentVersion;
  try {
    const data = await api('/api/jobs');
    if (version !== studioState.recentVersion) return;
    studioWorks = (data.jobs || []).slice(0, 12);
    studioWorksLoaded = true;
    const grid = app.querySelector('.recent-grid');
    if (grid) grid.innerHTML = studioWorksGrid();
    watchImages();
  } catch (error) {
    if (version !== studioState.recentVersion) return;
    studioWorksLoaded = true;
    studioWorks = [];
    const grid = app.querySelector('.recent-grid');
    if (grid) grid.innerHTML = `<div class="recent-empty">${escapeHtml(error.message || '暂时无法加载最近作品')}</div>`;
  }
}

window.renderStudio = renderStudio;
window.openStudioMode = openStudioMode;
