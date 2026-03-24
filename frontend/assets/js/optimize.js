const API_BASE = '/api';
let currentResults = null;

// ── INIT ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const token = localStorage.getItem('authToken');
  if (!token) {
    window.location.href = 'index.html?action=login';
    return;
  }

  // If ?id= is in the URL, load that history record and skip to results
  const loadedFromHistory = await maybeLoadFromHistory();
  if (!loadedFromHistory) {
    // Normal new-optimisation flow
    syncUsage();
  }
});

// ── HISTORY PREFILL ────────────────────────────────────────────────
async function maybeLoadFromHistory() {
  const params   = new URLSearchParams(window.location.search);
  const resumeId = params.get('id');
  if (!resumeId) return false;

  const token = localStorage.getItem('authToken');
  if (!token) return false;

  try {
    const res = await fetch(`${API_BASE}/resume/history/${resumeId}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!res.ok) {
      console.warn(`History record ${resumeId} not found (${res.status})`);
      return false;
    }

    const data = await res.json();

    // Pre-fill inputs so "Start over" restores them
    if (data.original_text) {
      const ta = document.getElementById('resumeText');
      if (ta) { ta.value = data.original_text; updateCharCount('resumeText', 'resumeCount'); }
    }
    if (data.job_description) {
      const jd = document.getElementById('jobText');
      if (jd) { jd.value = data.job_description; updateCharCount('jobText', 'jobCount'); }
    }

    // Build result object matching showResults() expectations
    const synthetic = {
      ats_score:        data.ats_score        ?? 0,
      missing_keywords: data.missing_keywords ?? [],
      improvements:     data.improvements     ?? [],
      optimized_text:   data.optimized_text   ?? '',
      uses_remaining:   undefined,
      uses_this_month:  undefined,
    };

    updateStepBar(3);
    showResults(synthetic);
    showHistoryBanner(data);
    return true;

  } catch (err) {
    console.warn('Could not load history record:', err);
    return false;
  }
}

function showHistoryBanner(data) {
  const resultsPanel = document.getElementById('resultsPanel');
  if (!resultsPanel || document.getElementById('historyBanner')) return;

  const date     = data.created_at
    ? new Date(data.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : '';
  const filename = data.original_filename || 'Resume';
  const jobTitle = data.job_title         || 'this role';

  const banner = document.createElement('div');
  banner.id = 'historyBanner';
  banner.style.cssText = `
    display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;
    background:#e8f5ef; border:1px solid #b2dfc7; border-radius:12px;
    padding:12px 18px; margin-bottom:20px; font-size:0.85rem; color:#1a7a4a;
  `;
  banner.innerHTML = `
    <span>
      📂 <strong>Viewing saved result</strong> —
      ${escHtml(filename)} optimised for <em>${escHtml(jobTitle)}</em>${date ? ` on ${date}` : ''}
    </span>
    <a href="optimize.html"
       style="color:#1a7a4a;font-weight:600;text-decoration:none;white-space:nowrap;">
      + New optimisation →
    </a>
  `;
  resultsPanel.insertBefore(banner, resultsPanel.firstChild);
}

// ── USAGE (from backend) ───────────────────────────────────────────
async function syncUsage() {
  const token = localStorage.getItem('authToken');
  if (!token) return;
  try {
    const res = await fetch(`${API_BASE}/resume/usage`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.status === 401) {
      localStorage.removeItem('authToken');
      localStorage.removeItem('userData');
      window.location.href = 'index.html?action=login';
      return;
    }
    if (!res.ok) return;
    const data = await res.json();
    updateUsageUI(data.uses_remaining, data.limit, data.uses_this_month);
  } catch (e) { /* silently fail */ }
}

function updateUsageUI(remaining, limit, used) {
  const freeText = document.getElementById('freeText');
  if (!freeText) return;
  if (remaining <= 0) {
    freeText.innerHTML = '<span style="color:var(--danger)">No optimizations left this month — <a href="pricing.html" style="color:var(--accent)">upgrade to Pro</a></span>';
    const btn = document.getElementById('optimizeBtn');
    if (btn) btn.disabled = true;
  } else {
    freeText.textContent = `${remaining} of ${limit} optimizations remaining this month`;
  }
}

// ── FILE UPLOAD ────────────────────────────────────────────────────
function handleDragOver(e, zoneId) { e.preventDefault(); document.getElementById(zoneId).classList.add('dragover'); }
function handleDragLeave(e, zoneId) { document.getElementById(zoneId).classList.remove('dragover'); }
function handleDrop(e, type) {
  e.preventDefault();
  document.getElementById('resumeUploadZone').classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) processFile(file);
}
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) processFile(file);
}

function processFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'docx', 'doc'].includes(ext)) { showToast('Only PDF or DOCX files are supported.', 'error'); return; }
  if (file.size > 5 * 1024 * 1024) { showToast('File must be under 5MB.', 'error'); return; }

  const zone = document.getElementById('resumeUploadZone');
  zone.classList.add('has-file');
  zone.innerHTML = `<div class="upload-filename">📎 ${file.name}</div><div class="upload-formats" style="margin-top:4px;">Click to change file</div>`;

  if (ext === 'pdf') {
    window._resumeFile = file;
    document.getElementById('resumeText').value = '';
    document.getElementById('resumeText').placeholder = `"${file.name}" will be extracted by the server when you click Optimize.`;
    updateCharCount('resumeText', 'resumeCount');
    showToast(`"${file.name}" ready — text will be extracted automatically`, 'success');
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    const cleaned = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    if (cleaned.length > 50) {
      document.getElementById('resumeText').value = cleaned;
      updateCharCount('resumeText', 'resumeCount');
      showToast(`"${file.name}" loaded`, 'success');
    } else {
      window._resumeFile = file;
      document.getElementById('resumeText').placeholder = `"${file.name}" will be extracted by the server when you click Optimize.`;
      showToast(`"${file.name}" ready`, 'success');
    }
  };
  reader.onerror = () => showToast('Could not read file. Please paste your resume text instead.', 'error');
  reader.readAsText(file);
  window._resumeFile = file;
}

function updateCharCount(textareaId, countId) {
  const len = document.getElementById(textareaId).value.length;
  document.getElementById(countId).textContent = `${len.toLocaleString()} characters`;
}

// ── VALIDATE ───────────────────────────────────────────────────────
function validateInputs() {
  const resumeText = document.getElementById('resumeText').value.trim();
  const jobText    = document.getElementById('jobText').value.trim();

  if (!resumeText && !window._resumeFile) {
    showToast('Please upload or paste your resume.', 'error'); return false;
  }
  if (!window._resumeFile && resumeText.length < 50) {
    showToast('Resume text seems too short.', 'error'); return false;
  }
  if (!jobText) { showToast('Please paste the job description.', 'error'); return false; }
  if (jobText.length < 50) { showToast('Job description seems too short.', 'error'); return false; }
  return true;
}

// ── OPTIMIZE ───────────────────────────────────────────────────────
async function startOptimize() {
  if (!validateInputs()) return;
  showPanel('processing');
  updateStepBar(2);
  await runOptimization();
}

async function runOptimization() {
  setStepState('pStep1', 'active', 'pStep1Status', 'In progress...');
  await delay(1500);
  setStepState('pStep1', 'done', 'pStep1Status', 'Done ✓');

  setStepState('pStep2', 'active', 'pStep2Status', 'In progress...');
  await delay(2000);
  setStepState('pStep2', 'done', 'pStep2Status', 'Done ✓');

  setStepState('pStep3', 'active', 'pStep3Status', 'In progress...');
  await delay(1500);
  setStepState('pStep3', 'done', 'pStep3Status', 'Done ✓');

  setStepState('pStep4', 'active', 'pStep4Status', 'Rewriting with AI...');

  try {
    const result = await callAI();
    setStepState('pStep4', 'done', 'pStep4Status', 'Done ✓');
    await delay(500);
    showResults(result);
  } catch (err) {
    showPanel('input');
    updateStepBar(1);
    showToast(err.message || 'Something went wrong. Please try again.', 'error');
  }
}

function setStepState(stepId, state, statusId, statusText) {
  const el = document.getElementById(stepId);
  el.classList.remove('active', 'done');
  if (state) el.classList.add(state);
  document.getElementById(statusId).textContent = statusText;
}

async function callAI() {
  const resumeText = document.getElementById('resumeText').value.trim();
  const jobText    = document.getElementById('jobText').value.trim();
  const token      = localStorage.getItem('authToken');

  if (!token) {
    window.location.href = 'index.html?action=login';
    throw new Error('Please log in to continue.');
  }

  const authHeader = { 'Authorization': `Bearer ${token}` };

  // PDF upload — send as FormData
  if (window._resumeFile && window._resumeFile.name.toLowerCase().endsWith('.pdf')) {
    const formData = new FormData();
    formData.append('resume_file', window._resumeFile);
    formData.append('job_description', jobText);

    const res = await fetch(`${API_BASE}/resume/upload`, {
      method: 'POST',
      headers: authHeader,
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      if (res.status === 401) { window.location.href = 'index.html?action=login'; throw new Error('Session expired. Please log in again.'); }
      if (res.status === 429) throw new Error(err.detail || 'Monthly limit reached. Upgrade to Pro for unlimited access.');
      throw new Error(err.detail || `Server error (${res.status}). Please try again.`);
    }
    return await res.json();
  }

  // Text-based submission
  const res = await fetch(`${API_BASE}/resume/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader },
    body: JSON.stringify({ resume_text: resumeText, job_description: jobText })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    if (res.status === 401) { window.location.href = 'index.html?action=login'; throw new Error('Session expired. Please log in again.'); }
    if (res.status === 429) throw new Error(err.detail || 'Monthly limit reached. Upgrade to Pro for unlimited access.');
    throw new Error(err.detail || `Server error (${res.status}). Please try again.`);
  }

  return await res.json();
}

