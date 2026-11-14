const app = document.querySelector('#app');
const dock = document.querySelector('#dock');
const input = document.querySelector('#file-input');
const icons = {
  back: '<path d="m14 5-7 7 7 7"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  camera: '<path d="M3 7h5l2-3h4l2 3h5v13H3z"/><circle cx="12" cy="13" r="4"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-1l2 6M4 12l2 6a7 7 0 0 0 12-1"/>',
  save: '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
  share: '<path d="M12 15V3m-4 4 4-4 4 4M6 11H4v10h16V11h-2"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  zoom: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6m-3-3v6"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-6 16-6 16 0"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',
  warning: '<path d="m12 3 10 18H2zM12 9v5m0 3v1"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || ''}</svg>`;
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const modelName = value => value === 'male' ? '男模特' : '女模特';
const isPending = job => ['queued', 'running'].includes(job.status);
const statusLabel = job => ({queued:'排队中', running:'生成中', failed:'生成失败', succeeded:'已完成'}[job.status] || '加载中');
let model = 'female', nickname = '衣拍访客';
try { model = localStorage.getItem('yipai-model') === 'male' ? 'male' : 'female'; nickname = localStorage.getItem('yipai-nickname') || nickname; } catch {}
let history = [], posts = [], draft = null, active = null, screen = 'home';
let busy = false, submitting = false, toastTimer, pollTimer, pendingSubmission = null;
let currentRoute = '', routeVersion = 0, homeSignature = '', pollError = '';
let sessionReady, sessionError = '', jobsLoaded = false;
const scrollPositions = new Map();
const publishDrafts = new Map();

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type':'application/json', ...options.headers}});
  let body;
  try { body = await response.json(); } catch { throw new Error('服务暂时无法连接，请重试'); }
  if (!response.ok) throw new Error(body.error || '请求失败，请重试');
  return body;
}
function toast(message) {
  const el = document.querySelector('#toast');
  el.textContent = message; el.classList.add('show'); clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}
