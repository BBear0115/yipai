// 创意裂变 — 一张图变出多张：换姿势 / 换背景。
// 虚拟试穿走首页「开拍」，创作历史在「我的」，这里只负责这两个工作流。
// 本文件先于 app.js 加载，因此不在顶层调用任何 app.js 的全局函数。

const STUDIO_MODES = {
  pose: {
    tab: '换姿势',
    caption: '同一模特多姿势，每个姿势单独成片。',
    uploadTitle: '上传模特上身图',
    uploadNote: '建议使用清晰的竖版上身图',
    hint: '一次生成一组独立姿势图，支持逐张查看和保存。',
    icon: '<circle cx="12" cy="5" r="2.5"/><path d="m10 9-3 5 4 2 1-4 4 2 2-3M11 16l-2 5m5-5 3 5"/>'
  },
  background: {
    tab: '换背景',
    caption: '保留人物与服装，换上新的拍摄场景。',
    uploadTitle: '上传需要换背景的图片',
    uploadNote: '商品图或模特上身图都可以',
    hint: '背景会替换为所选场景，人物与服装保持不变；无人商品图不会新增模特。',
    icon: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 14 8 9l4 4 3-3 6 6"/><circle cx="8.5" cy="8.5" r="1.5"/>'
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

// History cards, task status and result pages name jobs with these.
const workflowNames = {
  tryon: '虚拟试穿',
  pose_variation: '姿势裂变',
  background_change: '背景替换',
  remake: '拍同款'
};

function workflowJobName(job) {
  if (job.workflowType === 'background_change') {
    const scene = STUDIO_SCENES.find(item => item.value === job.workflowConfig?.scene_type);
    return `背景替换${scene ? ` · ${scene.label}` : ''}`;
  }
  return workflowNames[job.workflowType] && job.workflowType !== 'tryon' ? workflowNames[job.workflowType] : `${modelName(job.model)}作品`;
}

const studioState = {
  mode: 'pose',
  upload: '',
  poseCount: 4,
  scene: 'white',
  submitting: false,
  error: '',
  pending: null,
  uploadVersion: 0
};

let studioBound = false;

function studioModeOf(value) {
  return STUDIO_MODES[value] ? value : 'pose';
}

function openStudioMode(mode) {
  studioState.mode = studioModeOf(mode);
  studioState.error = '';
  navigate(studioState.mode === 'pose' ? '#variations' : '#variations/background', true);
}

// 同一张图 + 同一配置复用同一把 idempotencyKey，配置变化换新 key。
function studioSignature() {
  const config = studioState.mode === 'pose' ? studioState.poseCount : studioState.scene;
  return JSON.stringify([studioState.mode, studioState.upload, config]);
}

function studioPayload() {
  const signature = studioSignature();
  if (!studioState.pending || studioState.pending.signature !== signature) {
    studioState.pending = {signature, idempotencyKey: crypto.randomUUID()};
  }
  const workflow = studioState.mode === 'pose'
    ? {workflowType: 'pose_variation', workflowConfig: {pose_count: studioState.poseCount}}
    : {workflowType: 'background_change', workflowConfig: {scene_type: studioState.scene}};
  return {image: studioState.upload, model: 'female', idempotencyKey: studioState.pending.idempotencyKey, ...workflow};
}

function studioTabs() {
  const tabs = Object.entries(STUDIO_MODES).map(([key, mode]) => `<button class="mode-tab ${studioState.mode === key ? 'active' : ''}" type="button" data-studio-mode="${key}" aria-pressed="${studioState.mode === key}"><svg viewBox="0 0 24 24" aria-hidden="true">${mode.icon}</svg>${mode.tab}</button>`).join('');
  return `<div class="mode-tabs" role="group" aria-label="裂变方式">${tabs}</div>`;
}

// Empty state is a picker: camera and album stacked on the left, recent finished works scrolling on the right.
function studioRecentWorks() {
  return sortedJobs().filter(job => job.status === 'succeeded' && job.image).slice(0, 24);
}

function studioUploadField(mode) {
  const works = studioRecentWorks();
  const workList = works.length
    ? works.map(job => `<button type="button" class="picker-work" data-studio-work="${escapeHtml(job.id)}" aria-label="使用作品：${escapeHtml(workflowJobName(job))}，${escapeHtml(job.date)}"><img src="${escapeHtml(job.image)}" alt="" loading="lazy" decoding="async"></button>`).join('')
    : `<p class="picker-empty">${jobsLoaded ? '生成过的作品会出现在这里，可直接拿来再创作' : '正在加载作品…'}</p>`;
  const card = studioState.upload
    ? `<div class="upload-card has-image"><div class="upload-thumb">${photo(studioState.upload, mode.uploadTitle)}</div><div class="upload-actions"><button type="button" class="secondary" data-studio-remove>换一张 ${icon('refresh')}</button></div></div>`
    : `<div class="upload-card picker"><div class="picker-sources"><button type="button" class="picker-source" data-studio-camera>${icon('camera')}<span>拍照</span></button><button type="button" class="picker-source" data-studio-upload>${icon('image')}<span>相册</span></button></div><div class="picker-works" role="group" aria-label="从我的作品中选择">${workList}</div></div>`;
  return `<div class="studio-field"><div class="studio-field-label"><span>图片</span><small>${escapeHtml(mode.uploadNote)}</small></div>${card}<input id="studio-file" type="file" accept="image/jpeg,image/png,image/webp" hidden><input id="studio-camera" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden></div>`;
}

function studioOptions() {
  if (studioState.mode === 'pose') {
    return `<div class="studio-field"><div class="studio-field-label"><span>姿势数量</span><small>每个姿势输出一张独立图片</small></div><div class="option-grid three">${STUDIO_POSE_COUNTS.map(count => `<button class="option-chip ${studioState.poseCount === count ? 'active' : ''}" type="button" data-studio-count="${count}" aria-pressed="${studioState.poseCount === count}"><strong>${count} 个姿势</strong></button>`).join('')}</div></div>`;
  }
  const chips = STUDIO_SCENES.map(scene => `<button class="option-chip ${studioState.scene === scene.value ? 'active' : ''}" type="button" data-studio-scene="${scene.value}" aria-pressed="${studioState.scene === scene.value}"><span class="chip-dot ${scene.dot}"></span><strong>${scene.label}</strong></button>`).join('');
  return `<div class="studio-field"><div class="studio-field-label"><span>场景</span><small>选一个适合服装风格的环境</small></div><div class="option-grid three">${chips}</div></div>`;
}

function renderVariations(routeMode) {
  studioState.mode = studioModeOf(routeMode);
  const mode = STUDIO_MODES[studioState.mode];
  const disabled = !studioState.upload || studioState.submitting;
  const summary = studioState.mode === 'pose' ? `输出 ${studioState.poseCount} 张独立姿势图` : `输出一张${STUDIO_SCENES.find(scene => scene.value === studioState.scene)?.label || '白底'}背景图`;
  app.innerHTML = `<section class="page detail-page variations-page">${subTop('创意裂变', home)}${studioTabs()}<p class="variations-caption">${escapeHtml(mode.caption)}</p><form id="studio-form" novalidate>${studioUploadField(mode)}${studioOptions()}<p class="studio-hint">${escapeHtml(mode.hint)}</p><div class="inline-error" role="alert" ${studioState.error ? '' : 'hidden'}>${escapeHtml(studioState.error)}</div><div class="bottom-action"><button class="primary" type="submit" id="studio-generate" ${disabled ? 'disabled' : ''}>${studioState.submitting ? '正在提交…' : `开始生成 ${icon('arrow')}`}</button><p class="helper">${summary}，完成后可在「我的」查看</p></div></form></section>`;
  bindHeader(home);
  bindStudio();
  watchImages();
  // Works arrive with the session; refresh the picker once they do.
  if (!jobsLoaded && !studioState.upload) sessionReady.then(() => { if (screen === 'variations' && jobsLoaded && !studioState.upload) renderVariations(studioState.mode); });
}

function bindStudio() {
  if (studioBound) return;
  studioBound = true;
  app.addEventListener('click', studioClick);
  app.addEventListener('change', studioChange);
  app.addEventListener('submit', studioSubmitEvent);
  app.addEventListener('dragover', studioDragover);
  app.addEventListener('dragleave', studioDragleave);
  app.addEventListener('drop', studioDrop);
}

function studioClick(event) {
  if (screen !== 'variations') return;
  const target = event.target.closest('[data-studio-mode],[data-studio-upload],[data-studio-camera],[data-studio-work],[data-studio-remove],[data-studio-count],[data-studio-scene]');
  if (!target) return;
  if (target.hasAttribute('data-studio-mode')) { openStudioMode(target.dataset.studioMode); return; }
  if (target.hasAttribute('data-studio-upload')) { app.querySelector('#studio-file')?.click(); return; }
  if (target.hasAttribute('data-studio-camera')) { app.querySelector('#studio-camera')?.click(); return; }
  if (target.hasAttribute('data-studio-work')) { studioUseWork(target.dataset.studioWork); return; }
  if (target.hasAttribute('data-studio-remove')) { studioResetUpload(); return; }
  if (target.hasAttribute('data-studio-count')) { studioChoose('poseCount', Number(target.dataset.studioCount)); return; }
  if (target.hasAttribute('data-studio-scene')) studioChoose('scene', target.dataset.studioScene);
}

function studioChange(event) {
  if (event.target.id !== 'studio-file' && event.target.id !== 'studio-camera') return;
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
  renderVariations(studioState.mode);
}

// A picked work stays a server URL for the preview; studioSubmit turns it into image data.
function studioUseWork(id) {
  const job = history.find(item => item.id === id);
  if (!job?.image) return;
  ++studioState.uploadVersion;
  studioState.upload = job.image;
  studioState.pending = null;
  studioState.error = '';
  renderVariations(studioState.mode);
}

function studioChoose(key, value) {
  if (studioState[key] === value) return;
  studioState[key] = value;
  studioState.pending = null;
  renderVariations(studioState.mode);
}

async function studioReadFile(file) {
  if (!STUDIO_TYPES.includes(file.type)) { studioState.error = '请上传 JPG、PNG 或 WebP 图片'; renderVariations(studioState.mode); return; }
  if (file.size > STUDIO_MAX_BYTES) { studioState.error = '图片不能超过 20 MB'; renderVariations(studioState.mode); return; }
  const version = ++studioState.uploadVersion;
  try {
    const url = URL.createObjectURL(file);
    let image;
    try { image = await loadImage(url); }
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
  } catch (error) {
    if (version !== studioState.uploadVersion) return;
    studioState.error = error.message || '无法读取图片，请换一张清楚的 JPG、PNG 或 WebP 图片';
  }
  if (screen === 'variations') renderVariations(studioState.mode);
}

async function studioSubmit() {
  if (studioState.submitting) return;
  if (!studioState.upload) { studioState.error = '请先上传图片'; renderVariations(studioState.mode); return; }
  if (busy || submitting) { studioState.error = '已有图片正在生成，请完成后再提交。'; renderVariations(studioState.mode); return; }
  const submissionRoute = currentRoute;
  studioState.submitting = true; submitting = true;
  studioState.error = '';
  renderVariations(studioState.mode);
  try {
    await sessionReady;
    const payload = studioPayload();
    payload.image = await sourceData(payload.image);
    const data = await api('/api/jobs', {method: 'POST', body: JSON.stringify(payload)});
    studioState.submitting = false; submitting = false;
    studioState.upload = '';
    studioState.pending = null;
    const job = mergeJob({...data.job, workflowType: payload.workflowType, workflowConfig: payload.workflowConfig});
    toast(`${workflowJobName(job)}任务已提交`);
    if (currentRoute === submissionRoute) { active = job; navigate(`#job/${job.id}`); }
    schedulePoll();
  } catch (error) {
    studioState.submitting = false; submitting = false;
    busy = history.some(isPending);
    studioState.error = error.message || '提交失败，请重试';
    if (screen === 'variations') renderVariations(studioState.mode);
    else toast(studioState.error);
  }
}
