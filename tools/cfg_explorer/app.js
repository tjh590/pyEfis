async function loadJSONViaUrl(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return await res.json();
}

async function loadJSONFromFile(file) {
  const text = await file.text();
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new Error(`Invalid JSON in ${file.name}: ${e}`);
  }
}

function el(tag, text, attrs={}) {
  const e = document.createElement(tag);
  if (text) e.textContent = text;
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

function renderIncludes(listEl, includes) {
  listEl.innerHTML = '';
  includes.forEach(inc => {
    const li = el('li', `${inc.file} (${inc.used}x)`);
    li.addEventListener('click', () => {
      if (inc && inc.content && !inc.is_screen) {
        showDetails(`Include: ${inc.file}`, {
          logical: inc.logical,
          used: inc.used,
          locations: inc.locations,
          content: inc.content,
        });
      } else {
        showDetails('Include', inc);
      }
    });
    listEl.appendChild(li);
  });
}

function renderPreferences(listEl, prefs) {
  listEl.innerHTML = '';
  if (!prefs) return;
  // Show top-level keys from raw preferences
  const raw = prefs.raw || {};
  Object.keys(raw).sort().forEach(key => {
    const li = el('li', key);
    li.addEventListener('click', () => showDetails(`Preference: ${key}`, raw[key]));
    listEl.appendChild(li);
  });
  // Separator for implicit defaults
  const imp = prefs.implicit_defaults || {};
  Object.keys(imp).forEach(group => {
    const li = el('li', `[implicit] ${group}`);
    li.addEventListener('click', () => showDetails(`Implicit defaults: ${group}`, imp[group]));
    listEl.appendChild(li);
  });
}

function renderButtons(listEl, buttons) {
  listEl.innerHTML = '';
  (buttons || []).forEach(btn => {
    const label = btn.label ? String(btn.label).replace(/\n/g,' ') : btn.id;
    const li = el('li', `${label}`);
    li.addEventListener('click', () => {
      showButtonDetails(btn);
    });
    listEl.appendChild(li);
  });
}

function showButtonDetails(btn) {
  const title = `Button: ${btn.label || btn.id}`;
  document.getElementById('detailsTitle').textContent = title;
  // Build a readable multi-line summary
  const lines = [];
  lines.push(`id: ${btn.id}`);
  if (btn.type) lines.push(`type: ${btn.type}`);
  if (btn.dbkey) lines.push(`dbkey: ${btn.dbkey}`);
  lines.push(`file: ${btn.file}`);
  // Conditions block
  const conds = btn.conditions || [];
  if (conds.length === 0) {
    lines.push('conditions: (none)');
  } else {
    lines.push(`conditions (${conds.length}):`);
    conds.forEach((c, idx) => {
      const symList = (c.symbols && c.symbols.length) ? c.symbols.join(', ') : '(no symbols)';
      const acts = formatActions(c.actions);
      lines.push(`  [${idx+1}] when: ${c.when || '(always)'}${c.continue ? ' (continue)' : ''}`);
      lines.push(`       symbols: ${symList}`);
      lines.push(`       actions: ${acts}`);
    });
  }
  // Aggregated actions (unique)
  // const agg = uniqueActions(btn.actions || []);
  // lines.push(`all_actions (${agg.length} unique): ${agg.length ? formatActions(agg) : '(none)'}`);
  // Provenance
  if (btn.provenance) {
    lines.push('provenance:');
    Object.entries(btn.provenance).forEach(([k,v]) => {
      if (v === undefined || v === null) return;
      lines.push(`  ${k}: ${Array.isArray(v) ? (v.length ? v.join(' -> ') : '(empty)') : v}`);
    });
  }
  document.getElementById('detailsJson').textContent = lines.join('\n');
}

function uniqueActions(actions) {
  const seen = new Set();
  const out = [];
  for (const a of actions) {
    const key = typeof a === 'object' && a ? JSON.stringify(a) : String(a);
    if (!seen.has(key)) { seen.add(key); out.push(a); }
  }
  return out;
}

function formatActions(actions) {
  if (!actions || actions.length === 0) return '(no actions)';
  return actions.map(formatAction).join(', ');
}

function formatAction(a) {
  if (a == null) return 'null';
  if (typeof a === 'string') return a;
  if (typeof a !== 'object') return String(a);
  // Common action object patterns: {op: 'SET', path: 'X', value: 1}
  const keys = Object.keys(a);
  if (keys.length === 0) return '{}';
  // Provide concise summary
  const parts = [];
  for (const k of keys) {
    let v = a[k];
    if (typeof v === 'object' && v !== null) {
      v = JSON.stringify(v);
    }
    parts.push(`${k}=${v}`);
  }
  return `{${parts.join('; ')}}`;
}

function renderScreens(listEl, screens) {
  listEl.innerHTML = '';
  screens.forEach(s => {
    const li = el('li', `${s.name} — ${s.file}`);
    li.addEventListener('click', () => showScreen(s));
    listEl.appendChild(li);
  });
}

function showDetails(title, obj) {
  document.getElementById('detailsTitle').textContent = title;
  document.getElementById('detailsJson').textContent = JSON.stringify(obj, null, 2);
}

// Persistent preview state
let _currentGeometry = null;
let _previewSVG = null;
let _viewBox = null;
let _applyViewBox = () => {};
let _baseViewBox = null; // stores initial width/height to compute zoom factor

function rebuildLabels() {
  if (!_previewSVG || !_currentGeometry) return;
  // Remove existing label groups
  [..._previewSVG.querySelectorAll('g')].forEach(g => g.remove());
  const labelsEnabled = document.getElementById('toggleLabels').checked;
  if (!labelsEnabled) return;
  const svgRect = _previewSVG.getBoundingClientRect();
  const zoomFactor = (_baseViewBox && _viewBox) ? (_baseViewBox.w / _viewBox.w) : 1;
  _currentGeometry.items.forEach((it, idx) => {
    const base = it.label || it.type || `#${idx+1}`;
    const full = (it.group ? `${it.group}: ` : '') + base;
    addLabelToSVG(it, full, zoomFactor, svgRect);
  });
}

function addLabelToSVG(it, text, zoomFactor=1, svgRect=null) {
  if (!_previewSVG) return;
  const padding = 2;
  const x = it.x + 1, y = it.y + 1, w = it.w - 2; // safe defaults
  const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('class', 'label-bg');
  const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  t.setAttribute('class', 'label');
  // Adaptive font size: base 10px scaled up slightly when zoomed
  const fontSize = Math.min(16, 10 * Math.max(1, zoomFactor));
  t.setAttribute('font-size', String(fontSize));
  t.setAttribute('x', String(x + padding));
  t.setAttribute('y', String(y + fontSize + 2));
  t.textContent = text;
  g.appendChild(t);
  _previewSVG.appendChild(g); // attach to measure
  // Pixel-based allowable width: map instrument logical width to current pixel width
  let instrumentPixelWidth = w;
  if (svgRect && _viewBox) {
    instrumentPixelWidth = (w / _viewBox.w) * svgRect.width;
  }
  let tw = t.getBBox().width + padding * 2;
  if (tw > instrumentPixelWidth && instrumentPixelWidth > 25) {
    let s = text;
    // Truncate proportionally instead of char-by-char for speed, then refine
    const estRatio = instrumentPixelWidth / tw;
    const targetLen = Math.max(3, Math.floor(s.length * estRatio) - 1);
    s = s.slice(0, targetLen);
    t.textContent = s + '…';
    // Refine if still too wide
    while (s.length > 3 && t.getComputedTextLength() > (instrumentPixelWidth - padding * 2)) {
      s = s.slice(0, -1);
      t.textContent = s + '…';
    }
    tw = Math.min(instrumentPixelWidth, t.getBBox().width + padding * 2);
  }
  bg.setAttribute('x', String(x));
  bg.setAttribute('y', String(y));
  bg.setAttribute('width', String(Math.min(w, tw)));
  bg.setAttribute('height', String(fontSize + 4));
  g.insertBefore(bg, t);
  const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
  title.textContent = text;
  g.appendChild(title);
}

function renderPreview(containerEl, geometry) {
  _currentGeometry = geometry;
  containerEl.innerHTML = '';
  if (!geometry || !geometry.items || geometry.items.length === 0) {
    containerEl.textContent = 'No geometry available for this screen.';
    return;
  }
  const W = geometry.width || 1200;
  const H = geometry.height || 800;
  _viewBox = { x: 0, y: 0, w: W, h: H };
  _baseViewBox = { w: W, h: H };
  function applyViewBox() {
    if (_previewSVG) {
      _previewSVG.setAttribute('viewBox', `${_viewBox.x} ${_viewBox.y} ${_viewBox.w} ${_viewBox.h}`);
      // Recompute labels so truncation reflects current zoom level
      rebuildLabels();
    }
  }
  // Update global applyViewBox so control handlers act on current SVG
  _applyViewBox = applyViewBox;
  _previewSVG = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  _previewSVG.setAttribute('class', 'preview');
  applyViewBox();
  geometry.items.forEach((it, idx) => {
    const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    r.setAttribute('class', 'item');
    r.setAttribute('x', String(it.x));
    r.setAttribute('y', String(it.y));
    r.setAttribute('width', String(it.w));
    r.setAttribute('height', String(it.h));
      if (it.duplicates) {
        r.classList.add('dup');
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = `${it.duplicates} overlapping duplicate(s)`;
        r.appendChild(title);
      }
      if (it.adjusted) {
        r.classList.add('adjusted');
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = 'Adjusted to resolve overlap';
        r.appendChild(title);
      }
    r.addEventListener('click', () => showDetails('Instrument', it));
    _previewSVG.appendChild(r);
  });
  containerEl.appendChild(_previewSVG);
  // Interaction: wheel zoom & drag pan
  attachPanZoom(_previewSVG);
  rebuildLabels();
  wirePreviewControls();
}

function wirePreviewControls() {
  const fitBtn = document.getElementById('fitBtn');
  const labelsToggle = document.getElementById('toggleLabels');
  if (fitBtn && !fitBtn._wired) {
    fitBtn._wired = true;
    fitBtn.addEventListener('click', () => {
      if (!_currentGeometry) return;
      _viewBox = { x: 0, y: 0, w: _currentGeometry.width || 1200, h: _currentGeometry.height || 800 };
      _applyViewBox();
    });
  }
  if (labelsToggle && !labelsToggle._wired) {
    labelsToggle._wired = true;
    labelsToggle.addEventListener('change', rebuildLabels);
  }
  // Splitter drag
  const splitter = document.getElementById('splitter');
  const previewPane = document.getElementById('previewPane');
  const detailsPane = document.getElementById('detailsPane');
  if (splitter && !splitter._wired) {
    splitter._wired = true;
    let dragging = false;
    splitter.addEventListener('mousedown', (e) => {
      dragging = true;
      document.body.style.cursor = 'col-resize';
      e.preventDefault();
    });
    window.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      const total = previewPane.parentElement.getBoundingClientRect();
      const min = 150;
      let newWidth = e.clientX - total.left;
      if (newWidth < min) newWidth = min;
      if (newWidth > total.width - min) newWidth = total.width - min;
      previewPane.style.flex = '0 0 ' + newWidth + 'px';
      // Resize event: keep labels functional; viewBox stays the same (logical coords) so no change needed
    });
    window.addEventListener('mouseup', () => {
      if (dragging) {
        dragging = false;
        document.body.style.cursor = '';
      }
    });
  }
}

