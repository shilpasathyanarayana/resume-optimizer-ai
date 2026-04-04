document.addEventListener('DOMContentLoaded', () => {
  const yearEl = document.getElementById('footerYear') || document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  const updatedEl = document.getElementById('lastUpdated');
  if (updatedEl) {
    updatedEl.textContent = new Date().toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric'
    });
  }

  initScrollNav();
  initAuth();
  initPageActions();
  initContactForm();
});

function initScrollNav() {
  const nav = document.getElementById('navbar');
  if (!nav) return;
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 40);
  }, { passive: true });
}

// ── UTILS ──────────────────────────────────────────────────────────
function getToken() {
  return localStorage.getItem('authToken');
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


// ── AUTH INIT ─────────────────────────────────────────────────────
function initAuth() {
  const token = getToken();
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

// ======================================================
// 📩 CONTACT FORM (EmailJS)
// ======================================================

function initContactForm() {
  const form = document.getElementById('contactForm');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearFormErrors();

    const name = document.getElementById('contactName').value.trim();
    const email = document.getElementById('contactEmail').value.trim();
    const subject = document.getElementById('contactSubject').value;
    const message = document.getElementById('contactMessage').value.trim();

    let valid = true;

    if (!name) {
      showFieldError('contactNameError', 'Please enter your name.');
      valid = false;
    }

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showFieldError('contactEmailError', 'Please enter a valid email.');
      valid = false;
    }

    if (!subject) {
      showFieldError('contactSubjectError', 'Please select a subject.');
      valid = false;
    }

    if (!message || message.length < 10) {
      showFieldError('contactMessageError', 'Message must be at least 10 characters.');
      valid = false;
    }

    if (!valid) return;

    setButtonLoading('contactBtn', true);

    try {
      await emailjs.send('service_kvpquvr', 'template_95xxlyw', {
        contactName: name,
        contactEmail: email,
        contactMessage: message,
        contactSubject: subject
      });

      document.getElementById('contactFormFields').style.display = 'none';
      document.getElementById('contactSuccess').classList.add('visible');
      form.reset();

    } catch (error) {
      showToast('Failed to send message. Try again.', 'error');
      console.error(error);
    } finally {
      setButtonLoading('contactBtn', false);
    }
  });
}