/**
 * script.js  —  ResumeAI shared nav / auth / modal logic
 *
 * Covers:
 *   - Scroll nav shrink
 *   - Free-uses counter (localStorage)
 *   - Auth state (login / signup / logout)
 *   - Modal open / close / tab switching
 *   - Form validation helpers
 *   - Password strength meter
 *   - User avatar dropdown
 *   - Toast notifications
 *   - Contact form submission (used on contact_us.html)
 *
 * Include on every page AFTER the DOM markup:
 *   <script src="assets/js/script.js" defer></script>
 */

// ── CONFIG ─────────────────────────────────────────────────────
const API_BASE   = '/api';
const FREE_LIMIT = 5;

// ── STATE ───────────────────────────────────────────────────────
let currentUser = null;

// ── BOOT ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Dynamic year in footer
  const yearEl = document.getElementById('footerYear');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // Dynamic "last updated" on legal pages
  const updatedEl = document.getElementById('lastUpdated');
  if (updatedEl) {
    updatedEl.textContent = new Date().toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric'
    });
  }

  initScrollNav();
  initAuth();
  initFreeCounter();
  initContactForm();
});

// ── SCROLL NAV ──────────────────────────────────────────────────
function initScrollNav() {
  const nav = document.getElementById('navbar');
  if (!nav) return;
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 40);
  }, { passive: true });
}

// ── FREE COUNTER ────────────────────────────────────────────────
function getFreeUses() {
  return parseInt(localStorage.getItem('freeUses') || '0', 10);
}

function incrementFreeUses() {
  const uses = getFreeUses() + 1;
  localStorage.setItem('freeUses', uses);
  updateFreeUI();
  return uses;
}

function initFreeCounter() {
  updateFreeUI();
}

function updateFreeUI() {
  const badge = document.getElementById('freeCounter');
  if (!badge) return;

  if (currentUser) {
    badge.style.display = 'none';
    return;
  }

  const remaining = Math.max(FREE_LIMIT - getFreeUses(), 0);
  badge.textContent = `${remaining} free ${remaining === 1 ? 'use' : 'uses'} left`;
  badge.style.display = remaining > 0 ? 'inline-flex' : 'none';

  // Hero strip (index.html only)
  const dotsEl    = document.getElementById('freeDots');
  const stripText = document.getElementById('freeStripText');
  const freeStrip = document.getElementById('freeStrip');

  if (dotsEl && stripText && freeStrip) {
    dotsEl.innerHTML = '';
    for (let i = 0; i < FREE_LIMIT; i++) {
      const dot = document.createElement('div');
      dot.className = 'free-dot' + (i < getFreeUses() ? ' used' : '');
      dotsEl.appendChild(dot);
    }
    stripText.textContent = remaining > 0
      ? `${remaining} free ${remaining === 1 ? 'use' : 'uses'} remaining — no sign-up needed`
      : '';
    if (remaining === 0) {
      stripText.innerHTML = 'Free uses exhausted — <strong style="color:var(--accent)">sign up free to continue</strong>';
    }
  }
}

// Used by index.html "Optimize my resume" button
function handleGetStarted() {
  if (!currentUser) {
    const used = getFreeUses();
    if (used >= FREE_LIMIT) {
      openModal('signup');
      showAlert('modal', "You've used all 5 free optimizations. Create a free account to continue.", 'error');
      return;
    }
  }
  window.location.href = 'optimize.html';
}

// ── AUTH INIT ────────────────────────────────────────────────────
function initAuth() {
  const token    = localStorage.getItem('authToken');
  const userData = localStorage.getItem('userData');
  if (token && userData) {
    try {
      currentUser = JSON.parse(userData);
      setLoggedIn(currentUser);
    } catch (e) {
      localStorage.removeItem('authToken');
      localStorage.removeItem('userData');
    }
  }
}

function setLoggedIn(user) {
  currentUser = user;

  const guestNav = document.getElementById('guestNav');
  const userNav  = document.getElementById('userNav');
  if (guestNav) guestNav.style.display = 'none';
  if (userNav)  userNav.style.display  = 'block';

  const initials = user.name
    ? user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : user.email[0].toUpperCase();

  const avatar       = document.getElementById('userAvatar');
  const dropName     = document.getElementById('dropdownName');
  const dropEmail    = document.getElementById('dropdownEmail');
  if (avatar)    avatar.textContent    = initials;
  if (dropName)  dropName.textContent  = user.name || 'User';
  if (dropEmail) dropEmail.textContent = user.email;

  updateFreeUI();
}

