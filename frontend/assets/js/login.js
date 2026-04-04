
// ======================================================
// 🧾 Login/ Register FORM HELPERS
// ======================================================

function showFieldError(id, msg) {
  const el = document.getElementById(id);
  const input = document.getElementById(id.replace('Error', ''));

  if (el) {
    el.textContent = msg;
    el.classList.add('visible');
  }
  if (input) input.classList.add('error');
}

function clearFormErrors() {
  document.querySelectorAll('.form-error').forEach(el =>
    el.classList.remove('visible')
  );

  document.querySelectorAll('.form-input, .form-select, .form-textarea')
    .forEach(el => el.classList.remove('error'));
}

function showAlert(ctx, msg, type = 'error') {
  const el = document.getElementById('modalAlert');
  if (el) {
    el.textContent = msg;
    el.className = 'modal-alert ' + type;
  }
}

function clearModalAlert() {
  const el = document.getElementById('modalAlert');
  if (el) {
    el.textContent = '';
    el.className = 'modal-alert';
  }
}

function setButtonLoading(id, loading) {
  const btn = document.getElementById(id);
  if (!btn) return;

  btn.classList.toggle('loading', loading);
  btn.disabled = loading;
}


// ======================================================
// 🔐 LOGIN
// ======================================================

async function handleLogin(e) {
  e.preventDefault();
  clearFormErrors();
  clearModalAlert();

  const email = document.getElementById('loginEmail').value.trim();
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
    const res = await fetch(`${API_BASE}/auth/login`, {
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
    setTimeout(() => window.location.href = 'dashboard.html', 800);

  } catch (err) {
    showAlert('modal', err.message || 'Login failed. Please try again.', 'error');
  } finally {
    setButtonLoading('loginBtn', false);
  }
}

// ======================================================
// 🔐 SIGNUP
// ======================================================

async function handleSignup(e) {
  e.preventDefault();
  clearFormErrors();
  clearModalAlert();

  const name = document.getElementById('signupName').value.trim();
  const email = document.getElementById('signupEmail').value.trim();
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
    const res = await fetch(`${API_BASE}/auth/register`, {
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
    setTimeout(() => window.location.href = 'dashboard.html', 800);

  } catch (err) {
    showAlert('modal', err.message || 'Sign up failed. Please try again.', 'error');
  } finally {
    setButtonLoading('signupBtn', false);
  }
}


// ======================================================
// 🔐 PASSWORD STRENGTH
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