function pageError(message, host = app, retry) {
  const box = host.querySelector('[data-page-error]');
  if (!box) return;
  box.hidden = !message;
  box.innerHTML = message ? `<span>${escapeHtml(message)}</span>${retry ? '<button class="text-button" data-retry>重试</button>' : ''}` : '';
  box.querySelector('[data-retry]')?.addEventListener('click', retry);
}
const errorSlot = '<div class="inline-error" data-page-error role="alert" hidden></div>';
function normalizeJob(job) {
  return {...job, date: new Date(job.created).toLocaleString('zh-CN', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'})};
}
function mergeJob(job) {
  const value = normalizeJob(job);
  history = [value, ...history.filter(item => item.id !== value.id)];
  busy = submitting || history.some(isPending);
  return value;
}
async function syncJobs() {
  const data = await api('/api/jobs');
  history = data.jobs.map(normalizeJob); jobsLoaded = true;
  busy = submitting || history.some(isPending);
}
function sortedJobs() {
  return [...history].sort((a, b) => Number(isPending(b)) - Number(isPending(a)) || new Date(b.created) - new Date(a.created));
}

// Hash routes identify server-backed tasks. Navigation never creates a generation request.
function navigate(route, replace = false) {
  if (currentRoute) scrollPositions.set(currentRoute, window.scrollY || 0);
  if (location.hash !== route) {
    window.history[replace ? 'replaceState' : 'pushState']({yipai:true}, '', route);
  }
  void renderRoute();
}
function home() { navigate('#home'); }
function historyPage() { home(); void refreshHome(); }
function communityPage() { navigate('#community'); }
function prepare() { if (draft) navigate('#prepare'); else home(); }
function resultPage(job) { active = mergeJob(job); navigate(`#job/${job.id}`); }
function postPage(post) { if (post) navigate(`#post/${post.id}`); }
function publishPage(job) { active = job; navigate(`#publish/${job.id}`); }
function openJob(job) { active = mergeJob(job); navigate(`#job/${job.id}`); }
function setScreen(value, showDock = false) {
  screen = value; dock.classList.toggle('contextual', !showDock);
  app.classList.toggle('with-dock', showDock);
  for (const [id, valueForTab] of [['my-tab', 'home'], ['community-tab', 'community']]) {
    const tab = document.getElementById(id);
    tab.classList.toggle('active', value === valueForTab);
    if (value === valueForTab) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current');
  }
}
async function renderRoute() {
  closeOverlay(false);
  if (!location.hash) window.history.replaceState({yipai:true}, '', '#home');
  const version = ++routeVersion;
  const route = location.hash || '#home';
  if (currentRoute && currentRoute !== route) scrollPositions.set(currentRoute, window.scrollY || 0);
  currentRoute = route;
  const parts = route.slice(1).split('/');
  const restore = () => window.scrollTo(0, scrollPositions.get(route) || 0);
  if (parts[0] === 'home') {
    setScreen('studio', false);
    if (typeof renderStudio === 'function') renderStudio(); else renderMy();
    restore();
    return;
  }
  if (parts[0] === 'create') {
    setScreen('studio', false);
    if (typeof renderStudio === 'function') renderStudio(parts[1]); else renderMy();
    restore();
    return;
  }
  if (parts[0] === 'history') {
    setScreen('home', true); renderMy(); restore(); return;
  }
  if (parts[0] === 'prepare') {
    if (!draft) { navigate('#home', true); toast('请重新选择商品图'); return; }
    renderPrepare(); restore(); return;
  }
  if (parts[0] === 'community') {
    setScreen('community', true); renderCommunity(); restore();
    try { await loadPosts(); if (version === routeVersion) refreshCommunity(); }
    catch (error) { if (version === routeVersion) pageError(error.message, app, communityPage); }
    return;
  }
  if (parts[0] === 'tasks') {
    await openTasksPage();
    restore();
    return;
  }
  if (parts[0] === 'workflows') {
    setScreen('workflows');
    renderWorkflowsHub();
    restore();
    return;
  }
  if (parts[0] === 'workflow') {
    if (parts[1] === 'pose-variation') {
      renderPoseVariationPage();
      restore();
      return;
    }
    if (parts[1] === 'background-change') {
      renderBackgroundChangePage();
      restore();
      return;
    }
  }
  const validId = /^[a-f0-9]{32}$/.test(parts[1] || '');
  if ((parts[0] === 'job' || parts[0] === 'publish') && validId) {
    let job = history.find(item => item.id === parts[1]);
    if (!job) {
      setScreen('loading');
      app.innerHTML = `<section class="page">${subTop('正在加载', home)}<div class="loading-page"><div class="spinner"></div><p>正在找回作品</p></div></section>`;
      try { await sessionReady; job = mergeJob((await api(`/api/jobs/${parts[1]}`)).job); }
      catch (error) { if (version === routeVersion) renderUnavailable(error.message, '#home'); return; }
    }
    if (version !== routeVersion) return;
    active = job;
    if (parts[0] === 'publish') {
      if (job.status !== 'succeeded') { navigate(`#job/${job.id}`, true); return; }
      renderPublish(job);
    } else renderJob(job);
    restore();
    if (isPending(job)) schedulePoll();
    return;
  }
  if (parts[0] === 'post' && (validId || examples.some(post => post.id === parts[1]))) {
    let post = findPost(parts[1]);
    if (!post) {
      setScreen('loading'); app.innerHTML = `<section class="page">${subTop('社区作品', communityPage)}<div class="loading-page"><div class="spinner"></div></div></section>`;
      try { post = (await api(`/api/posts/${parts[1]}`)).post; posts = [post, ...posts.filter(item => item.id !== post.id)]; }
      catch (error) { if (version === routeVersion) renderUnavailable(error.message, '#community'); return; }
    }
    if (version === routeVersion) { renderPost(post); restore(); }
    return;
  }
  navigate('#home', true);
}
function renderUnavailable(message, destination) {
  setScreen('unavailable');
  app.innerHTML = `<section class="page">${subTop('暂时无法打开', () => navigate(destination))}<div class="state-panel">${icon('warning')}<h1>暂时无法打开</h1><p>${escapeHtml(message)}</p><button class="primary" id="reload-route">重新加载</button><button class="text-button" id="return-route">返回</button></div></section>`;
  bindHeader(() => navigate(destination));
  document.querySelector('#reload-route').onclick = () => void renderRoute();
  document.querySelector('#return-route').onclick = () => navigate(destination);
}
function subTop(title, back = home, more = false) {
  // Bind after rendering via bindHeader so callbacks never become inline attributes.
  return `<header class="sub-top"><button class="icon-button" id="back" aria-label="返回">${icon('back')}</button><h1>${title}</h1>${more ? `<button class="icon-button" id="more" aria-label="更多操作">${icon('more')}</button>` : '<span class="header-spacer"></span>'}</header>`;
}
function bindHeader(back = home) { document.querySelector('#back')?.addEventListener('click', back); }

function photo(src, alt, classes = '', lazy = false) {
  return `<div class="image-frame ${classes}"><img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}" ${lazy ? 'loading="lazy"' : ''} decoding="async"><div class="image-error" hidden><span>图片暂时无法加载</span><button class="secondary" type="button" data-image-retry>重新加载</button></div></div>`;
}
let actionObserver;
function observeActions() {
  if (typeof ResizeObserver === 'undefined') return;
  actionObserver?.disconnect();
  const footer = app.querySelector('.bottom-action, .result-actions');
  const page = app.querySelector('.detail-page');
  if (!footer || !page) return;
  const measure = () => page.style.setProperty('--action-height', `${getComputedStyle(footer).position === 'fixed' ? footer.getBoundingClientRect().height : 0}px`);
  actionObserver = new ResizeObserver(measure); actionObserver.observe(footer); measure();
}
function watchImages(root = app) {
  root.querySelectorAll('.image-frame').forEach(frame => {
    const img = frame.querySelector('img');
    const failure = frame.querySelector('.image-error');
    const ready = () => { frame.classList.add('loaded'); frame.classList.remove('broken'); failure.hidden = true; };
    const failed = () => { frame.classList.add('broken'); failure.hidden = false; };
    img.onload = ready; img.onerror = failed;
    const retry = frame.querySelector('[data-image-retry]');
    if (retry) retry.onclick = event => {
      event.stopPropagation(); failure.hidden = true; frame.classList.remove('broken', 'loaded');
      const src = img.getAttribute('src'); img.removeAttribute('src'); img.setAttribute('src', src);
    };
    if (img.complete) { if (img.naturalWidth) ready(); else failed(); }
  });
  observeActions();
}
function examplePreview() {
  return `<section class="example-preview"><div class="section-heading"><h2>一件商品，换种呈现</h2><span class="tag">效果示例</span></div><div class="example-pair" id="view-example" role="button" tabindex="0" aria-label="查看连衣裙原图与模特效果示例"><span>${photo(examples[0].productImage, '连衣裙商品原图')}<small>商品原图</small></span><span class="pair-arrow">${icon('arrow')}</span><span>${photo(examples[0].image, '连衣裙模特效果示例')}<small>模特效果</small></span></div></section>`;
}
function historyCard(job) {
  const title = typeof workflowJobName === 'function' ? workflowJobName(job) : `${modelName(job.model)}作品`;
  return `<article class="history-card" data-job-card="${job.id}"><div class="history-open" role="button" tabindex="0" data-job="${job.id}" aria-label="查看${title}，${statusLabel(job)}"><span class="history-photo">${photo(job.image || job.original, '商品创作图片', '', true)}${isPending(job) || job.status === 'failed' ? `<span class="status-badge ${job.status}">${isPending(job) ? '<span class="status-dot"></span>' : ''}${statusLabel(job)}</span>` : ''}</span><span class="card-copy"><strong>${escapeHtml(title)}</strong><time>${escapeHtml(job.date)}</time></span></div></article>`;
}
function bindHistory(root = app) {
  root.querySelectorAll('[data-job]').forEach(el => el.onclick = () => { const job = history.find(item => item.id === el.dataset.job); if (job) openJob(job); });
}
function renderMy() {
  app.innerHTML = `<section class="page workspace"><header class="topbar"><a class="brand" href="#home"><span class="brand-symbol">${icon('camera')}</span>衣拍<span class="brand-note">商品的另一面</span></a><div class="header-actions"><a class="tasks-link" href="#workflows" aria-label="工作流中心"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/></svg>工作流</a><a class="tasks-link" href="#tasks" aria-label="任务中心"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>任务</a><button class="profile-edit" id="edit-profile" aria-label="编辑昵称">${icon('user')}<span>${escapeHtml(nickname)}</span></button></div></header><div class="home-intro"><div><span class="eyebrow">你的随身商品摄影棚</span><h1>好商品，<br class="mobile-break">值得一张好照片。</h1><p>上传商品图，让模特替你展示。</p></div><div class="start-card" id="start-card"></div></div>${errorSlot}<div id="active-task"></div><div class="workspace-content"><section class="history-section"><div class="section-heading"><h2>创作历史 <span class="count" id="history-count"></span></h2><div class="heading-actions"><button class="text-button" id="show-example">查看效果示例 ${icon('arrow')}</button><button class="icon-button" id="refresh-history" aria-label="刷新创作历史">${icon('refresh')}</button></div></div><div id="history-content"></div></section><div id="example-content"></div></div></section>`;
  document.querySelector('#edit-profile').onclick = editProfile;
  document.querySelector('#refresh-history').onclick = refreshHome;
  document.querySelector('#show-example').onclick = () => postPage(examples[0]);
  homeSignature = ''; updateHome(); watchImages();
}
function updateHome() {
  if (screen !== 'home') return;
  const signature = JSON.stringify([draft, nickname, history, jobsLoaded, sessionError]);
  if (signature === homeSignature) return;
  homeSignature = signature;
  const start = document.querySelector('#start-card');
  start.innerHTML = `<div class="start-icon">${icon('camera')}</div><div><strong>${draft ? '这件商品，继续开拍' : '从一张商品图开始'}</strong><p>${draft ? '已保留当前商品与模特选择' : '平铺图、挂拍图都可以试试'}</p></div><button class="primary" id="start-create">${draft ? '继续创作' : '上传商品图'} ${icon('plus')}</button>${draft ? '<button class="text-button" id="change-product">换商品</button>' : '<button class="text-button" id="batch-upload">批量上传</button>'}`;
  document.querySelector('#start-create').onclick = () => draft ? prepare() : input.click();
  document.querySelector('#change-product')?.addEventListener('click', () => input.click());
  document.querySelector('#batch-upload')?.addEventListener('click', openBatchUpload);
  const pending = sortedJobs().find(isPending);
  document.querySelector('#active-task').innerHTML = pending ? `<button class="task-banner" data-job="${pending.id}"><span class="spinner small"></span><span><strong>${statusLabel(pending)}</strong><small>你的${modelName(pending.model)}作品正在创作，点此查看</small></span>${icon('arrow')}</button>` : '';
  document.querySelector('#history-count').textContent = jobsLoaded ? history.length : '';
  updateHistoryCards();
  document.querySelector('#show-example').hidden = !history.length;
  document.querySelector('#example-content').innerHTML = history.length ? '' : examplePreview();
  pageError(sessionError, app, refreshHome); bindHistory();
  document.querySelector('#view-example')?.addEventListener('click', () => postPage(examples[0]));
  watchImages();
}
function updateHistoryCards() {
  const container = document.querySelector('#history-content');
  if (!history.length) {
    container.innerHTML = `<div class="empty-history">${jobsLoaded ? '你的第一张模特图，从上方上传开始。' : '正在加载创作历史…'}</div>`;
    return;
  }
  if (!container.querySelector('.history-grid')) container.innerHTML = '<div class="history-grid"></div>';
  const grid = container.querySelector('.history-grid');
  const known = new Map([...grid.children].map(card => [card.dataset.jobCard, card]));
  sortedJobs().forEach((job, index) => {
    const signature = JSON.stringify(job);
    let card = known.get(job.id);
    if (!card || card.dataset.signature !== signature) {
      const template = document.createElement('template'); template.innerHTML = historyCard(job);
      const next = template.content.firstElementChild; next.dataset.signature = signature;
      if (card) card.replaceWith(next); card = next;
    }
    if (grid.children[index] !== card) grid.insertBefore(card, grid.children[index] || null);
    known.delete(job.id);
  });
  known.forEach(card => card.remove());
}
async function refreshHome() {
  try { await syncJobs(); sessionError = ''; updateHome(); if (busy) schedulePoll(); }
  catch (error) { sessionError = error.message; if (screen === 'home') pageError(error.message, app, refreshHome); }
}
function editProfile() {
  const layer = openOverlay(`<section class="sheet" role="dialog" aria-modal="true" aria-labelledby="nickname-title"><div class="sheet-heading"><h2 id="nickname-title">编辑昵称</h2><button class="icon-button" data-close aria-label="关闭">${icon('close')}</button></div><form id="nickname-form"><label class="field-label" for="nickname-input">昵称</label><input id="nickname-input" class="field-input" maxlength="20" required value="${escapeHtml(nickname)}">${errorSlot}<div class="sheet-actions"><button class="secondary" type="button" data-close>取消</button><button class="primary" type="submit">保存</button></div></form></section>`);
  layer.querySelector('#nickname-form').onsubmit = event => {
    event.preventDefault(); const value = layer.querySelector('#nickname-input').value.trim();
    if (!value) return pageError('请输入昵称', layer);
    nickname = value; try { localStorage.setItem('yipai-nickname', nickname); } catch {}
    closeOverlay(); renderMy(); document.querySelector('#edit-profile').focus();
  };
  layer.querySelector('#nickname-input').focus();
}
function selectModel(value) {
  model = value; try { localStorage.setItem('yipai-model', model); } catch {}
  document.querySelectorAll('[data-model]').forEach(button => {
    const selected = button.dataset.model === model;
    button.classList.toggle('selected', selected); button.setAttribute('aria-pressed', String(selected));
    button.querySelector('.model-check').innerHTML = selected ? icon('check') : '';
  });
}
function modelCards() {
  if (!selectedModelId || !allModels.length) {
    return ['female', 'male'].map(value => `<div class="model-chip ${model === value ? 'selected' : ''}" role="button" tabindex="0" data-model="${value}" aria-pressed="${model === value}">${photo(`assets/${value}-model.png`, `${modelName(value)}形象`)}<span class="model-label">${modelName(value)}<span class="model-check">${model === value ? icon('check') : ''}</span></span></div>`).join('');
  }
  const selected = allModels.find(m => m.id === selectedModelId) || allModels[0];
  return `<div class="model-chip selected" role="button" tabindex="0" data-open-picker aria-pressed="true">${photo(selected.image, selected.name)}<span class="model-label">${escapeHtml(selected.name)}<span class="model-check">${icon('check')}</span></span></div><button class="text-button" data-change-model>更换模特</button>`;
}
function renderPrepare() {
  setScreen('prepare');
  app.innerHTML = `<section class="page detail-page">${subTop('准备开拍')}<div class="prepare-layout"><section class="product-panel"><div class="section-heading"><h2>商品原图</h2><button class="text-button" id="replace">换一张 ${icon('refresh')}</button></div>${photo(draft, '上传的商品图片', 'product-preview')}<p class="muted image-note">商品完整、细节清楚，展示效果更好。</p></section><section class="configuration-panel"><span class="eyebrow">下一步，让商品上身</span><h2>选择出镜模特</h2><p class="muted">选好模特，就可以开始创作。</p><div class="compact-models">${modelCards()}</div>${errorSlot}<div class="bottom-action"><button id="generate" class="primary">生成图片 ${icon('arrow')}</button><p class="helper">一次生成一张，完成后可对照原图查看</p></div></section></div></section>`;
  bindHeader(); document.querySelector('#replace').onclick = () => input.click();
  document.querySelector('#generate').onclick = () => {
    const modelToUse = selectedModelId || model;
    void generate(draft, modelToUse);
  };
  document.querySelectorAll('[data-model]').forEach(button => button.onclick = () => selectModel(button.dataset.model));
  document.querySelector('[data-open-picker]')?.addEventListener('click', openModelPicker);
  document.querySelector('[data-change-model]')?.addEventListener('click', openModelPicker);
  watchImages();
}
function openModelPicker() {
  const picker = renderModelPicker();
  document.body.appendChild(picker);
}
function poseProgress(job) {
  if (job?.workflowType !== 'pose_variation') return '';
  const total = job.workflowConfig?.pose_count || 4;
  return `已生成 ${Math.min(job.images?.length || 0, total)} / ${total} 张`;
}
function waiting() {
  setScreen('generating');
  const job = active;
  app.innerHTML = `<section class="page detail-page">${subTop('正在创作')}<div class="state-panel generation-panel">${job?.original || draft ? photo(job?.original || draft, '正在创作的商品', 'task-product') : ''}<div class="status-line"><span class="spinner small"></span><span class="eyebrow">${job && typeof workflowJobName === 'function' ? escapeHtml(workflowJobName(job)) : modelName(job?.model || model)}</span></div><h1 id="task-status">${job ? statusLabel(job) : '正在提交'}</h1><p id="task-progress" ${poseProgress(job) ? '' : 'hidden'}>${poseProgress(job)}</p><p>可以离开，完成后在创作历史查看。</p>${errorSlot}<button class="primary" id="leave">返回工作台 ${icon('arrow')}</button></div></section>`;
  bindHeader(); document.querySelector('#leave').onclick = home; watchImages();
  if (pollError) pageError(pollError, app, () => void pollJobs());
}
function renderJob(job) {
  if (job.status === 'succeeded') renderResult(job);
  else if (job.status === 'failed') failedPage(job);
  else waiting();
}
function schedulePoll() { clearTimeout(pollTimer); pollTimer = setTimeout(pollJobs, 4000); }
async function pollJobs() {
  clearTimeout(pollTimer);
  const previous = new Map(history.map(job => [job.id, job.status]));
  try {
    await syncJobs(); pollError = '';
    if (screen === 'home' && !sessionError) pageError('');
    // A routed task can be older than the latest 100 jobs returned by the list endpoint.
    if (active && !history.some(job => job.id === active.id) && screen === 'generating') active = mergeJob((await api(`/api/jobs/${active.id}`)).job);
    else if (active) active = history.find(job => job.id === active.id) || active;
    if (screen === 'generating' && active) {
      if (!isPending(active)) renderJob(active);
      else {
        const title = document.querySelector('#task-status'); if (title) title.textContent = statusLabel(active);
        const progress = document.querySelector('#task-progress');
        if (progress) { progress.textContent = poseProgress(active); progress.hidden = !progress.textContent; }
        pageError('');
      }
    }
    updateHome();
    if ((screen === 'workflows' || screen === 'workflow-detail') && typeof refreshWorkflowRecent === 'function') refreshWorkflowRecent();
    if (screen !== 'result' && history.some(job => job.status === 'succeeded' && ['running','queued'].includes(previous.get(job.id)))) toast('图片已生成，可在创作历史查看');
  } catch (error) {
    pollError = '暂时连不上，任务可能仍在进行。';
    if (screen === 'generating') pageError(pollError, app, () => void pollJobs());
    else if (screen === 'home') pageError(pollError, app, refreshHome);
  }
  if (busy) schedulePoll();
}
function loadImage(src) {
  return new Promise((resolve, reject) => { const img = new Image(); img.onload = () => resolve(img); img.onerror = reject; img.src = src; });
}
async function sourceData(source) {
  if (source.startsWith('data:')) return source;
  const response = await fetch(source); if (!response.ok) throw new Error('原图已无法读取，请换一张');
  const blob = await response.blob();
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(blob); });
}
async function generate(source = draft, choice = model, workflow = {}) {
  if (busy || submitting) {
    pageError('已有图片正在生成，请完成后再提交。'); return;
  }
  if (!source) return;
  const submissionRoute = currentRoute;
  submitting = true; busy = true;
  const button = document.querySelector('#generate') || document.querySelector('#regenerate') || document.querySelector('#retry');
  if (button) { button.disabled = true; button.textContent = '正在提交…'; }
  pageError('');
  try {
    await sessionReady;
    const workflowType = workflow.workflowType || 'tryon';
    const workflowConfig = workflow.workflowConfig || null;
    const submissionKey = JSON.stringify([source, choice, workflowType, workflowConfig]);
    if (!pendingSubmission || pendingSubmission.key !== submissionKey) pendingSubmission = {source, model:choice, key:submissionKey, idempotencyKey:crypto.randomUUID()};
    const image = await sourceData(source);
    const payload = {image, model:choice, idempotencyKey:pendingSubmission.idempotencyKey};
    if (workflowType !== 'tryon') Object.assign(payload, {workflowType, workflowConfig});
    const data = await api('/api/jobs', {method:'POST', body:JSON.stringify(payload)});
    const submittedJob = mergeJob(data.job);
    pendingSubmission = null;
    if (draft === source) draft = null;
    submitting = false; busy = history.some(isPending);
    if (currentRoute === submissionRoute) { active = submittedJob; navigate(`#job/${submittedJob.id}`); }
    else { updateHome(); toast('任务已提交，可在创作历史查看'); }
    schedulePoll();
  } catch (error) {
    submitting = false; busy = history.some(isPending);
    // Preserve a newer draft chosen while a previous submission was in flight.
    if (!draft || draft === source) { draft = source; model = choice; }
    if (screen === 'prepare') renderPrepare();
    else if (screen === 'result' && active) renderResult(active);
    else if (screen === 'failed' && active) failedPage(active);
    else { updateHome(); }
    pageError(error.message || '生成失败，请重试');
  }
}
function failedPage(job) {
  active = job; setScreen('failed');
  app.innerHTML = `<section class="page detail-page">${subTop('未生成成功')}<div class="state-panel">${photo(job.original, '生成失败的商品', 'task-product')}<span class="failure-icon">${icon('warning')}</span><h1>这次没生成成功</h1><p>${escapeHtml(job.error || '请稍后重试，商品原图已保留。')}</p>${errorSlot}<button class="primary" id="retry">重新生成 ${icon('refresh')}</button><button class="text-button" id="return-home">返回工作台</button></div></section>`;
  bindHeader(); document.querySelector('#return-home').onclick = home;
  document.querySelector('#retry').onclick = () => { void generate(job.original, job.model, {workflowType:job.workflowType, workflowConfig:job.workflowConfig}); }; watchImages();
}
function renderResult(job) {
  setScreen('result');
  const outputTitle = typeof workflowJobName === 'function' ? workflowJobName(job) : '模特效果';
  const outputMeta = typeof workflowNames === 'undefined' ? modelName(job.model) : (job.workflowType && job.workflowType !== 'tryon' ? workflowJobName(job) : modelName(job.model));
  const poseImages = job.workflowType === 'pose_variation' && Array.isArray(job.images) && job.images.length
    ? job.images.map(image => typeof image === 'string' ? image : image?.url).filter(Boolean)
    : [job.image].filter(Boolean);
  let selectedPoseIndex = 0;
  const inputLabel = job.workflowType && job.workflowType !== 'tryon' ? '输入图片' : '商品原图';
  const previewNotice = job.previewOnly && job.workflowType === 'background_change'
    ? '<p class="preview-output-notice" role="status">这是一条旧的演示样例记录，未处理输入图片。点击重新生成可重新提交原图。</p>'
    : '';
  const hasPoseGallery = job.workflowType === 'pose_variation' && poseImages.length > 1;
  const poseGallery = hasPoseGallery ? `<div class="pose-gallery" aria-label="姿势裂变图片">
    <p class="pose-gallery-count" aria-live="polite">第 <span id="pose-result-index">1</span> 张 / 共 ${poseImages.length} 张独立图片</p>
    <div class="pose-gallery-thumbnails" role="group" aria-label="选择姿势图片">
      ${poseImages.map((image, index) => `<button class="pose-gallery-thumb ${index === 0 ? 'selected' : ''}" type="button" data-pose-image="${index}" aria-label="查看第 ${index + 1} 张图片" aria-pressed="${index === 0}"><img src="${escapeHtml(image)}" alt="姿势裂变第 ${index + 1} 张" decoding="async"><span>${index + 1}</span></button>`).join('')}
    </div>
  </div>` : '';
  const poseActions = hasPoseGallery ? `<button class="action-button" id="save-all">${icon('save')}<span>下载全部 ${poseImages.length} 张</span></button>` : '';
  app.innerHTML = `<section class="page detail-page result-page">${subTop('你的新作品', home, true)}<div class="result-layout"><div class="result-main"><div class="result-toolbar"><div class="segmented" aria-label="图片对照"><button class="selected" id="effect-tab" aria-pressed="true">效果图</button><button id="original-tab" aria-pressed="false">${inputLabel}</button></div><button class="icon-button" id="zoom-result" aria-label="放大查看图片">${icon('zoom')}</button></div><div class="comparison-grid"><div class="result-image-column"><span class="desktop-image-label">${escapeHtml(outputTitle)}${hasPoseGallery ? ' · <span id="pose-result-label">1</span> / ' + poseImages.length : ''}</span>${poseGallery}<div id="result-primary" role="button" tabindex="0" aria-label="全屏查看效果图">${photo(poseImages[0], hasPoseGallery ? '姿势裂变第 1 张' : '带衣拍水印的模特展示图', 'result-art')}</div></div><div class="desktop-original"><span class="desktop-image-label">${inputLabel}</span><div role="button" tabindex="0" id="result-original" aria-label="全屏查看${inputLabel}">${photo(job.original, inputLabel, 'result-art')}</div></div></div></div><aside class="result-side"><div class="result-summary"><span class="eyebrow">完成这一次创作</span><h2>让细节，也经得起看。</h2><p>发布前，对照原图检查颜色、图案和商品结构。</p>${previewNotice}<span class="result-meta">${escapeHtml(outputMeta)} · ${escapeHtml(job.date)}</span></div>${errorSlot}<div class="result-actions ${hasPoseGallery ? 'pose-result-actions' : ''}"><button class="action-button" id="regenerate">${icon('refresh')}<span>重新生成</span></button><button class="action-button primary-action" id="save">${icon('save')}<span>保存当前图片</span></button><button class="action-button" id="share">${icon('share')}<span>分享转发</span></button>${poseActions}</div></aside></div></section>`;
  bindHeader(); let showingOriginal = false;
  const selectedResult = () => hasPoseGallery ? {...job, image: poseImages[selectedPoseIndex], imageIndex: selectedPoseIndex + 1} : job;
  const choose = original => {
    showingOriginal = original;
    document.querySelector('#effect-tab').classList.toggle('selected', !original);
    document.querySelector('#original-tab').classList.toggle('selected', original);
    document.querySelector('#effect-tab').setAttribute('aria-pressed', String(!original));
    document.querySelector('#original-tab').setAttribute('aria-pressed', String(original));
    const primary = document.querySelector('#result-primary');
    primary.setAttribute('aria-label', `全屏查看${original ? inputLabel : '效果图'}`);
    primary.innerHTML = photo(original ? job.original : poseImages[selectedPoseIndex], original ? inputLabel : hasPoseGallery ? `姿势裂变第 ${selectedPoseIndex + 1} 张` : '带衣拍水印的模特展示图', 'result-art'); watchImages(primary);
  };
  document.querySelector('#effect-tab').onclick = () => choose(false);
  document.querySelector('#original-tab').onclick = () => choose(true);
  const view = () => openViewer(showingOriginal ? job : selectedResult(), showingOriginal);
  document.querySelector('#zoom-result').onclick = view;
  document.querySelector('#result-primary').onclick = view;
  document.querySelector('#result-primary').onkeydown = event => { if (['Enter',' '].includes(event.key)) { event.preventDefault(); view(); } };
  document.querySelector('#result-original').onclick = () => openViewer(job, true);
  document.querySelector('#result-original').onkeydown = event => { if (['Enter',' '].includes(event.key)) { event.preventDefault(); openViewer(job, true); } };
  document.querySelector('#regenerate').onclick = () => void generate(job.original, job.model, {workflowType:job.workflowType, workflowConfig:job.workflowConfig});
  document.querySelector('#save').onclick = () => save(selectedResult());
  if (hasPoseGallery) {
    document.querySelectorAll('[data-pose-image]').forEach(button => button.onclick = () => {
      selectedPoseIndex = Number(button.dataset.poseImage);
      document.querySelectorAll('[data-pose-image]').forEach(item => {
        const selected = Number(item.dataset.poseImage) === selectedPoseIndex;
        item.classList.toggle('selected', selected);
        item.setAttribute('aria-pressed', String(selected));
      });
      document.querySelector('#pose-result-index').textContent = String(selectedPoseIndex + 1);
      document.querySelector('#pose-result-label').textContent = String(selectedPoseIndex + 1);
      if (!showingOriginal) choose(false);
    });
    document.querySelector('#save-all').onclick = () => {
      const link = document.createElement('a');
      link.href = job.downloadAll || `/api/jobs/${job.id}/download.zip`;
      link.download = `衣拍-${job.id}-全部姿势.zip`;
      document.body.appendChild(link); link.click(); link.remove();
      toast('已发起全部图片下载');
    };
  }
  document.querySelector('#share').onclick = () => shareOptions(selectedResult());
  document.querySelector('#more').onclick = () => sheet('作品操作', '', [{label:'发布到社区', action:() => publishPage(job)}, {label:'删除这张作品', danger:true, action:() => confirmDelete(job)}, {label:'取消'}]);
  watchImages();
}
function save(result) {
  const link = document.createElement('a'); link.href = result.image; link.download = `衣拍-${result.id}${result.imageIndex ? `-${result.imageIndex}` : ''}.jpg`;
  document.body.appendChild(link); link.click(); link.remove(); toast('已发起下载，可在下载记录中查看');
}
function shareOptions(job) {
  sheet('分享作品', '', [{label:'分享图片', filled:true, action:() => void share(job)}, {label:'发布到社区', action:() => publishPage(job)}, {label:'取消'}]);
}
async function share(result) {
  try {
    const response = await fetch(result.image); if (!response.ok) throw new Error('图片无法读取');
    const blob = await response.blob(); const file = new File([blob], `衣拍-${result.id}.jpg`, {type:'image/jpeg'});
    if (navigator.canShare?.({files:[file]})) {
      try { await navigator.share({files:[file], title:'我的衣拍创作'}); }
      catch (error) { if (error.name !== 'AbortError') shareFallback(result); }
    } else shareFallback(result);
  } catch { shareFallback(result); }
}
function shareFallback(result) { sheet('分享图片', '请保存后转发', [{label:'稍后再说'}, {label:'保存图片', filled:true, action:() => save(result)}]); }

