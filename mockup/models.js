// 模特库管理

async function loadModels() {
  try {
    const response = await api('/api/models');
    allModels = response.models || [];
    return allModels;
  } catch (error) {
    console.error('加载模特失败:', error);
    toast('模特库加载失败');
    return [];
  }
}

function renderModelPicker() {
  const container = document.createElement('div');
  container.className = 'model-picker';
  container.setAttribute('role', 'presentation');
  container.innerHTML = `
    <section class="model-picker-panel" role="dialog" aria-modal="true" aria-labelledby="model-picker-title">
      <div class="model-picker-header">
        <h3 id="model-picker-title">从模特库选择</h3>
        <button class="icon-button" type="button" data-close aria-label="关闭">${icon('close')}</button>
      </div>
      <div class="model-grid" data-models></div>
      <div class="model-actions"><button class="text-button" type="button" data-upload>上传自定义模特</button></div>
    </section>
  `;

  const grid = container.querySelector('[data-models]');
  if (!allModels.length) grid.innerHTML = '<p class="model-empty">模特库还是空的，可以上传专属模特照片。</p>';
  allModels.forEach(model => {
    const card = document.createElement('div');
    card.className = 'model-card';
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-pressed', String(model.id === selectedModelId));
    if (model.id === selectedModelId) card.classList.add('selected');
    card.dataset.libraryModel = model.id;
    card.innerHTML = `
      <img src="${escapeHtml(model.image)}" alt="${escapeHtml(model.name)}" loading="lazy">
      <div class="model-info">
        <span class="model-name">${escapeHtml(model.name)}</span>
        ${model.isPreset ? '' : '<button class="icon-button-small" data-delete>删除</button>'}
      </div>
      ${model.id === selectedModelId ? `<div class="model-check">${icon('check')}</div>` : ''}
    `;
    card.addEventListener('click', (e) => {
      if (e.target.closest('[data-delete]')) {
        e.stopPropagation();
        deleteModel(model.id);
      } else {
        selectLibraryModel(model.id);
      }
    });
    grid.appendChild(card);
  });

  container.querySelector('[data-close]').onclick = () => container.remove();
  container.querySelector('[data-upload]').onclick = () => showModelUpload();
  container.addEventListener('click',event=>{if(event.target===container)container.remove();});

  return container;
}

function selectLibraryModel(modelId) {
  selectedModelId = modelId;
  if (typeof tryonDraftRevision !== 'undefined') { tryonDraftRevision++; pendingSubmission = null; }
  const selectedModel = allModels.find(m => m.id === modelId);
  if (selectedModel) {
    model = selectedModel.gender === 'male' ? 'male' : 'female';
    if (screen === 'remake' && typeof tryonDraftState !== 'undefined') {tryonDraftState.modelImage = null;tryonDraftState.modelFromWork=false;}
    try { localStorage.setItem('yipai-selected-model-id', modelId); localStorage.setItem('yipai-model', model); } catch {}
  }
  document.querySelector('.model-picker')?.remove();
  if (screen === 'prepare') renderPrepare();
  else if (screen === 'remake') renderRemake();
}

function showModelUpload() {
  const dialog = document.createElement('div');
  dialog.className = 'modal';
  dialog.innerHTML = `
    <div class="modal-content">
      <h3>上传自定义模特</h3>
      <form id="model-upload-form">
        <div class="form-group">
          <label for="model-upload-name">模特名称</label>
          <input id="model-upload-name" type="text" name="name" placeholder="例如：时尚模特 A" maxlength="20" required>
        </div>
        <div class="form-group">
          <label for="model-upload-gender">性别</label>
          <select id="model-upload-gender" name="gender" required>
            <option value="female">女性</option>
            <option value="male">男性</option>
          </select>
        </div>
        <div class="form-group">
          <label for="model-upload-image">模特照片</label>
          <input id="model-upload-image" type="file" name="image" accept="image/png,image/jpeg,image/webp" required>
          <small>支持 PNG、JPG、WebP，至少 400 × 400 像素；建议清晰正脸或上半身照。</small>
        </div>
        <div class="form-actions">
          <button type="button" class="text-button" data-cancel>取消</button>
          <button type="submit" class="primary">上传</button>
        </div>
      </form>
    </div>
  `;

  const form = dialog.querySelector('form');
  form.onsubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    const file = formData.get('image');

    if (!file || file.size === 0) {
      toast('请选择图片');
      return;
    }

    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const response = await api('/api/models', {
          method: 'POST',
          body: JSON.stringify({
            name: formData.get('name'),
            gender: formData.get('gender'),
            image: reader.result
          })
        });

        toast('模特上传成功');
        dialog.remove();
        await loadModels();
        if (response.model?.id) selectLibraryModel(response.model.id);
      } catch (error) {
        toast(error.message || '上传失败');
      }
    };
    reader.readAsDataURL(file);
  };

  dialog.querySelector('[data-cancel]').onclick = () => dialog.remove();
  document.body.appendChild(dialog);
}

async function deleteModel(modelId) {
  if (!confirm('确定删除这个模特吗？')) return;

  try {
    await api(`/api/models/${modelId}`, { method: 'DELETE' });
    toast('模特已删除');
    await loadModels();
    if (selectedModelId === modelId) {
      selectedModelId = null;
      try { localStorage.removeItem('yipai-selected-model-id'); } catch {}
    }

    const picker = document.querySelector('.model-picker');
    if (picker) picker.replaceWith(renderModelPicker());
  } catch (error) {
    toast(error.message || '删除失败');
  }
}

// 初始化时加载模特库
(async () => {
  await loadModels();
  try {
    const savedId = localStorage.getItem('yipai-selected-model-id');
    if (savedId && allModels.find(m => m.id === savedId)) selectedModelId = savedId;
    else { selectedModelId = null; localStorage.removeItem('yipai-selected-model-id'); }
  } catch {}
  if (screen === 'prepare') renderPrepare();
  else if (screen === 'remake') renderRemake();
})();
