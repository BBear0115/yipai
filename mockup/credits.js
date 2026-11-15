// 积分管理模块
const Credits = (() => {
  const STORAGE_KEY = 'yipai-credits';
  const INITIAL_CREDITS = 50;

  function get() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === null) {
        localStorage.setItem(STORAGE_KEY, String(INITIAL_CREDITS));
        return INITIAL_CREDITS;
      }
      const value = parseInt(stored, 10);
      return isNaN(value) ? INITIAL_CREDITS : Math.max(0, value);
    } catch {
      return INITIAL_CREDITS;
    }
  }

  function set(value) {
    try {
      localStorage.setItem(STORAGE_KEY, String(Math.max(0, value)));
    } catch {}
  }

  function deduct(amount = 1) {
    const current = get();
    const newValue = Math.max(0, current - amount);
    set(newValue);
    return newValue;
  }

  function add(amount = 1) {
    const current = get();
    const newValue = current + amount;
    set(newValue);
    return newValue;
  }

  function reset() {
    set(INITIAL_CREDITS);
    return INITIAL_CREDITS;
  }

  function checkLowBalance() {
    const current = get();
    if (current === 0) {
      return { empty: true, message: '生成次数已用完，演示模式将继续生成' };
    }
    if (current <= 5) {
      return { low: true, message: `剩余 ${current} 次生成机会` };
    }
    return { ok: true };
  }

  return { get, set, deduct, add, reset, checkLowBalance, INITIAL_CREDITS };
})();

// 渲染积分显示
function renderCreditsDisplay() {
  const credits = Credits.get();
  return `<div class="credits-display" id="credits-display">
    <div class="credits-avatar">
      ${icon('user')}
    </div>
    <span class="credits-text">剩余 <strong>${credits}</strong> 次</span>
  </div>`;
}

// 更新积分显示
function updateCreditsDisplay() {
  const display = document.querySelector('#credits-display');
  if (!display) return;

  const credits = Credits.get();
  const textEl = display.querySelector('.credits-text');
  if (textEl) {
    textEl.innerHTML = `剩余 <strong>${credits}</strong> 次`;
  }

  display.classList.toggle('credits-low', credits <= 5 && credits > 0);
  display.classList.toggle('credits-empty', credits === 0);
}

// 在生成成功后扣减积分
function onGenerationSuccess() {
  const newBalance = Credits.deduct(1);
  updateCreditsDisplay();

  const status = Credits.checkLowBalance();
  if (status.empty) {
    toast(status.message);
  } else if (status.low) {
    // 低余额时静默扣减，不打扰用户
  }

  return newBalance;
}