function attachPanZoom(svg) {
  if (!svg || svg._panZoomWired) return;
  svg._panZoomWired = true;
  let dragging = false;
  let startX = 0, startY = 0, vbStart = null;
  svg.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return; // left only
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    vbStart = { ..._viewBox };
    e.preventDefault();
  });
  window.addEventListener('mousemove', (e) => {
    if (!dragging || !vbStart) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    // Translate proportional to current viewBox scale vs element pixels
    const rect = svg.getBoundingClientRect();
    const scaleX = _viewBox.w / rect.width;
    const scaleY = _viewBox.h / rect.height;
    _viewBox.x = vbStart.x - dx * scaleX;
    _viewBox.y = vbStart.y - dy * scaleY;
    _applyViewBox();
  });
  window.addEventListener('mouseup', () => { dragging = false; });
  svg.addEventListener('wheel', (e) => {
    if (!_viewBox) return;
    e.preventDefault();
    const rect = svg.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width; // 0..1
    const py = (e.clientY - rect.top) / rect.height; // 0..1
    const factor = e.deltaY < 0 ? 0.85 : 1.18; // zoom in vs out
    const newW = _viewBox.w * factor;
    const newH = _viewBox.h * factor;
    // Keep point under cursor stable
    const cx = _viewBox.x + _viewBox.w * px;
    const cy = _viewBox.y + _viewBox.h * py;
    _viewBox.x = cx - newW * px;
    _viewBox.y = cy - newH * py;
    _viewBox.w = newW;
    _viewBox.h = newH;
    _applyViewBox();
  }, { passive: false });
}