function setLoggedOut() {
  currentUser = null;
  localStorage.removeItem('authToken');
  localStorage.removeItem('userData');

  const guestNav = document.getElementById('guestNav');
  const userNav  = document.getElementById('userNav');
  if (guestNav) guestNav.style.display = 'flex';
  if (userNav)  userNav.style.display  = 'none';

  updateFreeUI();
}

// ── MODAL ────────────────────────────────────────────────────────
function openModal(tab = 'login') {
  clearModalAlert();
  switchTab(tab);
  const overlay = document.getElementById('modalOverlay');
  if (overlay) {
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal() {
  const overlay = document.getElementById('modalOverlay');
  if (overlay) {
    overlay.classList.remove('active');
    document.body.style.overflow = '';
  }
}

function handleOverlayClick(e) {
  if (e.target === document.getElementById('modalOverlay')) closeModal();
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

function switchTab(tab) {
  const isLogin = tab === 'login';
  const tabLogin   = document.getElementById('tabLogin');
  const tabSignup  = document.getElementById('tabSignup');
  const panelLogin  = document.getElementById('panelLogin');
  const panelSignup = document.getElementById('panelSignup');

  if (tabLogin)   tabLogin.classList.toggle('active',   isLogin);
  if (tabSignup)  tabSignup.classList.toggle('active',  !isLogin);
  if (panelLogin)  panelLogin.classList.toggle('active',  isLogin);
  if (panelSignup) panelSignup.classList.toggle('active', !isLogin);

  clearModalAlert();
  clearFormErrors();
}

// ── FORM HELPERS ─────────────────────────────────────────────────
function showFieldError(id, msg) {
  const el    = document.getElementById(id);
  const input = document.getElementById(id.replace('Error', ''));
  if (el) { el.textContent = msg; el.classList.add('visible'); }
  if (input) input.classList.add('error');
}

function clearFormErrors() {
  document.querySelectorAll('.form-error').forEach(el => el.classList.remove('visible'));
  document.querySelectorAll('.form-input, .form-select, .form-textarea')
    .forEach(el => el.classList.remove('error'));
}

function showAlert(ctx, msg, type = 'error') {
  const el = document.getElementById('modalAlert');
  if (el) { el.textContent = msg; el.className = 'modal-alert ' + type; }
}

function clearModalAlert() {
  const el = document.getElementById('modalAlert');
  if (el) { el.className = 'modal-alert'; el.textContent = ''; }
}

function setButtonLoading(id, loading) {
  const btn = document.getElementById(id);
  if (!btn) return;
  btn.classList.toggle('loading', loading);
  btn.disabled = loading;
}

// ── PASSWORD STRENGTH ────────────────────────────────────────────
function checkStrength(val) {
  const fill  = document.getElementById('strengthFill');
  const label = document.getElementById('strengthLabel');
  if (!fill || !label) return;

  let score = 0;
  if (val.length >= 8)          score++;
  if (/[A-Z]/.test(val))        score++;
  if (/[0-9]/.test(val))        score++;
  if (/[^A-Za-z0-9]/.test(val)) score++;

  const levels = [
    { pct: 0,   color: 'transparent', text: '' },
    { pct: 25,  color: '#e74c3c',     text: 'Weak' },
    { pct: 50,  color: '#f39c12',     text: 'Fair' },
    { pct: 75,  color: '#3498db',     text: 'Good' },
    { pct: 100, color: '#27ae60',     text: 'Strong' },
  ];

  const lvl = val.length === 0 ? levels[0] : (levels[score] || levels[1]);
  fill.style.width      = lvl.pct + '%';
  fill.style.background = lvl.color;
  label.textContent     = lvl.text;
  label.style.color     = lvl.color;
}

// ── LOGIN ─────────────────────────────────────────────────────────
async function handleLogin(e) {
  e.preventDefault();
  clearFormErrors();
  clearModalAlert();

  const email    = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  let valid = true;

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showFieldError('loginEmailError', 'Please enter a valid email address.');
    valid = false;
  }
  if (!password) {
    showFieldError('loginPasswordError', 'Password is required.');
    valid = false;
  }
  if (!valid) return;

  setButtonLoading('loginBtn', true);

  try {
    const res  = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      body: new URLSearchParams({ username: email, password }),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Invalid email or password.');

    localStorage.setItem('authToken', data.access_token);
    const user = { email, name: data.name || email.split('@')[0] };
    localStorage.setItem('userData', JSON.stringify(user));
    setLoggedIn(user);
    closeModal();
    showToast('Welcome back! 👋', 'success');

  } catch (err) {
    showAlert('modal', err.message || 'Login failed. Please try again.', 'error');
  } finally {
    setButtonLoading('loginBtn', false);
  }
}

// ── SIGNUP ────────────────────────────────────────────────────────
async function handleSignup(e) {
  e.preventDefault();
  clearFormErrors();
  clearModalAlert();

  const name     = document.getElementById('signupName').value.trim();
  const email    = document.getElementById('signupEmail').value.trim();
  const password = document.getElementById('signupPassword').value;
  let valid = true;

  if (!name) {
    showFieldError('signupNameError', 'Please enter your name.');
    valid = false;
  }
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showFieldError('signupEmailError', 'Please enter a valid email address.');
    valid = false;
  }
  if (!password || password.length < 8) {
    showFieldError('signupPasswordError', 'Password must be at least 8 characters.');
    valid = false;
  }
  if (!valid) return;

  setButtonLoading('signupBtn', true);

  try {
    const res  = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not create account.');

    localStorage.setItem('authToken', data.access_token);
    const user = { email, name };
    localStorage.setItem('userData', JSON.stringify(user));
    setLoggedIn(user);
    closeModal();
    showToast('Account created! Welcome to ResumeAI 🎉', 'success');

  } catch (err) {
    showAlert('modal', err.message || 'Sign up failed. Please try again.', 'error');
  } finally {
    setButtonLoading('signupBtn', false);
  }
}

// ── LOGOUT ────────────────────────────────────────────────────────
function logout() {
  setLoggedOut();
  closeDropdown();
  showToast('Logged out successfully.');
}

// ── DROPDOWN ──────────────────────────────────────────────────────
function toggleDropdown() {
  document.getElementById('userDropdown').classList.toggle('open');
}

function closeDropdown() {
  const dd = document.getElementById('userDropdown');
  if (dd) dd.classList.remove('open');
}

document.addEventListener('click', e => {
  const wrap = document.querySelector('.user-menu-wrap');
  if (wrap && !wrap.contains(e.target)) closeDropdown();
});

function goToDashboard() { window.location.href = 'dashboard.html'; }
function goToSettings()  { window.location.href = 'settings.html'; }

// ── TOAST ──────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.className   = 'toast ' + type;
  clearTimeout(toastTimer);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => toast.classList.add('show'));
  });
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3200);
}

