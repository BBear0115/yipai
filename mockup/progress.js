// 生成进度动画组件
// 循环显示多个阶段提示，直到生成完成

function createProgressStage(container, options = {}) {
  const {
    onCancel = null,
    workflowType = 'tryon'
  } = options;

  // 不同工作流的阶段文案
  const stages = {
    tryon: [
      '正在分析服装细节...',
      '生成模特姿态...',
      '渲染光影效果...',
      '优化图像质量...'
    ],
    remake: [
      '正在分析参考图片...',
      '匹配服装风格...',
      '生成多个角度...',
      '渲染最终效果...'
    ],
    pose_variation: [
      '正在分析原图姿态...',
      '生成多个变体...',
      '优化姿势自然度...',
      '渲染最终图像...'
    ],
    background_change: [
      '正在分析背景元素...',
      '生成新背景...',
      '融合前景主体...',
      '优化整体效果...'
    ]
  };

  const stageTexts = stages[workflowType] || stages.tryon;
  let currentStageIndex = 0;
  let progressInterval = null;
  let destroyed = false;

  // 渲染组件 HTML
  const html = `
    <div class="progress-stage">
      <div class="progress-stage-content">
        <div class="progress-stage-spinner">
          <div class="spinner"></div>
        </div>
        <div class="progress-stage-text">${stageTexts[0]}</div>
        <div class="progress-bar-container">
          <div class="progress-bar-fill" style="width: 15%"></div>
          <div class="progress-bar-shimmer"></div>
        </div>
      </div>
      <p class="progress-stage-meta">预计需要 20-40 秒<br>可以离开，完成后在「我的」查看</p>
    </div>
  `;

  container.innerHTML = html;

  const textElement = container.querySelector('.progress-stage-text');
  const fillElement = container.querySelector('.progress-bar-fill');

  // 更新到下一个阶段
  function nextStage() {
    if (destroyed) return;

    // 淡出当前文本
    textElement.classList.add('fade-out');

    setTimeout(() => {
      if (destroyed) return;

      // 切换到下一个阶段
      currentStageIndex = (currentStageIndex + 1) % stageTexts.length;
      textElement.textContent = stageTexts[currentStageIndex];
      textElement.classList.remove('fade-out');

      // 更新进度条（15% 到 85% 之间循环）
      const progress = 15 + (currentStageIndex / stageTexts.length) * 70;
      fillElement.style.width = `${progress}%`;
    }, 300);
  }

  // 启动阶段循环，每 2.5 秒切换一次
  function start() {
    if (progressInterval) return;
    progressInterval = setInterval(nextStage, 2500);
  }

  // 停止并清理
  function destroy() {
    destroyed = true;
    if (progressInterval) {
      clearInterval(progressInterval);
      progressInterval = null;
    }
  }

  // 更新进度（从外部调用，例如收到实际进度信息时）
  function setProgress(percent, message) {
    if (destroyed) return;
    if (percent !== undefined && percent >= 0 && percent <= 100) {
      fillElement.style.width = `${percent}%`;
    }
    if (message) {
      textElement.classList.add('fade-out');
      setTimeout(() => {
        if (destroyed) return;
        textElement.textContent = message;
        textElement.classList.remove('fade-out');
      }, 300);
    }
  }

  // 完成动画
  function complete(callback) {
    if (destroyed) return;
    destroy();
    fillElement.style.width = '100%';
    textElement.classList.add('fade-out');
    setTimeout(() => {
      if (callback) callback();
    }, 400);
  }

  // 自动启动
  start();

  // 返回控制接口
  return {
    start,
    destroy,
    setProgress,
    complete,
    get currentStage() {
      return currentStageIndex;
    }
  };
}

// 全局导出
if (typeof window !== 'undefined') {
  window.createProgressStage = createProgressStage;
}
