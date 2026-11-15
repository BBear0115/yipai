const examples = [
  {id:'example-dress', nickname:'衣拍官方', productName:'碎花泡泡袖连衣裙', note:'方领和泡泡袖都保留下来了。上传时让裙摆完整入镜，生成后记得对照原图检查花色。', image:'assets/community/floral-dress-result.jpg', productImage:'assets/community/floral-dress-product.jpg', example:true},
  {id:'example-shirt', nickname:'衣拍官方', productName:'蓝白条纹长袖上衣', note:'让头发放到肩后、双手自然下垂，条纹和下摆会看得更清楚。拍商品原图时，尽量避免衣服折叠。', image:'assets/community/striped-shirt-result.jpg', productImage:'assets/community/striped-shirt-product.jpg', example:true}
];
async function loadPosts() {
  const data = await api('/api/posts'); posts = data.posts; return posts;
}
function refreshCommunity() {
  if (screen !== 'community') return;
  const feed = document.querySelector('.feed');
  const signature = JSON.stringify(posts.map(post => post.id));
  if (feed?.dataset.signature === signature) return;
  renderCommunity();
}
function timeAgo(created) {
  const time = new Date(created).getTime();
  if (!time) return '';
  const minutes = Math.max(0, Math.floor((Date.now() - time) / 60000));
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes}分钟前`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}小时前`;
  if (minutes < 43200) return `${Math.floor(minutes / 1440)}天前`;
  return new Date(time).toLocaleDateString('zh-CN', {month:'long', day:'numeric'});
}
// Member posts keep likes, saves and remakes on the server so their author can see the numbers.
// Official examples have no server row, so their reactions stay in this browser.
const exampleReactions = {like:new Set(), save:new Set()};
try { for (const key of ['like', 'save']) exampleReactions[key] = new Set(JSON.parse(localStorage.getItem(`yipai-example-${key}`) || '[]')); } catch {}
const isLiked = post => post.example ? exampleReactions.like.has(post.id) : Boolean(post.liked);
const isSaved = post => post.example ? exampleReactions.save.has(post.id) : Boolean(post.saved);
const likeCount = post => post.example ? Number(isLiked(post)) : post.likes || 0;
const likeLabel = post => likeCount(post) ? String(likeCount(post)) : '好看';
async function react(post, kind, active) {
  if (post.example) {
    const set = exampleReactions[kind];
    if (active) set.add(post.id); else set.delete(post.id);
    try { localStorage.setItem(`yipai-example-${kind}`, JSON.stringify([...set])); } catch {}
    return;
  }
  const {stats} = await api(`/api/posts/${post.id}/reactions`, {method:'POST', body:JSON.stringify({kind, active})});
  Object.assign(post, stats);
}
// One post reads like a social feed entry: author row, the effect photo with the product inset, actions, then caption.
function feedPost(post) {
  const id = escapeHtml(post.id), name = escapeHtml(post.productName);
  const liked = isLiked(post), saved = isSaved(post);
  return `<article class="feed-post"><header class="feed-post-head"><span class="small-avatar">${escapeHtml(post.nickname.slice(0,1))}</span><strong>${escapeHtml(post.nickname)}</strong>${post.example?'<span class="example-tag">官方示例</span>':''}<button class="icon-button feed-post-more" data-more="${id}" aria-label="${name}的更多操作">${icon('more')}</button></header><div class="feed-media"><div class="feed-photo" role="button" tabindex="0" data-view="${id}" aria-label="放大查看${name}效果图">${photo(post.image, `${post.productName}模特效果图`, 'feed-result', true)}</div><div class="feed-product"><div class="feed-product-thumb" role="button" tabindex="0" data-original="${id}" aria-label="查看${name}商品原图">${photo(post.productImage, `${post.productName}商品原图`, '', true)}</div><button class="feed-remake" data-reference="${id}">${icon('feature-remake')}做参考</button></div></div><div class="feed-actions"><button class="feed-action" data-like="${id}" aria-pressed="${liked}" aria-label="觉得${name}好看">${icon('community-like')}<span>${likeLabel(post)}</span></button><button class="feed-action" data-bookmark="${id}" aria-pressed="${saved}" aria-label="收藏${name}">${icon('community-bookmark')}<span>收藏</span></button><button class="feed-action" data-share="${id}" aria-label="分享${name}">${icon('community-share')}<span>分享</span></button><button class="icon-button feed-save" data-save="${id}" aria-label="保存${name}效果图">${icon('community-save')}</button></div><p class="feed-caption"><strong>${escapeHtml(post.nickname)}</strong> <span>${name}</span> ${escapeHtml(post.note)}</p><div class="feed-meta">${post.example ? '官方示例' : escapeHtml(timeAgo(post.created))}</div></article>`;
}
function renderCommunity() {
  const all = [...posts, ...examples];
  app.innerHTML = `<section class="page community-page"><header class="topbar"><h1 class="page-title">社区</h1>${renderCreditsDisplay()}</header>${errorSlot}<div class="feed" data-signature="${escapeHtml(JSON.stringify(posts.map(post => post.id)))}">${all.map(feedPost).join('')}</div>${all.length ? '' : '<div class="empty-history">社区还没有作品，完成创作后可以分享你的效果。</div>'}</section>`;
  const bind = (attribute, action) => document.querySelectorAll(`[data-${attribute}]`).forEach(el => {
    el.onclick = () => { const post = findPost(el.dataset[attribute]); if (post) action(post, el); };
    if (el.getAttribute('role') === 'button') el.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); el.onclick(); } };
  });
  bind('view', post => openViewer(post));
  bind('original', post => openViewer(post, true));
  bind('reference', useAsReference);
  // Flip the button at once; roll back if the server refuses.
  const toggle = async (post, el, kind, done) => {
    const next = !(kind === 'like' ? isLiked(post) : isSaved(post)), before = {...post};
    if (!post.example) Object.assign(post, kind === 'like' ? {liked:next, likes:(post.likes || 0) + (next ? 1 : -1)} : {saved:next, saves:(post.saves || 0) + (next ? 1 : -1)});
    const paint = () => { el.setAttribute('aria-pressed', String(kind === 'like' ? isLiked(post) : isSaved(post))); if (kind === 'like') el.querySelector('span').textContent = likeLabel(post); };
    paint();
    try { await react(post, kind, next); paint(); done?.(next); }
    catch { Object.assign(post, before); paint(); toast('操作失败，请重试'); }
  };
  bind('like', (post, el) => toggle(post, el, 'like'));
  bind('bookmark', (post, el) => toggle(post, el, 'save', saved => toast(saved ? '已收藏' : '已取消收藏')));
  bind('share', share);
  bind('save', save);
  bind('more', postActions);
  watchImages();
}
function postActions(post) {
  sheet(post.productName, '', [{label:'分享图片', action:() => share(post)}, {label:'保存效果图', action:() => save(post)}, ...(post.mine ? [{label:'撤回发布', danger:true, action:() => withdrawPost(post)}] : []), {label:'取消'}]);
}
function withdrawPost(post) {
  sheet('撤回这条发布？', '个人创作历史会保留。', [{label:'保留'}, {label:'撤回', danger:true, action:async () => {
    await api(`/api/posts/${post.id}`, {method:'DELETE'}); posts = posts.filter(item => item.id !== post.id);
    const job = history.find(item => item.id === post.id); if (job) job.post = null;
    communityPage(); toast('已撤回');
  }}]);
}
function findPost(id) { return [...posts, ...examples].find(post => post.id === id); }
function renderPublish(job) {
  setScreen('publish');
  const saved = publishDrafts.get(job.id) || {};
  app.innerHTML = `<section class="page sub-page publish-page">${subTop('发布到社区', () => resultPage(job))}<div class="publish-layout"><div class="publish-preview"><div>${photo(job.image, '即将发布的模特效果图')}</div><div>${photo(job.original, '本次使用的商品原图')}<small>商品原图</small></div></div><form id="publish-form"><label class="field-label" for="product-name">商品名称</label><input class="field-input" id="product-name" maxlength="30" placeholder="这次拍的是哪件商品？" required value="${escapeHtml(saved.productName || '')}"><label class="field-label" for="post-note">使用心得</label><textarea class="field-input" id="post-note" maxlength="300" rows="4" placeholder="分享你的出图效果和使用小技巧" required>${escapeHtml(saved.note || '')}</textarea><p class="publish-visibility">发布后，其他访客可看到效果图、商品原图和心得。</p>${errorSlot}<button class="primary" type="submit" id="publish-submit">发布到社区 ${icon('arrow')}</button></form></div></section>`;
  bindHeader(() => resultPage(job));
  const form = document.querySelector('#publish-form');
  const saveDraft = () => publishDrafts.set(job.id, {productName:form.querySelector('#product-name').value, note:form.querySelector('#post-note').value});
  form.addEventListener('input', saveDraft);
  form.onsubmit = async event => {
    event.preventDefault(); const button = document.querySelector('#publish-submit'); if (button.disabled) return;
    const productName = form.querySelector('#product-name').value.trim(), note = form.querySelector('#post-note').value.trim();
    if (!productName || !note) { pageError('请填写商品名称和使用心得'); return; }
    button.disabled = true; button.textContent = '正在发布…'; pageError('');
    try {
      const data = await api('/api/posts', {method:'POST', body:JSON.stringify({jobId:job.id, nickname, productName, note})});
      posts = [data.post, ...posts.filter(post => post.id !== data.post.id)]; publishDrafts.delete(job.id);
      const {productName:name, note:text, created, likes, saves, remakes} = data.post;
      job.post = {productName:name, note:text, created, likes, saves, remakes};
      communityPage(); toast('已发布到社区');
    } catch (error) { pageError(error.message); button.disabled = false; button.innerHTML = `发布到社区 ${icon('arrow')}`; }
  };
  watchImages();
}
