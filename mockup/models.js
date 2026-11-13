// 模特库管理
let allModels = [];
let selectedModelId = null;

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
  container.innerHTML = `
    <div class="model-picker-header">
      <h3>选择模特</h3>
      <button class="icon-button" data-close>${icon('close')}</button>
    </div>
    <div class="model-grid" data-models></div>
    <div class="model-actions">
      <button class="text-button" data-upload>上传自定义模特</button>
    </div>
  `;

  const grid = container.querySelector('[data-models]');
  allModels.forEach(model => {
    const card = document.createElement('div');
    card.className = 'model-card';
    if (model.id === selectedModelId) card.classList.add('selected');
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
        deleteModel(model.id);
      } else {
        selectModel(model.id);
      }
    });
    grid.appendChild(card);
  });

  container.querySelector('[data-close]').onclick = () => container.remove();
  container.querySelector('[data-upload]').onclick = () => showModelUpload();

  return container;
}

function selectModel(modelId) {
  selectedModelId = modelId;
  const picker = document.querySelector('.model-picker');
  if (picker) {
    picker.querySelectorAll('.model-card').forEach(card => card.classList.remove('selected'));
    const selected = Array.from(picker.querySelectorAll('.model-card')).find(card =>
      card.querySelector('img').src.includes(modelId)
    );
    if (selected) {
      selected.classList.add('selected');
      selected.innerHTML += `<div class="model-check">${icon('check')}</div>`;
    }
  }

  // 更新主界面显示
  const selectedModel = allModels.find(m => m.id === modelId);
  if (selectedModel) {
    try {
      localStorage.setItem('yipai-selected-model-id', modelId);
    } catch {}
  }
}

function showModelUpload() {
  const dialog = document.createElement('div');
  dialog.className = 'modal';
  dialog.innerHTML = `
    <div class="modal-content">
      <h3>上传自定义模特</h3>
      <form id="model-upload-form">
        <div class="form-group">
          <label>模特名称</label>
          <input type="text" name="name" placeholder="例如：时尚模特 A" maxlength="20" required>
        </div>
        <div class="form-group">
          <label>性别</label>
          <select name="gender" required>
            <option value="female">女性</option>
            <option value="male">男性</option>
          </select>
        </div>
        <div class="form-group">
          <label>模特照片</label>
          <input type="file" name="image" accept="image/png,image/jpeg,image/webp" required>
          <small>支持 PNG、JPG、WebP 格式，建议竖版全身照</small>
        </div>
        <div class="form-actions">
          <button type="button" class="text-button" data-cancel>取消</button>
          <button type="submit" class="primary-button">上传</button>
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

        // 刷新模特选择器
        const picker = document.querySelector('.model-picker');
        if (picker) {
          const newPicker = renderModelPicker();
          picker.replaceWith(newPicker);
        }
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

    // 刷新模特选择器
    const picker = document.querySelector('.model-picker');
    if (picker) {
      const newPicker = renderModelPicker();
      picker.replaceWith(newPicker);
    }
  } catch (error) {
    toast(error.message || '删除失败');
  }
}

// 初始化时加载模特库
(async () => {
  await loadModels();
  try {
    const savedId = localStorage.getItem('yipai-selected-model-id');
    if (savedId && allModels.find(m => m.id === savedId)) {
      selectedModelId = savedId;
    } else if (allModels.length > 0) {
      selectedModelId = allModels[0].id;
    }
  } catch {}
})();
