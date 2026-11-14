// Batch upload state
let batchFiles = [];
let batchModel = 'female';
let batchSubmitting = false;
let batchJobs = [];

// Opened from the photo library when several product photos are picked at once.
function openBatchUpload(initialFiles = []) {
  batchFiles.forEach(file => URL.revokeObjectURL(file.preview));
  batchFiles = [];
  const layer = openOverlay(`<section class="sheet batch-sheet" role="dialog" aria-modal="true" aria-labelledby="batch-title">
    <div class="sheet-heading">
      <h2 id="batch-title">批量作图</h2>
      <button class="icon-button" data-close aria-label="关闭">${icon('close')}</button>
    </div>
    <div class="batch-content">
      <div class="batch-dropzone" id="batch-dropzone">
        <div class="dropzone-content">
          ${icon('image')}
          <p><strong>拖拽多张商品图到这里</strong></p>
          <p class="muted">或点击选择文件，最多一次上传 10 张</p>
          <button class="primary" type="button" id="batch-select">选择图片</button>
        </div>
      </div>
      <div class="batch-preview" id="batch-preview" hidden>
        <div class="batch-controls">
          <p><strong>已选择 <span id="batch-count">0</span> 张图片</strong></p>
          <span class="batch-control-actions"><button class="text-button" id="batch-add">继续添加</button><button class="text-button" id="batch-clear">清空</button></span>
        </div>
        <div class="batch-grid" id="batch-grid"></div>
      </div>
      <div class="batch-model-select" id="batch-model-select" hidden>
        <span class="eyebrow">统一选择模特</span>
        <div class="compact-models" id="batch-models">${['female', 'male'].map(value =>
          `<div class="model-chip ${batchModel === value ? 'selected' : ''}" data-batch-model="${value}" role="button" tabindex="0" aria-pressed="${batchModel === value}">
            ${photo(`assets/${value}-model.png`, `${modelName(value)}形象`)}
            <span class="model-label">${modelName(value)}<span class="model-check">${batchModel === value ? icon('check') : ''}</span></span>
          </div>`).join('')}</div>
      </div>
      ${errorSlot}
      <div class="sheet-actions" id="batch-actions">
        <button class="secondary" type="button" data-close>取消</button>
        <button class="primary" type="button" id="batch-submit" disabled>开始生成</button>
      </div>
    </div>
  </section>`);

  const dropzone = layer.querySelector('#batch-dropzone');
  const preview = layer.querySelector('#batch-preview');
  const modelSelect = layer.querySelector('#batch-model-select');
  const actions = layer.querySelector('#batch-actions');
  const grid = layer.querySelector('#batch-grid');
  const countEl = layer.querySelector('#batch-count');
  const submitBtn = layer.querySelector('#batch-submit');
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = 'image/*,.heic,.heif';
  fileInput.multiple = true;
  fileInput.hidden = true;
  layer.appendChild(fileInput);

  function updateBatchUI() {
    const hasFiles = batchFiles.length > 0;
    dropzone.hidden = hasFiles;
    preview.hidden = !hasFiles;
    modelSelect.hidden = !hasFiles;
    countEl.textContent = batchFiles.length;
    layer.querySelector('#batch-add').hidden = batchFiles.length >= 10;
    submitBtn.disabled = !hasFiles || batchSubmitting;
    submitBtn.textContent = batchSubmitting ? '正在提交…' : `生成 ${batchFiles.length} 张图片`;

    grid.innerHTML = batchFiles.map((file, index) => `
      <div class="batch-item" data-index="${index}">
        <img src="${file.preview}" alt="${escapeHtml(file.name)}" />
        <button class="batch-remove" data-remove="${index}" aria-label="移除">${icon('close')}</button>
      </div>
    `).join('');

    grid.querySelectorAll('[data-remove]').forEach(btn => {
      btn.onclick = () => {
        const idx = parseInt(btn.dataset.remove);
        URL.revokeObjectURL(batchFiles[idx].preview);
        batchFiles.splice(idx, 1);
        updateBatchUI();
      };
    });

    watchImages(layer);
  }

  function selectBatchModel(value) {
    batchModel = value;
    layer.querySelectorAll('[data-batch-model]').forEach(button => {
      const selected = button.dataset.batchModel === batchModel;
      button.classList.toggle('selected', selected);
      button.setAttribute('aria-pressed', String(selected));
      button.querySelector('.model-check').innerHTML = selected ? icon('check') : '';
    });
  }

  async function processFiles(files) {
    const validFiles = [];
    for (const file of files) {
      if (batchFiles.length + validFiles.length >= 10) {
        pageError('最多一次上传 10 张图片', layer);
        break;
      }
      if (file.size > 20 * 1024 * 1024) continue;
      if (!file.type.match(/^image\/(jpeg|png|webp|heic|heif)/)) continue;

      try {
        const url = URL.createObjectURL(file);
        const img = await loadImage(url);
        const canvas = document.createElement('canvas');
        const scale = Math.min(1, 1200 / Math.max(img.width, img.height));
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);

        if (Math.min(canvas.width, canvas.height) < 512) {
          URL.revokeObjectURL(url);
          continue;
        }

        canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', .85);

        validFiles.push({
          name: file.name,
          preview: url,
          data: dataUrl,
          idempotencyKey: crypto.randomUUID()
        });
      } catch (e) {
        continue;
      }
    }

    if (validFiles.length > 0) {
      batchFiles.push(...validFiles);
      updateBatchUI();
      pageError('', layer);
    } else if (files.length > 0) {
      pageError('未找到有效图片，请上传 JPG、PNG 或 WebP 格式图片', layer);
    }
  }

  layer.querySelector('#batch-select').onclick = () => fileInput.click();
  layer.querySelector('#batch-add').onclick = () => fileInput.click();
  layer.querySelector('#batch-clear').onclick = () => {
    batchFiles.forEach(file => URL.revokeObjectURL(file.preview));
    batchFiles = [];
    updateBatchUI();
  };

  fileInput.onchange = async () => {
    if (fileInput.files.length > 0) {
      await processFiles(Array.from(fileInput.files));
      fileInput.value = '';
    }
  };

  dropzone.ondragover = (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  };

  dropzone.ondragleave = () => {
    dropzone.classList.remove('dragover');
  };

  dropzone.ondrop = async (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    await processFiles(Array.from(e.dataTransfer.files));
  };

  layer.querySelectorAll('[data-batch-model]').forEach(btn => {
    btn.onclick = () => selectBatchModel(btn.dataset.batchModel);
  });

  submitBtn.onclick = async () => {
    if (batchSubmitting || batchFiles.length === 0) return;

    batchSubmitting = true;
    submitBtn.disabled = true;
    submitBtn.textContent = '正在提交…';
    pageError('', layer);

    try {
      await sessionReady;
      const results = [];
      let successCount = 0;
      let queueFull = false;

      for (let i = 0; i < batchFiles.length; i++) {
        if (queueFull) break;

        const file = batchFiles[i];
        try {
          const response = await api('/api/jobs', {
            method: 'POST',
            body: JSON.stringify({
              image: file.data,
              model: batchModel,
              idempotencyKey: file.idempotencyKey
            })
          });

          results.push(response.job);
          successCount++;

          if (response.queueCount >= 10) {
            queueFull = true;
            break;
          }
        } catch (error) {
          if (error.message.includes('排队任务已达上限') || error.message.includes('已有图片正在生成')) {
            queueFull = true;
            break;
          }
          console.error('Batch submit error:', error);
        }
      }

      batchFiles.forEach(file => URL.revokeObjectURL(file.preview));
      batchFiles = [];
      batchSubmitting = false;

      if (successCount > 0) {
        results.forEach(job => mergeJob(job));
        closeOverlay();
        myPage();
        toast(queueFull
          ? `已提交 ${successCount} 张，其余请等待队列完成后再提交`
          : `已提交 ${successCount} 张图片，可在「我的」查看`
        );
        schedulePoll();
      } else {
        pageError('提交失败，请稍后重试', layer);
        submitBtn.disabled = false;
        submitBtn.textContent = `生成 ${batchFiles.length} 张图片`;
      }
    } catch (error) {
      batchSubmitting = false;
      submitBtn.disabled = false;
      submitBtn.textContent = `生成 ${batchFiles.length} 张图片`;
      pageError(error.message || '提交失败，请重试', layer);
    }
  };

  if (initialFiles.length) void processFiles(initialFiles);
  watchImages(layer);
}