function showScreen(s) {
  const title = `Screen: ${s.name}`;
  document.getElementById('detailsTitle').textContent = title;
  // Prefer showing expanded body JSON for now
  document.getElementById('detailsJson').textContent = JSON.stringify(s.expanded, null, 2);
  const geometry = s.geometry || (s.expanded && s.expanded.geometry);
  const container = document.getElementById('preview');
  renderPreview(container, geometry);
}

async function boot() {
  let data;
  const fileInput = document.getElementById('fileInput');
  // Activate splitter and preview controls early (before a screen is clicked)
  // Provide a no-op applyViewBox; real geometry wiring occurs on first renderPreview call.
  wirePreviewControls();
  fileInput.addEventListener('change', async (ev) => {
    const f = ev.target.files && ev.target.files[0];
    if (!f) return;
    try {
      data = await loadJSONFromFile(f);
      renderScreens(document.getElementById('screens'), data.screens || []);
      renderIncludes(document.getElementById('includes'), data.includes || []);
  renderPreferences(document.getElementById('preferences'), data.preferences || {});
  renderButtons(document.getElementById('buttons'), data.buttons || []);
      showDetails('Meta', data.meta || {});
    } catch (e) {
      showDetails('Error', { message: String(e) });
    }
  });
  showDetails('Instructions', {
    message: 'Use the file picker to open a normalized_config.json produced by config_normalizer.py',
    tip: 'Run: python3 tools/config_normalizer.py --config config/default.yaml --out tools/cfg_explorer/normalized_config.json'
  });
}

boot();
