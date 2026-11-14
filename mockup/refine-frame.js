// Generation preview: the input photo turns into a coarse mosaic, sharpens level by level while the
// job runs, then the finished image resolves in the same frame. Adapted from React Bits RefineFrame.
const REFINE_LEVELS = [48, 32, 20, 12, 8, 5, 3, 2, 1];
const REFINE_EDGE = 28, REFINE_STRIPS = 14;
const REFINE_LABELS = {queued:'排队中', generating:'生成中', complete:'已完成'};
const REFINE_MARKS = {spin:'<path d="M12 3a9 9 0 1 0 9 9"/>', complete:'<path d="m5 12 4 4L19 6"/>'};

function refineFrame(host, src, alt) {
  host.classList.add('refine-frame');
  host.innerHTML = `<img alt="${escapeHtml(alt)}" decoding="async"><canvas aria-hidden="true"></canvas><div class="refine-frame-sweep" aria-hidden="true"></div><div class="refine-frame-chip" aria-hidden="true"><span class="refine-frame-mark"></span></div>`;
  const img = host.querySelector('img'), canvas = host.querySelector('canvas'), chip = host.querySelector('.refine-frame-chip');
  const ctx = canvas.getContext('2d');
  const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const n = REFINE_LEVELS.length - 1;
  const s = {p:0, raf:0, last:0, key:'', w:0, h:0, levels:[], glint:null, status:'queued', floor:0, since:Date.now(), stage:.4, done:null};

  // While generating, the target creeps forward on its own so the frame never looks frozen.
  const goal = () => {
    if (s.status === 'complete') return 1;
    if (s.status === 'queued') return 0;
    return Math.min(.875, Math.max(s.floor, .25 + .6 * (1 - Math.exp(-(Date.now() - s.since) / 40000))));
  };
  const build = dpr => {
    const rect = canvas.getBoundingClientRect();
    const W = Math.max(1, Math.round(rect.width * dpr)), H = Math.max(1, Math.round(rect.height * dpr));
    const key = `${img.currentSrc}|${W}x${H}`;
    if (s.key === key) return;
    Object.assign(s, {key, w:W, h:H}); canvas.width = W; canvas.height = H;
    const cover = Math.max(W / img.naturalWidth, H / img.naturalHeight);
    const sw = W / cover, sh = H / cover, sx = (img.naturalWidth - sw) / 2, sy = (img.naturalHeight - sh) / 2;
    s.glint = ctx.createLinearGradient(0, 0, W, 0);
    for (const [at, a] of [[0,0],[.08,.1],[.2,.7],[.32,1],[.68,1],[.8,.7],[.92,.1],[1,0]]) s.glint.addColorStop(at, `rgba(255,255,255,${a})`);
    s.levels = REFINE_LEVELS.map(block => {
      const full = document.createElement('canvas'); full.width = W; full.height = H;
      const fc = full.getContext('2d');
      if (block === 1) { fc.imageSmoothingQuality = 'high'; fc.drawImage(img, sx, sy, sw, sh, 0, 0, W, H); return full; }
      const b = Math.max(2, Math.round(block * dpr));
      const small = document.createElement('canvas');
      small.width = Math.max(1, Math.round(W / b)); small.height = Math.max(1, Math.round(H / b));
      const sc = small.getContext('2d'); sc.imageSmoothingQuality = 'high';
      sc.drawImage(img, sx, sy, sw, sh, 0, 0, small.width, small.height);
      fc.imageSmoothingEnabled = false; fc.drawImage(small, 0, 0, W, H);
      return full;
    });
  };
  // The next, finer level slides in from the top behind a feathered edge with a thin glint on its front.
  const draw = dpr => {
    const L = s.p * n, i = Math.min(n, Math.floor(L + 1e-6)), frac = L - i;
    ctx.globalAlpha = 1; ctx.drawImage(s.levels[i], 0, 0);
    if (i >= n || frac <= 0) return;
    const edge = REFINE_EDGE * dpr, front = frac * (s.h + edge) - edge / 2, top = Math.max(0, Math.floor(front - edge / 2));
    if (top > 0) ctx.drawImage(s.levels[i + 1], 0, 0, s.w, top, 0, 0, s.w, top);
    const strip = edge / REFINE_STRIPS;
    for (let k = 0; k < REFINE_STRIPS; k += 1) {
      const y = front - edge / 2 + k * strip, y0 = Math.max(0, y), h0 = Math.min(s.h, y + strip) - y0;
      if (h0 <= 0) continue;
      const t = 1 - (k + .5) / REFINE_STRIPS; ctx.globalAlpha = t * t * (3 - 2 * t);
      ctx.drawImage(s.levels[i + 1], 0, y0, s.w, h0, 0, y0, s.w, h0);
    }
    if (!reduce && front > 0 && front < s.h) {
      ctx.fillStyle = s.glint;
      ctx.globalAlpha = .12; ctx.fillRect(0, front - 2 * dpr, s.w, 4 * dpr);
      ctx.globalAlpha = .3; ctx.fillRect(0, front - dpr, s.w, 2 * dpr);
    }
    ctx.globalAlpha = 1;
  };
  const tick = now => {
    s.raf = 0;
    if (!host.isConnected || !img.complete || !img.naturalWidth) { s.last = 0; return; }
    const dt = Math.min(.05, s.last ? (now - s.last) / 1000 : .016); s.last = now;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    build(dpr);
    const target = goal();
    s.p = target < s.p ? target : Math.min(target, s.p + (reduce ? 1 : dt / (n * s.stage)));
    draw(dpr);
    if (s.p >= 1) { host.dataset.resolved = ''; const done = s.done; s.done = null; done?.(); return; }
    if ((!reduce && s.status === 'generating') || s.p < target) s.raf = requestAnimationFrame(tick); else s.last = 0;
  };
  const wake = () => { if (!s.raf) s.raf = requestAnimationFrame(tick); };
  const setChip = status => {
    host.dataset.status = status;
    if (status === 'complete') delete host.dataset.active; else host.dataset.active = '';
    chip.querySelector('.refine-frame-mark').innerHTML = `<svg viewBox="0 0 24 24">${REFINE_MARKS[status === 'complete' ? 'complete' : 'spin']}</svg>`;
    chip.querySelector('.refine-frame-label')?.remove();
    chip.insertAdjacentHTML('beforeend', `<span class="refine-frame-label">${REFINE_LABELS[status]}</span>`);
  };

  const fit = () => host.style.setProperty('--rf-aspect', Math.min(1.25, Math.max(.5, img.naturalWidth / img.naturalHeight)));
  img.onload = () => { fit(); host.dataset.mosaic = ''; wake(); };
  img.src = src; setChip('queued');
  return {
    update({status, floor = 0, since = s.since}) {
      if (s.status === 'complete') return;
      if (status !== s.status) setChip(status);
      Object.assign(s, {status, floor, since}); wake();
    },
    // Swap in the finished image at a coarse level and let it sharpen; done runs once it is crisp.
    reveal(next, done) {
      let called = false;
      const finish = () => { if (!called) { called = true; done(); } };
      setTimeout(finish, 4000);
      s.status = 'complete'; s.stage = .25; s.done = finish; setChip('complete');
      if (!next || next === img.getAttribute('src')) { wake(); return; }
      img.onload = () => { fit(); s.p = Math.min(s.p, .25); s.key = ''; wake(); };
      img.onerror = finish;
      img.src = next;
    }
  };
}