// One overlay at a time, with focus trapping, Escape, and focus restoration.
let overlayTrigger = null;
function openOverlay(html, className = '') {
  closeOverlay(false); overlayTrigger = document.activeElement;
  const layer = document.createElement('div'); layer.className = `modal-backdrop ${className}`; layer.innerHTML = html;
  document.body.appendChild(layer); document.body.classList.add('overlay-open'); app.inert = true; dock.inert = true;
  layer.onclick = event => { if (event.target === layer || event.target.closest('[data-close]')) closeOverlay(); };
  layer.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeOverlay(); return; }
    if (event.key !== 'Tab') return;
    const focusables = [...layer.querySelectorAll('button:not(:disabled), input, textarea, [tabindex="0"]')].filter(el => !el.hidden);
    const first = focusables[0], last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  });
  layer.querySelector('button, input, [tabindex="0"]')?.focus(); return layer;
}
function closeOverlay(restoreFocus = true) {
  document.querySelector('.modal-backdrop')?.remove(); document.body.classList.remove('overlay-open'); app.inert = false; dock.inert = false;
  if (restoreFocus && overlayTrigger?.isConnected) overlayTrigger.focus(); overlayTrigger = null;
}
function sheet(title, body, buttons) {
  const layer = openOverlay(`<section class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title"><div class="sheet-heading"><h2 id="sheet-title">${escapeHtml(title)}</h2><button class="icon-button" data-close aria-label="关闭">${icon('close')}</button></div>${body ? `<p>${escapeHtml(body)}</p>` : ''}<div class="sheet-actions stacked">${buttons.map((button, index) => `<button class="${button.filled ? 'primary' : 'secondary'} ${button.danger ? 'danger' : ''}" data-index="${index}">${escapeHtml(button.label)}</button>`).join('')}</div>${errorSlot}</section>`);
  layer.querySelectorAll('[data-index]').forEach(el => el.onclick = async () => {
    const action = buttons[Number(el.dataset.index)].action; closeOverlay();
    if (action) { try { await action(); } catch (error) { pageError(error.message); } }
  });
}
function openViewer(item, original = false) {
  let showingOriginal = original, zoom = 1;
  const inputLabel = item.workflowType && item.workflowType !== 'tryon' ? '输入图片' : '商品原图';
  const layer = openOverlay(`<section class="viewer" role="dialog" aria-modal="true" aria-label="图片查看器"><header class="viewer-header"><div class="segmented"><button id="viewer-effect" aria-pressed="${!original}">效果图</button><button id="viewer-original" aria-pressed="${original}">${inputLabel}</button></div><button class="icon-button" data-close aria-label="关闭图片查看器">${icon('close')}</button></header><div class="viewer-stage" tabindex="0" aria-label="图片查看区域，可滚动查看放大细节"><div class="viewer-canvas"></div></div><footer class="viewer-controls"><button class="secondary" id="zoom-out" aria-label="缩小图片">−</button><output id="zoom-level" aria-live="polite">100%</output><button class="secondary" id="zoom-in" aria-label="放大图片">＋</button><button class="secondary" id="zoom-reset">还原</button></footer></section>`, 'viewer-backdrop');
  const update = () => {
    layer.querySelector('#viewer-effect').classList.toggle('selected', !showingOriginal); layer.querySelector('#viewer-original').classList.toggle('selected', showingOriginal);
    layer.querySelector('#viewer-effect').setAttribute('aria-pressed', String(!showingOriginal)); layer.querySelector('#viewer-original').setAttribute('aria-pressed', String(showingOriginal));
    layer.querySelector('.viewer-canvas').innerHTML = photo(showingOriginal ? (item.original || item.productImage) : item.image, showingOriginal ? inputLabel : '带水印的效果图');
    layer.querySelector('.viewer-canvas').style.setProperty('--zoom', zoom);
    layer.querySelector('#zoom-level').textContent = `${Math.round(zoom * 100)}%`;
    layer.querySelector('#zoom-out').disabled = zoom <= 1; layer.querySelector('#zoom-in').disabled = zoom >= 3;
    watchImages(layer);
  };
  const adjust = step => { zoom = Math.min(3, Math.max(1, zoom + step)); update(); };
  layer.querySelector('#zoom-in').onclick = () => adjust(.5); layer.querySelector('#zoom-out').onclick = () => adjust(-.5);
  layer.querySelector('#zoom-reset').onclick = () => { zoom = 1; update(); };
  layer.querySelector('#viewer-effect').onclick = () => { showingOriginal = false; zoom = 1; update(); };
  layer.querySelector('#viewer-original').onclick = () => { showingOriginal = true; zoom = 1; update(); };
  layer.addEventListener('keydown', event => {
    if (['+','=','-','0','ArrowLeft','ArrowRight'].includes(event.key)) event.preventDefault();
    if (['+','='].includes(event.key)) adjust(.5); else if (event.key === '-') adjust(-.5);
    else if (event.key === '0') { zoom = 1; update(); }
    else if (['ArrowLeft','ArrowRight'].includes(event.key)) { showingOriginal = !showingOriginal; zoom = 1; update(); }
  }); update();
}
function confirmDelete(job) {
  sheet('删除这张作品？', '删除后无法在创作历史找回。已发布内容需在社区单独撤回。', [{label:'保留'}, {label:'确认删除', danger:true, action:async () => {
    await api(`/api/jobs/${job.id}`, {method:'DELETE'}); history = history.filter(item => item.id !== job.id); active = null; home(); toast('作品已删除');
  }}]);
}

