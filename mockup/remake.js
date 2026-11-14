// 拍同款沿用独立的参考图反推和三图生成链路，商品与参考输入共用角色化工作台。
// 开拍的单商品草稿保存在 app.js 的 draft，这里的草稿只属于拍同款。
const remakeReferencePosts = new Map();

function renderRemake() {
  renderTryonStudio();
}

function useAsReference(post) {
  if (!post?.image) return;
  if (!tryonDraftState.references.includes(post.image)) {
    if (tryonDraftState.references.length >= TRYON_MAX_REFERENCES) {
      toast(`参考图最多 ${TRYON_MAX_REFERENCES} 张，请先移除一张。`);
      navigate('#remake');
      return;
    }
    tryonDraftState.references.push(post.image);
  }
  if (!post.example) remakeReferencePosts.set(post.image,post.id);
  tryonDraftRevision++; pendingSubmission=null;
  navigate('#remake');
  toast('已设为参考图，再上传你的商品');
}

function remakeWorks() {
  return sortedJobs().filter(job=>job.status==='succeeded' && job.image).slice(0,24);
}

async function openRemakeWorkPicker(kind, role) {
  if (!jobsLoaded) {
    await sessionReady;
    if (screen!=='remake') return;
  }
  const works=remakeWorks();
  const label=kind==='reference'?'选择拍摄参考':`选择${({upper:'上装',lower:'下装',single:'连体服装'})[role] || '商品'}作品`;
  const layer=openOverlay(`<section class="sheet tryon-work-sheet" role="dialog" aria-modal="true" aria-labelledby="remake-work-title"><div class="sheet-heading"><h2 id="remake-work-title">${label}</h2><button class="icon-button" type="button" data-close aria-label="关闭">${icon('close')}</button></div><p class="tryon-help">${kind==='reference'?'只参考作品的构图、姿势、场景和光线。':'使用作品中的商品，并沿用这张作品的人物；也可以在人物参考中重新选择。'}</p><div class="tryon-work-grid">${works.length?works.map(job=>`<button class="tryon-work-card" type="button" data-remake-work="${escapeHtml(job.id)}" aria-label="使用作品：${escapeHtml(workflowJobName(job))}，${escapeHtml(job.date)}">${photo(job.image,workflowJobName(job))}<span>${escapeHtml(job.date)}</span></button>`).join(''):'<p class="tryon-help">还没有已完成的作品，可以先上传本地图片。</p>'}</div></section>`);
  layer.querySelectorAll('[data-remake-work]').forEach(button=>button.onclick=()=>{
    if (remakeUseWork(button.dataset.remakeWork,kind,role)) closeOverlay(false);
  });
  watchImages(layer);
}

function remakeUseWork(id, kind='garment', role='upper') {
  const job=history.find(item=>item.id===id && item.status==='succeeded');
  if (!job?.image) return false;
  const state=tryonDraftState;
  if (kind==='reference') {
    if (state.references.includes(job.image)) return true;
    if (state.references.length>=TRYON_MAX_REFERENCES) {toast(`参考图最多 ${TRYON_MAX_REFERENCES} 张。`);return false;}
    state.references.push(job.image);
  } else {
    state.garments[role]=job.image;
    state.details[role]=[];
    state.modelImage=job.image;
    state.modelFromWork=true;
    selectedModelId=null;
    try {localStorage.removeItem('yipai-selected-model-id');} catch {}
  }
  tryonDraftRevision++; pendingSubmission=null;
  renderRemake();
  return true;
}

function remakePayload() {
  const workflow=buildTryonWorkflow();
  return {image:workflow.source,model,workflowType:'remake',workflowConfig:workflow.workflowConfig,inputImages:workflow.inputImages,...(workflow.modelId?{modelId:workflow.modelId}:{})};
}

async function recordRemakeReferences(referencePostIds) {
  const postIds=new Set(referencePostIds);
  for (const postId of postIds) {
    const post=findPost(postId);
    if (post) await react(post,'remake',true).catch(()=>{});
  }
}