// ── RESULTS ────────────────────────────────────────────────────────
function showResults(data) {
  currentResults = data;

  if (data.uses_remaining !== undefined) {
    updateUsageUI(data.uses_remaining, 5, data.uses_this_month);
  }

  const score   = data.ats_score || 0;
  const scoreEl = document.getElementById('atsScore');
  scoreEl.textContent = score;
  scoreEl.className   = 'ats-number ' + (score >= 75 ? 'high' : score >= 50 ? 'mid' : 'low');

  const keywords = data.missing_keywords || [];
  if (keywords.length > 0) {
    document.getElementById('keywordsList').innerHTML =
      keywords.map(k => `<span class="keyword-tag">⚠ ${k}</span>`).join('');
    document.getElementById('keywordsPanel').style.display = 'block';
  }

  const improvements = data.improvements || [];
  if (improvements.length > 0) {
    document.getElementById('improvementsList').innerHTML =
      improvements.map(i => `<div class="improvement-item">${i}</div>`).join('');
    document.getElementById('improvementsPanel').style.display = 'block';
  }

  document.getElementById('originalContent').textContent =
    document.getElementById('resumeText').value.trim() || '[Extracted from uploaded file]';
  document.getElementById('optimizedContent').textContent = data.optimized_text || '';

  showPanel('results');
  updateStepBar(3);
}

