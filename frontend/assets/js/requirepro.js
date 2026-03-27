function showProRequestBanner() {
    // Don't stack duplicates
    if (document.getElementById('proRequestBanner')) return;

    const style = document.createElement('style');
    style.textContent = `
        @keyframes slide-down {
            from { opacity: 0; transform: translateX(-50%) translateY(-16px); }
            to   { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
        @keyframes slide-up {
            from { opacity: 1; transform: translateX(-50%) translateY(0); }
            to   { opacity: 0; transform: translateX(-50%) translateY(-16px); }
        }
        #proRequestBanner {
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
            box-shadow: 0 8px 32px rgba(26, 107, 74, 0.35);
            display: flex;
            align-items: center;
            gap: 12px;
            max-width: 480px;
            width: calc(100% - 48px);
            animation: slide-down 0.3s ease;
        }
        #proRequestBanner.dismissing {
            animation: slide-up 0.3s ease forwards;
        }
        #proRequestBanner .dismiss-btn {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1rem;
            line-height: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-left: auto;
            flex-shrink: 0;
            transition: background 0.15s;
        }
        #proRequestBanner .dismiss-btn:hover {
            background: rgba(255,255,255,0.35);
        }
    `;
    document.head.appendChild(style);

    const banner = document.createElement('div');
    banner.id = 'proRequestBanner';
    banner.innerHTML = `
        <span style="font-size:1.2rem;">🔒</span>
        <span>This feature is available on <strong>Pro</strong>. Upgrade below to unlock it.</span>
        <button class="dismiss-btn" aria-label="Dismiss">×</button>
    `;
    document.body.appendChild(banner);

    // Dismiss with slide-up animation
    banner.querySelector('.dismiss-btn').addEventListener('click', dismissBanner);

    // Auto-dismiss after 10 seconds
    const timer = setTimeout(dismissBanner, 10000);

    function dismissBanner() {
        clearTimeout(timer);
        banner.classList.add('dismissing');
        banner.addEventListener('animationend', () => banner.remove(), { once: true });
    }
}

function showProBlur(redirectUrl) {
    showProRequestBanner();

    const style = document.createElement('style');
    style.textContent = `
        .pro-blur-backdrop {
            position: fixed;
            inset: 0;
            backdrop-filter: blur(6px);
            -webkit-backdrop-filter: blur(6px);
            background: rgba(255,255,255,0.55);
            z-index: 998;
            transition: opacity 0.3s ease;
        }
        .pro-blur-overlay {
            position: fixed;
            inset: 0;
            z-index: 999;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }
        .pro-gate-card {
            position: relative;
            z-index: 1000;
            background: var(--white, #fff);
            border: 1px solid var(--border, #e5e7eb);
            border-radius: 20px;
            padding: 40px 36px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.12);
            animation: gate-pop 0.25s ease;
        }
        @keyframes gate-pop {
            from { opacity: 0; transform: scale(0.95) translateY(10px); }
            to   { opacity: 1; transform: scale(1) translateY(0); }
        }
        .pro-gate-close {
            position: absolute;
            top: 14px;
            right: 16px;
            background: var(--surface, #f5f5f5);
            border: none;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            font-size: 1rem;
            line-height: 1;
            cursor: pointer;
            color: var(--muted, #6b7280);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.15s;
        }
        .pro-gate-close:hover { background: var(--border, #e5e7eb); }
        .pro-gate-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #fef3c7;
            color: #d97706;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 4px 12px;
            border-radius: 20px;
            margin-bottom: 20px;
        }
        .pro-gate-title {
            font-family: 'DM Serif Display', serif;
            font-size: 1.7rem;
            letter-spacing: -0.02em;
            color: var(--ink, #111);
            margin-bottom: 10px;
            line-height: 1.2;
        }
        .pro-gate-desc {
            font-size: 0.9rem;
            color: var(--muted, #6b7280);
            line-height: 1.6;
            margin-bottom: 28px;
        }
        .pro-gate-actions {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        /* Persistent top bar shown after dismissing the modal */
        #proSoftBar {
            position: fixed;
            top: 0; left: 0; right: 0;
            z-index: 997;
            background: linear-gradient(90deg, #1a7a4a, #22c55e);
            color: white;
            font-size: 0.85rem;
            font-weight: 500;
            padding: 10px 20px;
            display: none;
            align-items: center;
            justify-content: center;
            gap: 12px;
            text-align: center;
        }
        #proSoftBar a {
            color: white;
            font-weight: 700;
            text-decoration: underline;
            white-space: nowrap;
        }
        #proSoftBar.visible { display: flex; }

        /* Dim interactive elements to hint they're blocked */
        .pro-content-dimmed .resume-item,
        .pro-content-dimmed .filter-bar,
        .pro-content-dimmed .pagination {
            pointer-events: none;
            opacity: 0.45;
            user-select: none;
        }
    `;
    document.head.appendChild(style);

    // ── Soft bar (always visible after modal dismissed) ──
    const softBar = document.createElement('div');
    softBar.id = 'proSoftBar';
    softBar.innerHTML = `
        🔒 You're on the free plan — this feature is view-only.
        <a href="${redirectUrl}">Upgrade to Pro →</a>
    `;
    document.body.appendChild(softBar);

    // ── Backdrop ──
    const backdrop = document.createElement('div');
    backdrop.className = 'pro-blur-backdrop';

    // ── Modal ──
    const overlay = document.createElement('div');
    overlay.className = 'pro-blur-overlay';
    overlay.innerHTML = `
        <div class="pro-gate-card">
            <button class="pro-gate-close" id="proGateClose" aria-label="Close">×</button>
            <div class="pro-gate-badge">⭐ Pro Feature</div>
            <div class="pro-gate-title">Upgrade to View History</div>
            <p class="pro-gate-desc">
                Resume optimisation history is available on the Pro plan.
                Upgrade to track every submission, ATS score, and improvement over time.
            </p>
            <div class="pro-gate-actions">
                <a href="${redirectUrl}" class="btn btn-primary" style="text-align:center;">
                    Upgrade to Pro →
                </a>
                <button id="proGateDismiss" class="btn btn-ghost">
                    Continue in view-only mode
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(backdrop);
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';

    // ── Dismiss logic ──
    function dismiss() {
        backdrop.remove();
        overlay.remove();
        document.body.style.overflow = '';

        // Show persistent top bar
        softBar.classList.add('visible');
        // Push navbar + content down to make room
        document.getElementById('navbar').style.top = '40px';

        // Dim interactive elements so free user can see but not use them
        document.querySelector('.dashboard-wrapper').classList.add('pro-content-dimmed');

        // Re-intercept any clicks on blocked elements
        document.querySelectorAll('.resume-item').forEach(el => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopImmediatePropagation();
                showProRequestBanner();
            });
        });
    }

    document.getElementById('proGateClose').addEventListener('click', dismiss);
    document.getElementById('proGateDismiss').addEventListener('click', dismiss);
    // Click backdrop to dismiss too
    backdrop.addEventListener('click', dismiss);
}

function requirePro(redirectUrl = 'pricing.html?pro_request=true') {
    const raw = localStorage.getItem('userData');
    const plan = raw ? JSON.parse(raw).plan : 'free';
    if (plan !== 'pro') {
        showProBlur(redirectUrl);
        return false;
    }
    return true;
}