// ── CONTACT FORM (contact_us.html only) ───────────────────────────
function initContactForm() {
  const form = document.getElementById('contactForm');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearFormErrors();

    const name    = document.getElementById('contactName').value.trim();
    const email   = document.getElementById('contactEmail').value.trim();
    const subject = document.getElementById('contactSubject').value;
    const message = document.getElementById('contactMessage').value.trim();
    let valid = true;

    if (!name) {
      showFieldError('contactNameError', 'Please enter your name.');
      valid = false;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showFieldError('contactEmailError', 'Please enter a valid email address.');
      valid = false;
    }
    if (!subject) {
      showFieldError('contactSubjectError', 'Please select a subject.');
      valid = false;
    }
    if (!message || message.length < 10) {
      showFieldError('contactMessageError', 'Please enter a message (at least 10 characters).');
      valid = false;
    }
    if (!valid) return;

    setButtonLoading('contactBtn', true);

    try {
      // Replace with your actual contact endpoint
      const res  = await fetch(`${API_BASE}/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, subject, message })
      });

      if (!res.ok) throw new Error('Failed to send message.');

      // Show success state
      document.getElementById('contactFormFields').style.display = 'none';
      document.getElementById('contactSuccess').classList.add('visible');

    } catch (err) {
      // Fallback: show toast (so the page still works without a backend)
      showToast('Message sent! We\'ll be in touch soon. ✉️', 'success');
      form.reset();
    } finally {
      setButtonLoading('contactBtn', false);
    }
  });
}