// ── DOWNLOAD & COPY ────────────────────────────────────────────────
function downloadTxt() {
  if (!currentResults) return;
  const blob = new Blob([currentResults.optimized_text || ''], { type: 'text/plain' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'optimized-resume.txt'; a.click();
  URL.revokeObjectURL(url);
  showToast('Downloaded!', 'success');
}

function copyText(elementId) {
  navigator.clipboard.writeText(document.getElementById(elementId).textContent)
    .then(() => showToast('Copied!', 'success'))
    .catch(() => showToast('Copy failed.', 'error'));
}

// ── PANEL UTILS ────────────────────────────────────────────────────
function showPanel(panel) {
  document.getElementById('inputPanel').style.display      = panel === 'input'      ? 'block' : 'none';
  document.getElementById('processingPanel').style.display = panel === 'processing' ? 'block' : 'none';
  document.getElementById('resultsPanel').style.display    = panel === 'results'    ? 'block' : 'none';
}

function updateStepBar(activeStep) {
  for (let i = 1; i <= 3; i++) {
    const el = document.getElementById(`step${i}`);
    el.classList.remove('active', 'done');
    if (i < activeStep) el.classList.add('done');
    else if (i === activeStep) el.classList.add('active');
  }
}

function resetPage() {
  // Remove history banner if present
  const banner = document.getElementById('historyBanner');
  if (banner) banner.remove();

  // Clear URL param without reload
  window.history.replaceState({}, '', 'optimize.html');

  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`pStep${i}`);
    if (el) { el.className = 'progress-step'; document.getElementById(`pStep${i}Status`).textContent = 'Waiting'; }
  }
  currentResults     = null;
  window._resumeFile = null;

  const zone = document.getElementById('resumeUploadZone');
  zone.classList.remove('has-file');
  zone.innerHTML = `<div class="upload-icon">📎</div><div class="upload-text"><strong>Click to upload</strong> or drag & drop</div><div class="upload-formats">PDF or DOCX · Max 5MB</div>`;
  zone.onclick = () => document.getElementById('resumeFile').click();

  document.getElementById('resumeText').value = '';
  document.getElementById('jobText').value    = '';
  updateCharCount('resumeText', 'resumeCount');
  updateCharCount('jobText',    'jobCount');
  document.getElementById('keywordsPanel').style.display    = 'none';
  document.getElementById('improvementsPanel').style.display = 'none';

  showPanel('input');
  updateStepBar(1);
  syncUsage();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── GUEST SESSION ──────────────────────────────────────────────────
function getOrCreateGuestSession() {
  let id = localStorage.getItem('guestSessionId');
  if (!id) { id = 'guest_' + Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem('guestSessionId', id); }
  return id;
}

// ── UTILS ──────────────────────────────────────────────────────────
function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

let toastTimer;
function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className   = 'toast ' + type;
  clearTimeout(toastTimer);
  requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add('show')));
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3200);
}