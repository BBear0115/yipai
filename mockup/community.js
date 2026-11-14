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
// One post reads like a social feed entry: author row, swipeable effect/original photos, actions, then caption.
function feedPost(post) {
  const id = escapeHtml(post.id), name = escapeHtml(post.productName);
  return `<article class="feed-post"><header class="feed-post-head"><span class="small-avatar">${escapeHtml(post.nickname.slice(0,1))}</span><strong>${escapeHtml(post.nickname)}</strong>${post.example?'<span class="example-tag">官方示例</span>':''}<button class="icon-button feed-post-more" data-more="${id}" aria-label="${name}的更多操作">${icon('more')}</button></header><div class="feed-slides" data-slides aria-label="${name}作品图片，左右滑动对照效果图与商品原图"><div class="feed-slide" role="button" tabindex="0" data-post="${id}" aria-label="查看${name}效果图">${photo(post.image, `${post.productName}模特效果图`, 'feed-result', true)}<span class="feed-slide-label">效果图</span></div><div class="feed-slide" role="button" tabindex="0" data-post="${id}" aria-label="查看${name}商品原图">${photo(post.productImage, `${post.productName}商品原图`, 'feed-original', true)}<span class="feed-slide-label">商品原图</span></div></div><div class="feed-dots" aria-hidden="true"><span class="current"></span><span></span></div><div class="feed-actions">${post.example?`<button class="feed-action" data-recreate="${id}">${icon('camera')}拍同款</button>`:''}<button class="feed-action" data-share="${id}" aria-label="分享${name}">${icon('send')}分享</button><button class="icon-button feed-save" data-save="${id}" aria-label="保存${name}效果图">${icon('save')}</button></div><p class="feed-caption"><strong>${escapeHtml(post.nickname)}</strong> <span>${name}</span> ${escapeHtml(post.note)}</p><div class="feed-meta">${post.example ? '官方示例' : escapeHtml(timeAgo(post.created))}<span aria-hidden="true">·</span><button data-post="${id}">查看详情</button></div></article>`;
}
function renderCommunity() {
  const all = [...posts, ...examples];
  app.innerHTML = `<section class="page community-page"><header class="topbar"><h1 class="page-title">社区</h1></header>${errorSlot}<div class="feed" data-signature="${escapeHtml(JSON.stringify(posts.map(post => post.id)))}">${all.map(feedPost).join('')}</div>${all.length ? '' : '<div class="empty-history">社区还没有作品，完成创作后可以分享你的效果。</div>'}</section>`;
  document.querySelectorAll('[data-post]').forEach(button => {
    button.onclick = () => postPage(findPost(button.dataset.post));
    button.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); button.onclick(); } };
  });
  document.querySelectorAll('[data-share]').forEach(button => button.onclick = () => share(findPost(button.dataset.share)));
  document.querySelectorAll('[data-save]').forEach(button => button.onclick = () => save(findPost(button.dataset.save)));
  document.querySelectorAll('[data-recreate]').forEach(button => button.onclick = () => recreatePost(findPost(button.dataset.recreate)));
  document.querySelectorAll('[data-more]').forEach(button => button.onclick = () => postActions(findPost(button.dataset.more)));
  document.querySelectorAll('[data-slides]').forEach(slides => {
    const dots = slides.nextElementSibling.children;
    slides.onscroll = () => {
      const index = Math.round(slides.scrollLeft / Math.max(1, slides.clientWidth));
      [...dots].forEach((dot, i) => dot.classList.toggle('current', i === index));
    };
  });
  watchImages();
}
function postActions(post) {
  if (!post) return;
  sheet(post.productName, '', [{label:'查看作品详情', action:() => postPage(post)}, {label:'分享图片', action:() => share(post)}, {label:'保存效果图', action:() => save(post)}, ...(post.mine ? [{label:'撤回发布', danger:true, action:() => withdrawPost(post)}] : []), {label:'取消'}]);
}
function withdrawPost(post) {
  sheet('撤回这条发布？', '个人创作历史会保留。', [{label:'保留'}, {label:'撤回', danger:true, action:async () => {
    await api(`/api/posts/${post.id}`, {method:'DELETE'}); posts = posts.filter(item => item.id !== post.id); communityPage(); toast('已撤回');
  }}]);
}
function findPost(id) { return [...posts, ...examples].find(post => post.id === id); }
function renderPost(post) {
  if (!post) return;
  setScreen('post');
  app.innerHTML = `<section class="page sub-page post-detail">${subTop('社区作品', communityPage)}<div class="post-author"><span class="small-avatar">${escapeHtml(post.nickname.slice(0,1))}</span><strong>${escapeHtml(post.nickname)}</strong>${post.example?'<span class="example-tag">官方示例</span>':''}</div><div class="post-compare">${photo(post.image, `${post.productName}模特效果图`, 'post-detail-image')}<button class="text-button" id="post-original-toggle">查看商品原图 ${icon('arrow')}</button><div id="post-original" hidden>${photo(post.productImage, `${post.productName}商品原图`, 'post-detail-image')}</div></div><h1>${escapeHtml(post.productName)}</h1><p class="post-note">${escapeHtml(post.note)}</p><div class="product-detail">${photo(post.productImage, `${post.productName}商品缩略图`)}<div><span>本次使用的商品</span><strong>${escapeHtml(post.productName)}</strong></div></div><div class="detail-actions">${post.example?`<button class="primary" id="recreate-example">${icon('camera')}拍同款</button>`:''}<button class="secondary" id="post-share">${icon('share')}分享图片</button>${post.mine?'<button class="withdraw secondary" id="withdraw">撤回发布</button>':''}</div></section>`;
  bindHeader(communityPage);
  const toggle = document.querySelector('#post-original-toggle');
  toggle.onclick = () => { const original = document.querySelector('#post-original'); original.hidden = !original.hidden; toggle.innerHTML = `${original.hidden ? '查看' : '收起'}商品原图 ${icon('arrow')}`; watchImages(original); };
  document.querySelector('#recreate-example')?.addEventListener('click', () => recreatePost(post));
  document.querySelector('#post-share').onclick = () => share(post);
  document.querySelector('#withdraw')?.addEventListener('click', () => withdrawPost(post));
  watchImages();
}
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
      posts = [data.post, ...posts.filter(post => post.id !== data.post.id)]; publishDrafts.delete(job.id); postPage(data.post); toast('已发布到社区');
    } catch (error) { pageError(error.message); button.disabled = false; button.innerHTML = `发布到社区 ${icon('arrow')}`; }
  };
  watchImages();
}
