// Workflow creation studio for Yipai.

const workflows = [
  { id: 'pose-variation', name: '姿势裂变', description: '一张上身照，生成 4 / 6 / 8 张独立姿势图', icon: 'pose', route: '#workflow/pose-variation' },
  { id: 'background-change', name: '背景替换', description: '保留原图主体，切换六种拍摄场景', icon: 'background', route: '#workflow/background-change' }
];

const workflowNames = {
  tryon: '虚拟试穿',
  pose_variation: '姿势裂变',
  background_change: '背景替换'
};

const workflowIcons = {
  tryon: '<path d="M4 8h16l-1 13H5L4 8zM9 8a3 3 0 0 1 6 0"/>',
  pose: '<circle cx="12" cy="5" r="2.5"/><path d="m10 9-3 5 4 2 1-4 4 2 2-3M11 16l-2 5m5-5 3 5"/>',
  background: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 14 8 9l4 4 3-3 6 6"/><circle cx="8.5" cy="8.5" r="1.5"/>'
};

const workflowIcon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${workflowIcons[name] || ''}</svg>`;

let workflowUpload = null;
let workflowSubmitting = false;
let workflowPendingSubmission = null;
let selectedPoseCount = 4;
let selectedSceneType = 'white';

const sceneTypes = [
  { id: 'white', name: '白底', description: '干净电商棚拍', swatch: 'white' },
  { id: 'studio_gray', name: '灰底', description: '柔光摄影棚', swatch: 'gray' },
  { id: 'outdoor_street', name: '街拍', description: '自然都市光线', swatch: 'street' },
  { id: 'indoor_minimal', name: '室内', description: '明亮简约空间', swatch: 'indoor' },
  { id: 'beach', name: '海边', description: '阳光度假氛围', swatch: 'beach' },
  { id: 'cafe', name: '咖啡馆', description: '温暖生活场景', swatch: 'cafe' }
];

function workflowJobName(job) {
  if (job.workflowType === 'background_change') {
    const scene = sceneTypes.find(item => item.id === job.workflowConfig?.scene_type);
    return `背景替换${scene ? ` · ${scene.name}` : ''}`;
  }
  return workflowNames[job.workflowType] || modelName(job.model) + '作品';
}

function workflowJobStatus(job) {
  return job.status === 'succeeded' ? '已完成' : job.status === 'failed' ? '失败' : statusLabel(job);
}

function workflowTopbar() {
  return `<header class="topbar workflow-topbar">
    <a class="brand" href="#home"><span class="brand-symbol">${icon('camera')}</span>衣拍<span class="brand-note">商品的另一面</span></a>
    <div class="header-actions">
      <a class="tasks-link" href="#workflows" aria-current="page">创作工作台</a>
      <a class="tasks-link" href="#home">创作历史</a>
      <button class="profile-edit" id="edit-profile" aria-label="编辑昵称">${icon('user')}<span>${escapeHtml(nickname)}</span></button>
    </div>
  </header>`;
}

function renderWorkflowHistory() {
  const recent = sortedJobs().slice(0, 8);
  return recent.length ? recent.map(job => `
    <article class="workflow-recent-item">
      ${photo(job.image || job.original, workflowJobName(job), 'workflow-recent-image', true)}
      <button class="workflow-recent-open" type="button" data-recent-job="${escapeHtml(job.id)}"><strong>${escapeHtml(workflowJobName(job))}</strong><small>${escapeHtml(workflowJobStatus(job))}</small></button>
    </article>
  `).join('') : '<p class="workflow-recent-empty">生成后的作品会显示在这里</p>';
}

function workflowNavigation(active) {
  return `<aside class="workflow-tool-rail" aria-label="创作功能">
    <p class="workflow-rail-label">创作工具</p>
    <button class="workflow-tool ${active === 'tryon' ? 'active' : ''}" type="button" data-tool="tryon">
      <span class="workflow-tool-icon">${workflowIcon('tryon')}</span><span>虚拟试穿</span>
    </button>
    ${workflows.map(item => `<button class="workflow-tool ${active === item.id ? 'active' : ''}" type="button" data-workflow="${item.id}" ${active === item.id ? 'aria-current="page"' : ''}>
      <span class="workflow-tool-icon">${workflowIcon(item.icon)}</span><span>${escapeHtml(item.name)}</span>
    </button>`).join('')}
    <div class="workflow-rail-foot"><span class="workflow-status-dot"></span>3 项创作工具</div>
  </aside>`;
}

function workflowRecentPanel() {
  return `<aside class="workflow-recent-panel" aria-label="最近任务">
    <div class="workflow-recent-heading"><h2>最近任务</h2><a href="#home">全部</a></div>
    <div class="workflow-recent-list">${renderWorkflowHistory()}</div>
  </aside>`;
}

function refreshWorkflowRecent() {
  const panel = app.querySelector('.workflow-recent-list');
  if (!panel) return;
  panel.innerHTML = renderWorkflowHistory();
  panel.querySelectorAll('[data-recent-job]').forEach(button => button.addEventListener('click', () => {
    const job = history.find(item => item.id === button.dataset.recentJob);
    if (job) openJob(job);
  }));
  watchImages(panel);
}

function renderWorkflowsHub() {
  setScreen('workflows');
  app.innerHTML = `
    <section class="page workflow-page">
      ${workflowTopbar()}
      <div class="workflow-studio-grid workflow-hub-grid">
        ${workflowNavigation('')}
        ${workflowRecentPanel()}
        <section class="workflow-hub-main">
          <span class="eyebrow">YIPAI CREATION STUDIO</span>
          <h1>选一个工作流，开始创作</h1>
          <p class="muted">虚拟试穿、姿势裂变和背景替换都在这里完成。</p>
          <div class="workflow-hub-cards">
            <button class="workflow-hub-card" type="button" data-tool="tryon">
              <span class="workflow-hub-icon">${workflowIcon('tryon')}</span><span><strong>虚拟试穿</strong><small>上传商品图，查看模特上身效果</small></span>${icon('arrow')}
            </button>
            ${workflows.map(item => `<button class="workflow-hub-card" type="button" data-workflow="${item.id}">
              <span class="workflow-hub-icon">${workflowIcon(item.icon)}</span><span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.description)}</small></span>${icon('arrow')}
            </button>`).join('')}
          </div>
        </section>
        <section class="workflow-preview workflow-hub-preview">
          <div class="workflow-preview-heading"><div><span class="eyebrow">预览区域</span><h2>你的创作空间</h2></div></div>
          <div class="workflow-preview-empty">${icon('image')}<strong>从左侧选择创作工具</strong><p>上传图片后可在这里检查输入图，再提交生成任务。</p></div>
        </section>
      </div>
      ${errorSlot}
    </section>`;

  bindWorkflowStudio();
  document.querySelector('#edit-profile')?.addEventListener('click', editProfile);
  watchImages();
}

function workflowPageMarkup(type) {
  const isPose = type === 'pose_variation';
  const item = isPose ? workflows[0] : workflows[1];
  const title = item.name;
  const description = isPose
    ? '从一张模特上身图，生成多姿势商业大片。'
    : '保留原图中的商品与人物，只替换拍摄背景。';
  const uploadLabel = isPose ? '上传模特上身照' : '上传需要换背景的原图';
  const uploadHint = isPose ? '建议上传清晰的竖版上身图，人物与服装主体完整。' : '支持商品图和模特上身照；无人商品图不会新增模特。';
  const options = isPose ? `
    <div class="workflow-section">
      <div class="workflow-section-title"><div><h2>生成数量</h2><p>每个姿势单独生成一张完整图片。</p></div><span class="workflow-step">02</span></div>
      <div class="pose-count-options">${[4, 6, 8].map(count => `<button class="pose-count-option ${selectedPoseCount === count ? 'selected' : ''}" type="button" data-count="${count}" aria-pressed="${selectedPoseCount === count}" ${workflowSubmitting ? 'disabled' : ''}><strong>${count}</strong><span>个姿势</span></button>`).join('')}</div>
    </div>` : `
    <div class="workflow-section">
      <div class="workflow-section-title"><div><h2>背景场景</h2><p>选一个适合服装风格的拍摄环境。</p></div><span class="workflow-step">02</span></div>
      <div class="scene-type-grid">${sceneTypes.map(scene => `<button class="scene-type-card ${selectedSceneType === scene.id ? 'selected' : ''}" type="button" data-scene="${scene.id}" aria-pressed="${selectedSceneType === scene.id}" ${workflowSubmitting ? 'disabled' : ''}><span class="scene-swatch ${scene.swatch}"></span><span class="scene-card-copy"><strong>${escapeHtml(scene.name)}</strong><small>${escapeHtml(scene.description)}</small></span><span class="scene-check">${selectedSceneType === scene.id ? icon('check') : ''}</span></button>`).join('')}</div>
    </div>`;

  return `<section class="page workflow-page">
    ${workflowTopbar()}
    <div class="workflow-studio-grid">
      ${workflowNavigation(isPose ? 'pose-variation' : 'background-change')}
      ${workflowRecentPanel()}
      <section class="workflow-config-panel">
        <div class="workflow-config-heading"><span class="eyebrow">创作配置</span><h1>${escapeHtml(title)}</h1><p>${escapeHtml(description)}</p></div>
        <div class="workflow-form">
          <section class="workflow-section">
            <div class="workflow-section-title"><div><h2>${escapeHtml(uploadLabel)}</h2><p>${escapeHtml(uploadHint)}</p></div><span class="workflow-step">01</span></div>
            <div class="workflow-upload-area ${workflowUpload ? 'has-image' : ''}">
              ${workflowUpload ? `<div class="workflow-upload-thumb">${photo(workflowUpload, uploadLabel, '', true)}<button type="button" class="text-button" id="workflow-reupload" ${workflowSubmitting ? 'disabled' : ''}>换一张 ${icon('refresh')}</button></div>` : `<button class="workflow-dropzone" type="button" id="workflow-upload-btn" ${workflowSubmitting ? 'disabled' : ''}>${icon('image')}<strong>${isPose ? '选择一张上身效果图' : '选择商品图或模特照片'}</strong><small>JPG、PNG 或 WebP，最大 20 MB</small><span class="secondary">浏览图片 ${icon('plus')}</span></button>`}
              <input id="workflow-local-file" type="file" accept="image/jpeg,image/png,image/webp" hidden />
            </div>
          </section>
          ${options}
          <div class="workflow-form-footnote"><span>${icon('warning')}</span><p>生成结果可能改变细节，请在使用前核对服装颜色、版型与图案。</p></div>
          <div class="workflow-submit-block">
            <button class="primary" id="submit-workflow" type="button" ${!workflowUpload || workflowSubmitting ? 'disabled' : ''}>${workflowSubmitting ? '正在提交…' : '开始生成'} ${icon('arrow')}</button>
            <p class="helper">${isPose ? `输出 ${selectedPoseCount} 张独立姿势图` : '输出一张替换背景效果图'} · 生成结果将保存在创作历史</p>
          </div>
        </div>
      </section>
      <section class="workflow-preview">
        <div class="workflow-preview-heading"><div><span class="eyebrow">效果预览</span><h2>${workflowUpload ? '输入图片' : '待上传图片'}</h2></div><span class="workflow-preview-badge">${workflowUpload ? '已就绪' : '等待上传'}</span></div>
        <div class="workflow-preview-stage ${workflowUpload ? 'has-image' : ''}">${workflowUpload ? photo(workflowUpload, '创作输入图片', 'workflow-main-preview') : `<div class="workflow-preview-empty">${icon('image')}<strong>上传后预览创作素材</strong><p>${escapeHtml(uploadLabel)}会显示在这里。你可以先检查图片，再调整生成选项。</p></div>`}</div>
        ${workflowUpload ? `<div class="workflow-preview-caption"><span>${icon('check')}</span><span><strong>素材已准备</strong><small>这张图片将作为商品与主体参考。</small></span></div>` : ''}
        <div class="workflow-preview-note"><strong>${isPose ? '姿势裂变' : `背景替换 · ${sceneTypes.find(scene => scene.id === selectedSceneType)?.name || '白底'}`}</strong><p>${isPose ? `同一人物呈现 ${selectedPoseCount} 种姿势，每种姿势分别生成完整图片。` : '保留原图主体、服装细节和构图；无人商品图保持无人，只替换背景与环境光线。'}</p></div>
      </section>
    </div>
    ${errorSlot}
  </section>`;
}

function renderPoseVariationPage() {
  setScreen('workflow-detail');
  app.innerHTML = workflowPageMarkup('pose_variation');
  bindWorkflowPage('pose_variation');
}

function renderBackgroundChangePage() {
  setScreen('workflow-detail');
  app.innerHTML = workflowPageMarkup('background_change');
  bindWorkflowPage('background_change');
}

function bindWorkflowStudio() {
  app.querySelectorAll('[data-workflow]').forEach(button => button.addEventListener('click', () => {
    const target = workflows.find(item => item.id === button.dataset.workflow);
    if (target) navigate(target.route);
  }));
  app.querySelectorAll('[data-tool="tryon"]').forEach(button => button.addEventListener('click', () => {
    if (draft) navigate('#prepare');
    else input.click();
  }));
  app.querySelectorAll('[data-recent-job]').forEach(button => button.addEventListener('click', () => {
    const job = history.find(item => item.id === button.dataset.recentJob);
    if (job) openJob(job);
  }));
}

function bindWorkflowPage(type) {
  bindWorkflowStudio();
  document.querySelector('#edit-profile')?.addEventListener('click', editProfile);
  const fileInput = document.querySelector('#workflow-local-file');
  const uploadButton = document.querySelector('#workflow-upload-btn');
  const reuploadButton = document.querySelector('#workflow-reupload');
  const submitButton = document.querySelector('#submit-workflow');

  if (uploadButton) uploadButton.onclick = () => fileInput.click();
  if (reuploadButton) reuploadButton.onclick = () => fileInput.click();
  if (fileInput) fileInput.onchange = async () => {
    const file = fileInput.files?.[0];
    fileInput.value = '';
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) { pageError('图片不能超过 20 MB，请换一张'); return; }
    try {
      const url = URL.createObjectURL(file);
      let img;
      try { img = await loadImage(url); }
      finally { URL.revokeObjectURL(url); }
      const canvas = document.createElement('canvas');
      const scale = Math.min(1, 1200 / Math.max(img.width, img.height));
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      if (Math.min(canvas.width, canvas.height) < 512) throw new Error('图片尺寸过小，请换一张清楚的图片');
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      workflowUpload = canvas.toDataURL('image/jpeg', .85);
      workflowPendingSubmission = null;
      type === 'pose_variation' ? renderPoseVariationPage() : renderBackgroundChangePage();
    } catch (error) {
      pageError(error.message || '无法读取图片，请上传清晰的 JPG、PNG 或 WebP 图片');
    }
  };

  app.querySelectorAll('[data-count]').forEach(button => button.addEventListener('click', () => {
    selectedPoseCount = Number(button.dataset.count);
    workflowPendingSubmission = null;
    renderPoseVariationPage();
  }));
  app.querySelectorAll('[data-scene]').forEach(button => button.addEventListener('click', () => {
    selectedSceneType = button.dataset.scene;
    workflowPendingSubmission = null;
    renderBackgroundChangePage();
  }));
  if (submitButton) submitButton.onclick = () => void submitWorkflow(type, type === 'pose_variation' ? {pose_count: selectedPoseCount} : {scene_type: selectedSceneType});
  watchImages();
}

async function submitWorkflow(type, config) {
  if (!workflowUpload) return;
  if (busy || submitting || workflowSubmitting) {
    pageError('已有图片正在生成，请完成后再提交。');
    return;
  }

  const submissionRoute = currentRoute;
  const source = workflowUpload;
  const configKey = JSON.stringify(config);
  if (!workflowPendingSubmission || workflowPendingSubmission.source !== source || workflowPendingSubmission.type !== type || workflowPendingSubmission.configKey !== configKey) {
    workflowPendingSubmission = {source, type, configKey, idempotencyKey: crypto.randomUUID()};
  }
  const idempotencyKey = workflowPendingSubmission.idempotencyKey;
  workflowSubmitting = true;
  submitting = true;
  const button = document.querySelector('#submit-workflow');
  if (button) { button.disabled = true; button.textContent = '正在提交…'; }
  pageError('');

  try {
    await sessionReady;
    const data = await api('/api/jobs', {method:'POST', body:JSON.stringify({
      image: source,
      model: 'female',
      idempotencyKey,
      workflowType: type,
      workflowConfig: config
    })});
    const job = mergeJob({...data.job, workflowType: type, workflowConfig: config});
    workflowPendingSubmission = null;
    workflowSubmitting = false;
    submitting = false;
    busy = history.some(isPending);
    active = job;
    toast(`${workflowJobName(job)}任务已提交`);
    if (currentRoute === submissionRoute) navigate(`#job/${job.id}`);
    else if (screen === 'workflows' || screen === 'workflow-detail') void renderRoute();
    else if (screen === 'home') updateHome();
    schedulePoll();
  } catch (error) {
    workflowSubmitting = false;
    submitting = false;
    busy = history.some(isPending);
    if (currentRoute === submissionRoute && screen === 'workflow-detail') {
      type === 'pose_variation' ? renderPoseVariationPage() : renderBackgroundChangePage();
      pageError(error.message || '提交失败，请重试');
    } else {
      if (screen === 'workflows' || screen === 'workflow-detail') void renderRoute();
      toast(error.message || '提交失败，请重试');
    }
  }
}
