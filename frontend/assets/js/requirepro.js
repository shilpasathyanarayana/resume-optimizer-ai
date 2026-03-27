// ─────────────────────────────────────────────────────────────
// GENERIC REQUIRE PRO — server-verified
// Never trust JWT claims; always fetch is_pro from backend
// ─────────────────────────────────────────────────────────────

async function getToken() {
    return localStorage.getItem('authToken');
}

async function getIsProFromServer() {
    const token = await getToken();
    if (!token) return false;

    try {
        const res = await fetch(`${API_BASE}/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });

        if (!res.ok) {
            if (res.status === 401) localStorage.removeItem('authToken');
            return false;
        }

        const user = await res.json();
        // console.log('User data from API:', user);

        return user.is_pro === true;
    } catch (err) {
        console.error('Fetch error:', err);
        return false;
    }
}

// ─────────────────────────────────────────────────────────────
// PRO REQUEST BANNER
// ─────────────────────────────────────────────────────────────
function showProRequestBanner(message = "This feature is available on Pro. Upgrade to unlock.") {
    if (document.getElementById('proRequestBanner')) return;

    const banner = document.createElement('div');
    banner.id = 'proRequestBanner';
    banner.style.cssText = `
        position: fixed;
        top: 90px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 9999;
        background: #1a7a4a;
        color: white;
        padding: 14px 24px;
        border-radius: 12px;
        font-size: 0.9rem;
        font-weight: 500;
        max-width: 480px;
        width: calc(100% - 48px);
        display: flex;
        align-items: center;
        gap: 12px;
        box-shadow: 0 8px 32px rgba(26, 107, 74, 0.35);
    `;
    banner.innerHTML = `
        <span style="font-size:1.2rem;">🔒</span>
        <span>${message}</span>
        <button class="dismiss-btn" style="
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1rem;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-left: auto;">×</button>
    `;
    document.body.appendChild(banner);
    banner.querySelector('.dismiss-btn').addEventListener('click', () => banner.remove());
    setTimeout(() => banner.remove(), 10000);
}

// ─────────────────────────────────────────────────────────────
// FREE USER TOP NAV BANNER
// ─────────────────────────────────────────────────────────────
function showFreeTopBanner(message = "You're on the Free plan. Upgrade for more features!") {
    if (document.getElementById('freeTopBanner')) return;

    const banner = document.createElement('div');
    banner.id = 'freeTopBanner';
    banner.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        z-index: 10000;
        background: #facc15;
        color: #1f2937;
        text-align: center;
        padding: 12px 0;
        font-weight: 600;
        font-size: 0.95rem;
        cursor: pointer;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    `;
    banner.innerText = message;

    banner.addEventListener('click', () => {
        window.location.href = 'pricing.html';
    });

    document.body.appendChild(banner);
    document.body.style.paddingTop = banner.offsetHeight + 'px';
}

// ─────────────────────────────────────────────────────────────
// GENERIC PRO MODAL + BLUR
// ─────────────────────────────────────────────────────────────
function showProBlur({ redirectUrl = 'pricing.html', title = "Pro Feature", description = "" }) {
    showProRequestBanner();

    const backdrop = document.createElement('div');
    backdrop.style.cssText = `
        position: fixed; inset: 0; z-index: 998;
        backdrop-filter: blur(6px); background: rgba(255,255,255,0.55);
    `;

    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed; inset: 0; z-index: 999;
        display: flex; align-items: center; justify-content: center; padding: 24px;
    `;
    overlay.innerHTML = `
        <div style="
            position: relative; z-index:1000;
            background:#fff; border-radius:20px;
            padding: 40px 36px; max-width:420px; width:100%; text-align:center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.12);">
            <button id="proGateClose" style="
                position:absolute; top:14px; right:16px;
                width:28px;height:28px;border:none;border-radius:50%;cursor:pointer;">×</button>
            <div style="background:#fef3c7;color:#d97706;font-weight:700;border-radius:20px;padding:4px 12px;margin-bottom:20px;">⭐ Pro Feature</div>
            <div style="font-size:1.5rem;font-weight:600;margin-bottom:10px;">${title}</div>
            <p style="color:#6b7280;font-size:0.9rem;line-height:1.6;margin-bottom:28px;">${description}</p>
            <div style="display:flex;flex-direction:column;gap:10px;">
                <a href="${redirectUrl}" style="padding:10px 16px;background:#1a7a4a;color:white;border-radius:12px;text-decoration:none;">Upgrade to Pro →</a>
                <button id="proGateDismiss" style="padding:10px 16px;border-radius:12px;border:1px solid #e5e7eb;background:#fff;">Continue in view-only mode</button>
            </div>
        </div>
    `;

    document.body.appendChild(backdrop);
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';

    function dismiss() {
        backdrop.remove();
        overlay.remove();
        document.body.style.overflow = '';
    }

    document.getElementById('proGateClose').addEventListener('click', dismiss);
    document.getElementById('proGateDismiss').addEventListener('click', dismiss);
    backdrop.addEventListener('click', dismiss);
}

// ─────────────────────────────────────────────────────────────
// GENERIC REQUIRE PRO
// pageSelector = selector of content to dim (optional)
// ─────────────────────────────────────────────────────────────
async function requirePro({ pageSelector = null, title = "Pro Feature", description = "", redirectUrl = 'pricing.html' } = {}) {
    const isPro = await getIsProFromServer();

    if (!isPro) {
        showProBlur({ title, description, redirectUrl });
        showFreeTopBanner();

        if (pageSelector) {
            document.querySelectorAll(pageSelector).forEach(el => {
                el.style.pointerEvents = 'none';
                el.style.opacity = 0.45;
            });
        }

        return false;
    }

    return true;
}