// ======================================================
// 🚀 BOOT  (single DOMContentLoaded for the whole app)
// ======================================================
let currentUser = null;


// ── SCROLL NAV ───────────────────────────────────────────────────
function initScrollNav() {
    const nav = document.getElementById('navbar');
    if (!nav) return;
    window.addEventListener('scroll', () => {
        nav.classList.toggle('scrolled', window.scrollY > 40);
    }, { passive: true });
}


// ── PAGE ACTIONS (replaces initFreeCounter) ───────────────────────
function initPageActions() {
    const path = window.location.pathname;
    const isIndex = path.endsWith('index.html') || path === '/' || path.endsWith('/');

    // Only open login modal when redirected to index with ?action=login
    if (isIndex) {
        const params = new URLSearchParams(window.location.search);
        if (params.get('action') === 'login') {
            openModal('login');
            window.history.replaceState({}, '', window.location.pathname);
        }
    }

    // Update nav badge only for logged-in users, only on non-dashboard pages
    // (dashboard loads its own usage via loadDashboard())
    const isDashboard = path.endsWith('dashboard.html');
    if (!isDashboard && currentUser) {
        updateNavBadge();
    }
}

async function updateNavBadge() {
    const token = localStorage.getItem('authToken');
    if (!token) return;

    try {
        const res = await fetch(`${API_BASE}/resume/usage`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return; // silently fail — never redirect from here
        const data = await res.json();
        const badge = document.getElementById('freeCounter');
        if (badge) {
            badge.textContent = `${data.uses_remaining} of ${data.limit} left`;
            badge.style.display = 'inline-flex';
        }
    } catch (e) { /* silently fail */ }
}


function setLoggedIn(user) {
    currentUser = user;

    const guestNav = document.getElementById('guestNav');
    const userNav = document.getElementById('userNav');
    if (guestNav) guestNav.style.display = 'none';
    if (userNav) userNav.style.display = 'block';

    const initials = user.name
        ? user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
        : user.email[0].toUpperCase();

    const avatar = document.getElementById('userAvatar');
    const dropName = document.getElementById('dropdownName');
    const dropEmail = document.getElementById('dropdownEmail');
    const welcomeName = document.getElementById('welcomeName');

    if (avatar) avatar.textContent = initials;
    if (dropName) dropName.textContent = user.name || 'User';
    if (dropEmail) dropEmail.textContent = user.email;
    if (welcomeName) welcomeName.textContent = user.name || 'User';

    // Hide free badge — updateNavBadge() will show the real count
    const badge = document.getElementById('freeCounter');
    if (badge) badge.style.display = 'none';
}

function setLoggedOut() {
    currentUser = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('userData');

    const guestNav = document.getElementById('guestNav');
    const userNav = document.getElementById('userNav');
    if (guestNav) guestNav.style.display = 'flex';
    if (userNav) userNav.style.display = 'none';

    const badge = document.getElementById('freeCounter');
    if (badge) badge.style.display = 'none';

    // Redirect to index unless already there
    const path = window.location.pathname;
    const isIndex = path.endsWith('index.html') || path === '/' || path.endsWith('/');
    if (!isIndex) {
        window.location.href = 'index.html';
    }
}

// ======================================================
// 🧩 MODAL Login/Resister
// ======================================================

function openModal(tab = 'login') {
    clearModalAlert();
    clearFormErrors();
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
    if (e.target.id === 'modalOverlay') closeModal();
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
});

function switchTab(tab) {
    const isLogin = tab === 'login';
    document.getElementById('tabLogin')?.classList.toggle('active', isLogin);
    document.getElementById('tabSignup')?.classList.toggle('active', !isLogin);
    document.getElementById('panelLogin')?.classList.toggle('active', isLogin);
    document.getElementById('panelSignup')?.classList.toggle('active', !isLogin);
    clearModalAlert();
    clearFormErrors();
}

// ======================================================
// 🔔 TOAST  (single declaration — not in nav.js)
// ======================================================

let toastTimer;

