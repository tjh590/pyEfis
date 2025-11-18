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

function rebuildLabels() {
  if (!_previewSVG || !_currentGeometry) return;
  // Remove existing label groups
  [..._previewSVG.querySelectorAll('g')].forEach(g => g.remove());
  const labelsEnabled = document.getElementById('toggleLabels').checked;
  if (!labelsEnabled) return;
  _currentGeometry.items.forEach((it, idx) => {
    const full = (it.group ? `${it.group}: ` : '') + (it.type || `#${idx+1}`);
    addLabelToSVG(it, full);
  });
}

function addLabelToSVG(it, text) {
  if (!_previewSVG) return;
  const padding = 2;
  const x = it.x + 1, y = it.y + 1, w = it.w - 2; // safe defaults
  const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('class', 'label-bg');
  const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  t.setAttribute('class', 'label');
  t.setAttribute('x', String(x + padding));
  t.setAttribute('y', String(y + 12));
  t.textContent = text;
  g.appendChild(t);
  _previewSVG.appendChild(g); // attach to measure
  let tw = t.getBBox().width + padding * 2;
  if (tw > w && w > 20) {
    let s = text;
    while (s.length > 3 && t.getComputedTextLength() > (w - padding * 2)) {
      s = s.slice(0, -1);
      t.textContent = s + '…';
    }
    tw = t.getBBox().width + padding * 2;
  }
  bg.setAttribute('x', String(x));
  bg.setAttribute('y', String(y));
  bg.setAttribute('width', String(Math.min(w, tw)));
  bg.setAttribute('height', String(14));
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
  function applyViewBox() {
    if (_previewSVG) {
      _previewSVG.setAttribute('viewBox', `${_viewBox.x} ${_viewBox.y} ${_viewBox.w} ${_viewBox.h}`);
    }
  }
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
  rebuildLabels();
  wirePreviewControls(applyViewBox);
}

function wirePreviewControls(applyViewBox) {
  const fitBtn = document.getElementById('fitBtn');
  const zoomInBtn = document.getElementById('zoomInBtn');
  const zoomOutBtn = document.getElementById('zoomOutBtn');
  const labelsToggle = document.getElementById('toggleLabels');
  if (fitBtn && !fitBtn._wired) {
    fitBtn._wired = true;
    fitBtn.addEventListener('click', () => {
      if (!_currentGeometry) return;
      _viewBox = { x: 0, y: 0, w: _currentGeometry.width || 1200, h: _currentGeometry.height || 800 };
      applyViewBox();
    });
  }
  function zoom(factor) {
    if (!_viewBox) return;
    const cx = _viewBox.x + _viewBox.w / 2;
    const cy = _viewBox.y + _viewBox.h / 2;
    const nw = _viewBox.w * factor;
    const nh = _viewBox.h * factor;
    _viewBox = { x: cx - nw / 2, y: cy - nh / 2, w: nw, h: nh };
    applyViewBox();
  }
  if (zoomInBtn && !zoomInBtn._wired) {
    zoomInBtn._wired = true;
    zoomInBtn.addEventListener('click', () => zoom(0.8));
  }
  if (zoomOutBtn && !zoomOutBtn._wired) {
    zoomOutBtn._wired = true;
    zoomOutBtn.addEventListener('click', () => zoom(1.25));
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
  const pathInput = document.getElementById('jsonPath');
  const loadBtn = document.getElementById('loadBtn');
  const fileInput = document.getElementById('fileInput');
  async function doLoad() {
    try {
      data = await loadJSONViaUrl(pathInput.value.trim());
      renderScreens(document.getElementById('screens'), data.screens || []);
      renderIncludes(document.getElementById('includes'), data.includes || []);
  renderPreferences(document.getElementById('preferences'), data.preferences || {});
      showDetails('Meta', data.meta || {});
    } catch (e) {
      const hint = location.protocol === 'file:'
        ? 'Hint: Browser blocked fetch over file://. Use the file picker or run a local server.'
        : '';
      showDetails('Error', { message: String(e), hint });
    }
  }
  loadBtn.addEventListener('click', doLoad);
  fileInput.addEventListener('change', async (ev) => {
    const f = ev.target.files && ev.target.files[0];
    if (!f) return;
    try {
      data = await loadJSONFromFile(f);
      renderScreens(document.getElementById('screens'), data.screens || []);
      renderIncludes(document.getElementById('includes'), data.includes || []);
  renderPreferences(document.getElementById('preferences'), data.preferences || {});
      showDetails('Meta', data.meta || {});
    } catch (e) {
      showDetails('Error', { message: String(e) });
    }
  });
  doLoad();
}

boot();
