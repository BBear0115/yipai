// Batch upload state
let batchFiles = [];
let batchModel = 'female';
let batchSubmitting = false;
let batchJobs = [];

// Opened from the photo library when several product photos are picked at once.
function openBatchUpload(initialFiles = [], keepPending = false) {
  if (batchSubmitting) { toast('批量图片正在提交，请稍候'); return; }
  if (!keepPending) {
    batchFiles.forEach(file => URL.revokeObjectURL(file.preview));
    batchFiles = [];
  }
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
        if (batchSubmitting) return;
        const idx = parseInt(btn.dataset.remove);
        URL.revokeObjectURL(batchFiles[idx].preview);
        batchFiles.splice(idx, 1);
        updateBatchUI();
      };
    });

    watchImages(layer);
  }

  function selectBatchModel(value) {
    if (batchSubmitting) return;
    batchModel = value;
    layer.querySelectorAll('[data-batch-model]').forEach(button => {
      const selected = button.dataset.batchModel === batchModel;
      button.classList.toggle('selected', selected);
      button.setAttribute('aria-pressed', String(selected));
      button.querySelector('.model-check').innerHTML = selected ? icon('check') : '';
    });
  }

  async function processFiles(files) {
    if (batchSubmitting) return;
    const validFiles = [];
    for (const file of files) {
      if (batchFiles.length + validFiles.length >= 10) {
        pageError('最多一次上传 10 张图片', layer);
        break;
      }
      if (file.size > 20 * 1024 * 1024) continue;
      if (!file.type.match(/^image\/(jpeg|png|webp|heic|heif)/)) continue;

      let url;
      try {
        url = URL.createObjectURL(file);
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
        if (url) URL.revokeObjectURL(url);
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
    if (batchSubmitting) return;
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
      const submittedFiles = new Set();
      const submissionFiles = [...batchFiles];
      let successCount = 0;
      let queueFull = false;

      for (let i = 0; i < submissionFiles.length; i++) {
        if (queueFull) break;

        const file = submissionFiles[i];
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
          submittedFiles.add(file);
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

      batchFiles.filter(file => submittedFiles.has(file)).forEach(file => URL.revokeObjectURL(file.preview));
      batchFiles = batchFiles.filter(file => !submittedFiles.has(file));
      batchSubmitting = false;

      if (successCount > 0) {
        results.forEach(job => mergeJob(job));
        closeOverlay();
        openBatchResults(results, batchFiles.length ? `已提交 ${successCount} 张，${batchFiles.length} 张未提交，可稍后重试` : null);
        schedulePoll();
      } else {
        pageError('提交失败，请稍后重试', layer);
        updateBatchUI();
      }
    } catch (error) {
      batchSubmitting = false;
      submitBtn.disabled = false;
      submitBtn.textContent = `生成 ${batchFiles.length} 张图片`;
      pageError(error.message || '提交失败，请重试', layer);
    }
  };

  if (keepPending) updateBatchUI();
  if (initialFiles.length) void processFiles(initialFiles);
  watchImages(layer);
}

// Batch results display - shows generation progress and download options
function openBatchResults(jobIds, noticeMessage = null) {
  const jobs = jobIds.map(job => history.find(h => h.id === job.id) || job);

  const layer = openOverlay(`<section class="sheet batch-results-sheet" role="dialog" aria-modal="true" aria-labelledby="batch-results-title">
    <div class="sheet-heading">
      <h2 id="batch-results-title">批量生成进度</h2>
      <button class="icon-button" data-close aria-label="关闭">${icon('close')}</button>
    </div>
    <div class="batch-results-content">
      ${noticeMessage ? `<div class="batch-notice">${icon('warning')}<span>${escapeHtml(noticeMessage)}</span></div>` : ''}
      <div class="batch-results-summary">
        <div class="batch-stat">
          <strong id="batch-completed-count">0</strong>
          <span>已完成</span>
        </div>
        <div class="batch-stat">
          <strong id="batch-pending-count">${jobs.filter(isPending).length}</strong>
          <span>生成中</span>
        </div>
        <div class="batch-stat">
          <strong id="batch-failed-count">0</strong>
          <span>失败</span>
        </div>
      </div>
      <div class="batch-results-grid" id="batch-results-grid"></div>
      <div class="batch-results-actions">
        <button class="primary" id="batch-download-all" disabled>
          ${icon('save')}批量下载已完成
        </button>
        <button class="secondary" id="batch-go-my">
          前往我的作品
        </button>
        ${batchFiles.length ? '<button class="secondary" id="batch-retry-pending">重试未提交图片</button>' : ''}
      </div>
    </div>
  </section>`, 'batch-results-overlay');

  const grid = layer.querySelector('#batch-results-grid');
  const completedCount = layer.querySelector('#batch-completed-count');
  const pendingCount = layer.querySelector('#batch-pending-count');
  const failedCount = layer.querySelector('#batch-failed-count');
  const downloadAllBtn = layer.querySelector('#batch-download-all');

  function updateBatchResults() {
    const currentJobs = jobIds.map(job => history.find(h => h.id === job.id) || job);
    const completed = currentJobs.filter(j => j.status === 'succeeded');
    const pending = currentJobs.filter(isPending);
    const failed = currentJobs.filter(j => j.status === 'failed');

    completedCount.textContent = completed.length;
    pendingCount.textContent = pending.length;
    failedCount.textContent = failed.length;
    downloadAllBtn.disabled = completed.length === 0;

    grid.innerHTML = currentJobs.map((job, index) => {
      const status = job.status;
      const isCompleted = status === 'succeeded';
      const isFailed = status === 'failed';
      const isPendingJob = isPending(job);

      return `
        <div class="batch-result-card ${status}" data-job-id="${job.id}">
          <div class="batch-result-image">
            ${isCompleted ? photo(job.image, `生成结果 ${index + 1}`, '', true) : ''}
            ${isPendingJob ? `<div class="batch-result-spinner"><span class="spinner small"></span></div>` : ''}
            ${isFailed ? `<div class="batch-result-failed">${icon('warning')}</div>` : ''}
          </div>
          <div class="batch-result-info">
            <div class="batch-result-status">
              <span class="status-badge ${status}">${statusLabel(job)}</span>
            </div>
            ${isCompleted ? `
              <button class="batch-result-download" data-download="${job.id}" aria-label="下载">
                ${icon('save')}
              </button>
            ` : ''}
          </div>
        </div>
      `;
    }).join('');

    // Bind download buttons
    grid.querySelectorAll('[data-download]').forEach(btn => {
      btn.onclick = () => {
        const job = currentJobs.find(j => j.id === btn.dataset.download);
        if (job && job.status === 'succeeded') {
          // 使用新的导出模块生成带时间戳和任务类型的文件名
          if (typeof downloadSingleImage === 'function') {
            downloadSingleImage(job);
          } else {
            const link = document.createElement('a');
            link.href = job.image;
            link.download = `衣拍-${job.id}.jpg`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            toast('已发起下载');
          }
        }
      };
    });

    // Bind image click to open viewer
    grid.querySelectorAll('.batch-result-card.succeeded .image-frame').forEach(frame => {
      const jobId = frame.closest('.batch-result-card').dataset.jobId;
      const job = currentJobs.find(j => j.id === jobId);
      if (job) {
        frame.style.cursor = 'pointer';
        frame.onclick = () => {
          closeOverlay();
          openJob(job);
        };
      }
    });

    watchImages(layer);
  }

  updateBatchResults();

  // Poll for updates if any jobs are still pending
  let pollInterval;
  const startPolling = () => {
    if (pollInterval) return;
    pollInterval = setInterval(() => {
      const currentJobs = jobIds.map(job => history.find(h => h.id === job.id) || job);
      const stillPending = currentJobs.some(isPending);

      if (!stillPending) {
        clearInterval(pollInterval);
        pollInterval = null;
      }

      updateBatchResults();
    }, 3000);
  };

  if (jobs.some(isPending)) {
    startPolling();
  }

  downloadAllBtn.onclick = () => {
    const currentJobs = jobIds.map(job => history.find(h => h.id === job.id) || job);
    const completed = currentJobs.filter(j => j.status === 'succeeded');

    if (completed.length === 0) {
      toast('暂无已完成的图片');
      return;
    }

    // 使用新的导出模块批量下载多个作品
    if (typeof downloadBatchJobs === 'function') {
      downloadBatchJobs(completed);
      return;
    }

    // 降级方案：逐个下载
    completed.forEach((job, index) => {
      setTimeout(() => {
        const link = document.createElement('a');
        link.href = job.image;
        link.download = `衣拍-批量-${index + 1}.jpg`;
        document.body.appendChild(link);
        link.click();
        link.remove();
      }, index * 300); // Stagger downloads to avoid browser blocking
    });

    toast(`正在下载 ${completed.length} 张图片`);
  };

  layer.querySelector('#batch-go-my').onclick = () => {
    closeOverlay();
    myPage();
  };
  layer.querySelector('#batch-retry-pending')?.addEventListener('click', () => openBatchUpload([], true));

  // Clean up polling when overlay closes
  layer.onClose = () => {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  };
}