function showToast(msg, type = '') {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = msg;
    toast.className = 'toast ' + type;

    clearTimeout(toastTimer);
    requestAnimationFrame(() => {
        requestAnimationFrame(() => toast.classList.add('show'));
    });

    toastTimer = setTimeout(() => toast.classList.remove('show'), 3200);
}

// ======================================================
// 🧾 FORM HELPERS
// ======================================================

function showFieldError(id, msg) {
    const el = document.getElementById(id);
    const input = document.getElementById(id.replace('Error', ''));
    if (el) { el.textContent = msg; el.classList.add('visible'); }
    if (input) input.classList.add('error');
}

function clearFormErrors() {
    document.querySelectorAll('.form-error')
        .forEach(el => el.classList.remove('visible'));
    document.querySelectorAll('.form-input, .form-select, .form-textarea')
        .forEach(el => el.classList.remove('error'));
}

function showAlert(ctx, msg, type = 'error') {
    const el = document.getElementById('modalAlert');
    if (el) { el.textContent = msg; el.className = 'modal-alert ' + type; }
}

function clearModalAlert() {
    const el = document.getElementById('modalAlert');
    if (el) { el.textContent = ''; el.className = 'modal-alert'; }
}

function setButtonLoading(id, loading) {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.classList.toggle('loading', loading);
    btn.disabled = loading;
}


// ======================================================
// 🔑 PASSWORD STRENGTH
// ======================================================

function checkStrength(val) {
    const fill = document.getElementById('strengthFill');
    const label = document.getElementById('strengthLabel');
    if (!fill || !label) return;

    let score = 0;
    if (val.length >= 8) score++;
    if (/[A-Z]/.test(val)) score++;
    if (/[0-9]/.test(val)) score++;
    if (/[^A-Za-z0-9]/.test(val)) score++;

    const levels = [
        { pct: 0, color: 'transparent', text: '' },
        { pct: 25, color: '#e74c3c', text: 'Weak' },
        { pct: 50, color: '#f39c12', text: 'Fair' },
        { pct: 75, color: '#3498db', text: 'Good' },
        { pct: 100, color: '#27ae60', text: 'Strong' },
    ];

    const lvl = val.length === 0 ? levels[0] : (levels[score] || levels[1]);
    fill.style.width = lvl.pct + '%';
    fill.style.background = lvl.color;
    label.textContent = lvl.text;
    label.style.color = lvl.color;
}

// ======================================================
// 🌐 API HELPER
// ======================================================

async function apiFetch(endpoint, options = {}) {
    const token = localStorage.getItem('authToken');

    const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(options.headers || {})
        }
    });

    // Expired / invalid token — kick back to login
    if (res.status === 401) {
        localStorage.clear();
        window.location.href = 'index.html?action=login';
        return;
    }

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    return data;
}

// ── DROPDOWN ─────────────────────────────────────────────────────
function toggleDropdown() {
    const dd = document.getElementById('userDropdown');
    if (dd) dd.classList.toggle('open');
}

function closeDropdown() {
    const dd = document.getElementById('userDropdown');
    if (dd) dd.classList.remove('open');
}

// ── LOGOUT ────────────────────────────────────────────────────────
function logout() {
    setLoggedOut();
    closeDropdown();
}

document.addEventListener('click', e => {
    const wrap = document.querySelector('.user-menu-wrap');
    if (wrap && !wrap.contains(e.target)) closeDropdown();
});

function goToDashboard() { window.location.href = 'dashboard.html'; }
function goToSettings() { window.location.href = 'settings.html'; }
function goToMyResumes() { window.location.href = 'resume_history.html' }


// ── HELPERS ───────────────────────────────────────────────────────
function getOrCreateGuestSession() {
    let id = localStorage.getItem('guestSessionId');
    if (!id) {
        id = 'guest_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
        localStorage.setItem('guestSessionId', id);
    }
    return id;
}

function getFreeUses() {
    return parseInt(localStorage.getItem('freeUses') || '0', 10);
}


