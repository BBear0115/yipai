// 图片对比滑块组件
function createCompareSlider(container, originalSrc, effectSrc, options = {}) {
  const {
    originalLabel = '商品原图',
    effectLabel = '效果图',
    initialPosition = 50
  } = options;

  let position = initialPosition;
  let isDragging = false;
  let startX = 0;

  // 本地 HTML 转义函数
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  const html = `
    <div class="compare-slider" data-compare-slider>
      <div class="compare-container">
        <div class="compare-image compare-original">
          <img src="${escape(originalSrc)}" alt="${escape(originalLabel)}" draggable="false">
          <span class="compare-label">${escape(originalLabel)}</span>
        </div>
        <div class="compare-image compare-effect">
          <img src="${escape(effectSrc)}" alt="${escape(effectLabel)}" draggable="false">
          <span class="compare-label">${escape(effectLabel)}</span>
        </div>
        <div class="compare-divider" data-divider style="--position: ${position}%">
          <div class="compare-handle" role="slider" tabindex="0" aria-label="拖动对比滑块" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${position}">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M15 6l-6 6 6 6"/>
            </svg>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 6l6 6-6 6"/>
            </svg>
          </div>
        </div>
      </div>
    </div>
  `;

  container.innerHTML = html;

  const slider = container.querySelector('[data-compare-slider]');
  const divider = slider.querySelector('[data-divider]');
  const handle = slider.querySelector('.compare-handle');
  const effectImage = slider.querySelector('.compare-effect');

  function updatePosition(newPosition) {
    position = Math.max(0, Math.min(100, newPosition));
    divider.style.setProperty('--position', `${position}%`);
    effectImage.style.clipPath = `inset(0 0 0 ${position}%)`;
    handle.setAttribute('aria-valuenow', Math.round(position));
  }

  function getPositionFromEvent(event, containerRect) {
    const clientX = event.type.startsWith('touch') ? event.touches[0].clientX : event.clientX;
    const x = clientX - containerRect.left;
    return (x / containerRect.width) * 100;
  }

  function startDrag(event) {
    isDragging = true;
    const rect = slider.querySelector('.compare-container').getBoundingClientRect();
    startX = getPositionFromEvent(event, rect);
    updatePosition(startX);
    event.preventDefault();
  }

  function drag(event) {
    if (!isDragging) return;
    const rect = slider.querySelector('.compare-container').getBoundingClientRect();
    const newPosition = getPositionFromEvent(event, rect);
    updatePosition(newPosition);
    event.preventDefault();
  }

  function stopDrag() {
    isDragging = false;
  }

  // 鼠标事件
  handle.addEventListener('mousedown', startDrag);
  document.addEventListener('mousemove', drag);
  document.addEventListener('mouseup', stopDrag);

  // 触摸事件
  handle.addEventListener('touchstart', startDrag, { passive: false });
  document.addEventListener('touchmove', drag, { passive: false });
  document.addEventListener('touchend', stopDrag);

  // 键盘导航
  handle.addEventListener('keydown', (event) => {
    let step = 0;
    if (event.key === 'ArrowLeft') step = -5;
    else if (event.key === 'ArrowRight') step = 5;
    else if (event.key === 'Home') { updatePosition(0); event.preventDefault(); return; }
    else if (event.key === 'End') { updatePosition(100); event.preventDefault(); return; }
    else return;

    event.preventDefault();
    updatePosition(position + step);
  });

  // 点击容器直接跳转到该位置
  slider.querySelector('.compare-container').addEventListener('click', (event) => {
    if (event.target.closest('.compare-handle')) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const newPosition = getPositionFromEvent(event, rect);
    updatePosition(newPosition);
  });

  // 初始化位置
  updatePosition(position);

  // 清理函数
  return {
    destroy: () => {
      document.removeEventListener('mousemove', drag);
      document.removeEventListener('mouseup', stopDrag);
      document.removeEventListener('touchmove', drag);
      document.removeEventListener('touchend', stopDrag);
    },
    setPosition: (newPosition) => {
      updatePosition(newPosition);
    },
    getPosition: () => position
  };
}
