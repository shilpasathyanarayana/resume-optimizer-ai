/**
 * optimize.js  —  ResumeAI optimizer page logic
 * Requires script.js to be loaded first.
 */

// ── STATE ─────────────────────────────────────────────────────────
let currentResults = null;

// ── INIT ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Auth guard — must be logged in
  const token = localStorage.getItem('authToken');
  if (!token) {
    window.location.href = 'index.html?action=login';
    return;
  }

  syncUsage();
  showPanel('input');
  updateStepBar(1);
});

// ── USAGE (from backend) ───────────────────────────────────────────
async function syncUsage() {
  const token = localStorage.getItem('authToken');
  if (!token) return;

  try {
    const res = await fetch('/api/resume/usage', {
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
    updateUsageBanner(data.uses_remaining, data.limit);
  } catch (e) { /* silently fail */ }
}

function updateUsageBanner(remaining, limit) {
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

// ── FILE UPLOAD ───────────────────────────────────────────────────
function handleDragOver(e, zoneId) {
  e.preventDefault();
  const zone = document.getElementById(zoneId);
  if (zone) zone.classList.add('dragover');
}

function handleDragLeave(e, zoneId) {
  const zone = document.getElementById(zoneId);
  if (zone) zone.classList.remove('dragover');
}

function handleDrop(e, type) {
  e.preventDefault();
  const zone = document.getElementById('resumeUploadZone');
  if (zone) zone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) processFile(file);
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) processFile(file);
}

function processFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();

  if (!['pdf', 'docx', 'doc'].includes(ext)) {
    showToast('Only PDF or DOCX files are supported.', 'error');
    return;
  }

  if (file.size > 5 * 1024 * 1024) {
    showToast('File must be under 5MB.', 'error');
    return;
  }

  const zone = document.getElementById('resumeUploadZone');
  if (zone) {
    zone.classList.add('has-file');
    zone.innerHTML = `
      <div class="upload-filename">📎 ${file.name}</div>
      <div class="upload-formats" style="margin-top:4px;">Click to change file</div>
    `;
  }

  window._resumeFile = file;

  const resumeTextEl = document.getElementById('resumeText');
  if (resumeTextEl) {
    resumeTextEl.value = '';
    resumeTextEl.placeholder = `"${file.name}" will be extracted by the server when you click Optimize.`;
    updateCharCount('resumeText', 'resumeCount');
  }

  showToast(`"${file.name}" ready`, 'success');
}

// ── CHAR COUNT ────────────────────────────────────────────────────
function updateCharCount(textareaId, countId) {
  const textarea = document.getElementById(textareaId);
  const counter = document.getElementById(countId);
  if (textarea && counter) {
    counter.textContent = `${textarea.value.length.toLocaleString()} characters`;
  }
}

// ── VALIDATE ──────────────────────────────────────────────────────
function validateInputs() {
  const resumeText = (document.getElementById('resumeText')?.value || '').trim();
  const jobText = (document.getElementById('jobText')?.value || '').trim();

  if (!resumeText && !window._resumeFile) {
    showToast('Please upload or paste your resume.', 'error');
    return false;
  }
  if (!window._resumeFile && resumeText.length < 50) {
    showToast('Resume text seems too short.', 'error');
    return false;
  }
  if (!jobText) {
    showToast('Please paste the job description.', 'error');
    return false;
  }
  if (jobText.length < 50) {
    showToast('Job description seems too short.', 'error');
    return false;
  }
  return true;
}

// ── OPTIMIZE ──────────────────────────────────────────────────────
async function startOptimize() {
  const token = localStorage.getItem('authToken');
  if (!token) {
    window.location.href = 'index.html?action=login';
    return;
  }

  if (!validateInputs()) return;

  showPanel('processing');
  updateStepBar(2);
  await animateProgressSteps();
}