let uploadVersion = 0;
input.onchange = async () => {
  const file = input.files[0]; input.value = ''; if (!file) return;
  const version = ++uploadVersion;
  if (file.size > 20 * 1024 * 1024) { pageError('图片不能超过 20 MB，请换一张'); return; }
  try {
    const url = URL.createObjectURL(file); let img;
    try { img = await loadImage(url); } finally { URL.revokeObjectURL(url); }
    if (version !== uploadVersion) return;
    const canvas = document.createElement('canvas'); const scale = Math.min(1, 1200 / Math.max(img.width, img.height));
    canvas.width = Math.round(img.width * scale); canvas.height = Math.round(img.height * scale);
    if (Math.min(canvas.width, canvas.height) < 512) throw new Error('图片尺寸过小，请换一张清楚的图片');
    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
    draft = canvas.toDataURL('image/jpeg', .85); pendingSubmission = null; prepare();
  } catch { if (version === uploadVersion) pageError('无法读取图片或尺寸不足，请换一张清楚的 JPG、PNG 或 WebP 图片'); }
};
document.querySelector('#camera-tab').onclick = () => input.click();
document.querySelector('#my-tab').onclick = historyPage;
document.querySelector('#community-tab').onclick = communityPage;
document.addEventListener('keydown', event => {
  if (['Enter', ' '].includes(event.key) && event.target.matches('[role="button"]') && !event.target.onkeydown) { event.preventDefault(); event.target.click(); }
});
window.addEventListener('popstate', () => void renderRoute());
window.addEventListener('hashchange', () => { if (location.hash !== currentRoute) void renderRoute(); });
window.addEventListener('online', () => { if (busy) void pollJobs(); else if (screen === 'home') void refreshHome(); });
window.addEventListener('resize', () => {
  if (window.innerWidth >= 768 && screen === 'result' && document.querySelector('#original-tab')?.getAttribute('aria-pressed') === 'true') document.querySelector('#effect-tab').click();
});
sessionReady = (async () => {
  try {
    const session = await api('/api/session');
    const notice = document.querySelector('#service-mode-notice');
    if (notice) notice.hidden = session.generationMode !== 'demo';
    await syncJobs(); sessionError = '';
  }
  catch (error) { sessionError = error.message; }
})();
void renderRoute();
void sessionReady.then(() => {
  updateHome();
  if ((screen === 'workflows' || screen === 'workflow-detail') && typeof refreshWorkflowRecent === 'function') refreshWorkflowRecent();
  if (busy) schedulePoll();
});
