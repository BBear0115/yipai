// Workflows module for Yipai

const workflows = [
  {
    id: 'pose-variation',
    name: '姿势裂变',
    description: '一张商品图，生成多角度模特效果',
    icon: 'pose',
    route: '#workflow/pose-variation'
  },
  {
    id: 'background-change',
    name: '换背景',
    description: '保持模特姿势，更换场景背景',
    icon: 'background',
    route: '#workflow/background-change'
  }
];

const workflowIcons = {
  pose: '<path d="M12 2a4 4 0 0 1 4 4 4 4 0 0 1-4 4 4 4 0 0 1-4-4 4 4 0 0 1 4-4zm-2 14h4v6h-4z"/><path d="M7 12h10M7 16l-3 6M17 16l3 6"/>',
  background: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 14 8 9l4 4 3-3 6 6"/><circle cx="8.5" cy="8.5" r="1.5"/>'
};

const workflowIcon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${workflowIcons[name] || ''}</svg>`;

let workflowUpload = null;
let selectedPoseCount = 4;
let selectedSceneType = 'studio';

const sceneTypes = [
  { id: 'studio', name: '摄影棚', description: '纯色背景，突出商品' },
  { id: 'outdoor', name: '户外场景', description: '自然光线，生活化' },
  { id: 'indoor', name: '室内场景', description: '居家环境，温馨感' },
  { id: 'street', name: '街景', description: '都市风格，时尚感' }
];

function renderWorkflowsHub() {
  setScreen('workflows');
  app.innerHTML = `
    <section class="page workflows-page">
      ${subTop('工作流中心', home)}
      <div class="page-intro">
        <h2>智能工作流</h2>
        <p>选择专业的批量创作工具，提升商品图制作效率。</p>
      </div>
      <div class="workflow-hub">
        ${workflows.map(workflow => `
          <article class="workflow-card" data-workflow="${workflow.id}">
            <button class="workflow-card-button" aria-label="${workflow.name}">
              <div class="workflow-icon">${workflowIcon(workflow.icon)}</div>
              <div class="workflow-info">
                <h3>${escapeHtml(workflow.name)}</h3>
                <p>${escapeHtml(workflow.description)}</p>
              </div>
              <div class="workflow-arrow">${icon('arrow')}</div>
            </button>
          </article>
        `).join('')}
      </div>
    </section>
  `;

  bindHeader(home);
  app.querySelectorAll('[data-workflow]').forEach(card => {
    card.querySelector('.workflow-card-button').onclick = () => {
      const workflow = workflows.find(w => w.id === card.dataset.workflow);
      if (workflow) navigate(workflow.route);
    };
  });
}

function renderPoseVariationPage() {
  setScreen('workflow-detail');
  app.innerHTML = `
    <section class="page workflow-page">
      ${subTop('姿势裂变', () => navigate('#workflows'))}
      <div class="workflow-header">
        <div class="workflow-header-icon">${workflowIcon('pose')}</div>
        <div>
          <h2>姿势裂变</h2>
          <p class="muted">上传一张商品图，生成多个不同姿势的模特效果</p>
        </div>
      </div>

      <div class="workflow-content">
        <div class="workflow-section">
          <h3>上传商品图</h3>
          <div class="workflow-upload-area" id="pose-upload-area">
            ${workflowUpload ? `
              ${photo(workflowUpload, '已上传的商品图', 'workflow-upload-preview')}
              <button class="text-button workflow-reupload" id="pose-reupload">重新上传 ${icon('refresh')}</button>
            ` : `
              <div class="upload-placeholder">
                ${icon('image')}
                <p>上传商品平铺图或挂拍图</p>
                <button class="primary" id="pose-upload-btn">选择图片 ${icon('plus')}</button>
              </div>
            `}
          </div>
        </div>

        <div class="workflow-section">
          <h3>生成数量</h3>
          <p class="section-desc">选择需要生成的姿势数量</p>
          <div class="pose-count-options">
            ${[4, 6, 8].map(count => `
              <button class="pose-count-option ${selectedPoseCount === count ? 'selected' : ''}"
                      data-count="${count}"
                      aria-pressed="${selectedPoseCount === count}">
                <span class="count-number">${count}</span>
                <span class="count-label">张</span>
                ${selectedPoseCount === count ? `<span class="option-check">${icon('check')}</span>` : ''}
              </button>
            `).join('')}
          </div>
        </div>
      </div>

      <div class="bottom-action">
        <button class="primary" id="start-pose-workflow" ${!workflowUpload ? 'disabled' : ''}>
          开始生成 ${icon('arrow')}
        </button>
        <p class="helper">预计生成时间：${selectedPoseCount * 15} 秒</p>
      </div>
      ${errorSlot}
    </section>
  `;

  bindHeader(() => navigate('#workflows'));

  const uploadBtn = document.querySelector('#pose-upload-btn');
  const reuploadBtn = document.querySelector('#pose-reupload');
  const startBtn = document.querySelector('#start-pose-workflow');

  if (uploadBtn) {
    uploadBtn.onclick = () => {
      const fileInput = document.querySelector('#file-input');
      fileInput.onchange = async () => {
        const file = fileInput.files[0];
        fileInput.value = '';
        if (!file) return;

        try {
          const url = URL.createObjectURL(file);
          let img;
          try { img = await loadImage(url); }
          finally { URL.revokeObjectURL(url); }

          const canvas = document.createElement('canvas');
          const scale = Math.min(1, 1200 / Math.max(img.width, img.height));
          canvas.width = Math.round(img.width * scale);
          canvas.height = Math.round(img.height * scale);

          if (Math.min(canvas.width, canvas.height) < 512) {
            throw new Error('图片尺寸过小，请换一张清楚的图片');
          }

          canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
          workflowUpload = canvas.toDataURL('image/jpeg', .85);
          renderPoseVariationPage();
        } catch (error) {
          pageError(error.message || '无法读取图片，请换一张清楚的图片', app);
        }
      };
      fileInput.click();
    };
  }

  if (reuploadBtn) {
    reuploadBtn.onclick = () => {
      workflowUpload = null;
      renderPoseVariationPage();
    };
  }

  app.querySelectorAll('.pose-count-option').forEach(btn => {
    btn.onclick = () => {
      selectedPoseCount = Number(btn.dataset.count);
      renderPoseVariationPage();
    };
  });

  if (startBtn) {
    startBtn.onclick = async () => {
      if (!workflowUpload) return;

      startBtn.disabled = true;
      pageError('', app);

      try {
        toast(`正在生成 ${selectedPoseCount} 张姿势裂变图...`);
        // TODO: API integration
        await new Promise(resolve => setTimeout(resolve, 1500));
        toast('姿势裂变任务已提交');
        navigate('#tasks');
      } catch (error) {
        pageError(error.message || '提交失败，请重试', app);
        startBtn.disabled = false;
      }
    };
  }

  watchImages();
  observeActions();
}

function renderBackgroundChangePage() {
  setScreen('workflow-detail');
  app.innerHTML = `
    <section class="page workflow-page">
      ${subTop('换背景', () => navigate('#workflows'))}
      <div class="workflow-header">
        <div class="workflow-header-icon">${workflowIcon('background')}</div>
        <div>
          <h2>换背景</h2>
          <p class="muted">保持模特姿势，为商品图更换不同场景背景</p>
        </div>
      </div>

      <div class="workflow-content">
        <div class="workflow-section">
          <h3>上传商品图</h3>
          <div class="workflow-upload-area" id="bg-upload-area">
            ${workflowUpload ? `
              ${photo(workflowUpload, '已上传的商品图', 'workflow-upload-preview')}
              <button class="text-button workflow-reupload" id="bg-reupload">重新上传 ${icon('refresh')}</button>
            ` : `
              <div class="upload-placeholder">
                ${icon('image')}
                <p>上传商品平铺图或挂拍图</p>
                <button class="primary" id="bg-upload-btn">选择图片 ${icon('plus')}</button>
              </div>
            `}
          </div>
        </div>

        <div class="workflow-section">
          <h3>场景类型</h3>
          <p class="section-desc">选择想要更换的背景场景</p>
          <div class="scene-type-grid">
            ${sceneTypes.map(scene => `
              <button class="scene-type-card ${selectedSceneType === scene.id ? 'selected' : ''}"
                      data-scene="${scene.id}"
                      aria-pressed="${selectedSceneType === scene.id}">
                <div class="scene-check">
                  ${selectedSceneType === scene.id ? icon('check') : ''}
                </div>
                <strong>${escapeHtml(scene.name)}</strong>
                <span class="scene-desc">${escapeHtml(scene.description)}</span>
              </button>
            `).join('')}
          </div>
        </div>
      </div>

      <div class="bottom-action">
        <button class="primary" id="start-bg-workflow" ${!workflowUpload ? 'disabled' : ''}>
          开始生成 ${icon('arrow')}
        </button>
        <p class="helper">将生成 1 张换背景效果图</p>
      </div>
      ${errorSlot}
    </section>
  `;

  bindHeader(() => navigate('#workflows'));

  const uploadBtn = document.querySelector('#bg-upload-btn');
  const reuploadBtn = document.querySelector('#bg-reupload');
  const startBtn = document.querySelector('#start-bg-workflow');

  if (uploadBtn) {
    uploadBtn.onclick = () => {
      const fileInput = document.querySelector('#file-input');
      fileInput.onchange = async () => {
        const file = fileInput.files[0];
        fileInput.value = '';
        if (!file) return;

        try {
          const url = URL.createObjectURL(file);
          let img;
          try { img = await loadImage(url); }
          finally { URL.revokeObjectURL(url); }

          const canvas = document.createElement('canvas');
          const scale = Math.min(1, 1200 / Math.max(img.width, img.height));
          canvas.width = Math.round(img.width * scale);
          canvas.height = Math.round(img.height * scale);

          if (Math.min(canvas.width, canvas.height) < 512) {
            throw new Error('图片尺寸过小，请换一张清楚的图片');
          }

          canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
          workflowUpload = canvas.toDataURL('image/jpeg', .85);
          renderBackgroundChangePage();
        } catch (error) {
          pageError(error.message || '无法读取图片，请换一张清楚的图片', app);
        }
      };
      fileInput.click();
    };
  }

  if (reuploadBtn) {
    reuploadBtn.onclick = () => {
      workflowUpload = null;
      renderBackgroundChangePage();
    };
  }

  app.querySelectorAll('.scene-type-card').forEach(btn => {
    btn.onclick = () => {
      selectedSceneType = btn.dataset.scene;
      renderBackgroundChangePage();
    };
  });

  if (startBtn) {
    startBtn.onclick = async () => {
      if (!workflowUpload) return;

      startBtn.disabled = true;
      pageError('', app);

      try {
        const sceneName = sceneTypes.find(s => s.id === selectedSceneType)?.name || '场景';
        toast(`正在生成${sceneName}背景效果图...`);
        // TODO: API integration
        await new Promise(resolve => setTimeout(resolve, 1500));
        toast('换背景任务已提交');
        navigate('#tasks');
      } catch (error) {
        pageError(error.message || '提交失败，请重试', app);
        startBtn.disabled = false;
      }
    };
  }

  watchImages();
  observeActions();
}