async function animateProgressSteps() {
  const steps = [
    { id: 'pStep1', statusId: 'pStep1Status', duration: 1500 },
    { id: 'pStep2', statusId: 'pStep2Status', duration: 2000 },
    { id: 'pStep3', statusId: 'pStep3Status', duration: 1500 },
    { id: 'pStep4', statusId: 'pStep4Status', duration: 0 },
  ];

  // Start API call immediately in parallel
  const apiPromise = callOptimizeAPI();

  // Animate first 3 steps with delays
  for (let i = 0; i < steps.length - 1; i++) {
    const step = steps[i];
    setStepState(step.id, 'active', step.statusId, 'In progress...');
    await delay(step.duration);
    setStepState(step.id, 'done', step.statusId, 'Done ✓');
  }

  // Final step — wait for actual API result
  setStepState('pStep4', 'active', 'pStep4Status', 'Rewriting with AI...');
  try {
    const result = await apiPromise;
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
  if (el) { el.classList.remove('active', 'done'); if (state) el.classList.add(state); }
  const statusEl = document.getElementById(statusId);
  if (statusEl) statusEl.textContent = statusText;
}

// ── API CALL ──────────────────────────────────────────────────────
async function callOptimizeAPI() {
  const token = localStorage.getItem('authToken');
  if (!token) throw new Error('Please log in to continue.');

  const authHeader = { 'Authorization': `Bearer ${token}` };
  const jobText = document.getElementById('jobText').value.trim();
  const resumeText = document.getElementById('resumeText').value.trim();

  // PDF/DOCX file upload
  if (window._resumeFile) {
    const formData = new FormData();
    formData.append('resume_file', window._resumeFile);
    formData.append('job_description', jobText);

    const res = await fetch('/api/resume/upload', {
      method: 'POST',
      headers: authHeader,
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      if (res.status === 401) { window.location.href = 'index.html?action=login'; throw new Error('Session expired.'); }
      if (res.status === 429) throw new Error(err.detail || 'Monthly limit reached. Upgrade to Pro for unlimited access.');
      throw new Error(err.detail || `Server error (${res.status}).`);
    }

    const data = await res.json();
    // Update usage banner after successful call
    if (data.uses_remaining !== undefined) updateUsageBanner(data.uses_remaining, 5);
    return data;
  }

  // Text-based submission
  const res = await fetch('/api/resume/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader },
    body: JSON.stringify({ resume_text: resumeText, job_description: jobText })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    if (res.status === 401) { window.location.href = 'index.html?action=login'; throw new Error('Session expired.'); }
    if (res.status === 429) throw new Error(err.detail || 'Monthly limit reached. Upgrade to Pro for unlimited access.');
    throw new Error(err.detail || `Server error (${res.status}).`);
  }

  const data = await res.json();
  if (data.uses_remaining !== undefined) updateUsageBanner(data.uses_remaining, 5);
  return data;
}

// ── RESULTS ───────────────────────────────────────────────────────
function showResults(data) {
  currentResults = data;

  // ATS score
  const score = data.ats_score || 0;
  const scoreEl = document.getElementById('atsScore');
  if (scoreEl) {
    scoreEl.textContent = score;
    scoreEl.className = 'ats-number ' + (score >= 75 ? 'high' : score >= 50 ? 'mid' : 'low');
  }

  // Missing keywords
  const keywords = data.missing_keywords || [];
  const keywordsPanel = document.getElementById('keywordsPanel');
  const keywordsList = document.getElementById('keywordsList');
  if (keywordsPanel && keywordsList) {
    if (keywords.length > 0) {
      keywordsList.innerHTML = keywords.map(k => `<span class="keyword-tag">⚠ ${k}</span>`).join('');
      keywordsPanel.style.display = 'block';
    } else {
      keywordsPanel.style.display = 'none';
    }
  }

  // Improvements
  const improvements = data.improvements || [];
  const improvementsPanel = document.getElementById('improvementsPanel');
  const improvementsList = document.getElementById('improvementsList');
  if (improvementsPanel && improvementsList) {
    if (improvements.length > 0) {
      improvementsList.innerHTML = improvements.map(i => `<div class="improvement-item">${i}</div>`).join('');
      improvementsPanel.style.display = 'block';
    } else {
      improvementsPanel.style.display = 'none';
    }
  }

  // Original vs Optimized
  const resumeTextEl = document.getElementById('resumeText');
  const originalContent = document.getElementById('originalContent');
  const optimizedContent = document.getElementById('optimizedContent');
  if (originalContent) originalContent.textContent = resumeTextEl?.value.trim() || '[Extracted from uploaded file]';
  if (optimizedContent) optimizedContent.textContent = data.optimized_text || '';

  showPanel('results');
  updateStepBar(3);
}

// ── DOWNLOAD ──────────────────────────────────────────────────────
function downloadTxt() {
  if (!currentResults) return;
  const text = currentResults.optimized_text || '';
  const blob = new Blob([text], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'optimized-resume.txt';
  a.click();
  URL.revokeObjectURL(url);
  showToast('TXT downloaded!', 'success');
}

async function downloadDocx() {
  if (!currentResults) return;
  downloadTxt(); // fallback until DOCX endpoint is ready
}

// ── COPY ──────────────────────────────────────────────────────────
function copyText(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(() => {
    showToast('Copied to clipboard!', 'success');
  }).catch(() => {
    showToast('Copy failed — please select and copy manually.', 'error');
  });
}

// ── PANEL SWITCHING ───────────────────────────────────────────────
function showPanel(panel) {
  ['inputPanel', 'processingPanel', 'resultsPanel'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = id === `${panel}Panel` ? 'block' : 'none';
  });
}

function updateStepBar(activeStep) {
  for (let i = 1; i <= 3; i++) {
    const el = document.getElementById(`step${i}`);
    if (!el) continue;
    el.classList.remove('active', 'done');
    if (i < activeStep) el.classList.add('done');
    else if (i === activeStep) el.classList.add('active');
  }
}

// ── RESET ─────────────────────────────────────────────────────────
function resetPage() {
  currentResults = null;
  window._resumeFile = null;

  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`pStep${i}`);
    const statusEl = document.getElementById(`pStep${i}Status`);
    if (el) el.classList.remove('active', 'done');
    if (statusEl) statusEl.textContent = 'Waiting';
  }

  const zone = document.getElementById('resumeUploadZone');
  if (zone) {
    zone.classList.remove('has-file');
    zone.innerHTML = `
      <div class="upload-icon">📎</div>
      <div class="upload-text"><strong>Click to upload</strong> or drag & drop</div>
      <div class="upload-formats">PDF or DOCX · Max 5MB</div>
    `;
    zone.onclick = () => document.getElementById('resumeFile')?.click();
  }

  const resumeTextEl = document.getElementById('resumeText');
  const jobTextEl = document.getElementById('jobText');
  if (resumeTextEl) { resumeTextEl.value = ''; resumeTextEl.placeholder = 'Paste your resume text here...'; }
  if (jobTextEl) jobTextEl.value = '';

  updateCharCount('resumeText', 'resumeCount');
  updateCharCount('jobText', 'jobCount');
  syncUsage();

  showPanel('input');
  updateStepBar(1);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── UTILS ─────────────────────────────────────────────────────────
function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
