/* ============================================================
   UFIT MOTION — Vanilla JS SPA
   Mobile-first. No framework. Coaches use this on phones.
   ============================================================ */
'use strict';

/* ============================================================
   1. STATE
   ============================================================ */

// Safe data store for passing objects into onclick handlers without XSS risk.
// Usage: _modalStore.set(id, obj) in render, _modalStore.get(id) in handler.
const _modalStore = (() => {
  const _map = new Map();
  let _seq = 0;
  return {
    set(obj) { const id = ++_seq; _map.set(id, obj); return id; },
    get(id)  { return _map.get(Number(id)); },
    clear()  { _map.clear(); },
  };
})();

const state = {
  user: null,
  currentPage: 'login',
  notifications: [],
  loading: false,
  error: null,
  modal: null,
};

/* ============================================================
   2. ROLE / PORTAL HELPERS
   ============================================================ */
const ADMIN_ROLES  = new Set(['ceo', 'admin']);
const COACH_ROLES  = new Set(['head_coach', 'assistant_coach', 'site_coordinator', 'coach_overseer']);
const SCHOOL_ROLES = new Set(['principal', 'school_staff']);

function getPortal(user) {
  if (!user) return 'login';
  const r = (user.role || '').toLowerCase();
  if (ADMIN_ROLES.has(r))  return 'admin';
  if (COACH_ROLES.has(r))  return 'coach';
  if (r === 'parent')      return 'parent';
  if (SCHOOL_ROLES.has(r)) return 'principal';
  return 'login';
}

/* ============================================================
   3. SVG ICONS
   ============================================================ */
function icon(path, w = 18, h = 18) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"
    viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
}
const iconDashboard  = () => icon('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>');
const iconSchools    = () => icon('<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>');
const iconCoaches    = () => icon('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>');
const iconStudents   = () => icon('<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>');
const iconSessions   = () => icon('<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>');
const iconReports    = () => icon('<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>');
const iconAssess     = () => icon('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>');
const iconIncidents  = () => icon('<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>');
const iconSurveys    = () => icon('<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>');
const iconSettings   = () => icon('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>');
const iconLogout     = () => icon('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>');
const iconBell       = () => icon('<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>', 20, 20);
const iconPerformance = () => icon('<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>');
const iconMenu       = () => icon('<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>', 22, 22);
const iconClose      = () => icon('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>', 22, 22);
const iconCheck      = () => icon('<polyline points="20 6 9 17 4 12"/>');
const iconAlert      = () => icon('<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>');
const iconPlus       = () => icon('<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>');
const iconEdit       = () => icon('<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>');
const iconEod        = () => icon('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>');
const iconWindows    = () => icon('<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><polyline points="9 15 11 17 15 13"/>');
const iconBehavior   = () => icon('<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>');
const iconPrograms   = () => icon('<rect x="2" y="3" width="6" height="6" rx="1"/><rect x="9" y="3" width="13" height="2" rx="1"/><rect x="9" y="7" width="9" height="2" rx="1"/><rect x="2" y="11" width="6" height="6" rx="1"/><rect x="9" y="11" width="13" height="2" rx="1"/><rect x="9" y="15" width="9" height="2" rx="1"/>');

/* ============================================================
   4. UTILITY HELPERS
   ============================================================ */
function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function $(sel, ctx = document) { return ctx.querySelector(sel); }
function $$(sel, ctx = document) { return [...ctx.querySelectorAll(sel)]; }

function getInitials(name = '') {
  return name.split(' ').slice(0, 2).map(w => w[0] || '').join('').toUpperCase();
}

function fmtDate(d) {
  if (!d) return '—';
  const dt = new Date(d.includes('T') ? d : d + 'T00:00:00');
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function fmtSkillName(s) {
  return s ? s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : '—';
}

function fmtLabel(v) {
  if (!v || v === '—') return '—';
  return esc(v.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()));
}

function todayFull() {
  return new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
}

function pct(rate) {
  return rate != null ? `${Math.round(rate * 100)}%` : '—';
}

/* ============================================================
   5. API HELPER
   ============================================================ */
async function api(method, path, body = null) {
  const opts = {
    method: method.toUpperCase(),
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    credentials: 'same-origin',
  };
  if (body && method.toUpperCase() !== 'GET') opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (res.status === 401 && path !== '/api/auth/login' && path !== '/api/auth/session') {
    closeModal();
    state.user = null;
    state.currentPage = 'login';
    render();
    showAlert('Your session has expired. Please sign in again.', 'warning');
    return;
  }
  const ct = res.headers.get('content-type') || '';
  const data = ct.includes('application/json') ? await res.json() : { message: await res.text() };
  if (!res.ok) throw new Error(data?.error || data?.message || `Error ${res.status}`);
  return data;
}

/* ============================================================
   6. ALERT SYSTEM
   ============================================================ */
function ensureAlertStack() {
  let s = document.getElementById('alert-stack');
  if (!s) { s = document.createElement('div'); s.id = 'alert-stack'; s.className = 'alert-stack'; document.body.appendChild(s); }
  return s;
}

function showAlert(msg, type = 'info', ms = 4500) {
  const stack = ensureAlertStack();
  const id = 'a-' + Date.now();
  const iconMap = { error: iconAlert(), success: iconCheck(), warning: iconAlert(), info: iconAlert() };
  const div = document.createElement('div');
  div.id = id; div.className = `alert alert-${type}`; div.setAttribute('role', 'alert');
  div.innerHTML = `<span class="alert-icon">${iconMap[type] || ''}</span><span class="alert-body">${esc(msg)}</span><button class="alert-dismiss" aria-label="Dismiss">&times;</button>`;
  div.querySelector('.alert-dismiss').onclick = () => dismissAlert(id);
  stack.appendChild(div);
  if (ms > 0) setTimeout(() => dismissAlert(id), ms);
  return id;
}

function dismissAlert(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.cssText += 'opacity:0;transform:translateY(-8px);transition:opacity 200ms,transform 200ms';
  setTimeout(() => el.remove(), 200);
}

/* ============================================================
   7. MODAL SYSTEM
   ============================================================ */
function openModal(html, onClose) {
  closeModal();
  const overlay = document.createElement('div');
  overlay.id = 'modal-overlay';
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `<div class="modal" role="dialog" aria-modal="true">${html}</div>`;
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(onClose); });
  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';
  const first = overlay.querySelector('input,select,textarea,button:not(.modal-close)');
  first && first.focus();
}

function closeModal(cb) {
  const overlay = document.getElementById('modal-overlay');
  if (overlay) overlay.remove();
  document.body.style.overflow = '';
  if (cb) cb();
}

/* ============================================================
   8. LOADING PLACEHOLDER
   ============================================================ */
function renderSkeleton(rows = 4) {
  return `<div class="skeleton-list">${Array(rows).fill('<div class="skeleton-row"></div>').join('')}</div>`;
}

/* ============================================================
   9. ROUTER
   ============================================================ */
const PAGE_TITLES = {
  dashboard: 'Dashboard', schools: 'Schools', coaches: 'Coaches',
  students: 'Students', incidents: 'Incidents', reports: 'Reports',
  sessions: 'My Sessions', 'eod-reports': 'EOD Reports', assessments: 'Assessments',
  settings: 'Settings', skills: 'Skills Overview', 'principal-dashboard': 'Dashboard', 'principal-students': 'My Students',
  'parent-home': 'My Children', behavior: 'Behavior Observations', performance: 'My Performance',
};

function navigate(page) {
  closeModal();
  state.currentPage = page;
  window.history.pushState({ page }, '', `?page=${page}`);
  render();
  window.scrollTo({ top: 0, behavior: 'instant' });
}

window.addEventListener('popstate', e => {
  closeModal();
  const page = e.state?.page || 'dashboard';
  state.currentPage = page;
  render();
});

function render() {
  const app = document.getElementById('app');
  if (!app) return;
  if (!state.user || state.currentPage === 'login') {
    app.innerHTML = renderLogin();
    attachLoginListeners();
    return;
  }
  app.innerHTML = renderShell();
  attachShellListeners();
  renderPage();
}

function renderPage() {
  const main = document.getElementById('page-main');
  if (!main) return;
  const portal = getPortal(state.user);

  if (portal === 'admin') {
    switch (state.currentPage) {
      case 'dashboard': loadAdminDashboard(main); break;
      case 'schools':   loadSchoolsPage(main);    break;
      case 'coaches':   loadCoachesPage(main);     break;
      case 'students':  loadStudentsGrowth(main);  break;
      case 'eod-reports': loadAdminEodPage(main);  break;
      case 'incidents':   loadIncidentsPage(main); break;
      case 'reports':     loadReportsPage(main);   break;
      case 'surveys':      loadAdminSurveys(main);      break;
      case 'evaluations':  loadAdminEvaluations(main);  break;
      case 'settings':  main.innerHTML = renderSettingsPage(); attachSettingsListeners(); break;
      default:          loadAdminDashboard(main);
    }
  } else if (portal === 'coach') {
    switch (state.currentPage) {
      case 'dashboard':   loadCoachDashboard(main);   break;
      case 'eod-reports': loadEodPage(main);          break;
      case 'assessments': loadAssessmentsPage(main);  break;
      case 'behavior':    loadBehaviorObsPage(main);  break;
      case 'students':    loadMyStudents(main);        break;
      case 'incidents':   loadCoachIncidents(main);   break;
      case 'performance': loadMyPerformancePage(main); break;
      case 'evaluate':    loadCoachEvaluatePage(main); break;
      case 'settings':    main.innerHTML = renderSettingsPage(); attachSettingsListeners(); break;
      default:            loadCoachDashboard(main);
    }
  } else if (portal === 'principal') {
    switch (state.currentPage) {
      case 'dashboard':
      case 'principal-dashboard': loadPrincipalDashboard(main); break;
      case 'students':
      case 'principal-students':  loadPrincipalStudents(main); break;
      case 'incidents':           loadPrincipalIncidents(main); break;
      case 'skills':              loadPrincipalSkillAverages(main); break;
      case 'survey':              loadPrincipalSurvey(main); break;
      case 'settings': main.innerHTML = renderSettingsPage(); attachSettingsListeners(); break;
      default: loadPrincipalDashboard(main);
    }
  } else if (portal === 'parent') {
    switch (state.currentPage) {
      case 'parent-home': loadParentHome(main); break;
      case 'settings':    main.innerHTML = renderSettingsPage(); attachSettingsListeners(); break;
      default:            loadParentHome(main);
    }
  }

  syncNavActive();
}

function syncNavActive() {
  $$('.nav-item[data-page]').forEach(el => el.classList.toggle('active', el.dataset.page === state.currentPage));
  $$('.mobile-nav-btn[data-page]').forEach(el => el.classList.toggle('active', el.dataset.page === state.currentPage));
}

/* ============================================================
   10. LOGIN PAGE
   ============================================================ */
function renderLogin() {
  const portals = [
    { key: 'admin', label: 'Admin Portal',    emoji: '🏢' },
    { key: 'coach', label: 'Coach Portal',    emoji: '🏃' },
    { key: 'staff', label: 'Staff / Parent',  emoji: '👤' },
  ];
  const sel = state._loginPortal || 'admin';
  return `
    <div class="login-page">
      <div class="login-card">
        <div class="login-logo">
          <div class="login-logo-mark"><span class="login-logo-ufit">UFIT</span><span class="login-logo-motion">MOTION</span></div>
          <div class="login-logo-tagline">School Fitness Platform</div>
        </div>
        <div class="portal-selector-label">Select your portal</div>
        <div class="portal-selector" id="portal-selector">
          ${portals.map(p => `<button class="portal-btn ${sel === p.key ? 'active' : ''}" data-portal="${p.key}" type="button">
            <div class="portal-btn-icon">${p.emoji}</div>${p.label}</button>`).join('')}
        </div>
        <form id="login-form" novalidate>
          <div class="form-stack">
            <div id="login-alert-area"></div>
            <div class="form-group">
              <label class="form-label" for="email">Email address</label>
              <input class="form-input" type="email" id="email" name="email" placeholder="you@school.edu" autocomplete="username" inputmode="email" required />
            </div>
            <div class="form-group">
              <label class="form-label" for="password">Password</label>
              <input class="form-input" type="password" id="password" name="password" placeholder="Enter your password" autocomplete="current-password" required />
            </div>
            <button class="btn btn-primary btn-full" type="submit" id="signin-btn">Sign In</button>
            <div style="text-align:center;margin-top:4px;">
              <button class="btn btn-ghost btn-sm" type="button" id="forgot-pw-link" style="font-size:0.875rem;">Forgot password?</button>
            </div>
          </div>
        </form>
        <div class="login-footer-text">Ufit Motion &mdash; &copy; ${new Date().getFullYear()} Ufit Online</div>
      </div>
    </div>`;
}

function attachLoginListeners() {
  $$('.portal-btn').forEach(btn => btn.addEventListener('click', () => {
    state._loginPortal = btn.dataset.portal;
    $$('.portal-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }));

  document.getElementById('forgot-pw-link')?.addEventListener('click', openForgotPasswordModal);

  const form = document.getElementById('login-form');
  if (!form) return;
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const email = form.querySelector('#email').value.trim();
    const password = form.querySelector('#password').value;
    if (!email || !password) { showLoginError('Please enter your email and password.'); return; }
    const btn = document.getElementById('signin-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner spinner-white"></span> Signing in…`;
    try {
      const data = await api('POST', '/api/auth/login', { email, password, portal: state._loginPortal || 'admin' });
      state.user = data.user || data;
      state.currentPage = 'dashboard';
      render();
    } catch (err) {
      showLoginError(err.message || 'Invalid email or password.');
      btn.disabled = false; btn.innerHTML = 'Sign In';
    }
  });
}

function showLoginError(msg) {
  const a = document.getElementById('login-alert-area');
  if (a) a.innerHTML = `<div class="alert alert-error" role="alert"><span class="alert-icon">${iconAlert()}</span><span class="alert-body">${esc(msg)}</span></div>`;
}

function openForgotPasswordModal() {
  openModal(`
    <div class="modal-header">
      <h2 class="modal-title">Forgot Password</h2>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <form id="forgot-pw-form" class="modal-body form-stack">
      <p style="margin:0 0 12px;color:var(--color-text-secondary);font-size:0.875rem;">Enter your email address and we'll send you a reset link if an account exists.</p>
      <div class="form-group">
        <label class="form-label" for="forgot-email">Email address</label>
        <input class="form-input" type="email" id="forgot-email" name="email" placeholder="you@school.edu" required inputmode="email" autocomplete="email" />
      </div>
      <div id="forgot-pw-msg"></div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="forgot-pw-submit">Send Reset Link</button>
      </div>
    </form>`);

  document.getElementById('forgot-pw-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('forgot-pw-submit');
    const msg = document.getElementById('forgot-pw-msg');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    const email = document.getElementById('forgot-email')?.value.trim() || '';
    try {
      await api('POST', '/api/auth/forgot-password', { email });
      if (msg) msg.innerHTML = `<div class="alert alert-success" role="alert"><span class="alert-body">If an account exists for <strong>${esc(email)}</strong>, a reset link has been sent.</span></div>`;
      btn.disabled = true; btn.textContent = 'Sent';
    } catch (err) {
      if (msg) msg.innerHTML = `<div class="alert alert-error" role="alert"><span class="alert-body">${esc(err.message)}</span></div>`;
      btn.disabled = false; btn.textContent = 'Send Reset Link';
    }
  });
}

/* ============================================================
   11. APP SHELL
   ============================================================ */
function navConfig(portal) {
  if (portal === 'admin') return [
    { page: 'dashboard',   label: 'Dashboard',   icon: iconDashboard },
    { page: 'schools',     label: 'Schools',     icon: iconSchools   },
    { page: 'coaches',     label: 'Coaches',     icon: iconCoaches   },
    { page: 'students',    label: 'Students',    icon: iconStudents  },
    { page: 'eod-reports', label: 'EOD Reports', icon: iconEod       },
    { page: 'incidents',   label: 'Incidents',   icon: iconIncidents },
    { page: 'reports',     label: 'Reports',     icon: iconReports   },
    { page: 'surveys',     label: 'Surveys',     icon: iconSurveys   },
    { page: 'evaluations', label: 'Evaluations', icon: iconAssess    },
    { page: 'settings',    label: 'Settings',    icon: iconSettings  },
  ];
  if (portal === 'coach') {
    const items = [
      { page: 'dashboard',    label: 'Dashboard',    icon: iconDashboard },
      { page: 'eod-reports',  label: 'EOD Reports',  icon: iconEod       },
      { page: 'assessments',  label: 'Assessments',  icon: iconAssess    },
      { page: 'behavior',     label: 'Behavior',     icon: iconBehavior  },
      { page: 'students',     label: 'Students',     icon: iconStudents  },
      { page: 'incidents',    label: 'Incidents',    icon: iconIncidents },
      { page: 'performance',  label: 'My Score',     icon: iconPerformance },
      { page: 'settings',     label: 'Settings',     icon: iconSettings  },
    ];
    if (state.user?.role === 'head_coach' || state.user?.role === 'site_coordinator') {
      items.splice(items.length - 1, 0, { page: 'evaluate', label: 'Evaluate', icon: iconSurveys });
    }
    return items;
  }
  if (portal === 'principal') return [
    { page: 'dashboard', label: 'Dashboard', icon: iconDashboard },
    { page: 'students',  label: 'Students',  icon: iconStudents  },
    { page: 'skills',    label: 'Skills',    icon: iconAssess    },
    { page: 'incidents', label: 'Incidents', icon: iconIncidents },
    { page: 'survey',    label: 'Survey',    icon: iconSurveys   },
    { page: 'settings',  label: 'Settings',  icon: iconSettings  },
  ];
  return [
    { page: 'parent-home', label: 'My Children', icon: iconStudents },
    { page: 'settings',    label: 'Settings',    icon: iconSettings },
  ];
}

function renderShell() {
  const portal = getPortal(state.user);
  const items = navConfig(portal);
  const name = state.user?.first_name ? `${state.user.first_name} ${state.user.last_name || ''}`.trim() : state.user?.email || 'User';
  const initials = getInitials(name);
  const roleLabel = (state.user?.role || 'User').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  const sideItems = items.map(i => `
    <div class="nav-item ${i.page === state.currentPage ? 'active' : ''}" data-page="${i.page}" role="button" tabindex="0" aria-label="${i.label}">
      <span class="nav-item-icon">${i.icon()}</span><span class="nav-item-label">${i.label}</span>
    </div>`).join('');

  const mobileItems = items.slice(0, 5).map(i => `
    <button class="mobile-nav-btn ${i.page === state.currentPage ? 'active' : ''}" data-page="${i.page}" type="button" aria-label="${i.label}">
      <span class="mobile-nav-icon-wrap">${i.icon()}</span><span>${i.label}</span>
    </button>`).join('');

  return `
    <div class="sidebar-overlay" id="sidebar-overlay"></div>
    <div class="app-layout">
      <aside class="sidebar" id="sidebar" role="navigation" aria-label="Main navigation">
        <div class="nav-logo">
          <div class="nav-logo-text"><span class="nav-logo-ufit">Ufit</span><span class="nav-logo-motion">Motion</span><span class="nav-logo-dot"></span></div>
          <div class="nav-logo-subtitle">School Fitness Platform</div>
        </div>
        <nav>${sideItems}</nav>
        <div class="sidebar-footer">
          <div class="sidebar-user">
            <div class="sidebar-user-avatar">${initials}</div>
            <div><div class="sidebar-user-name truncate">${esc(name)}</div><div class="sidebar-user-role">${esc(roleLabel)}</div></div>
          </div>
        </div>
      </aside>
      <div class="main-content">
        <header class="top-nav" role="banner">
          <div class="top-nav-left">
            <button class="hamburger-btn" id="hamburger-btn" aria-label="Open navigation" aria-expanded="false">${iconMenu()}</button>
            <span class="nav-page-title">${esc(PAGE_TITLES[state.currentPage] || 'Dashboard')}</span>
          </div>
          <div class="top-nav-right">
            <button class="bell-btn" id="bell-btn" aria-label="Notifications" style="position:relative;">
              ${iconBell()}
              ${state.notifications.filter(n => !n.is_read).length > 0 ? `<span style="position:absolute;top:2px;right:2px;background:var(--color-error,#dc2626);color:#fff;border-radius:50%;width:14px;height:14px;font-size:9px;display:flex;align-items:center;justify-content:center;font-weight:700;">${state.notifications.filter(n => !n.is_read).length > 9 ? '9+' : state.notifications.filter(n => !n.is_read).length}</span>` : ''}
            </button>
            <button class="user-menu-btn" id="logout-btn" aria-label="Sign out" title="Sign out">
              <div class="user-menu-avatar">${initials}</div>
              <span class="user-menu-name">${esc(state.user?.first_name || name)}</span>
              <span style="color:var(--color-text-secondary);margin-left:4px;">${iconLogout()}</span>
            </button>
          </div>
        </header>
        <main class="page-container" id="page-main" role="main"></main>
      </div>
    </div>
    <nav class="mobile-nav" role="navigation" aria-label="Mobile navigation">${mobileItems}</nav>`;
}

function attachShellListeners() {
  $$('.nav-item[data-page]').forEach(el => {
    el.addEventListener('click', () => { navigate(el.dataset.page); if (window.innerWidth < 769) closeSidebar(); });
    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(el.dataset.page); if (window.innerWidth < 769) closeSidebar(); } });
  });
  $$('.mobile-nav-btn[data-page]').forEach(el => el.addEventListener('click', () => navigate(el.dataset.page)));
  document.getElementById('hamburger-btn')?.addEventListener('click', toggleSidebar);
  document.getElementById('sidebar-overlay')?.addEventListener('click', closeSidebar);
  document.getElementById('logout-btn')?.addEventListener('click', handleLogout);
  document.getElementById('bell-btn')?.addEventListener('click', showNotificationsPanel);
  if (window.innerWidth >= 769 && localStorage.getItem('sidebar_collapsed') === '1') {
    document.getElementById('sidebar')?.classList.add('collapsed');
    const mc = document.querySelector('.main-content');
    if (mc) mc.style.marginLeft = '64px';
  }
}

function toggleSidebar() {
  const sb = document.getElementById('sidebar'), ov = document.getElementById('sidebar-overlay'), hb = document.getElementById('hamburger-btn');
  if (window.innerWidth >= 769) {
    const collapsed = sb?.classList.toggle('collapsed');
    const mc = document.querySelector('.main-content');
    if (mc) mc.style.marginLeft = collapsed ? '64px' : '';
    localStorage.setItem('sidebar_collapsed', collapsed ? '1' : '0');
    hb?.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  } else {
    const open = sb?.classList.contains('open');
    if (open) closeSidebar();
    else { sb?.classList.add('open'); ov?.classList.add('active'); hb?.setAttribute('aria-expanded', 'true'); if (hb) hb.innerHTML = iconClose(); }
  }
}
function closeSidebar() {
  if (window.innerWidth >= 769) return;
  const sb = document.getElementById('sidebar'), ov = document.getElementById('sidebar-overlay'), hb = document.getElementById('hamburger-btn');
  sb?.classList.remove('open'); ov?.classList.remove('active'); hb?.setAttribute('aria-expanded', 'false'); if (hb) hb.innerHTML = iconMenu();
}

/* ============================================================
   12. ADMIN DASHBOARD
   ============================================================ */
async function loadAdminDashboard(container) {
  container.innerHTML = renderSkeleton(6);
  try {
    const d = await api('GET', '/api/admin/dashboard');
    const eodPct = d.eod_compliance_rate != null ? Math.round(d.eod_compliance_rate * 100) : 0;
    container.innerHTML = `
      <div class="welcome-card">
        <div class="welcome-greeting">Welcome back, ${esc(state.user?.first_name || 'Admin')}! 👋</div>
        <div class="welcome-subtitle"><span class="badge badge-yellow" style="margin-right:8px;">${fmtLabel(state.user?.role || 'Admin')}</span>${todayFull()}</div>
      </div>
      <div class="stats-grid">
        ${statCard('Schools', d.active_schools ?? 0, iconSchools(), '')}
        ${statCard('Active Coaches', d.active_coaches ?? 0, iconCoaches(), 'accent')}
        ${statCard('Sessions This Week', d.sessions_this_week ?? 0, iconSessions(), 'success')}
        ${statCard('EOD Compliance', eodPct + '%', iconEod(), eodPct < 70 ? 'error' : 'success')}
        ${statCard('Open Incidents', d.open_incidents ?? 0, iconIncidents(), d.open_incidents > 0 ? 'error' : '')}
      </div>
      <div class="cards-grid">
        <div class="card">
          <div class="card-header"><div class="card-title">Quick Actions</div></div>
          <div class="form-stack" style="gap:8px;">
            <button class="btn btn-primary btn-full" id="qa-add-school" type="button" style="justify-content:flex-start;">${iconPlus()} Add New School</button>
            <button class="btn btn-ghost btn-full" id="qa-add-coach" type="button" style="justify-content:flex-start;">${iconPlus()} Add New Coach</button>
            <button class="btn btn-ghost btn-full" data-page="incidents" type="button" style="justify-content:flex-start;">${iconIncidents()} Review Open Incidents</button>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><div class="card-title">This Week at a Glance</div></div>
          <div class="kv-list">
            <div class="kv-row"><span class="kv-key">Sessions logged</span><span class="kv-val">${d.sessions_this_week ?? 0}</span></div>
            <div class="kv-row"><span class="kv-key">EOD compliance</span><span class="kv-val ${eodPct < 70 ? 'text-error' : 'text-success'}">${eodPct}%</span></div>
            <div class="kv-row"><span class="kv-key">Open incidents</span><span class="kv-val ${(d.open_incidents ?? 0) > 0 ? 'text-error' : ''}">${d.open_incidents ?? 0}</span></div>
          </div>
        </div>
      </div>`;
    document.getElementById('qa-add-school')?.addEventListener('click', () => openAddSchoolModal());
    document.getElementById('qa-add-coach')?.addEventListener('click', openAddCoachModal);
    $$('[data-page]', container).forEach(el => el.addEventListener('click', () => navigate(el.dataset.page)));
  } catch (err) {
    container.innerHTML = errorCard(err.message);
  }
}

function statCard(label, value, iconSvg, colorClass = '') {
  return `<div class="stat-card ${colorClass}">
    <div class="stat-icon ${colorClass}">${iconSvg}</div>
    <div class="stat-value">${esc(String(value))}</div>
    <div class="stat-label">${esc(label)}</div>
  </div>`;
}

/* ============================================================
   13. SCHOOLS PAGE
   ============================================================ */
async function loadSchoolsPage(container) {
  container.innerHTML = `
    <div class="page-header">
      <div><div class="text-h2">Schools</div><div class="text-caption">Manage all schools in the program</div></div>
      <button class="btn btn-primary" id="add-school-btn" type="button">${iconPlus()} Add School</button>
    </div>
    <div id="schools-content">${renderSkeleton(5)}</div>`;
  document.getElementById('add-school-btn')?.addEventListener('click', () => openAddSchoolModal(() => loadSchoolsPage(container)));

  try {
    const d = await api('GET', '/api/admin/schools');
    const schools = d.schools || [];
    const schoolsContent = document.getElementById('schools-content');
    if (!schoolsContent) return;
    if (!schools.length) {
      schoolsContent.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">${iconSchools()}</div>
        <div class="empty-state-title">No schools yet</div>
        <div class="empty-state-text">Add your first school to get started.</div>
        <button class="btn btn-primary" onclick="document.getElementById('add-school-btn').click()">Add First School</button>
      </div>`;
      return;
    }
    schoolsContent.innerHTML = `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>School Name</th><th>Type</th><th>City, State</th>
            <th>Coaches</th><th>Sessions This Week</th><th>Last EOD</th><th></th>
          </tr></thead>
          <tbody>${schools.map(s => `
            <tr>
              <td><strong>${esc(s.school_name)}</strong>${s.principal_name ? `<div class="text-caption">${esc(s.principal_name)}</div>` : ''}</td>
              <td><span class="badge">${fmtLabel(s.school_type)}</span></td>
              <td>${s.city ? esc(s.city) + (s.state ? ', ' + esc(s.state) : '') : '—'}</td>
              <td>${s.coach_count ?? 0}</td>
              <td>${s.session_count_this_week ?? 0}</td>
              <td>${fmtDate(s.last_eod_date)}</td>
              <td><button class="btn btn-ghost btn-sm" aria-label="Edit school" data-school-id="${s.school_id}" onclick="openEditSchoolModal(${s.school_id})">${iconEdit()}</button></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  } catch (err) {
    const c = document.getElementById('schools-content');
    if (c) c.innerHTML = errorCard(err.message);
  }
}

async function openAddSchoolModal(onSuccess) {
  let orgs = [];
  try { const d = await api('GET', '/api/organizations'); orgs = d.organizations || []; } catch (_) {}

  const orgOptions = orgs.map(o => `<option value="${o.organization_id}">${esc(o.organization_name)}</option>`).join('');
  const hasOrgs = orgs.length > 0;

  openModal(`
    <div class="modal-header"><h2 class="modal-title">Add School</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <form id="add-school-form" class="modal-body form-stack">
      ${!hasOrgs ? `
        <div class="alert alert-warning"><span class="alert-icon">${iconAlert()}</span><span class="alert-body">No organizations exist yet. Create one first.</span></div>
        <div class="form-group">
          <label class="form-label">Organization Name *</label>
          <input class="form-input" name="new_org_name" placeholder="e.g. Portland Public Schools" required />
        </div>` : `
        <div class="form-group">
          <label class="form-label">Organization *</label>
          <select class="form-input form-select" name="organization_id" required><option value="">Select organization…</option>${orgOptions}</select>
        </div>`}
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">School Name *</label>
          <input class="form-input" name="school_name" placeholder="e.g. Lincoln Elementary" required />
        </div>
        <div class="form-group">
          <label class="form-label">Type</label>
          <select class="form-input form-select" name="school_type">
            <option value="elementary">Elementary</option>
            <option value="middle">Middle</option>
            <option value="high">High</option>
            <option value="k8">K-8</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">City</label>
          <input class="form-input" name="city" placeholder="Portland" />
        </div>
        <div class="form-group">
          <label class="form-label">State</label>
          <input class="form-input" name="state" placeholder="OR" maxlength="2" style="text-transform:uppercase;" />
        </div>
        <div class="form-group">
          <label class="form-label">Zip Code</label>
          <input class="form-input" name="zip_code" placeholder="97201" maxlength="10" />
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Principal First Name</label>
          <input class="form-input" name="principal_first_name" placeholder="Jane" />
        </div>
        <div class="form-group">
          <label class="form-label">Principal Last Name</label>
          <input class="form-input" name="principal_last_name" placeholder="Smith" />
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Principal Email</label>
          <input class="form-input" type="email" name="principal_email" placeholder="principal@school.edu" id="principal-email-field" />
        </div>
      </div>
      <div id="principal-login-section" style="display:none; border:1px solid #e5e7eb; border-radius:8px; padding:16px; background:#f9fafb;">
        <p style="margin:0 0 12px; font-weight:600; font-size:14px;">Principal Login Credentials</p>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Temporary Password *</label>
            <input class="form-input" type="password" name="principal_password" placeholder="Min 8 characters" minlength="8" />
          </div>
          <div class="form-group">
            <label class="form-label">Confirm Password *</label>
            <input class="form-input" type="password" name="principal_password_confirm" placeholder="Re-enter password" />
          </div>
        </div>
        <p style="margin:4px 0 0; font-size:12px; color:#6b7280;">The principal will use their email and this password to log in. They can change it after signing in.</p>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="add-school-submit">Add School</button>
      </div>
    </form>`);

  // Show principal login section when email is entered
  document.getElementById('principal-email-field')?.addEventListener('input', function() {
    const section = document.getElementById('principal-login-section');
    if (section) section.style.display = this.value.trim() ? 'block' : 'none';
  });

  document.getElementById('add-school-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = document.getElementById('add-school-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';

    const principalEmail = fd.get('principal_email').trim().toLowerCase();
    const principalPassword = fd.get('principal_password') || '';
    const principalPasswordConfirm = fd.get('principal_password_confirm') || '';
    const principalFirstName = fd.get('principal_first_name').trim();
    const principalLastName = fd.get('principal_last_name').trim();

    if (principalEmail && principalPassword) {
      if (principalPassword.length < 8) {
        showAlert('Principal password must be at least 8 characters.', 'error');
        btn.disabled = false; btn.innerHTML = 'Add School'; return;
      }
      if (principalPassword !== principalPasswordConfirm) {
        showAlert('Passwords do not match.', 'error');
        btn.disabled = false; btn.innerHTML = 'Add School'; return;
      }
    }

    try {
      let orgId = fd.get('organization_id') ? parseInt(fd.get('organization_id')) : null;
      if (!orgId && fd.get('new_org_name')) {
        const orgRes = await api('POST', '/api/organizations', { organization_name: fd.get('new_org_name').trim() });
        orgId = orgRes.organization?.organization_id;
      }
      if (!orgId) { showAlert('Please select or create an organization.', 'error'); btn.disabled = false; btn.innerHTML = 'Add School'; return; }

      const principalName = [principalFirstName, principalLastName].filter(Boolean).join(' ') || null;
      const schoolRes = await api('POST', '/api/schools', {
        organization_id: orgId,
        school_name: fd.get('school_name').trim(),
        school_type: fd.get('school_type'),
        city: fd.get('city').trim() || null,
        state: fd.get('state').trim().toUpperCase() || null,
        zip_code: fd.get('zip_code').trim() || null,
        principal_name: principalName,
        principal_email: principalEmail || null,
      });

      // Create principal login account if email + password were provided
      if (principalEmail && principalPassword && principalFirstName) {
        const newSchoolId = schoolRes.school?.school_id;
        try {
          await api('POST', '/api/users', {
            first_name: principalFirstName,
            last_name: principalLastName || principalFirstName,
            email: principalEmail,
            role: 'principal',
            password: principalPassword,
            school_id: newSchoolId,
          });
        } catch (userErr) {
          // School was created — warn but don't roll back
          closeModal();
          showAlert(`School added, but could not create principal login: ${userErr.message}`, 'warning');
          if (onSuccess) onSuccess();
          else loadSchoolsPage(document.getElementById('page-main'));
          return;
        }
      }

      closeModal();
      showAlert(principalEmail && principalPassword ? 'School added and principal account created!' : 'School added successfully!', 'success');
      if (onSuccess) onSuccess();
      else loadSchoolsPage(document.getElementById('page-main'));
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.innerHTML = 'Add School';
    }
  });
}

async function openEditSchoolModal(schoolId) {
  const numericId = Number(schoolId);
  let school = null;
  try {
    const d = await api('GET', '/api/admin/schools');
    school = (d.schools || []).find(s => s.school_id === numericId);
  } catch (_) {}
  if (!school) { showAlert('Could not load school details.', 'error'); return; }

  openModal(`
    <div class="modal-header"><h2 class="modal-title">Edit School</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <form id="edit-school-form" class="modal-body form-stack">
      <div class="form-group"><label class="form-label">School Name *</label>
        <input class="form-input" name="school_name" value="${esc(school.school_name)}" required /></div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">City</label>
          <input class="form-input" name="city" value="${esc(school.city || '')}" /></div>
        <div class="form-group"><label class="form-label">State</label>
          <input class="form-input" name="state" value="${esc(school.state || '')}" maxlength="2" style="text-transform:uppercase;" /></div>
        <div class="form-group"><label class="form-label">Zip Code</label>
          <input class="form-input" name="zip_code" value="${esc(school.zip_code || '')}" maxlength="10" /></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Principal Name</label>
          <input class="form-input" name="principal_name" value="${esc(school.principal_name || '')}" /></div>
        <div class="form-group"><label class="form-label">Principal Email</label>
          <input class="form-input" type="email" name="principal_email" value="${esc(school.principal_email || '')}" /></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="edit-school-submit">Save Changes</button>
      </div>
    </form>`);

  document.getElementById('edit-school-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = document.getElementById('edit-school-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    try {
      await api('PATCH', `/api/schools/${schoolId}`, {
        school_name: fd.get('school_name').trim(),
        city: fd.get('city').trim() || null,
        state: fd.get('state').trim().toUpperCase() || null,
        zip_code: fd.get('zip_code').trim() || null,
        principal_name: fd.get('principal_name').trim() || null,
        principal_email: fd.get('principal_email').trim().toLowerCase() || null,
      });
      closeModal();
      showAlert('School updated.', 'success');
      loadSchoolsPage(document.getElementById('page-main'));
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.innerHTML = 'Save Changes';
    }
  });
}

/* ============================================================
   14. COACHES PAGE
   ============================================================ */
async function loadCoachesPage(container) {
  container.innerHTML = `
    <div class="page-header">
      <div><div class="text-h2">Coaches</div><div class="text-caption">All active coaches and their weekly activity</div></div>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-ghost" id="send-invites-btn" type="button">Send Invites</button>
        <button class="btn btn-primary" id="add-coach-btn" type="button">${iconPlus()} Add Coach</button>
      </div>
    </div>
    <div id="coaches-content">${renderSkeleton(5)}</div>`;
  document.getElementById('add-coach-btn')?.addEventListener('click', openAddCoachModal);
  document.getElementById('send-invites-btn')?.addEventListener('click', openSendInvitesModal);

  try {
    const d = await api('GET', '/api/admin/coaches');
    const coaches = d.coaches || [];
    const cc = document.getElementById('coaches-content');
    if (!cc) return;
    if (!coaches.length) {
      cc.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">${iconCoaches()}</div>
        <div class="empty-state-title">No coaches yet</div>
        <div class="empty-state-text">Add your first coach to get started.</div>
        <button class="btn btn-primary" onclick="document.getElementById('add-coach-btn').click()">Add First Coach</button>
      </div>`; return;
    }
    cc.innerHTML = `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Coach</th><th>Role</th><th>School</th><th>Score</th><th>EODs This Week</th><th>Late</th><th>Incidents</th><th></th></tr></thead>
          <tbody>${coaches.map(c => {
            const late = c.late_submissions_this_week ?? 0;
            const score = c.rolling_score != null ? Math.round(c.rolling_score) : null;
            const band = c.rolling_band || '';
            const bandClass = {'Exceptional':'badge-success','Strong':'badge-success','Meeting Expectations':'','Developing':'badge-warning','Needs Improvement':'badge-error'}[band] || '';
            const _sid = _modalStore.set(c);
            return `<tr>
              <td><strong>${esc(c.first_name)} ${esc(c.last_name)}</strong><div class="text-caption">${esc(c.email)}</div></td>
              <td><span class="badge">${fmtLabel(c.role)}</span></td>
              <td>${esc(c.school_name || '—')}</td>
              <td>${score != null ? `<span class="badge ${bandClass}">${score} · ${esc(band)}</span>` : '<span class="text-muted">—</span>'}</td>
              <td>${c.eod_submissions_this_week ?? 0}</td>
              <td class="${late > 0 ? 'text-error' : ''}">${late}</td>
              <td>${c.incidents_filed_this_week ?? 0}</td>
              <td><button class="btn btn-ghost btn-sm" onclick="openCoachScorecardModal(_modalStore.get(${_sid}))">Scorecard</button></td>
            </tr>`;}).join('')}
          </tbody>
        </table>
      </div>`;
  } catch (err) {
    const cc = document.getElementById('coaches-content');
    if (cc) cc.innerHTML = errorCard(err.message);
  }
}

async function openCoachScorecardModal(coach) {
  openModal(`
    <div class="modal-header">
      <h2 class="modal-title">${esc(coach.first_name)} ${esc(coach.last_name)} — Scorecard</h2>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <div class="modal-body">
      <div id="scorecard-content">${renderSkeleton(3)}</div>
    </div>`);

  try {
    const d = await api('GET', `/api/admin/coaches/${coach.staff_id}/score`);
    const sc = d.scorecard || {};
    const snaps = d.snapshots || [];
    const el = document.getElementById('scorecard-content');
    if (!el) return;

    const overall = sc.overall_score != null ? Math.round(sc.overall_score) : null;
    const bandClass = {'Exceptional':'badge-success','Strong':'badge-success','Meeting Expectations':'','Developing':'badge-warning','Needs Improvement':'badge-error'}[sc.performance_band] || '';

    const pillarBar = (label, score, detail) => {
      const pct = score != null ? Math.round(score) : 0;
      const color = pct >= 75 ? 'var(--color-success)' : pct >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
      return `
        <div style="margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-weight:600;">${label}</span>
            <span>${score != null ? Math.round(score) + '/100' : 'N/A'}</span>
          </div>
          <div style="background:var(--color-border);border-radius:4px;height:8px;">
            <div style="width:${pct}%;background:${color};border-radius:4px;height:8px;transition:width 0.4s;"></div>
          </div>
          ${detail ? `<div class="text-caption" style="margin-top:4px;">${detail}</div>` : ''}
        </div>`;
    };

    const fmtRate = r => r != null ? Math.round(r) + '%' : 'N/A';
    const complianceDetail = [
      `EOD on-time: ${fmtRate(sc.eod_ontime_rate)}`,
      `Sessions logged: ${fmtRate(sc.session_log_rate)}`,
      sc.incident_file_rate != null ? `Incident filing: ${fmtRate(sc.incident_file_rate)}` : null,
      sc.assessment_part_rate != null ? `Assessment: ${fmtRate(sc.assessment_part_rate)}` : null,
    ].filter(Boolean).join(' · ');

    const outcomesDetail = [
      sc.avg_growth != null ? `Avg growth: ${sc.avg_growth > 0 ? '+' : ''}${sc.avg_growth}pts` : null,
      `Attendance: ${fmtRate(sc.participation_rate)}`,
      sc.avg_sel_score != null ? `SEL: ${sc.avg_sel_score.toFixed(1)}/5` : null,
    ].filter(Boolean).join(' · ');

    const obsDetail = sc.observation_count
      ? `Based on ${sc.observation_count} observation${sc.observation_count > 1 ? 's' : ''}`
      : 'No observations in this period';

    const historyRows = snaps.length
      ? snaps.map(s => `<tr>
          <td>${esc(s.period_start)} – ${esc(s.period_end)}</td>
          <td>${s.overall_score != null ? Math.round(s.overall_score) : '—'}</td>
          <td><span class="badge">${esc(s.performance_band || '—')}</span></td>
        </tr>`).join('')
      : `<tr><td colspan="3" class="text-muted">No frozen snapshots yet.</td></tr>`;

    el.innerHTML = `
      <div style="text-align:center;padding:16px 0 24px;">
        <div style="font-size:2.5rem;font-weight:700;color:var(--color-primary);">${overall != null ? overall : '—'}</div>
        <span class="badge ${bandClass}" style="font-size:0.9rem;">${esc(sc.performance_band || 'No data')}</span>
        <div class="text-caption" style="margin-top:4px;">Rolling 30 days · ${esc(sc.period_start || '')} → ${esc(sc.period_end || '')}</div>
      </div>
      <div style="border-top:1px solid var(--color-border);padding-top:20px;">
        ${pillarBar('Compliance', sc.compliance_score, complianceDetail)}
        ${pillarBar('Student Outcomes', sc.outcomes_score, outcomesDetail)}
        ${pillarBar('Observations', sc.observations_score, obsDetail)}
      </div>
      <div style="border-top:1px solid var(--color-border);padding-top:16px;margin-top:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <strong>Score History</strong>
          <button class="btn btn-ghost btn-sm" id="freeze-score-btn">Freeze Now</button>
        </div>
        <table class="data-table">
          <thead><tr><th>Period</th><th>Score</th><th>Band</th></tr></thead>
          <tbody>${historyRows}</tbody>
        </table>
      </div>`;

    document.getElementById('freeze-score-btn')?.addEventListener('click', async () => {
      const btn = document.getElementById('freeze-score-btn');
      btn.disabled = true; btn.textContent = 'Saving…';
      try {
        await api('POST', `/api/admin/coaches/${coach.staff_id}/score/freeze`, {});
        showAlert('Score snapshot saved.', 'success');
        closeModal();
        openCoachScorecardModal(coach);
      } catch (err) {
        showAlert(err.message, 'error');
        btn.disabled = false; btn.textContent = 'Freeze Now';
      }
    });
  } catch (err) {
    const el = document.getElementById('scorecard-content');
    if (el) el.innerHTML = errorCard(err.message);
  }
}

async function openAddCoachModal(onSuccess) {
  let schools = [];
  try { const d = await api('GET', '/api/admin/schools'); schools = d.schools || []; } catch (_) {}
  const schoolOpts = schools.map(s => `<option value="${s.school_id}">${esc(s.school_name)}</option>`).join('');

  openModal(`
    <div class="modal-header"><h2 class="modal-title">Add Coach</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <form id="add-coach-form" class="modal-body form-stack">
      <div class="form-row">
        <div class="form-group"><label class="form-label">First Name *</label><input class="form-input" name="first_name" required /></div>
        <div class="form-group"><label class="form-label">Last Name *</label><input class="form-input" name="last_name" required /></div>
      </div>
      <div class="form-group"><label class="form-label">Email *</label><input class="form-input" type="email" name="email" required /></div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Role *</label>
          <select class="form-input form-select" name="role" required>
            <option value="head_coach">Head Coach</option>
            <option value="assistant_coach">Assistant Coach</option>
            <option value="site_coordinator">Site Coordinator</option>
          </select>
        </div>
        <div class="form-group"><label class="form-label">School</label>
          <select class="form-input form-select" name="school_id">
            <option value="">Assign later…</option>${schoolOpts}
          </select>
        </div>
      </div>
      <div class="form-group"><label class="form-label">Position Title</label>
        <input class="form-input" name="position_title" placeholder="e.g. Head Coach, PE Specialist" maxlength="100" /></div>
      <div class="form-group"><label class="form-label">Temporary Password *</label>
        <input class="form-input" type="password" name="password" placeholder="Min 8 characters" minlength="8" required /></div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="add-coach-submit">Add Coach</button>
      </div>
    </form>`);

  document.getElementById('add-coach-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = document.getElementById('add-coach-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    try {
      await api('POST', '/api/users', {
        first_name: fd.get('first_name').trim(),
        last_name: fd.get('last_name').trim(),
        email: fd.get('email').trim().toLowerCase(),
        role: fd.get('role'),
        password: fd.get('password'),
        school_id: fd.get('school_id') ? parseInt(fd.get('school_id')) : null,
        position_title: fd.get('position_title').trim() || null,
      });
      closeModal();
      showAlert('Coach added successfully!', 'success');
      if (onSuccess) onSuccess();
      else loadCoachesPage(document.getElementById('page-main'));
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.innerHTML = 'Add Coach';
    }
  });
}

async function sendUserInvite(userId, btnEl) {
  if (btnEl) { btnEl.disabled = true; btnEl.textContent = 'Sending…'; }
  try {
    await api('POST', `/api/admin/users/${userId}/send-invite`);
    if (btnEl) { btnEl.textContent = 'Sent ✓'; btnEl.classList.add('btn-success'); }
    else showAlert('Invite email sent!', 'success');
  } catch (err) {
    if (btnEl) { btnEl.disabled = false; btnEl.textContent = 'Send Invite'; }
    showAlert(err.message || 'Failed to send invite.', 'error');
  }
}

async function openSendInvitesModal() {
  openModal(`
    <div class="modal-header"><h2 class="modal-title">Send Invites</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <div class="modal-body"><div class="spinner"></div><div class="loading-text">Loading coaches…</div></div>`);

  let coaches = [];
  try {
    const d = await api('GET', '/api/admin/coaches');
    coaches = d.coaches || [];
  } catch (err) {
    const mb = document.querySelector('.modal-body');
    if (mb) mb.innerHTML = errorCard(err.message); return;
  }

  const mb = document.querySelector('.modal-body');
  if (!mb) return;

  if (!coaches.length) {
    mb.innerHTML = `<div class="empty-state"><div class="empty-state-title">No coaches yet</div><div class="empty-state-text">Add coaches first, then send invites.</div></div>`;
    return;
  }

  mb.innerHTML = `
    <p style="margin:0 0 16px;color:var(--color-text-secondary);font-size:0.875rem;">Each coach will receive an email with a link to set their password. Links expire in 24 hours.</p>
    <div class="form-stack" style="gap:0;">
      ${coaches.map(c => `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--color-border);">
          <div>
            <div style="font-weight:600;">${esc(c.first_name)} ${esc(c.last_name)}</div>
            <div class="text-caption">${esc(c.email)} &middot; ${fmtLabel(c.role)}</div>
          </div>
          <button class="btn btn-ghost btn-sm" onclick="sendUserInvite(${c.user_id}, this)">Send Invite</button>
        </div>`).join('')}
    </div>`;
}

/* ============================================================
   15. INCIDENTS PAGE (Admin)
   ============================================================ */
async function loadIncidentsPage(container) {
  container.innerHTML = `<div class="text-h2" style="margin-bottom:16px;">Incidents</div><div id="incidents-content">${renderSkeleton(4)}</div>`;

  let statusFilter = 'open';

  async function fetchAndRender() {
    const ic = document.getElementById('incidents-content');
    if (!ic) return;
    ic.innerHTML = renderSkeleton(4);
    try {
      const [summary, list] = await Promise.all([
        api('GET', '/api/admin/incidents?weeks=4'),
        api('GET', `/api/admin/incidents/list?status=${statusFilter}&per_page=50`),
      ]);
      const byS = summary.by_severity || [];
      const incidents = list.incidents || [];
      const sevColor = s => ({ high: 'error', critical: 'error', medium: 'warning', low: 'secondary' }[s] || 'secondary');

      ic.innerHTML = `
        <div class="stats-grid" style="margin-bottom:20px;">
          ${statCard('Total (4 Weeks)', summary.total ?? 0, iconIncidents(), summary.total > 0 ? 'error' : '')}
          ${byS.map(s => statCard(fmtLabel(s.severity_level || 'Unknown'), s.count, iconIncidents(), sevColor(s.severity_level))).join('')}
        </div>
        <div class="card">
          <div class="card-header">
            <div class="card-title">Incident List</div>
            <div style="display:flex;gap:8px;">
              <button class="btn btn-sm ${statusFilter==='open'?'btn-primary':'btn-ghost'}" id="filter-open">Open</button>
              <button class="btn btn-sm ${statusFilter==='resolved'?'btn-primary':'btn-ghost'}" id="filter-resolved">Resolved</button>
              <button class="btn btn-sm ${statusFilter===''?'btn-primary':'btn-ghost'}" id="filter-all">All</button>
            </div>
          </div>
          ${incidents.length ? `
          <div class="table-container"><table class="table">
            <thead><tr><th>Date</th><th>School</th><th>Reporter</th><th>Type</th><th>Severity</th><th>Status</th><th></th></tr></thead>
            <tbody>${incidents.map(i => { const _sid = _modalStore.set(i); return `<tr>
              <td>${fmtDate(i.report_date)}</td>
              <td>${esc(i.school_name)}</td>
              <td>${esc(i.reporter_name)}</td>
              <td>${fmtLabel(i.incident_type)}</td>
              <td><span class="badge badge-${sevColor(i.severity_level)}">${fmtLabel(i.severity_level)}</span></td>
              <td><span class="badge badge-${i.status==='open'?'error':'success'}">${fmtLabel(i.status)}</span></td>
              <td><button class="btn btn-ghost btn-sm" onclick="openResolveIncidentModal(_modalStore.get(${_sid}))">
                ${i.status === 'open' ? 'Review' : 'View'}
              </button></td>
            </tr>`; }).join('')}</tbody>
          </table></div>` : `<div class="empty-state"><div class="empty-state-title">No ${statusFilter} incidents</div></div>`}
        </div>`;

      document.getElementById('filter-open')?.addEventListener('click', () => { statusFilter = 'open'; fetchAndRender(); });
      document.getElementById('filter-resolved')?.addEventListener('click', () => { statusFilter = 'resolved'; fetchAndRender(); });
      document.getElementById('filter-all')?.addEventListener('click', () => { statusFilter = ''; fetchAndRender(); });
    } catch (err) {
      const ic = document.getElementById('incidents-content');
      if (ic) ic.innerHTML = errorCard(err.message);
    }
  }

  fetchAndRender();
}

function openResolveIncidentModal(incident) {
  const isOpen = incident.status === 'open';
  openModal(`
    <div class="modal-header">
      <h2 class="modal-title">${isOpen ? 'Resolve Incident' : 'Incident Detail'}</h2>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <div class="modal-body form-stack">
      <div class="card" style="background:var(--color-bg);padding:12px 16px;margin-bottom:4px;">
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
          <span class="badge badge-${ {high:'error',critical:'error',medium:'warning',low:'secondary'}[incident.severity_level]||'secondary'}">${esc(incident.severity_level)}</span>
          <span class="badge badge-${incident.status==='open'?'error':'success'}">${fmtLabel(incident.status)}</span>
          <span style="font-size:0.75rem;color:var(--color-text-secondary);">${fmtDate(incident.report_date)} · ${esc(incident.school_name)}</span>
        </div>
        <div style="font-size:0.875rem;margin-bottom:4px;"><strong>Reporter:</strong> ${esc(incident.reporter_name)}${incident.student_name ? ` &mdash; <strong>Student:</strong> ${esc(incident.student_name)}` : ''}</div>
        <div style="font-size:0.875rem;margin-bottom:4px;"><strong>Type:</strong> ${esc(incident.incident_type)}</div>
        <div style="font-size:0.875rem;margin-bottom:4px;"><strong>Description:</strong> ${esc(incident.description)}</div>
        <div style="font-size:0.875rem;"><strong>Action Taken:</strong> ${esc(incident.immediate_action_taken || '—')}</div>
      </div>
      ${incident.admin_response ? `<div class="alert alert-info"><span class="alert-body"><strong>Previous Admin Response:</strong> ${esc(incident.admin_response)}</span></div>` : ''}
      <div class="form-group">
        <label class="form-label">Admin Response / Notes</label>
        <textarea class="form-input form-textarea" id="admin-response-field" rows="3" placeholder="Explain the outcome, steps taken, or follow-up required…">${esc(incident.admin_response || '')}</textarea>
      </div>
      ${incident.resolution_notes ? `<div class="form-group"><label class="form-label">Resolution Notes</label><textarea class="form-input form-textarea" id="resolution-notes-field" rows="2">${esc(incident.resolution_notes)}</textarea></div>` : `<div class="form-group"><label class="form-label">Resolution Notes</label><textarea class="form-input form-textarea" id="resolution-notes-field" rows="2" placeholder="Optional internal notes…"></textarea></div>`}
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        ${isOpen ? `<button class="btn btn-primary" id="resolve-btn" onclick="submitIncidentResolution(${incident.incident_id}, 'resolved')">Mark Resolved</button>` : `<button class="btn btn-ghost btn-sm" id="reopen-btn" onclick="submitIncidentResolution(${incident.incident_id}, 'open')">Reopen</button><button class="btn btn-primary" id="resolve-btn" onclick="submitIncidentResolution(${incident.incident_id}, 'resolved')">Update Notes</button>`}
      </div>
    </div>`);
}

async function submitIncidentResolution(incidentId, status) {
  const btn = document.getElementById(status === 'open' ? 'reopen-btn' : 'resolve-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
  try {
    await api('PATCH', `/api/admin/incidents/${incidentId}`, {
      status,
      admin_response: document.getElementById('admin-response-field')?.value.trim() || null,
      resolution_notes: document.getElementById('resolution-notes-field')?.value.trim() || null,
    });
    closeModal();
    showAlert(status === 'resolved' ? 'Incident marked resolved.' : 'Incident reopened.', 'success');
    loadIncidentsPage(document.getElementById('page-main'));
  } catch (err) {
    showAlert(err.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = status === 'open' ? 'Reopen' : 'Mark Resolved'; }
  }
}

/* ============================================================
   16. STUDENTS GROWTH (Admin)
   ============================================================ */
async function loadStudentsGrowth(container) {
  container.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
      <div class="text-h2">Student Growth</div>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-ghost" onclick="openImportStudentsModal()">Import CSV</button>
        <button class="btn btn-primary" onclick="openAddStudentModal()">${iconPlus()} Add Student</button>
      </div>
    </div>
    <div id="growth-content">${renderSkeleton(4)}</div>`;
  let growthData = null, schoolList = [], studentList = [];
  try {
    const [gd, sd] = await Promise.all([
      api('GET', '/api/admin/students/growth'),
      api('GET', '/api/admin/schools'),
    ]);
    growthData = gd;
    schoolList = sd.schools || [];
  } catch (err) {
    const gc = document.getElementById('growth-content');
    if (gc) gc.innerHTML = errorCard(err.message); return;
  }

  async function renderStudentSection(schoolId = '', search = '') {
    const sl = document.getElementById('student-list-section');
    if (!sl) return;
    sl.innerHTML = renderSkeleton(3);
    try {
      const params = new URLSearchParams({ per_page: 200 });
      if (schoolId) params.set('school_id', schoolId);
      if (search) params.set('search', search);
      const sd2 = await api('GET', `/api/students?${params}`);
      const sts = sd2.students || [];
      const total = sd2.total || sts.length;
      sl.innerHTML = sts.length ? `
        ${total > sts.length ? `<div class="text-caption" style="margin-bottom:8px;">Showing ${sts.length} of ${total} students — refine your search to see more.</div>` : ''}
        <div class="table-container">
          <table class="table">
            <thead><tr><th>Name</th><th>Grade</th><th>School</th><th>Avg Level</th><th></th></tr></thead>
            <tbody>${sts.map(s => {
              const lvl = s.avg_raw_level;
              const lvlColor = lvl == null ? '' : lvl >= 4 ? 'var(--color-success)' : lvl >= 3 ? 'var(--color-warning)' : 'var(--color-danger)';
              const lvlDisplay = lvl != null ? `<span style="font-weight:700;color:${lvlColor};">${typeof lvl === 'number' ? lvl.toFixed(1) : lvl}</span><span class="text-caption"> /5</span>` : '—';
              return `<tr>
              <td>${esc(s.student_last_name)}, ${esc(s.student_first_name)}</td>
              <td>${esc(s.grade_level || '—')}</td>
              <td>${esc(s.school_name || '—')}</td>
              <td>${lvlDisplay}</td>
              <td><button class="btn btn-ghost btn-sm" onclick="openStudentProgressModal(${s.student_id})">Progress</button></td>
            </tr>`;
            }).join('')}</tbody>
          </table>
        </div>` : `<div class="empty-state"><div class="empty-state-title">No students found</div></div>`;
    } catch (e) { sl.innerHTML = errorCard(e.message); }
  }

  const gc = document.getElementById('growth-content');
  if (!gc) return;
  const byS = growthData?.by_school || [];
  const schoolOpts = schoolList.map(s => `<option value="${s.school_id}">${esc(s.school_name)}</option>`).join('');

  gc.innerHTML = `
    <div class="stats-grid" style="margin-bottom:20px;">
      ${statCard('Total Students', growthData?.total_students ?? 0, iconStudents(), '')}
      ${statCard('Assessed', growthData?.assessed_students ?? 0, iconAssess(), 'accent')}
    </div>
    ${byS.length ? `
    <div class="card" style="margin-bottom:20px;">
      <div class="card-header"><div class="card-title">Coverage by School</div></div>
      <div class="table-container"><table class="table">
        <thead><tr><th>School</th><th>Total</th><th>Assessed</th><th>Coverage</th></tr></thead>
        <tbody>${byS.map(s => {
          const pct = s.total_students ? Math.round(s.assessed_count / s.total_students * 100) : 0;
          return `<tr>
            <td>${esc(s.school_name)}</td>
            <td>${s.total_students}</td>
            <td>${s.assessed_count}</td>
            <td><div style="display:flex;align-items:center;gap:8px;">
              <div style="flex:1;background:var(--color-border);border-radius:4px;height:6px;">
                <div style="width:${pct}%;background:var(--color-primary);border-radius:4px;height:6px;"></div>
              </div>
              <span style="font-size:0.75rem;min-width:32px;">${pct}%</span>
            </div></td>
          </tr>`;
        }).join('')}</tbody>
      </table></div>
    </div>` : ''}
    <div class="card">
      <div class="card-header">
        <div class="card-title">Student Roster</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <select class="form-input" id="school-filter-growth" style="width:auto;">
            <option value="">All Schools</option>${schoolOpts}
          </select>
          <input class="form-input" id="student-search-growth" type="search" placeholder="Search name…" style="width:180px;" />
        </div>
      </div>
      <div id="student-list-section">${renderSkeleton(3)}</div>
    </div>`;

  renderStudentSection();

  let searchTimer;
  document.getElementById('school-filter-growth')?.addEventListener('change', e => {
    renderStudentSection(e.target.value, document.getElementById('student-search-growth')?.value || '');
  });
  document.getElementById('student-search-growth')?.addEventListener('input', e => {
    clearTimeout(searchTimer);
    const school = document.getElementById('school-filter-growth')?.value || '';
    searchTimer = setTimeout(() => renderStudentSection(school, e.target.value), 350);
  });
}

async function openAddStudentModal() {
  let schools = [];
  try { const d = await api('GET', '/api/admin/schools'); schools = d.schools || []; } catch (_) {}
  const schoolOpts = schools.map(s => `<option value="${s.school_id}">${esc(s.school_name)}</option>`).join('');
  const today = new Date().toISOString().slice(0, 10);

  openModal(`
    <div class="modal-header"><h2 class="modal-title">Add Student</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <form id="add-student-form" class="modal-body form-stack">
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">First Name *</label>
          <input class="form-input" name="student_first_name" required maxlength="100" />
        </div>
        <div class="form-group">
          <label class="form-label">Last Name *</label>
          <input class="form-input" name="student_last_name" required maxlength="100" />
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">School *</label>
          <select class="form-input form-select" name="school_id" required><option value="">Select school…</option>${schoolOpts}</select>
        </div>
        <div class="form-group">
          <label class="form-label">Grade Level *</label>
          <select class="form-input form-select" name="grade_level" required>
            <option value="">Select…</option>
            <option value="K">Kindergarten</option>
            <option value="1">1st Grade</option>
            <option value="2">2nd Grade</option>
            <option value="3">3rd Grade</option>
            <option value="4">4th Grade</option>
            <option value="5">5th Grade</option>
            <option value="6">6th Grade</option>
            <option value="7">7th Grade</option>
            <option value="8">8th Grade</option>
          </select>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Student ID</label>
          <input class="form-input" name="local_student_identifier" maxlength="50" placeholder="Optional" />
        </div>
        <div class="form-group">
          <label class="form-label">Enrollment Date</label>
          <input class="form-input" type="date" name="enrollment_start" value="${today}" />
        </div>
      </div>
      <div style="border:1px solid #e5e7eb; border-radius:8px; padding:16px; background:#f9fafb;">
        <p style="margin:0 0 4px; font-weight:600; font-size:14px;">Parent / Guardian Account <span style="font-weight:400; color:#6b7280; font-size:12px;">(optional)</span></p>
        <p style="margin:0 0 12px; font-size:12px; color:#6b7280;">Fill this in to create a login so the parent can view their child's progress.</p>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">First Name</label>
            <input class="form-input" name="parent_first_name" placeholder="Maria" />
          </div>
          <div class="form-group">
            <label class="form-label">Last Name</label>
            <input class="form-input" name="parent_last_name" placeholder="Garcia" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Email</label>
            <input class="form-input" type="email" name="parent_email" placeholder="parent@email.com" />
          </div>
          <div class="form-group">
            <label class="form-label">Temporary Password</label>
            <input class="form-input" type="password" name="parent_password" placeholder="Min 8 characters" />
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="add-student-submit">Add Student</button>
      </div>
    </form>`);

  document.getElementById('add-student-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('add-student-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    const fd = new FormData(e.target);

    const parentFirstName = fd.get('parent_first_name').trim();
    const parentLastName = fd.get('parent_last_name').trim();
    const parentEmail = fd.get('parent_email').trim().toLowerCase();
    const parentPassword = fd.get('parent_password');

    // Validate parent fields if any are filled in
    const parentPartial = parentFirstName || parentEmail || parentPassword;
    if (parentPartial) {
      if (!parentFirstName || !parentEmail || !parentPassword) {
        showAlert('To create a parent account, fill in first name, email, and password.', 'error');
        btn.disabled = false; btn.textContent = 'Add Student'; return;
      }
      if (parentPassword.length < 8) {
        showAlert('Parent password must be at least 8 characters.', 'error');
        btn.disabled = false; btn.textContent = 'Add Student'; return;
      }
    }

    try {
      const studentRes = await api('POST', '/api/students', {
        student_first_name: fd.get('student_first_name').trim(),
        student_last_name: fd.get('student_last_name').trim(),
        school_id: parseInt(fd.get('school_id')),
        grade_level: fd.get('grade_level'),
        local_student_identifier: fd.get('local_student_identifier').trim() || null,
        enrollment_start: fd.get('enrollment_start') || null,
      });

      // Create parent account and link to student if provided
      if (parentFirstName && parentEmail && parentPassword) {
        try {
          const parentRes = await api('POST', '/api/users', {
            first_name: parentFirstName,
            last_name: parentLastName || parentFirstName,
            email: parentEmail,
            role: 'parent',
            password: parentPassword,
          });
          const parentId = parentRes.user?.parent_id;
          const studentId = studentRes.student?.student_id;
          if (parentId && studentId) {
            await api('PATCH', `/api/students/${studentId}`, { parent_primary_id: parentId });
          }
        } catch (parentErr) {
          closeModal();
          showAlert(`Student added, but could not create parent account: ${parentErr.message}`, 'warning');
          loadStudentsGrowth(document.getElementById('page-main'));
          return;
        }
      }

      closeModal();
      showAlert(parentPartial ? 'Student and parent account added!' : 'Student added successfully!', 'success');
      loadStudentsGrowth(document.getElementById('page-main'));
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.textContent = 'Add Student';
    }
  });
}

async function openImportStudentsModal() {
  let schools = [];
  try { const d = await api('GET', '/api/admin/schools'); schools = d.schools || []; } catch (_) {}

  openModal(`
    <div class="modal-header"><h2 class="modal-title">Import Students (CSV)</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <div class="modal-body form-stack">
      <p style="margin:0 0 8px;">Upload a CSV with columns: <code>first_name, last_name, grade_level, school_id</code> (optional: <code>local_student_identifier, enrollment_start</code>).</p>
      <div class="form-group"><label class="form-label">School (applies to all rows if CSV has no school_id)</label>
        <select class="form-input" id="import-school-id">
          <option value="">— use CSV school_id column —</option>
          ${schools.map(s => `<option value="${s.school_id}">${esc(s.school_name)}</option>`).join('')}
        </select>
      </div>
      <div class="form-group"><label class="form-label">CSV File *</label>
        <input type="file" accept=".csv,text/csv" id="import-csv-file" class="form-input" />
      </div>
      <div id="import-preview" style="display:none;"></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" id="import-csv-submit" onclick="submitStudentImport()">Import</button>
    </div>`);
}

async function submitStudentImport() {
  const file = document.getElementById('import-csv-file')?.files?.[0];
  if (!file) { showAlert('Please select a CSV file.', 'error'); return; }
  const schoolId = document.getElementById('import-school-id')?.value || null;
  const btn = document.getElementById('import-csv-submit');
  btn.disabled = true; btn.textContent = 'Importing…';

  try {
    const text = await file.text();
    const lines = text.trim().split('\n');
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/"/g, ''));
    const students = lines.slice(1).filter(l => l.trim()).map(line => {
      const vals = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''));
      const obj = {};
      headers.forEach((h, i) => { obj[h] = vals[i] || ''; });
      return {
        first_name: obj['first_name'] || obj['firstname'] || '',
        last_name: obj['last_name'] || obj['lastname'] || '',
        grade_level: obj['grade_level'] || obj['grade'] || '',
        school_id: schoolId ? parseInt(schoolId) : (obj['school_id'] ? parseInt(obj['school_id']) : null),
        local_student_identifier: obj['local_student_identifier'] || obj['student_id'] || null,
        enrollment_start: obj['enrollment_start'] || null,
      };
    }).filter(s => s.first_name && s.last_name);

    if (!students.length) { showAlert('No valid rows found in CSV.', 'error'); btn.disabled = false; btn.textContent = 'Import'; return; }

    const preview = document.getElementById('import-preview');
    if (preview) {
      preview.style.display = 'block';
      preview.innerHTML = `<div class="text-caption" style="margin-bottom:8px;">Preview: ${students.length} students found. Importing…</div>`;
    }

    const result = await api('POST', '/api/students/import', { students });
    closeModal();
    showAlert(`Imported ${result.imported} student${result.imported !== 1 ? 's' : ''}${result.skipped ? ` (${result.skipped} skipped)` : ''}.`, 'success');
    loadStudentsGrowth(document.getElementById('page-main'));
  } catch (err) {
    showAlert(err.message || 'Import failed.', 'error');
    btn.disabled = false; btn.textContent = 'Import';
  }
}

/* ============================================================
   17. COACH DASHBOARD
   ============================================================ */
async function loadCoachDashboard(container) {
  container.innerHTML = renderSkeleton(4);
  try {
    const [sessRes, eodRes, winRes] = await Promise.allSettled([
      api('GET', '/api/sessions?per_page=5'),
      api('GET', '/api/eod-reports?per_page=5'),
      api('GET', '/api/coach/assessment-windows'),
    ]);
    const sessions = sessRes.status === 'fulfilled' ? (sessRes.value.sessions || []) : [];
    const eods = eodRes.status === 'fulfilled' ? (eodRes.value.reports || []) : [];
    const allWindows = winRes.status === 'fulfilled' ? (winRes.value.windows || []) : [];
    const activeWindows = allWindows.filter(w => w.status === 'active');
    const todayStr = new Date().toISOString().split('T')[0];
    const todayEod = eods.find(e => e.report_date === todayStr);

    container.innerHTML = `
      <div class="welcome-card">
        <div class="welcome-greeting">Hey ${esc(state.user?.first_name || 'Coach')}! 👋</div>
        <div class="welcome-subtitle"><span class="badge badge-yellow" style="margin-right:8px;">${fmtLabel(state.user?.role || 'Coach')}</span>${todayFull()}</div>
      </div>
      ${activeWindows.length ? `<div class="alert alert-info" style="margin-bottom:16px;"><span class="alert-icon">${iconAssess()}</span><span class="alert-body"><strong>Active Assessment Window${activeWindows.length > 1 ? 's' : ''}:</strong> ${activeWindows.map(w => `${esc(w.window_name)} (${esc(w.school_name || '')} · ends ${fmtDate(w.end_date)})`).join('; ')}</span></div>` : ''}
      <div class="stats-grid">
        ${statCard('Sessions Logged', sessions.length, iconSessions(), '')}
        ${statCard("Today's EOD", todayEod ? 'Submitted ✓' : 'Pending', iconEod(), todayEod ? 'success' : 'error')}
      </div>
      <div class="cards-grid">
        <div class="card">
          <div class="card-header"><div class="card-title">Quick Actions</div></div>
          <div class="form-stack" style="gap:8px;">
            <button class="btn btn-primary btn-full" id="dash-log-session-btn" type="button" style="justify-content:flex-start;">${iconSessions()} Log Today's Session</button>
            <button class="btn btn-ghost btn-full" data-page="eod-reports" type="button" style="justify-content:flex-start;">${iconEod()} Submit EOD Report</button>
            <button class="btn btn-ghost btn-full" data-page="incidents" type="button" style="justify-content:flex-start;">${iconIncidents()} File an Incident</button>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><div class="card-title">Recent Sessions</div></div>
          ${sessions.length ? `<div class="kv-list">${sessions.slice(0, 5).map(s => `
            <div class="kv-row"><span class="kv-key">${fmtDate(s.session_date)}</span><span class="kv-val">${fmtLabel(s.session_type)}</span></div>`).join('')}
          </div>` : `<div class="empty-state-sm">No sessions logged yet.</div>`}
        </div>
      </div>`;
    $$('[data-page]', container).forEach(el => el.addEventListener('click', () => navigate(el.dataset.page)));
    document.getElementById('dash-log-session-btn')?.addEventListener('click', () => openLogSessionModal(() => loadCoachDashboard(container)));
  } catch (err) {
    container.innerHTML = errorCard(err.message);
  }
}

/* ============================================================
   18. COACH SESSIONS
   ============================================================ */
async function loadSessionsPage(container) {
  container.innerHTML = `
    <div class="page-header">
      <div><div class="text-h2">Sessions</div><div class="text-caption">Your logged coaching sessions</div></div>
      <button class="btn btn-primary" id="log-session-btn" type="button">${iconPlus()} Log Session</button>
    </div>
    <div id="sessions-content">${renderSkeleton(5)}</div>`;
  document.getElementById('log-session-btn')?.addEventListener('click', () => openLogSessionModal(() => loadSessionsPage(container)));

  try {
    const d = await api('GET', '/api/sessions?per_page=20');
    const sessions = d.sessions || [];
    const sc = document.getElementById('sessions-content');
    if (!sc) return;
    if (!sessions.length) {
      sc.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">${iconSessions()}</div>
        <div class="empty-state-title">No sessions logged yet</div>
        <div class="empty-state-text">Log your first session to get started.</div>
        <button class="btn btn-primary" onclick="document.getElementById('log-session-btn').click()">Log First Session</button>
      </div>`; return;
    }
    sc.innerHTML = `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Date</th><th>Type</th><th>School</th><th>Duration</th><th>Students</th><th>EOD Filed</th></tr></thead>
          <tbody>${sessions.map(s => `<tr>
            <td>${fmtDate(s.session_date)}</td>
            <td><span class="badge">${fmtLabel(s.session_type)}</span></td>
            <td>${esc(s.school_name || '—')}</td>
            <td>${s.duration_minutes != null ? s.duration_minutes + ' min' : '—'}</td>
            <td>${s.student_count ?? '—'}</td>
            <td>${s.eod_filed ? '<span class="text-success">✓</span>' : '<span class="text-error">Pending</span>'}</td>
          </tr>`).join('')}</tbody>
        </table>
      </div>`;
  } catch (err) {
    const sc = document.getElementById('sessions-content');
    if (sc) sc.innerHTML = errorCard(err.message);
  }
}

async function openLogSessionModal(onSuccess) {
  let students = [];
  try { const d = await api('GET', '/api/my-students'); students = d.students || []; } catch (_) {}

  const todayStr = new Date().toISOString().split('T')[0];
  openModal(`
    <div class="modal-header"><h2 class="modal-title">Log Session</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <form id="log-session-form" class="modal-body form-stack">
      <div class="form-row">
        <div class="form-group"><label class="form-label">Date *</label>
          <input class="form-input" type="date" name="session_date" value="${todayStr}" required /></div>
        <div class="form-group"><label class="form-label">Type *</label>
          <select class="form-input form-select" name="session_type" required>
            <option value="regular">Regular</option>
            <option value="enrichment">Enrichment</option>
            <option value="makeup">Makeup</option>
            <option value="assessment">Assessment</option>
          </select>
        </div>
      </div>
      <div class="form-group"><label class="form-label">Duration (minutes) *</label>
        <input class="form-input" type="number" name="duration_minutes" value="45" min="5" max="480" required /></div>
      <div class="form-group"><label class="form-label">Notes</label>
        <textarea class="form-input form-textarea" name="notes" placeholder="Session notes (optional)" rows="3"></textarea></div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="log-session-submit">Log Session</button>
      </div>
    </form>`);

  document.getElementById('log-session-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = document.getElementById('log-session-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    if (!state.user?.school_id) {
      showAlert('No school assignment on your account. Contact your administrator.', 'error');
      btn.disabled = false; btn.innerHTML = 'Log Session';
      return;
    }
    if (!state.user?.program_id) {
      showAlert('No active program assigned to your account. Contact your administrator.', 'error');
      btn.disabled = false; btn.innerHTML = 'Log Session';
      return;
    }
    try {
      await api('POST', '/api/sessions', {
        school_id: state.user?.school_id,
        program_id: state.user?.program_id,
        session_date: fd.get('session_date'),
        session_type: fd.get('session_type'),
        duration_minutes: parseInt(fd.get('duration_minutes')),
        notes: fd.get('notes').trim() || null,
        student_ids: students.map(s => s.student_id),
      });
      closeModal();
      showAlert('Session logged!', 'success');
      if (onSuccess) onSuccess();
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.innerHTML = 'Log Session';
    }
  });
}

/* ============================================================
   19. COACH EOD REPORTS
   ============================================================ */
async function loadEodPage(container) {
  container.innerHTML = `
    <div class="page-header">
      <div><div class="text-h2">EOD Reports</div><div class="text-caption">Your end-of-day report history</div></div>
      <button class="btn btn-primary" id="submit-eod-btn" type="button">${iconPlus()} Submit EOD</button>
    </div>
    <div id="eod-content">${renderSkeleton(5)}</div>`;
  document.getElementById('submit-eod-btn')?.addEventListener('click', () => openEodModal(() => loadEodPage(container)));

  try {
    const d = await api('GET', '/api/eod-reports?per_page=20');
    const reports = d.reports || [];
    const ec = document.getElementById('eod-content');
    if (!ec) return;
    if (!reports.length) {
      ec.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">${iconEod()}</div>
        <div class="empty-state-title">No EOD reports yet</div>
        <div class="empty-state-text">Submit your first end-of-day report after each session.</div>
        <button class="btn btn-primary" onclick="document.getElementById('submit-eod-btn').click()">Submit First Report</button>
      </div>`; return;
    }
    ec.innerHTML = `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Date</th><th>Session</th><th>On Time</th><th>Submitted</th><th></th></tr></thead>
          <tbody>${reports.map(r => { const _eid = _modalStore.set(r); return `<tr>
            <td>${fmtDate(r.report_date)}</td>
            <td>${fmtLabel(r.session_type)}</td>
            <td>${r.submitted_on_time ? '<span class="text-success">✓ On Time</span>' : '<span class="text-error">Late</span>'}</td>
            <td>${fmtDate(r.created_at)}</td>
            <td><button class="btn btn-ghost btn-sm" aria-label="View EOD report" onclick="openEodDetailModal(_modalStore.get(${_eid}))">View</button></td>
          </tr>`; }).join('')}</tbody>
        </table>
      </div>`;
  } catch (err) {
    const ec = document.getElementById('eod-content');
    if (ec) ec.innerHTML = errorCard(err.message);
  }
}

function openEodModal(onSuccess) {
  if (!state.user?.school_id) {
    alert('You are not assigned to a school. Please contact your administrator before submitting an EOD report.');
    return;
  }
  const todayStr = new Date().toISOString().split('T')[0];
  const yesNo = (name, required=false) => `
    <select class="form-input" name="${name}"${required ? ' required' : ''}>
      <option value="">— Select —</option>
      <option value="yes">Yes</option>
      <option value="no">No</option>
    </select>`;
  const yesNoMaybe = (name) => `
    <select class="form-input" name="${name}">
      <option value="">— Not sure / N/A —</option>
      <option value="yes">Yes</option>
      <option value="no">No</option>
    </select>`;

  openModal(`
    <div class="modal-header">
      <h2 class="modal-title">Submit EOD Report</h2>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <form id="eod-form" style="display:contents;"><div class="modal-body form-stack">

      <div class="form-section-label" style="font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-text-muted);margin:8px 0 4px;">Report Info</div>
      <div class="form-group"><label class="form-label">Report Date *</label>
        <input class="form-input" type="date" name="report_date" value="${todayStr}" required /></div>

      <div class="form-section-label" style="font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-text-muted);margin:16px 0 4px;">Activities</div>
      <div class="form-group"><label class="form-label">Activities Completed *</label>
        <textarea class="form-input form-textarea" name="activities_completed" placeholder="What activities were covered today?" rows="3" maxlength="1500" required></textarea></div>

      <div class="form-section-label" style="font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-text-muted);margin:16px 0 4px;">Student Summary</div>
      <div class="form-group"><label class="form-label">Attendance Summary</label>
        <textarea class="form-input form-textarea" name="attendance_summary" placeholder="How many students attended? Any absences to note?" rows="2" maxlength="500"></textarea></div>
      <div class="form-group"><label class="form-label">Student Engagement Summary *</label>
        <textarea class="form-input form-textarea" name="student_engagement_summary" placeholder="Overall engagement level, highlights, participation notes" rows="2" maxlength="1000" required></textarea></div>
      <div class="form-group"><label class="form-label">Behavior Summary</label>
        <textarea class="form-input form-textarea" name="behavior_summary" placeholder="Overall behavior, any notable incidents" rows="2" maxlength="500"></textarea></div>
      <div class="form-group"><label class="form-label">Success Story</label>
        <textarea class="form-input form-textarea" name="success_story" placeholder="A positive moment or win from today" rows="2" maxlength="500"></textarea></div>
      <div class="form-group"><label class="form-label">Challenge Summary</label>
        <textarea class="form-input form-textarea" name="challenge_summary" placeholder="What challenges came up today?" rows="2" maxlength="500"></textarea></div>

      <div class="form-section-label" style="font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-text-muted);margin:16px 0 4px;">Coach Checklist</div>
      <div class="form-group"><label class="form-label">All coaches clocked in?</label>${yesNoMaybe('coaches_clocked_in')}</div>
      <div class="form-group"><label class="form-label">Coaches arrived late?</label>
        <input class="form-input" type="text" name="late_arrivals" placeholder="Names or details (leave blank if none)" /></div>
      <div class="form-group"><label class="form-label">All coaches in uniform?</label>${yesNoMaybe('coaches_in_uniform')}</div>
      <div class="form-group"><label class="form-label">Coaches setup ready before students arrived?</label>${yesNoMaybe('coaches_setup_ready')}</div>
      <div class="form-group"><label class="form-label">Equipment accounted for?</label>${yesNoMaybe('equipment_accounted')}</div>
      <div class="form-group"><label class="form-label">Transitions between activities orderly?</label>${yesNoMaybe('transitions_orderly')}</div>
      <div class="form-group"><label class="form-label">Yard/space supervised at all times?</label>${yesNoMaybe('yard_supervised')}</div>
      <div class="form-group"><label class="form-label">Curriculum followed as planned?</label>${yesNoMaybe('curriculum_followed')}</div>
      <div class="form-group"><label class="form-label">Verbal warnings issued?</label>
        <input class="form-input" type="text" name="verbal_warnings" placeholder="Names or details (leave blank if none)" /></div>
      <div class="form-group"><label class="form-label">HR app issues?</label>
        <input class="form-input" type="text" name="hr_app_issues" placeholder="Describe any HR/app problems (leave blank if none)" /></div>
      <div class="form-group"><label class="form-label">Equipment requests</label>
        <input class="form-input" type="text" name="equipment_requests" placeholder="Any equipment needed?" /></div>

      <div class="form-section-label" style="font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-text-muted);margin:16px 0 4px;">Incidents</div>
      <div class="form-group"><label class="form-label">Any injury or safety incident today? *</label>${yesNo('injury_incident_flag', true)}</div>
      <div class="form-group"><label class="form-label">Incident report filed?</label>${yesNoMaybe('incident_report_filed')}</div>
      <div class="form-group"><label class="form-label">Followup needed?</label>${yesNo('followup_needed', true)}</div>
      <div class="form-group"><label class="form-label">Safety hazards observed</label>
        <input class="form-input" type="text" name="safety_hazards" placeholder="Describe any safety hazards (leave blank if none)" /></div>

      <div class="form-section-label" style="font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-text-muted);margin:16px 0 4px;">School Concerns</div>
      <div class="form-group"><label class="form-label">School concerns (describe any issues with the school)</label>
        <textarea class="form-input form-textarea" name="school_concerns" placeholder="Leave blank if none" rows="2" maxlength="1000"></textarea></div>
      <div class="form-group"><label class="form-label">School concerns resolved?</label>${yesNoMaybe('school_concerns_resolved')}</div>
      <div class="form-group"><label class="form-label">School concerns notes</label>
        <textarea class="form-input form-textarea" name="school_concerns_notes" placeholder="Details about any school concerns" rows="2" maxlength="1000"></textarea></div>
      <div class="form-group"><label class="form-label">Schedule changes</label>
        <input class="form-input" type="text" name="schedule_changes" placeholder="Any changes to the scheduled program today?" /></div>

      <div class="form-section-label" style="font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-text-muted);margin:16px 0 4px;">Communication</div>
      <div class="form-group"><label class="form-label">Principal communication needed? *</label>${yesNo('principal_communication_needed', true)}</div>
      <div class="form-group"><label class="form-label">Principal communication notes</label>
        <textarea class="form-input form-textarea" name="principal_communication_notes" placeholder="What does the principal need to know?" rows="2" maxlength="1000"></textarea></div>
      <div class="form-group"><label class="form-label">Ufit Standards Notes *</label>
        <textarea class="form-input form-textarea" name="ufit_standards_notes" placeholder="Notes on Ufit curriculum and standards compliance" rows="2" maxlength="1000" required></textarea></div>
      <div class="form-group"><label class="form-label">Additional Notes</label>
        <textarea class="form-input form-textarea" name="notes" placeholder="Anything else to report?" rows="2" maxlength="1000"></textarea></div>

    </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="eod-submit">Submit Report</button>
      </div>
    </form>`);

  const parseBool = (val, nullable=false) => {
    if (val === 'yes') return true;
    if (val === 'no') return false;
    return nullable ? null : false;
  };

  document.getElementById('eod-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = document.getElementById('eod-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    if (!state.user?.school_id) {
      showAlert('No school assignment on your account. Contact your administrator.', 'error');
      btn.disabled = false; btn.innerHTML = 'Submit Report';
      return;
    }
    const strOrNull = f => { const v = fd.get(f)?.trim(); return v || null; };
    try {
      await api('POST', '/api/eod-reports', {
        school_id: state.user.school_id,
        program_id: state.user.program_id || null,
        report_date: fd.get('report_date'),
        activities_completed: fd.get('activities_completed').trim(),
        student_engagement_summary: fd.get('student_engagement_summary').trim(),
        ufit_standards_notes: fd.get('ufit_standards_notes').trim(),
        attendance_summary: strOrNull('attendance_summary'),
        behavior_summary: strOrNull('behavior_summary'),
        success_story: strOrNull('success_story'),
        challenge_summary: strOrNull('challenge_summary'),
        notes: strOrNull('notes'),
        injury_incident_flag: parseBool(fd.get('injury_incident_flag')),
        followup_needed: parseBool(fd.get('followup_needed')),
        principal_communication_needed: parseBool(fd.get('principal_communication_needed')),
        incident_report_filed: parseBool(fd.get('incident_report_filed'), true),
        school_concerns: strOrNull('school_concerns'),
        school_concerns_resolved: parseBool(fd.get('school_concerns_resolved'), true),
        school_concerns_notes: strOrNull('school_concerns_notes'),
        schedule_changes: strOrNull('schedule_changes'),
        coaches_clocked_in: parseBool(fd.get('coaches_clocked_in'), true),
        late_arrivals: strOrNull('late_arrivals'),
        coaches_in_uniform: parseBool(fd.get('coaches_in_uniform'), true),
        coaches_setup_ready: parseBool(fd.get('coaches_setup_ready'), true),
        equipment_accounted: parseBool(fd.get('equipment_accounted'), true),
        transitions_orderly: parseBool(fd.get('transitions_orderly'), true),
        yard_supervised: parseBool(fd.get('yard_supervised'), true),
        curriculum_followed: parseBool(fd.get('curriculum_followed'), true),
        verbal_warnings: strOrNull('verbal_warnings'),
        hr_app_issues: strOrNull('hr_app_issues'),
        safety_hazards: strOrNull('safety_hazards'),
        equipment_requests: strOrNull('equipment_requests'),
        principal_communication_notes: strOrNull('principal_communication_notes'),
      });
      closeModal();
      showAlert('EOD report submitted!', 'success');
      if (onSuccess) onSuccess();
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.innerHTML = 'Submit Report';
    }
  });
}

function openEodDetailModal(r) {
  if (!r) return;

  // ── helpers ──────────────────────────────────────────────────────────────
  const check = v => v === true || v === 1
    ? '<span style="color:var(--color-success);font-size:1.1rem;font-weight:700;">✓</span>'
    : (v === false || v === 0)
    ? '<span style="color:var(--color-danger);font-size:1.1rem;font-weight:700;">✗</span>'
    : '<span style="color:var(--color-text-secondary);">—</span>';
  const flag = v => v === true || v === 1
    ? '<span class="badge badge-error">Yes</span>'
    : '<span class="badge badge-secondary" style="opacity:.6;">No</span>';

  // Section heading
  const sh = label => `<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--color-text-secondary);margin-bottom:12px;padding-bottom:6px;border-bottom:2px solid var(--color-border);">${label}</div>`;

  // Checklist item row
  const chk = (label, val) => `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-bottom:1px solid var(--color-border);">
      <span style="font-size:0.875rem;">${label}</span>
      ${check(val)}
    </div>`;

  // Field box — each field gets its own bordered card with label above, value inside
  const field = (label, val) => {
    if (!val) return '';
    return `
    <div style="border:1px solid var(--color-border);border-radius:8px;overflow:hidden;margin-bottom:10px;">
      <div style="background:var(--color-surface-alt,#f8fafc);padding:5px 12px;border-bottom:1px solid var(--color-border);">
        <span style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:var(--color-text-secondary);">${label}</span>
      </div>
      <div style="padding:10px 12px;font-size:0.9rem;line-height:1.55;color:var(--color-text);">${esc(val)}</div>
    </div>`;
  };

  // Two-column grid wrapper for field boxes
  const grid2 = (...fields) => {
    const rendered = fields.filter(Boolean);
    if (!rendered.length) return '';
    return `<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:0;">${rendered.join('')}</div>`;
  };

  const timely = r.submitted_on_time
    ? '<span class="badge badge-success">On Time</span>'
    : '<span class="badge badge-error">Late</span>';

  openModal(`
    <div class="modal-header">
      <div>
        <h2 class="modal-title" style="margin-bottom:2px;">EOD Report</h2>
        <div style="font-size:0.8rem;color:var(--color-text-secondary);">${fmtDate(r.report_date)} &mdash; ${esc(r.school_name || '—')}</div>
      </div>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>

    <div class="modal-body" style="max-height:72vh;overflow-y:auto;padding:0 20px 20px;">

      <!-- ── Meta strip ─────────────────────────────────────────────────── -->
      <div style="display:flex;gap:12px;flex-wrap:wrap;padding:14px 0 18px;border-bottom:1px solid var(--color-border);margin-bottom:20px;">
        <div style="flex:1;min-width:120px;">
          <div style="font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-secondary);margin-bottom:2px;">Coach</div>
          <div style="font-weight:600;">${esc(r.coach_name || '—')}</div>
        </div>
        <div style="flex:1;min-width:120px;">
          <div style="font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-secondary);margin-bottom:2px;">School</div>
          <div style="font-weight:600;">${esc(r.school_name || '—')}</div>
        </div>
        <div style="flex:1;min-width:100px;">
          <div style="font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-secondary);margin-bottom:2px;">Session Type</div>
          <div>${esc(r.session_type ? fmtLabel(r.session_type) : '—')}</div>
        </div>
        <div style="flex:1;min-width:100px;">
          <div style="font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-secondary);margin-bottom:2px;">Submission</div>
          <div>${timely}</div>
        </div>
      </div>

      <!-- ── Session Summary ────────────────────────────────────────────── -->
      <div style="margin-bottom:24px;">
        ${sh('Session Summary')}
        ${field('Activities Completed', r.activities_completed)}
        ${grid2(
            field('Student Engagement', r.student_engagement_summary),
            field('Attendance', r.attendance_summary)
          )}
        ${field('Behavior', r.behavior_summary)}
        ${grid2(
            field('Success Story / Highlight', r.success_story),
            field('Challenges', r.challenge_summary)
          )}
      </div>

      <!-- ── Operations Checklist ───────────────────────────────────────── -->
      <div style="margin-bottom:24px;">
        ${sh('Operations Checklist')}
        <div style="border:1px solid var(--color-border);border-radius:8px;overflow:hidden;">
          ${chk('Coaches Clocked In', r.coaches_clocked_in)}
          ${chk('In Uniform', r.coaches_in_uniform)}
          ${chk('Setup Ready Before Students', r.coaches_setup_ready)}
          ${chk('Equipment Accounted For', r.equipment_accounted)}
          ${chk('Transitions Orderly', r.transitions_orderly)}
          ${chk('Yard Supervised', r.yard_supervised)}
          <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;">
            <span style="font-size:0.875rem;">Curriculum Followed</span>
            ${check(r.curriculum_followed)}
          </div>
        </div>
      </div>

      <!-- ── Flags & Incidents ──────────────────────────────────────────── -->
      <div style="margin-bottom:24px;">
        ${sh('Flags & Incidents')}
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px;">
          <div style="border:1px solid ${r.injury_incident_flag ? 'var(--color-danger,#dc2626)' : 'var(--color-border)'};border-radius:8px;overflow:hidden;">
            <div style="background:${r.injury_incident_flag ? '#fef2f2' : 'var(--color-surface-alt,#f8fafc)'};padding:5px 12px;border-bottom:1px solid ${r.injury_incident_flag ? 'var(--color-danger,#dc2626)' : 'var(--color-border)'};">
              <span style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:${r.injury_incident_flag ? 'var(--color-danger,#dc2626)' : 'var(--color-text-secondary)'};">Injury / Incident</span>
            </div>
            <div style="padding:10px 12px;">${flag(r.injury_incident_flag)}</div>
          </div>
          <div style="border:1px solid ${r.followup_needed ? 'var(--color-warning,#f59e0b)' : 'var(--color-border)'};border-radius:8px;overflow:hidden;">
            <div style="background:${r.followup_needed ? '#fffbeb' : 'var(--color-surface-alt,#f8fafc)'};padding:5px 12px;border-bottom:1px solid ${r.followup_needed ? 'var(--color-warning,#f59e0b)' : 'var(--color-border)'};">
              <span style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:${r.followup_needed ? 'var(--color-warning,#f59e0b)' : 'var(--color-text-secondary)'};">Follow-up Needed</span>
            </div>
            <div style="padding:10px 12px;">${flag(r.followup_needed)}</div>
          </div>
          <div style="border:1px solid var(--color-border);border-radius:8px;overflow:hidden;">
            <div style="background:var(--color-surface-alt,#f8fafc);padding:5px 12px;border-bottom:1px solid var(--color-border);">
              <span style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--color-text-secondary);">Incident Report Filed</span>
            </div>
            <div style="padding:10px 12px;">${check(r.incident_report_filed)}</div>
          </div>
        </div>
        ${grid2(
            field('Late Arrivals', r.late_arrivals),
            field('Verbal Warnings', r.verbal_warnings)
          )}
        ${grid2(
            field('Safety Hazards', r.safety_hazards),
            field('HR App Issues', r.hr_app_issues)
          )}
      </div>

      <!-- ── School & Admin Notes ───────────────────────────────────────── -->
      <div style="margin-bottom:8px;">
        ${sh('School & Admin Notes')}
        ${r.school_concerns ? `
          <div style="border:1px solid var(--color-warning,#f59e0b);border-radius:8px;overflow:hidden;margin-bottom:10px;">
            <div style="background:#fffbeb;padding:5px 12px;border-bottom:1px solid var(--color-warning,#f59e0b);">
              <span style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--color-warning,#f59e0b);">⚠ School Concern Raised</span>
            </div>
            <div style="padding:10px 12px;font-size:0.9rem;line-height:1.5;">${esc(r.school_concerns)}</div>
            ${(r.school_concerns_resolved !== null && r.school_concerns_resolved !== undefined) ? `
            <div style="padding:6px 12px 10px;display:flex;align-items:center;gap:8px;font-size:0.8rem;border-top:1px solid var(--color-border);">
              <span style="color:var(--color-text-secondary);">Resolved:</span> ${check(r.school_concerns_resolved)}
              ${r.school_concerns_notes ? `<span style="color:var(--color-text-secondary);margin-left:4px;">${esc(r.school_concerns_notes)}</span>` : ''}
            </div>` : ''}
          </div>` : ''}
        ${r.principal_communication_needed ? `
          <div style="border:1px solid var(--color-primary);border-radius:8px;overflow:hidden;margin-bottom:10px;">
            <div style="background:#eff6ff;padding:5px 12px;border-bottom:1px solid var(--color-primary);">
              <span style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--color-primary);">Principal Communication Required</span>
            </div>
            ${r.principal_communication_notes ? `<div style="padding:10px 12px;font-size:0.9rem;line-height:1.5;">${esc(r.principal_communication_notes)}</div>` : ''}
          </div>` : ''}
        ${grid2(
            field('Equipment Requests', r.equipment_requests),
            field('Ufit Standards Notes', r.ufit_standards_notes)
          )}
        ${field('Additional Notes', r.notes)}
      </div>

    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Close</button>
    </div>`);
}

/* ============================================================
   20. MY STUDENTS (Coach)
   ============================================================ */
async function loadMyStudents(container) {
  container.innerHTML = `<div class="text-h2" style="margin-bottom:16px;">My Students</div><div id="students-content">${renderSkeleton(5)}</div>`;
  try {
    const d = await api('GET', '/api/my-students');
    const students = d.students || [];
    const sc = document.getElementById('students-content');
    if (!sc) return;
    if (!students.length) {
      sc.innerHTML = `<div class="empty-state"><div class="empty-state-icon">${iconStudents()}</div><div class="empty-state-title">No students assigned to your school yet</div></div>`;
      return;
    }
    sc.innerHTML = `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Name</th><th>Grade</th><th>Last Assessed</th><th>Avg Level</th></tr></thead>
          <tbody>${students.map(s => {
            const lvl = s.avg_raw_level;
            const lvlColor = lvl == null ? '' : lvl >= 4 ? 'var(--color-success)' : lvl >= 3 ? 'var(--color-warning)' : 'var(--color-danger)';
            const lvlDisplay = lvl != null ? `<span style="font-weight:700;color:${lvlColor};">${typeof lvl === 'number' ? lvl.toFixed(1) : lvl}</span><span class="text-caption"> /5</span>` : '—';
            return `<tr>
            <td>${esc(s.student_last_name || s.last_name)}, ${esc(s.student_first_name || s.first_name)}</td>
            <td>${esc(s.grade_level || '—')}</td>
            <td>${fmtDate(s.latest_assessment_date)}</td>
            <td>${lvlDisplay}</td>
          </tr>`;
          }).join('')}</tbody>
        </table>
      </div>`;
  } catch (err) {
    const sc = document.getElementById('students-content');
    if (sc) sc.innerHTML = errorCard(err.message);
  }
}

/* ============================================================
   21. COACH INCIDENTS
   ============================================================ */
async function loadCoachIncidents(container) {
  container.innerHTML = `
    <div class="page-header">
      <div><div class="text-h2">Incidents</div></div>
      <button class="btn btn-primary" id="file-incident-btn" type="button">${iconPlus()} File Incident</button>
    </div>
    <div id="coach-incidents-content">${renderSkeleton(4)}</div>`;
  document.getElementById('file-incident-btn')?.addEventListener('click', () => openFileIncidentModal(() => loadCoachIncidents(container)));

  try {
    const d = await api('GET', '/api/incidents?per_page=20');
    const incidents = d.incidents || [];
    const ic = document.getElementById('coach-incidents-content');
    if (!ic) return;
    if (!incidents.length) {
      ic.innerHTML = `<div class="empty-state"><div class="empty-state-icon">${iconIncidents()}</div><div class="empty-state-title">No incidents filed</div></div>`;
      return;
    }
    ic.innerHTML = `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Date</th><th>Type</th><th>Severity</th><th>Status</th><th>Admin Response</th></tr></thead>
          <tbody>${incidents.map(i => { const _sid = _modalStore.set(i); return `<tr class="clickable-row" onclick="openCoachIncidentDetailModal(_modalStore.get(${_sid}))">
            <td>${fmtDate(i.report_date)}</td>
            <td>${fmtLabel(i.incident_type)}</td>
            <td><span class="badge ${i.severity_level === 'high' || i.severity_level === 'critical' ? 'badge-error' : ''}">${fmtLabel(i.severity_level)}</span></td>
            <td><span class="badge ${i.status === 'resolved' ? 'badge-success' : ''}">${fmtLabel(i.status || 'open')}</span></td>
            <td>${i.admin_response ? `<span class="text-success">&#10003; Responded</span>` : '<span class="text-muted">Pending</span>'}</td>
          </tr>`; }).join('')}</tbody>
        </table>
      </div>`;
  } catch (err) {
    const ic = document.getElementById('coach-incidents-content');
    if (ic) ic.innerHTML = errorCard(err.message);
  }
}

function openCoachIncidentDetailModal(i) {
  const severityClass = (i.severity_level === 'high' || i.severity_level === 'critical') ? 'badge-error' : '';
  const statusClass = i.status === 'resolved' ? 'badge-success' : '';
  openModal(`
    <div class="modal-header">
      <h2 class="modal-title">Incident Report</h2>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <div class="modal-body form-stack">
      <div class="form-row">
        <div class="form-group"><label class="form-label">Date</label><div>${fmtDate(i.report_date)}</div></div>
        <div class="form-group"><label class="form-label">Status</label><div><span class="badge ${statusClass}">${fmtLabel(i.status || 'open')}</span></div></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Type</label><div>${fmtLabel(i.incident_type)}</div></div>
        <div class="form-group"><label class="form-label">Severity</label><div><span class="badge ${severityClass}">${fmtLabel(i.severity_level)}</span></div></div>
      </div>
      <div class="form-group"><label class="form-label">Description</label><div class="text-secondary">${esc(i.description || '—')}</div></div>
      ${i.immediate_action_taken ? `<div class="form-group"><label class="form-label">Action Taken</label><div class="text-secondary">${esc(i.immediate_action_taken)}</div></div>` : ''}
      ${i.admin_response || i.resolution_notes ? `
        <div style="border-top:1px solid var(--color-border);padding-top:16px;margin-top:8px;">
          <div class="text-label" style="color:var(--color-primary);margin-bottom:12px;">Admin Response</div>
          ${i.admin_response ? `<div class="form-group"><label class="form-label">Response</label><div class="text-secondary">${esc(i.admin_response)}</div></div>` : ''}
          ${i.resolution_notes ? `<div class="form-group"><label class="form-label">Resolution Notes</label><div class="text-secondary">${esc(i.resolution_notes)}</div></div>` : ''}
          ${i.acknowledged_at ? `<div class="form-group"><label class="form-label">Acknowledged</label><div class="text-secondary">${fmtDate(i.acknowledged_at)}</div></div>` : ''}
        </div>` : `
        <div style="border-top:1px solid var(--color-border);padding-top:16px;margin-top:8px;">
          <div class="text-secondary" style="font-style:italic;">No admin response yet — your report is under review.</div>
        </div>`}
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Close</button>
    </div>`);
}

function openFileIncidentModal(onSuccess) {
  const todayStr = new Date().toISOString().split('T')[0];
  openModal(`
    <div class="modal-header"><h2 class="modal-title">File Incident Report</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <form id="incident-form" class="modal-body form-stack">
      <div class="form-row">
        <div class="form-group"><label class="form-label">Date *</label>
          <input class="form-input" type="date" name="report_date" value="${todayStr}" required /></div>
        <div class="form-group"><label class="form-label">Severity *</label>
          <select class="form-input form-select" name="severity_level" required>
            <option value="low">Low</option><option value="medium" selected>Medium</option>
            <option value="high">High</option><option value="critical">Critical</option>
          </select></div>
      </div>
      <div class="form-group"><label class="form-label">Incident Type *</label>
        <select class="form-input form-select" name="incident_type" required>
          <option value="injury">Injury</option><option value="behavior">Behavior</option>
          <option value="medical">Medical</option><option value="safety">Safety Concern</option>
          <option value="property">Property Damage</option><option value="other">Other</option>
        </select></div>
      <div class="form-group"><label class="form-label">Description *</label>
        <textarea class="form-input form-textarea" name="description" rows="4" placeholder="Describe what happened…" maxlength="2000" required></textarea></div>
      <div class="form-group"><label class="form-label">Immediate Action Taken *</label>
        <textarea class="form-input form-textarea" name="immediate_action_taken" rows="2" placeholder="What action was taken immediately?" maxlength="1000" required></textarea></div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-danger" type="submit" id="incident-submit">File Report</button>
      </div>
    </form>`);

  document.getElementById('incident-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = document.getElementById('incident-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    try {
      await api('POST', '/api/incidents', {
        school_id: state.user?.school_id,
        report_date: fd.get('report_date'),
        severity_level: fd.get('severity_level'),
        incident_type: fd.get('incident_type'),
        description: fd.get('description').trim(),
        immediate_action_taken: fd.get('immediate_action_taken').trim(),
      });
      closeModal();
      showAlert('Incident report filed.', 'success');
      if (onSuccess) onSuccess();
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.innerHTML = 'File Report';
    }
  });
}

/* ============================================================
   22. COACH ASSESSMENTS (Skill Progressions)
   ============================================================ */
async function loadAssessmentsPage(container) {
  container.innerHTML = `
    <div class="page-header">
      <div><div class="text-h2">Assessments</div><div class="text-caption">Student skill progressions</div></div>
      <button class="btn btn-primary" id="new-assessment-btn" type="button">${iconPlus()} New Assessment</button>
    </div>
    <div id="assess-content">${renderSkeleton(4)}</div>`;
  document.getElementById('new-assessment-btn')?.addEventListener('click', () =>
    openNewAssessmentModal(() => loadAssessmentsPage(container))
  );

  try {
    const d = await api('GET', '/api/assessments?per_page=20');
    const items = d.assessments || [];
    const ac = document.getElementById('assess-content');
    if (!ac) return;
    if (!items.length) {
      ac.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">${iconAssess()}</div>
        <div class="empty-state-title">No assessments yet</div>
        <div class="empty-state-text">Tap "New Assessment" to score a student's skill progression.</div>
      </div>`; return;
    }
    const scoreDot = n => {
      const c = ['','#ef4444','#f97316','#eab308','#84cc16','#22c55e'][n] || '#9ca3af';
      return `<span style="display:inline-flex;align-items:center;gap:5px;background:#f3f4f6;border-radius:20px;padding:3px 9px 3px 6px;font-size:12px;font-weight:500;color:#111827;">
        <span style="width:8px;height:8px;border-radius:50%;background:${c};flex-shrink:0;"></span>${esc(fmtSkillName(s.skill_name) || String(s.skill_id))}&nbsp;<strong>${n}</strong>
      </span>`;
    };
    ac.innerHTML = `<div style="display:flex;flex-direction:column;gap:10px;">
      ${items.map(a => {
        const studentName = a.student_last_name
          ? `${esc(a.student_first_name)} ${esc(a.student_last_name)}`
          : esc(String(a.student_id));
        const scorePills = (a.scores || []).map(s => {
          const n = s.raw_level;
          const c = ['','#ef4444','#f97316','#eab308','#84cc16','#22c55e'][n] || '#9ca3af';
          return `<span style="display:inline-flex;align-items:center;gap:5px;background:#f3f4f6;border-radius:20px;padding:3px 9px 3px 6px;font-size:12px;font-weight:500;color:#111827;">
            <span style="width:8px;height:8px;border-radius:50%;background:${c};flex-shrink:0;"></span>${esc(fmtSkillName(s.skill_name) || String(s.skill_id))}&nbsp;<strong>${n}</strong>
          </span>`;
        }).join('');
        return `<div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
            <span style="font-weight:600;font-size:15px;color:#111827;">${studentName}</span>
            <span style="font-size:12px;color:#6b7280;">${fmtDate(a.assessment_date)}</span>
          </div>
          ${scorePills ? `<div style="display:flex;flex-wrap:wrap;gap:6px;">${scorePills}</div>` : '<span style="font-size:13px;color:#9ca3af;">No scores recorded</span>'}
        </div>`;
      }).join('')}
    </div>`;
  } catch (err) {
    const ac = document.getElementById('assess-content');
    if (ac) ac.innerHTML = errorCard(err.message);
  }
}

async function openNewAssessmentModal(onSuccess) {
  openModal(`<div class="modal-header"><h2 class="modal-title">New Assessment</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <div class="modal-body"><div class="spinner"></div><div class="loading-text">Loading…</div></div>`);

  let students = [], domains = [];
  try {
    const [sd, sk] = await Promise.all([
      api('GET', '/api/my-students'),
      api('GET', '/api/skills'),
    ]);
    students = sd.students || [];
    domains = sk.domains || [];
  } catch (err) {
    const mb = document.querySelector('.modal-body');
    if (mb) mb.innerHTML = errorCard(err.message); return;
  }

  if (!students.length) {
    const mb = document.querySelector('.modal-body');
    if (mb) mb.innerHTML = `<div class="empty-state"><div class="empty-state-title">No students</div><div class="empty-state-text">No students are enrolled at your school yet.</div></div>`;
    return;
  }

  const skillsWithDomain = domains.flatMap(d => d.skills.map(s => ({ ...s, domain_name: d.domain_name })));

  if (!skillsWithDomain.length) {
    const mb = document.querySelector('.modal-body');
    if (mb) mb.innerHTML = `<div class="empty-state"><div class="empty-state-title">No skills configured</div><div class="empty-state-text">An admin must add skill definitions before assessments can be scored.</div></div>`;
    return;
  }

  const todayStr = new Date().toISOString().split('T')[0];

  // Group skills by domain
  const domainMap = {};
  skillsWithDomain.forEach(s => {
    if (!domainMap[s.domain_name]) domainMap[s.domain_name] = [];
    domainMap[s.domain_name].push(s);
  });

  const scoreColors = ['','#ef4444','#f97316','#eab308','#84cc16','#22c55e'];
  const scoreLabels = ['','1','2','3','4','5'];

  const domainCards = Object.entries(domainMap).map(([domain, skills]) => {
    const skillRows = skills.map(s => `
      <div style="display:flex;align-items:center;gap:12px;padding:11px 14px;border-bottom:1px solid #f3f4f6;">
        <span style="flex:1;font-size:14px;font-weight:500;color:#111827;">${esc(fmtSkillName(s.skill_name))}</span>
        <div style="display:flex;gap:5px;">
          ${[1,2,3,4,5].map(n => `
            <label style="cursor:pointer;display:flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:50%;border:2px solid ${scoreColors[n]};font-size:15px;font-weight:700;color:${scoreColors[n]};transition:all 0.12s;" class="score-btn" data-skill="${s.skill_id}" data-val="${n}">
              <input type="radio" name="skill_${s.skill_id}" value="${n}" style="position:absolute;opacity:0;width:0;height:0;">
              ${scoreLabels[n]}
            </label>`).join('')}
        </div>
      </div>`).join('');
    return `
      <div style="border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;margin-bottom:10px;">
        <div style="background:#1e40af;color:white;padding:9px 14px;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">${esc(fmtSkillName(domain))}</div>
        ${skillRows}
      </div>`;
  }).join('');

  const modalEl = document.querySelector('.modal');
  if (!modalEl) return;
  // Replace entire modal content so we control the full layout
  modalEl.innerHTML = `
    <div class="modal-header">
      <h2 class="modal-title">New Assessment</h2>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <form id="assess-form" style="display:contents;">
      <div class="modal-body" style="padding:16px 20px;flex-shrink:0;border-bottom:1px solid #e5e7eb;overflow:visible;">
        <div class="form-group" style="margin:0 0 10px;">
          <label class="form-label">Student</label>
          <select class="form-input" name="student_id" required>
            <option value="">— Select student —</option>
            ${students.map(s => `<option value="${s.student_id}">${esc(s.student_last_name)}, ${esc(s.student_first_name)} · Grade ${esc(s.grade_level || '?')}</option>`).join('')}
          </select>
        </div>
        <div class="form-group" style="margin:0;">
          <label class="form-label">Date</label>
          <input class="form-input" type="date" name="assessment_date" value="${todayStr}" max="${todayStr}" required />
        </div>
      </div>
      <div style="flex:1;overflow-y:auto;padding:16px 20px;">
        ${domainCards}
        <textarea class="form-input form-textarea" name="notes" placeholder="Notes (optional)" rows="2" maxlength="2000" style="resize:none;font-size:14px;margin-top:4px;"></textarea>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="assess-submit">Submit</button>
      </div>
    </form>`;

  // Score button tap — fill selected, clear siblings
  document.querySelectorAll('.score-btn').forEach(lbl => {
    lbl.addEventListener('click', () => {
      const skillId = lbl.dataset.skill;
      const val = parseInt(lbl.dataset.val, 10);
      const color = scoreColors[val];
      document.querySelectorAll(`.score-btn[data-skill="${skillId}"]`).forEach(l => {
        const c = scoreColors[parseInt(l.dataset.val, 10)];
        l.style.background = '';
        l.style.color = c;
        l.style.borderColor = c;
      });
      lbl.style.background = color;
      lbl.style.color = 'white';
      lbl.style.borderColor = color;
      lbl.querySelector('input').checked = true;
    });
  });

  document.getElementById('assess-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('assess-submit');
    btn.disabled = true; btn.innerHTML = 'Saving…';
    const fd = new FormData(e.target);
    const scores = skillsWithDomain
      .map(s => {
        const raw_level = parseInt(fd.get(`skill_${s.skill_id}`), 10);
        return { skill_id: s.skill_id, raw_score: raw_level };
      })
      .filter(s => !isNaN(s.raw_score));
    if (scores.length === 0) {
      showAlert('Please score at least one skill before submitting.', 'error');
      btn.disabled = false; btn.innerHTML = 'Submit';
      return;
    }
    try {
      await api('POST', '/api/assessments', {
        student_id: parseInt(fd.get('student_id'), 10),
        assessment_date: fd.get('assessment_date'),
        window_id: null,
        scores,
        overall_assessment_notes: fd.get('notes').trim() || null,
        assessment_method: 'observational',
      });
      closeModal();
      showAlert('Assessment saved.', 'success');
      if (onSuccess) onSuccess();
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.innerHTML = 'Submit';
    }
  });
}

/* ============================================================
   23. PRINCIPAL PORTAL
   ============================================================ */
async function loadPrincipalDashboard(container) {
  container.innerHTML = renderSkeleton(5);
  try {
    const d = await api('GET', '/api/principal/dashboard');
    const school = d.school || {};
    state.principalSchool = school;
    const compliancePct = d.session_compliance_monthly != null ? Math.round(d.session_compliance_monthly * 100) : null;
    const complianceVariant = compliancePct == null ? '' : compliancePct >= 80 ? 'success' : compliancePct >= 60 ? 'warning' : 'error';
    const complianceDisplay = compliancePct != null ? compliancePct + '%' : '—';

    function domainBars(domains) {
      return domains.map(dm => {
        const score = dm.avg_score ?? 0;
        const barColor = score >= 70 ? 'var(--color-success)' : score >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
        return `
          <div style="margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
              <span style="font-weight:600;font-size:0.9rem;">${esc(dm.domain_name || dm.domain || '')}</span>
              <span style="font-size:0.85rem;color:var(--color-text-secondary);">${Math.round(score)}/100</span>
            </div>
            <div style="height:8px;background:var(--color-border);border-radius:4px;overflow:hidden;">
              <div style="height:100%;width:${Math.min(score, 100)}%;background:${barColor};border-radius:4px;transition:width 0.3s;"></div>
            </div>
            ${dm.student_count != null ? `<div class="text-caption" style="margin-top:3px;">${dm.student_count} students</div>` : ''}
          </div>`;
      }).join('');
    }

    function coachBadge(reliability) {
      const map = {
        strong:        ['badge-success',    'Strong'],
        developing:    ['badge-warning',    'Developing'],
        needs_support: ['badge-error',      'Needs Support'],
        unscored:      ['badge-secondary',  'Not Scored'],
      };
      const [cls, label] = map[reliability] || ['badge-secondary', fmtLabel(reliability || 'unscored')];
      return `<span class="badge ${cls}">${label}</span>`;
    }

    container.innerHTML = `
      <div class="welcome-card">
        <div class="welcome-greeting">${esc(school.school_name || 'Your School')}</div>
        <div class="welcome-subtitle">${school.city ? esc(school.city) + (school.state ? ', ' + esc(school.state) : '') : ''} &mdash; ${todayFull()}</div>
      </div>
      <div class="stats-grid">
        ${statCard('Total Students',        d.students_total ?? 0,    iconStudents(),  '')}
        ${statCard('Assessed',              d.students_assessed ?? 0, iconAssess(),    'accent')}
        ${statCard('Sessions This Week',    d.sessions_this_week ?? 0, iconSessions(), 'success')}
        ${statCard('Session Compliance',    complianceDisplay,         iconSessions(), complianceVariant)}
        ${statCard('Open Incidents',        d.open_incidents ?? 0,    iconIncidents(), d.open_incidents > 0 ? 'error' : '')}
      </div>
      ${d.domain_averages?.length ? `
      <div class="card">
        <div class="card-header">
          <div class="card-title">Skill Domain Averages</div>
          <button class="btn btn-ghost btn-sm" onclick="navigate('skills')">View All</button>
        </div>
        <div style="padding:0 4px;">${domainBars(d.domain_averages)}</div>
      </div>` : ''}
      <div class="card">
        <div class="card-header">
          <div class="card-title">Coaches at ${esc(school.school_name || 'Your School')}</div>
          <button class="btn btn-ghost btn-sm" onclick="navigate('students')">View Students</button>
        </div>
        ${d.coaches?.length ? `<div class="table-wrap"><table class="data-table">
          <thead><tr><th>Name</th><th>Role</th><th>Performance Score</th><th>Status</th><th></th></tr></thead>
          <tbody>${(d.coaches || []).map(c => `<tr style="cursor:pointer;" onclick="openPrincipalCoachScoreModal(${c.staff_id})">
            <td style="font-weight:600;">${esc(c.first_name)} ${esc(c.last_name)}</td>
            <td><span class="badge">${fmtLabel(c.role)}</span></td>
            <td>
              ${c.composite_score != null ? `<span style="font-weight:700;">${Math.round(c.composite_score)}/100</span>` : '<span style="color:var(--color-text-secondary);">Not yet scored</span>'}
              ${c.period_label ? `<div class="text-caption">${esc(c.period_label)}</div>` : ''}
            </td>
            <td>${coachBadge(c.reliability_badge)}</td>
            <td><span style="color:var(--color-primary);font-size:0.8rem;">View breakdown →</span></td>
          </tr>`).join('')}</tbody>
        </table></div>` : `<div class="empty-state" style="padding:24px 0 8px;">
          <div class="empty-state-text">No coaches assigned yet — contact Ufit to add coaches to this school.</div>
        </div>`}
      </div>`;
  } catch (err) {
    container.innerHTML = errorCard(err.message);
  }
}

async function loadPrincipalSkillAverages(container) {
  container.innerHTML = renderSkeleton(4);
  try {
    const d = await api('GET', '/api/principal/skill-averages');
    const overall = d.domain_averages || [];
    const byGrade = d.by_grade || [];

    function domainBars(domains) {
      if (!domains.length) return `<div class="empty-state-text" style="padding:12px 0;">No data available.</div>`;
      return domains.map(dm => {
        const score = dm.avg_score ?? 0;
        const barColor = score >= 70 ? 'var(--color-success)' : score >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
        return `
          <div style="margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
              <span style="font-weight:600;font-size:0.9rem;">${esc(dm.domain_name || dm.domain || '')}</span>
              <span style="font-size:0.85rem;color:var(--color-text-secondary);">${Math.round(score)}/100</span>
            </div>
            <div style="height:8px;background:var(--color-border);border-radius:4px;overflow:hidden;">
              <div style="height:100%;width:${Math.min(score, 100)}%;background:${barColor};border-radius:4px;transition:width 0.3s;"></div>
            </div>
            ${dm.student_count != null ? `<div class="text-caption" style="margin-top:3px;">${dm.student_count} students</div>` : ''}
          </div>`;
      }).join('');
    }

    const gradeSections = byGrade.length ? byGrade.map(g => `
      <div class="card" style="margin-top:16px;">
        <div class="card-header">
          <div class="card-title">Grade ${esc(g.grade_level || '')}</div>
        </div>
        <div style="padding:0 4px;">${domainBars(g.domains || [])}</div>
      </div>`).join('') : '';

    container.innerHTML = `
      <div class="page-header">
        <div class="text-h2">Skills Overview</div>
      </div>
      ${overall.length ? `
      <div class="card">
        <div class="card-header">
          <div class="card-title">All Grades — Domain Averages</div>
        </div>
        <div style="padding:0 4px;">${domainBars(overall)}</div>
      </div>` : `<div class="card"><div class="empty-state" style="padding:32px 0;">
        <div class="empty-state-text">No skill assessment data available yet.</div>
      </div></div>`}
      ${gradeSections}`;
  } catch (err) {
    container.innerHTML = errorCard(err.message);
  }
}

async function openPrincipalCoachScoreModal(staffId) {
  openModal(`<div class="modal-header"><h2 class="modal-title">Coach Performance</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <div class="modal-body"><div class="spinner"></div><div class="loading-text">Loading…</div></div>`);

  let d;
  try {
    d = await api('GET', `/api/principal/coaches/${staffId}/score`);
  } catch (err) {
    const mb = document.querySelector('.modal-body');
    if (mb) mb.innerHTML = errorCard(err.message);
    return;
  }

  const coach = d.coach || {};
  const snap = d.snapshot;
  const act = d.activity || {};

  const scoreBar = (score, color) => {
    const pct = Math.min(Math.round(score ?? 0), 100);
    const c = color || (pct >= 80 ? 'var(--color-success)' : pct >= 60 ? 'var(--color-warning)' : 'var(--color-danger)');
    return `<div style="display:flex;align-items:center;gap:10px;margin-top:4px;">
      <div style="flex:1;background:var(--color-border);border-radius:4px;height:10px;">
        <div style="width:${pct}%;background:${c};border-radius:4px;height:10px;transition:width 500ms;"></div>
      </div>
      <span style="min-width:44px;font-size:0.82rem;font-weight:700;text-align:right;">${score != null ? Math.round(score) : '—'}/100</span>
    </div>`;
  };

  const metricRow = (label, desc, score) => `
    <div style="padding:14px 0;border-bottom:1px solid var(--color-border);">
      <div style="display:flex;justify-content:space-between;align-items:baseline;">
        <span style="font-weight:600;font-size:0.9rem;">${label}</span>
        <span style="font-size:0.78rem;color:var(--color-text-secondary);">${score != null ? Math.round(score) + '/100' : 'No data'}</span>
      </div>
      <div style="font-size:0.75rem;color:var(--color-text-secondary);margin:2px 0 6px;">${desc}</div>
      ${score != null ? scoreBar(score) : '<div style="font-size:0.75rem;color:var(--color-text-secondary);">Not yet evaluated</div>'}
    </div>`;

  const bandColors = { exemplary: 'success', proficient: 'info', developing: 'warning', needs_improvement: 'error' };
  const bandLabel = { exemplary: 'Exemplary', proficient: 'Proficient', developing: 'Developing', needs_improvement: 'Needs Support' };
  const band = snap?.performance_band;

  const mb = document.querySelector('.modal-body');
  if (!mb) return;
  mb.innerHTML = `
    <div style="margin-bottom:20px;">
      <div style="font-size:1.1rem;font-weight:700;">${esc(coach.first_name)} ${esc(coach.last_name)}</div>
      <div style="font-size:0.85rem;color:var(--color-text-secondary);">${fmtLabel(coach.role || '')}</div>
    </div>

    ${!snap ? `<div class="empty-state" style="padding:24px 0;">
      <div class="empty-state-text">No performance score available yet for this coach.</div>
    </div>` : `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:16px;background:var(--color-bg-secondary);border-radius:10px;margin-bottom:20px;">
      <div>
        <div style="font-size:0.75rem;font-weight:700;color:var(--color-text-secondary);text-transform:uppercase;letter-spacing:0.05em;">Overall Score</div>
        <div style="font-size:2.2rem;font-weight:800;color:${snap.overall_score >= 80 ? 'var(--color-success)' : snap.overall_score >= 60 ? 'var(--color-warning)' : 'var(--color-danger)'};">${Math.round(snap.overall_score)}<span style="font-size:1rem;font-weight:400;color:var(--color-text-secondary);">/100</span></div>
        ${snap.period_start ? `<div style="font-size:0.72rem;color:var(--color-text-secondary);">Period: ${esc(snap.period_start)} – ${esc(snap.period_end || '')}</div>` : ''}
      </div>
      <span class="badge badge-${bandColors[band] || 'secondary'}" style="font-size:0.85rem;padding:6px 14px;">${bandLabel[band] || esc(band || 'Unscored')}</span>
    </div>

    <div style="margin-bottom:8px;font-size:0.75rem;font-weight:700;color:var(--color-text-secondary);text-transform:uppercase;letter-spacing:0.06em;">Score Breakdown</div>
    ${metricRow('Compliance', 'Following Ufit protocols, punctuality, and program standards.', snap.compliance_score)}
    ${metricRow('Student Outcomes', 'Student skill growth and assessment participation rates.', snap.outcomes_score)}
    ${metricRow('Observations', 'Quality scores from supervisor observations of sessions.', snap.observations_score)}

    <div style="margin:20px 0 8px;font-size:0.75rem;font-weight:700;color:var(--color-text-secondary);text-transform:uppercase;letter-spacing:0.06em;">Operational Rates (Last 30 Days)</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:8px;">
      <div style="background:var(--color-bg-secondary);border-radius:8px;padding:12px;text-align:center;">
        <div style="font-size:1.5rem;font-weight:800;color:${(snap.eod_ontime_rate??0)>=80?'var(--color-success)':(snap.eod_ontime_rate??0)>=60?'var(--color-warning)':'var(--color-danger)'};">${snap.eod_ontime_rate != null ? Math.round(snap.eod_ontime_rate)+'%' : '—'}</div>
        <div style="font-size:0.72rem;color:var(--color-text-secondary);margin-top:2px;">EOD Reports On-Time</div>
      </div>
      <div style="background:var(--color-bg-secondary);border-radius:8px;padding:12px;text-align:center;">
        <div style="font-size:1.5rem;font-weight:800;color:${(snap.session_log_rate??0)>=80?'var(--color-success)':(snap.session_log_rate??0)>=60?'var(--color-warning)':'var(--color-danger)'};">${snap.session_log_rate != null ? Math.round(snap.session_log_rate)+'%' : '—'}</div>
        <div style="font-size:0.72rem;color:var(--color-text-secondary);margin-top:2px;">Sessions Logged Rate</div>
      </div>
    </div>

    <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--color-border);">
      <div style="font-size:0.75rem;font-weight:700;color:var(--color-text-secondary);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:10px;">Activity — Last 30 Days</div>
      <div style="display:flex;gap:16px;flex-wrap:wrap;">
        <div style="font-size:0.85rem;"><strong>${act.sessions_logged_30d ?? 0}</strong> sessions logged</div>
        <div style="font-size:0.85rem;"><strong>${act.eods_filed_30d ?? 0}</strong> EOD reports filed</div>
        <div style="font-size:0.85rem;"><strong>${act.eods_ontime_30d ?? 0}</strong> on-time</div>
      </div>
    </div>`}`;
}

async function loadPrincipalStudents(container) {
  let page = 1;
  const perPage = 25;

  async function fetch(p = 1) {
    container.innerHTML = `<div class="text-h2" style="margin-bottom:16px;">Students</div>${renderSkeleton(6)}`;
    try {
      const search = (state._studentSearch || '');
      const d = await api('GET', `/api/principal/students?page=${p}&per_page=${perPage}${search ? '&search=' + encodeURIComponent(search) : ''}`);
      const students = d.students || [];
      const total = d.total || 0;
      container.innerHTML = `
        <div class="page-header">
          <div class="text-h2">Students</div>
          <input class="form-input" id="student-search" type="search" placeholder="Search by name…" value="${esc(search)}" style="max-width:240px;" />
        </div>
        ${students.length ? `
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>Name</th><th>Grade</th><th>Last Assessed</th><th>Avg Level</th></tr></thead>
              <tbody>${students.map(s => {
                const lvl = s.avg_raw_level;
                const lvlColor = lvl == null ? '' : lvl >= 4 ? 'var(--color-success)' : lvl >= 3 ? 'var(--color-warning)' : 'var(--color-danger)';
                const lvlDisplay = lvl != null ? `<span style="font-weight:700;color:${lvlColor};">${lvl.toFixed(1)}</span><span class="text-caption"> /5</span>` : '—';
                return `<tr style="cursor:pointer;" onclick="openStudentProgressModal(${s.student_id})">
                <td>${esc(s.first_name)} ${esc(s.last_name)}</td>
                <td>${esc(s.grade_level || '—')}</td>
                <td>${fmtDate(s.latest_assessment_date)}</td>
                <td>${lvlDisplay}</td>
                <td><span style="color:var(--color-primary);font-size:0.8rem;">View →</span></td>
              </tr>`;}).join('')}</tbody>
            </table>
          </div>
          <div class="pagination">
            ${p > 1 ? `<button class="btn btn-ghost btn-sm" id="prev-page">← Previous</button>` : ''}
            <span class="text-caption">Showing ${(p-1)*perPage+1}–${Math.min(p*perPage, total)} of ${total}</span>
            ${p * perPage < total ? `<button class="btn btn-ghost btn-sm" id="next-page">Next →</button>` : ''}
          </div>` : `<div class="empty-state"><div class="empty-state-icon">${iconStudents()}</div><div class="empty-state-title">No students found</div></div>`}`;

      document.getElementById('prev-page')?.addEventListener('click', () => fetch(p - 1));
      document.getElementById('next-page')?.addEventListener('click', () => fetch(p + 1));
      let searchTimer;
      document.getElementById('student-search')?.addEventListener('input', e => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => { state._studentSearch = e.target.value; fetch(1); }, 350);
      });
    } catch (err) { container.innerHTML = errorCard(err.message); }
  }
  fetch(page);
}

/* ============================================================
   22b. PRINCIPAL INCIDENTS
   ============================================================ */
async function loadPrincipalIncidents(container) {
  let statusFilter = 'open';
  async function fetchIncidents(status) {
    statusFilter = status;
    container.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
        <div class="text-h2">Incidents</div>
        <div style="display:flex;gap:8px;">
          <button class="btn ${status==='open'?'btn-primary':'btn-ghost'} btn-sm" id="inc-filter-open">Open</button>
          <button class="btn ${status==='resolved'?'btn-primary':'btn-ghost'} btn-sm" id="inc-filter-resolved">Resolved</button>
          <button class="btn ${status===''?'btn-primary':'btn-ghost'} btn-sm" id="inc-filter-all">All</button>
        </div>
      </div>
      <div id="incidents-list">${renderSkeleton(3)}</div>`;
    document.getElementById('inc-filter-open')?.addEventListener('click', () => fetchIncidents('open'));
    document.getElementById('inc-filter-resolved')?.addEventListener('click', () => fetchIncidents('resolved'));
    document.getElementById('inc-filter-all')?.addEventListener('click', () => fetchIncidents(''));
    const el = document.getElementById('incidents-list');
    try {
      const url = '/api/principal/incidents' + (status ? `?status=${status}` : '');
      const d = await api('GET', url);
      const incidents = d.incidents || [];
      if (!incidents.length) {
        el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">${iconIncidents()}</div><div class="empty-state-title">No ${status || ''} incidents</div><div class="empty-state-text">No incidents to review for your school.</div></div>`;
        return;
      }
      el.innerHTML = `<div style="display:flex;flex-direction:column;gap:12px;">
        ${incidents.map(i => {
          const sevColor = i.severity_level === 'critical' || i.severity_level === 'high' ? '#ef4444' : i.severity_level === 'medium' ? '#f59e0b' : '#6b7280';
          const sevBg   = i.severity_level === 'critical' || i.severity_level === 'high' ? '#fee2e2' : i.severity_level === 'medium' ? '#fef3c7' : '#f3f4f6';
          const statusColor = i.status === 'open' ? '#ef4444' : i.status === 'resolved' ? '#22c55e' : '#f59e0b';
          const _sid = _modalStore.set(i);
          return `
          <div class="card" style="padding:16px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
              <div style="flex:1;min-width:0;">
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
                  <span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;background:${sevBg};color:${sevColor};">${fmtLabel(i.severity_level || 'unknown')}</span>
                  <span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;background:${i.status==='open'?'#fee2e2':i.status==='resolved'?'#dcfce7':'#fef3c7'};color:${statusColor};">${fmtLabel(i.status)}</span>
                  <span style="font-size:12px;color:var(--color-text-muted);">${fmtDate(i.report_date)}</span>
                </div>
                <div style="font-size:14px;font-weight:600;margin-bottom:4px;">${fmtLabel(i.incident_type || 'Incident')}</div>
                <div style="font-size:13px;color:var(--color-text-muted);margin-bottom:4px;">Reported by: ${esc(i.reporter_name || '—')}${i.student_name ? ` &mdash; Student: ${esc(i.student_name)}` : ''}</div>
                <div style="font-size:13px;color:var(--color-text);line-height:1.5;">${esc(i.description || '—')}</div>
                ${i.immediate_action_taken ? `<div style="font-size:13px;color:var(--color-text-muted);margin-top:4px;"><strong>Action taken:</strong> ${esc(i.immediate_action_taken)}</div>` : ''}
                ${i.admin_response ? `<div style="font-size:13px;color:var(--color-primary);margin-top:6px;"><strong>Response on file:</strong> ${esc(i.admin_response)}</div>` : ''}
              </div>
              <button class="btn btn-ghost btn-sm" style="white-space:nowrap;" onclick="openPrincipalIncidentModal(_modalStore.get(${_sid}), loadPrincipalIncidents.bind(null, document.getElementById('page-main')))">
                ${i.status === 'open' ? 'Respond' : 'View'}
              </button>
            </div>
          </div>`;
        }).join('')}
      </div>`;
    } catch(err) { el.innerHTML = errorCard(err.message); }
  }
  fetchIncidents(statusFilter);
}

function openPrincipalIncidentModal(incident, onSuccess) {
  const isOpen = incident.status === 'open' || incident.status === 'under_review';
  openModal(`
    <div class="modal-header">
      <h2 class="modal-title">${isOpen ? 'Respond to Incident' : 'Incident Detail'}</h2>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <form id="principal-incident-form" style="display:contents;">
    <div class="modal-body form-stack">
      <div class="card" style="background:var(--color-bg);padding:12px 16px;">
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
          <span class="badge badge-${incident.severity_level==='high'||incident.severity_level==='critical'?'error':incident.severity_level==='medium'?'warning':'secondary'}">${fmtLabel(incident.severity_level)}</span>
          <span class="badge badge-${incident.status==='open'?'error':'success'}">${fmtLabel(incident.status)}</span>
          <span style="font-size:12px;color:var(--color-text-muted);">${fmtDate(incident.report_date)}</span>
        </div>
        <div style="font-size:13px;margin-bottom:4px;"><strong>Type:</strong> ${fmtLabel(incident.incident_type || '—')}</div>
        <div style="font-size:13px;margin-bottom:4px;"><strong>Reporter:</strong> ${esc(incident.reporter_name || '—')}${incident.student_name ? ` &mdash; <strong>Student:</strong> ${esc(incident.student_name)}` : ''}</div>
        <div style="font-size:13px;margin-bottom:4px;"><strong>Description:</strong> ${esc(incident.description || '—')}</div>
        ${incident.immediate_action_taken ? `<div style="font-size:13px;"><strong>Immediate action:</strong> ${esc(incident.immediate_action_taken)}</div>` : ''}
      </div>
      <div class="form-group">
        <label class="form-label">Principal Response / Notes</label>
        <textarea class="form-input form-textarea" id="principal-response-field" rows="3" placeholder="Describe what action you're taking, follow-up steps, or outcome…">${esc(incident.admin_response || '')}</textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Resolution Notes <span style="color:var(--color-text-muted);font-weight:400;">(optional)</span></label>
        <textarea class="form-input form-textarea" id="principal-resolution-field" rows="2" placeholder="Internal notes about how this was resolved…">${esc(incident.resolution_notes || '')}</textarea>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
      ${isOpen
        ? `<button class="btn btn-ghost btn-sm" id="principal-review-btn" type="button" onclick="submitPrincipalIncident(${incident.incident_id},'under_review')">Mark Under Review</button>
           <button class="btn btn-primary" id="principal-resolve-btn" type="button" onclick="submitPrincipalIncident(${incident.incident_id},'resolved')">Mark Resolved</button>`
        : `<button class="btn btn-ghost btn-sm" id="principal-reopen-btn" type="button" onclick="submitPrincipalIncident(${incident.incident_id},'open')">Reopen</button>
           <button class="btn btn-primary" id="principal-resolve-btn" type="button" onclick="submitPrincipalIncident(${incident.incident_id},'resolved')">Update Notes</button>`
      }
    </div>
    </form>`);
  window._principalIncidentCallback = onSuccess;
}

async function submitPrincipalIncident(incidentId, status) {
  const btnId = status === 'open' ? 'principal-reopen-btn' : status === 'under_review' ? 'principal-review-btn' : 'principal-resolve-btn';
  const btn = document.getElementById(btnId);
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
  try {
    await api('PATCH', `/api/principal/incidents/${incidentId}`, {
      status,
      admin_response: document.getElementById('principal-response-field')?.value.trim() || null,
      resolution_notes: document.getElementById('principal-resolution-field')?.value.trim() || null,
    });
    closeModal();
    const msg = status === 'resolved' ? 'Incident marked resolved.' : status === 'under_review' ? 'Incident marked under review.' : 'Incident reopened.';
    showAlert(msg, 'success');
    if (window._principalIncidentCallback) window._principalIncidentCallback();
  } catch(err) {
    showAlert(err.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = status === 'open' ? 'Reopen' : status === 'under_review' ? 'Mark Under Review' : 'Mark Resolved'; }
  }
}

/* ============================================================
   22c. PRINCIPAL SATISFACTION SURVEY
   ============================================================ */
function loadPrincipalSurvey(container) {
  const school = state.principalSchool || {};
  container.innerHTML = `
    <div style="max-width:680px;margin:0 auto;padding:0 0 40px;">
      <div class="text-h2" style="margin-bottom:4px;">Principal Satisfaction Survey</div>
      <p style="color:var(--color-text-secondary);margin-bottom:24px;font-size:14px;">Help us improve the Ufit program at your school. All responses go directly to the Ufit admin team.</p>
      <div id="survey-success" style="display:none;margin-bottom:20px;" class="alert alert-success">
        Thank you — your response has been submitted!
      </div>
      <form id="principal-survey-form" autocomplete="off">

        <div class="card" style="margin-bottom:16px;padding:20px;">
          <div class="text-h3" style="margin-bottom:16px;">About You</div>
          <div class="form-group">
            <label class="form-label" for="ps-name">Your Name *</label>
            <input class="form-input" id="ps-name" type="text" placeholder="Full name" required maxlength="200">
          </div>
          <div class="form-group">
            <label class="form-label" for="ps-position">Your Position *</label>
            <input class="form-input" id="ps-position" type="text" placeholder="e.g. Principal, School Coordinator" required maxlength="200">
          </div>
          <div class="form-group">
            <label class="form-label" for="ps-school">School Name *</label>
            <input class="form-input" id="ps-school" type="text" value="${esc(school.school_name || '')}" placeholder="School name" required maxlength="200">
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <label class="form-label" for="ps-email">Email Address (optional)</label>
            <input class="form-input" id="ps-email" type="email" placeholder="your@email.com" maxlength="200">
          </div>
        </div>

        <div class="card" style="margin-bottom:16px;padding:20px;">
          <div class="text-h3" style="margin-bottom:16px;">Rating Questions</div>
          <p style="font-size:13px;color:var(--color-text-secondary);margin-bottom:16px;">Rate each area from 1 (Poor) to 5 (Excellent).</p>
          ${surveyRatingField('ps-satisfaction', 'Overall satisfaction with the Ufit PE program', true)}
          ${surveyRatingField('ps-yard-safety', 'Yard safety and supervision by Ufit coaches', true)}
          ${surveyRatingField('ps-coach-perf', 'Coach performance and professionalism', true)}
          ${surveyRatingField('ps-communication', 'Communication between Ufit coaches and school staff', true)}
          ${surveyRatingField('ps-wellbeing', 'Effectiveness of the program in supporting student wellbeing', false)}
        </div>

        <div class="card" style="margin-bottom:24px;padding:20px;">
          <div class="text-h3" style="margin-bottom:16px;">Open-Ended Questions</div>
          <div class="form-group">
            <label class="form-label" for="ps-improvements">What improvements or suggestions do you have for the Ufit program?</label>
            <textarea class="form-input form-textarea" id="ps-improvements" rows="3" placeholder="Your suggestions..." maxlength="5000" style="resize:vertical;"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label" for="ps-contributions">How has the Ufit program contributed to student development at your school?</label>
            <textarea class="form-input form-textarea" id="ps-contributions" rows="3" placeholder="Describe contributions..." maxlength="5000" style="resize:vertical;"></textarea>
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <label class="form-label" for="ps-additional">Are there additional services or support you would like Ufit to provide?</label>
            <textarea class="form-input form-textarea" id="ps-additional" rows="3" placeholder="Additional services..." maxlength="5000" style="resize:vertical;"></textarea>
          </div>
        </div>

        <button type="submit" class="btn btn-primary" id="survey-submit-btn" style="width:100%;height:48px;font-size:16px;">Submit Survey</button>
      </form>
    </div>`;

  document.getElementById('principal-survey-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('survey-submit-btn');
    btn.disabled = true; btn.textContent = 'Submitting…';

    const getRating = (id) => {
      const sel = document.querySelector(`input[name="${id}"]:checked`);
      return sel ? parseInt(sel.value) : null;
    };

    const payload = {
      respondent_name: document.getElementById('ps-name').value.trim(),
      respondent_position: document.getElementById('ps-position').value.trim(),
      school_name: document.getElementById('ps-school').value.trim(),
      email: document.getElementById('ps-email').value.trim() || null,
      satisfaction_rating: getRating('ps-satisfaction'),
      yard_safety_rating: getRating('ps-yard-safety'),
      coach_performance_rating: getRating('ps-coach-perf'),
      communication_rating: getRating('ps-communication'),
      wellbeing_effectiveness_rating: getRating('ps-wellbeing') || null,
      improvements_suggestions: document.getElementById('ps-improvements').value.trim() || null,
      contributions_description: document.getElementById('ps-contributions').value.trim() || null,
      additional_services: document.getElementById('ps-additional').value.trim() || null,
    };

    const ratingFieldMap = {
      satisfaction_rating: 'ps-satisfaction',
      yard_safety_rating: 'ps-yard-safety',
      coach_performance_rating: 'ps-coach-perf',
      communication_rating: 'ps-communication',
    };
    let hasError = false;
    for (const [k, name] of Object.entries(ratingFieldMap)) {
      const container = document.getElementById(`stars-${name}`);
      if (!payload[k]) {
        hasError = true;
        if (container) container.style.outline = '2px solid #EF4444';
      } else {
        if (container) container.style.outline = 'none';
      }
    }
    if (hasError) {
      showAlert('Please select a rating for all required fields (marked in red).', 'error');
      btn.disabled = false; btn.textContent = 'Submit Survey';
      return;
    }

    try {
      await api('POST', '/api/principal/survey', payload);
      document.getElementById('principal-survey-form').style.display = 'none';
      const s = document.getElementById('survey-success');
      s.style.display = 'block';
      s.scrollIntoView({ behavior: 'smooth' });
    } catch(err) {
      showAlert(err.message || 'Could not submit survey.', 'error');
      btn.disabled = false; btn.textContent = 'Submit Survey';
    }
  });
}

function surveyRatingField(name, label, required) {
  const req = required ? ' *' : '';
  const stars = [1,2,3,4,5].map(n => `
    <label style="display:flex;flex-direction:column;align-items:center;gap:4px;cursor:pointer;min-width:44px;">
      <input type="radio" name="${name}" value="${n}" style="display:none;" class="survey-radio" data-group="${name}">
      <span class="survey-star" data-val="${n}" data-group="${name}" style="font-size:26px;color:#D1D5DB;transition:color 0.15s;user-select:none;">★</span>
      <span style="font-size:11px;color:var(--color-text-secondary);">${n}</span>
    </label>`).join('');
  return `
    <div class="form-group" style="margin-bottom:20px;">
      <label class="form-label" style="margin-bottom:8px;">${esc(label)}${req}</label>
      <div id="stars-${name}" style="display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-radius:6px;transition:outline 0.15s;">${stars}</div>
    </div>`;
}

// Wire up star rating interactivity after DOM is ready
document.addEventListener('click', (e) => {
  const star = e.target.closest('.survey-star');
  if (!star) return;
  const group = star.dataset.group;
  const val = parseInt(star.dataset.val);
  const radio = document.querySelector(`input[name="${group}"][value="${val}"]`);
  if (radio) radio.checked = true;
  document.querySelectorAll(`.survey-star[data-group="${group}"]`).forEach(s => {
    s.style.color = parseInt(s.dataset.val) <= val ? 'var(--color-accent)' : '#D1D5DB';
  });
  const container = document.getElementById(`stars-${group}`);
  if (container) container.style.outline = 'none';
});

/* ============================================================
   22d. ADMIN SURVEYS VIEW
   ============================================================ */
async function loadAdminEvaluations(container) {
  container.innerHTML = `<div class="text-h2" style="margin-bottom:16px;">Coach Evaluations</div><div id="evals-content">${renderSkeleton(4)}</div>`;
  try {
    const d = await api('GET', '/api/admin/evaluations');
    const evals = d.evaluations || [];
    const content = document.getElementById('evals-content');
    if (!evals.length) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-title">No Evaluations Yet</div><div class="empty-state-text">Head coach evaluation submissions will appear here.</div></div>`;
      return;
    }
    const LABELS = {
      shows_up_consistently:'Shows up consistently & in uniform',reports_on_time:'Reports on time',processes_consistently:'Processes consistently & on deadline',
      follows_sop:'Follows UFIT SOPs',problem_solves:'Problem-solves for activity flow',demonstrates_improvement:'Demonstrates improvement in duties',
      apprises_lead_coach:'Apprises lead coach of situations',provides_feedback_to_lead:'Provides timely feedback to lead',follows_up_timely:'Follows up timely to requests',communicates_regularly:'Communicates regularly with lead',
      practices_restorative_justice:'Practices restorative justice',creates_inclusive_environment:'Creates inclusive environment',teaches_transferable_skills:'Teaches transferable skills',maintains_positive_atmosphere:'Maintains positive atmosphere',uses_reward_systems:'Uses appropriate reward systems',implements_activities_fidelity:'Implements activities with fidelity',
      learns_student_names:'Learns student names',provides_student_feedback:'Provides feedback to students',uses_positive_language:'Uses positive language',
      provides_supervision:'Provides appropriate supervision',uses_designated_spaces:'Uses designated spaces',ensures_safe_areas:'Ensures areas free of hazards',determines_best_areas:'Determines best areas for activities',follows_safety_procedures:'Follows safety procedures',maintains_equipment:'Maintains equipment condition',maintains_orderly_flow:'Maintains orderly activity flow',implements_rules_safeguards:'Implements rules & safeguards',
    };
    const starBar = (v) => '★'.repeat(v) + '☆'.repeat(5 - v);
    content.innerHTML = evals.map(e => {
      const date = e.submitted_at ? e.submitted_at.slice(0, 10) : '—';
      const sections = [
        { title: 'Attendance', fields: ['shows_up_consistently','reports_on_time','processes_consistently'] },
        { title: 'Continuous Skill Application', fields: ['follows_sop','problem_solves','demonstrates_improvement'] },
        { title: 'Communication', fields: ['apprises_lead_coach','provides_feedback_to_lead','follows_up_timely','communicates_regularly'] },
        { title: 'School & Team Interactions', fields: ['practices_restorative_justice','creates_inclusive_environment','teaches_transferable_skills','maintains_positive_atmosphere','uses_reward_systems','implements_activities_fidelity'] },
        { title: 'Student Interaction', fields: ['learns_student_names','provides_student_feedback','uses_positive_language'] },
        { title: 'Safety & Compliance', fields: ['provides_supervision','uses_designated_spaces','ensures_safe_areas','determines_best_areas','follows_safety_procedures','maintains_equipment','maintains_orderly_flow','implements_rules_safeguards'] },
      ];
      const sectionHtml = sections.map(s => `
        <div style="margin-bottom:12px;">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--color-primary);margin-bottom:6px;">${s.title}</div>
          ${s.fields.map(f => `<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:13px;border-bottom:1px solid var(--color-border,#E5E7EB);">
            <span style="color:var(--color-text-secondary);">${LABELS[f]}</span>
            <span style="color:var(--color-accent);letter-spacing:1px;font-size:12px;" title="${e[f]}/5">${starBar(e[f] || 0)}</span>
          </div>`).join('')}
        </div>`).join('');
      return `
        <div class="card" style="margin-bottom:16px;padding:20px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:16px;">
            <div>
              <div style="font-weight:700;font-size:16px;">${esc(e.evaluated_name || '—')}</div>
              <div style="font-size:13px;color:var(--color-text-secondary);">Evaluated by ${esc(e.evaluator_name || '—')} · ${esc(e.school_name || '—')} · ${date}</div>
              ${e.same_day_calloff ? `<span style="font-size:12px;background:#FEE2E2;color:#DC2626;border-radius:4px;padding:2px 6px;display:inline-block;margin-top:4px;">Same-day call-off reported</span>` : ''}
            </div>
          </div>
          ${sectionHtml}
          ${e.coach_strengths ? `<div style="margin-top:12px;"><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--color-text-secondary);letter-spacing:.5px;">Strengths</span><p style="margin:4px 0 0;font-size:14px;word-break:break-word;">${esc(e.coach_strengths)}</p></div>` : ''}
          ${e.coach_weaknesses ? `<div style="margin-top:8px;"><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--color-text-secondary);letter-spacing:.5px;">Areas for Growth</span><p style="margin:4px 0 0;font-size:14px;word-break:break-word;">${esc(e.coach_weaknesses)}</p></div>` : ''}
          ${e.improvement_plan ? `<div style="margin-top:8px;"><span style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--color-text-secondary);letter-spacing:.5px;">Improvement Plan</span><p style="margin:4px 0 0;font-size:14px;word-break:break-word;">${esc(e.improvement_plan)}</p></div>` : ''}
        </div>`;
    }).join('');
  } catch(err) {
    document.getElementById('evals-content').innerHTML = `<div class="alert alert-error">Could not load evaluations.</div>`;
  }
}

/* ============================================================
   22e. HEAD COACH EVALUATE PAGE
   ============================================================ */
async function loadCoachEvaluatePage(container) {
  container.innerHTML = renderSkeleton(3);
  try {
    const [subData, evalData] = await Promise.all([
      api('GET', '/api/coach/subordinates'),
      api('GET', '/api/coach/evaluations'),
    ]);
    const coaches = subData.coaches || [];
    const evals = evalData.evaluations || [];

    if (!coaches.length) {
      container.innerHTML = `
        <div class="page-header"><h1 class="page-title">Evaluate Coach</h1></div>
        <div class="empty-state">
          <div class="empty-state-icon">${iconSurveys()}</div>
          <div class="empty-state-title">No coaches to evaluate</div>
          <div class="empty-state-text">There are no assistant coaches assigned to your school yet.</div>
        </div>`;
      return;
    }

    const coachOptions = coaches.map(c =>
      `<option value="${c.staff_id}">${esc(c.first_name)} ${esc(c.last_name)} — ${fmtLabel(c.role)}</option>`
    ).join('');

    const SECTIONS = [
      {
        id: 'attendance', title: 'ATTENDANCE RATE (Personal)',
        calloff: true,
        fields: [
          { key:'shows_up_consistently', label:'Shows up consistently and in complete uniform and accessories' },
          { key:'reports_on_time', label:'Reports to work consistently and on time' },
          { key:'processes_consistently', label:'Processes consistently and within expected deadlines (clock-in, etc.)' },
        ],
      },
      {
        id: 'skill', title: 'CONTINUOUS SKILL APPLICATION & ONGOING IMPROVEMENT',
        fields: [
          { key:'follows_sop', label:'Follows UFIT standard operating procedures' },
          { key:'problem_solves', label:'Problem-solves to ensure adequate flow of activity for students and inclusion of all students' },
          { key:'demonstrates_improvement', label:'Demonstrates improvement in knowledge of expectations and/or relevant duties' },
        ],
      },
      {
        id: 'comms', title: 'COMMUNICATION',
        fields: [
          { key:'apprises_lead_coach', label:'Apprises Lead Coach / site coordinator of any situations such as injuries, student behavior, equipment, or concerns' },
          { key:'provides_feedback_to_lead', label:"Provides timely and consistent, relevant feedback to lead coach about students' performance" },
          { key:'follows_up_timely', label:'Follows up timely and appropriately to requests from site coordinator and UFIT administration' },
          { key:'communicates_regularly', label:'Communicates regularly and appropriately with the Lead Coach / site coordinator' },
        ],
      },
      {
        id: 'team', title: 'SCHOOL & TEAM INTERACTIONS',
        fields: [
          { key:'practices_restorative_justice', label:'Practices restorative justice on the playground' },
          { key:'creates_inclusive_environment', label:'Creates an environment where all students have opportunities to be involved and feel supported' },
          { key:'teaches_transferable_skills', label:'Teaches skills and activities that help students learn and be active in other settings' },
          { key:'maintains_positive_atmosphere', label:'Establishes and maintains a positive atmosphere to promote harmony and growth of students' },
          { key:'uses_reward_systems', label:'Uses appropriate reward systems with students that promote positive behaviors' },
          { key:'implements_activities_fidelity', label:'Implements UFIT activities consistently and with fidelity' },
        ],
      },
      {
        id: 'students', title: 'STUDENT INTERACTION',
        fields: [
          { key:'learns_student_names', label:"Makes efforts to learn students' names" },
          { key:'provides_student_feedback', label:'Provides timely and consistent, relevant feedback to students (developmental or praise)' },
          { key:'uses_positive_language', label:'Uses clear and consistent positive language (to model for students)' },
        ],
      },
      {
        id: 'safety', title: 'SAFETY & COMPLIANCE',
        fields: [
          { key:'provides_supervision', label:'Provides appropriate supervision of all students' },
          { key:'uses_designated_spaces', label:'Makes plans to use the designated spaces' },
          { key:'ensures_safe_areas', label:'Ensures activity areas are free of impediments that might pose a safety hazard for students' },
          { key:'determines_best_areas', label:'Determines areas that can be best used for certain games and sports' },
          { key:'follows_safety_procedures', label:"Follows UFIT's manual in responding to safety procedures and all established school safety rules" },
          { key:'maintains_equipment', label:'Maintains equipment condition and amount to promote engaging activities for students' },
          { key:'maintains_orderly_flow', label:'Maintains an orderly and productive flow of activities and transitions' },
          { key:'implements_rules_safeguards', label:'Implements rules/safeguards to ensure a positive environment (e.g. procedures – "no name-calling", etc.)' },
        ],
      },
    ];

    const renderSection = (sec) => {
      const calloffHtml = sec.calloff ? `
        <div class="form-group" style="margin-bottom:16px;">
          <label class="form-label">Were there any same-day call-offs?</label>
          <div style="display:flex;gap:16px;margin-top:6px;">
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:14px;">
              <input type="radio" name="same_day_calloff" value="0" checked> No
            </label>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:14px;">
              <input type="radio" name="same_day_calloff" value="1"> Yes
            </label>
          </div>
        </div>` : '';
      const fields = sec.fields.map(f => evalRatingField(f.key, f.label)).join('');
      return `<div class="card" style="margin-bottom:16px;padding:20px;">
        <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--color-primary);margin-bottom:14px;">${sec.title}</div>
        ${calloffHtml}${fields}
      </div>`;
    };

    const pastEvalsHtml = evals.length ? evals.slice(0, 5).map(e => {
      const date = e.submitted_at ? e.submitted_at.slice(0, 10) : '—';
      return `<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--color-border,#E5E7EB);">
        <div>
          <div style="font-size:14px;font-weight:500;">${esc(e.evaluated_name || '—')}</div>
          <div style="font-size:12px;color:var(--color-text-secondary);">${date}</div>
        </div>
        <span class="badge">${e.same_day_calloff ? 'Call-off reported' : 'Complete'}</span>
      </div>`;
    }).join('') : `<div style="color:var(--color-text-secondary);font-size:14px;padding:12px 0;">No evaluations submitted yet.</div>`;

    container.innerHTML = `
      <div style="max-width:720px;margin:0 auto;padding:0 0 40px;">
        <div class="text-h2" style="margin-bottom:4px;">Coach Evaluation</div>
        <p style="color:var(--color-text-secondary);font-size:14px;margin-bottom:24px;">Evaluate an assistant coach at your school. Ratings use a 1–5 scale (1 = Needs Improvement, 5 = Outstanding).</p>

        ${evals.length ? `<div class="card" style="margin-bottom:20px;padding:18px 20px;">
          <div class="card-title" style="margin-bottom:0;">Recent Evaluations</div>
          ${pastEvalsHtml}
        </div>` : ''}

        <div id="eval-success" style="display:none;" class="alert alert-success">Evaluation submitted successfully!</div>
        <form id="coach-eval-form" autocomplete="off">
          <div class="card" style="margin-bottom:16px;padding:20px;">
            <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--color-primary);margin-bottom:14px;">COACH BEING EVALUATED</div>
            <div class="form-group">
              <label class="form-label" for="eval-coach-select">Select Coach *</label>
              <select class="form-select" id="eval-coach-select" required>
                <option value="">— Select a coach —</option>
                ${coachOptions}
              </select>
            </div>
            <div class="form-group" style="margin-bottom:0;">
              <label class="form-label" for="eval-email">Your Email (optional)</label>
              <input class="form-input" id="eval-email" type="email" placeholder="coach@ufitonline.net" maxlength="200">
            </div>
          </div>

          ${SECTIONS.map(renderSection).join('')}

          <div class="card" style="margin-bottom:24px;padding:20px;">
            <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--color-primary);margin-bottom:14px;">SUPERVISOR'S SUMMARY</div>
            <div class="form-group">
              <label class="form-label" for="eval-strengths">Coach Strengths *</label>
              <textarea class="form-input form-textarea" id="eval-strengths" rows="3" placeholder="Describe the coach's key strengths..." maxlength="5000" style="resize:vertical;" required></textarea>
            </div>
            <div class="form-group">
              <label class="form-label" for="eval-weaknesses">Areas for Growth *</label>
              <textarea class="form-input form-textarea" id="eval-weaknesses" rows="3" placeholder="Describe areas needing improvement..." maxlength="5000" style="resize:vertical;" required></textarea>
            </div>
            <div class="form-group" style="margin-bottom:0;">
              <label class="form-label" for="eval-plan">Improvement Plan to Observe on Next Evaluation *</label>
              <textarea class="form-input form-textarea" id="eval-plan" rows="3" placeholder="Describe specific actions the coach should take..." maxlength="5000" style="resize:vertical;" required></textarea>
            </div>
          </div>

          <button type="submit" class="btn btn-primary" id="eval-submit-btn" style="width:100%;height:48px;font-size:16px;">Submit Evaluation</button>
        </form>
      </div>`;

    document.getElementById('coach-eval-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = document.getElementById('eval-submit-btn');
      btn.disabled = true; btn.textContent = 'Submitting…';

      const getRating = (name) => {
        const el = document.querySelector(`input[name="${name}"]:checked`);
        return el ? parseInt(el.value) : null;
      };

      const ratingKeys = [
        'shows_up_consistently','reports_on_time','processes_consistently',
        'follows_sop','problem_solves','demonstrates_improvement',
        'apprises_lead_coach','provides_feedback_to_lead','follows_up_timely','communicates_regularly',
        'practices_restorative_justice','creates_inclusive_environment','teaches_transferable_skills',
        'maintains_positive_atmosphere','uses_reward_systems','implements_activities_fidelity',
        'learns_student_names','provides_student_feedback','uses_positive_language',
        'provides_supervision','uses_designated_spaces','ensures_safe_areas','determines_best_areas',
        'follows_safety_procedures','maintains_equipment','maintains_orderly_flow','implements_rules_safeguards',
      ];

      const evaluated_staff_id = document.getElementById('eval-coach-select').value;
      if (!evaluated_staff_id) {
        showAlert('Please select a coach to evaluate.', 'error');
        btn.disabled = false; btn.textContent = 'Submit Evaluation';
        return;
      }

      const ratings = {};
      let hasError = false;
      for (const k of ratingKeys) {
        const v = getRating(`eval_${k}`);
        if (!v) {
          const el = document.getElementById(`eval-stars-${k}`);
          if (el) el.style.outline = '2px solid #EF4444';
          hasError = true;
        } else {
          const el = document.getElementById(`eval-stars-${k}`);
          if (el) el.style.outline = 'none';
          ratings[k] = v;
        }
      }
      if (hasError) {
        showAlert('Please rate all required fields (highlighted in red).', 'error');
        btn.disabled = false; btn.textContent = 'Submit Evaluation';
        return;
      }

      const calloffEl = document.querySelector('input[name="same_day_calloff"]:checked');
      const payload = {
        evaluated_staff_id: parseInt(evaluated_staff_id),
        email: document.getElementById('eval-email').value.trim() || null,
        same_day_calloff: calloffEl ? parseInt(calloffEl.value) : 0,
        coach_strengths: document.getElementById('eval-strengths').value.trim(),
        coach_weaknesses: document.getElementById('eval-weaknesses').value.trim(),
        improvement_plan: document.getElementById('eval-plan').value.trim(),
        ...ratings,
      };

      try {
        await api('POST', '/api/coach/evaluations', payload);
        document.getElementById('coach-eval-form').style.display = 'none';
        const s = document.getElementById('eval-success');
        s.style.display = 'block';
        s.scrollIntoView({ behavior: 'smooth' });
      } catch(err) {
        showAlert(err.message || 'Could not submit evaluation.', 'error');
        btn.disabled = false; btn.textContent = 'Submit Evaluation';
      }
    });
  } catch(err) {
    container.innerHTML = errorCard('Could not load evaluation form.');
  }
}

function evalRatingField(key, label) {
  const stars = [1,2,3,4,5].map(n => `
    <label style="display:flex;flex-direction:column;align-items:center;gap:3px;cursor:pointer;min-width:44px;">
      <input type="radio" name="eval_${key}" value="${n}" style="display:none;" class="eval-radio" data-egroup="eval_${key}">
      <span class="eval-star" data-val="${n}" data-egroup="eval_${key}" style="font-size:24px;color:#D1D5DB;transition:color 0.15s;user-select:none;">★</span>
      <span style="font-size:10px;color:var(--color-text-secondary);">${n}</span>
    </label>`).join('');
  return `
    <div class="form-group" style="margin-bottom:16px;">
      <label class="form-label" style="margin-bottom:6px;font-size:13px;line-height:1.4;">${esc(label)} *</label>
      <div id="eval-stars-${key}" style="display:flex;gap:6px;align-items:flex-start;padding:4px 0;border-radius:6px;transition:outline 0.15s;">${stars}</div>
    </div>`;
}

// Wire eval star click handler
document.addEventListener('click', (e) => {
  const star = e.target.closest('.eval-star');
  if (!star) return;
  const group = star.dataset.egroup;
  const val = parseInt(star.dataset.val);
  const radio = document.querySelector(`input[name="${group}"][value="${val}"]`);
  if (radio) radio.checked = true;
  document.querySelectorAll(`.eval-star[data-egroup="${group}"]`).forEach(s => {
    s.style.color = parseInt(s.dataset.val) <= val ? 'var(--color-accent)' : '#D1D5DB';
  });
  const key = group.replace('eval_', '');
  const container = document.getElementById(`eval-stars-${key}`);
  if (container) container.style.outline = 'none';
});
async function loadAdminSurveys(container) {
  container.innerHTML = `<div class="text-h2" style="margin-bottom:16px;">Principal Surveys</div><div id="surveys-content">${renderSkeleton(4)}</div>`;
  try {
    const d = await api('GET', '/api/admin/surveys');
    const surveys = d.surveys || [];
    const content = document.getElementById('surveys-content');
    if (!surveys.length) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-title">No Surveys Yet</div><div class="empty-state-text">Principal responses will appear here once submitted.</div></div>`;
      return;
    }
    content.innerHTML = surveys.map(s => {
      const date = s.submitted_at ? s.submitted_at.slice(0, 10) : '—';
      const school = esc(s.resolved_school_name || s.school_name || '—');
      const rb = (v, label) => v
        ? `<span style="display:inline-flex;align-items:center;gap:2px;font-size:12px;background:var(--color-surface-alt,#F3F4F6);border-radius:4px;padding:2px 6px;white-space:nowrap;"><span style="color:var(--color-accent);">★</span>${v} <span style="color:var(--color-text-secondary);">${label}</span></span>`
        : '';
      const textBlock = (heading, val) => val
        ? `<div style="margin-bottom:8px;"><span style="font-size:11px;font-weight:600;text-transform:uppercase;color:var(--color-text-secondary);letter-spacing:.5px;">${heading}</span><p style="margin:4px 0 0;font-size:14px;word-break:break-word;overflow-wrap:break-word;">${esc(val)}</p></div>`
        : '';
      return `
        <div class="card" style="margin-bottom:12px;padding:18px 20px;">
          <div style="margin-bottom:10px;">
            <div style="font-weight:600;font-size:15px;">${esc(s.respondent_name)} <span style="font-weight:400;color:var(--color-text-secondary);font-size:13px;">· ${esc(s.respondent_position)}</span></div>
            <div style="font-size:13px;color:var(--color-text-secondary);">${school} · ${date}${s.email ? ' · ' + esc(s.email) : ''}</div>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;">
            ${rb(s.satisfaction_rating, 'Overall')}
            ${rb(s.yard_safety_rating, 'Safety')}
            ${rb(s.coach_performance_rating, 'Coach')}
            ${rb(s.communication_rating, 'Comms')}
            ${rb(s.wellbeing_effectiveness_rating, 'Wellbeing')}
          </div>
          ${textBlock('Improvements', s.improvements_suggestions)}
          ${textBlock('Contributions', s.contributions_description)}
          ${textBlock('Additional Services', s.additional_services)}
        </div>`;
    }).join('');
  } catch(err) {
    document.getElementById('surveys-content').innerHTML = `<div class="alert alert-error">Could not load surveys.</div>`;
  }
}

/* ============================================================
   23. PARENT PORTAL
   ============================================================ */
async function loadParentHome(container) {
  container.innerHTML = renderSkeleton(3);
  try {
    const d = await api('GET', '/api/parent/student');
    const children = d.children || [];
    if (!children.length) {
      container.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">${iconStudents()}</div>
        <div class="empty-state-title">No children enrolled</div>
        <div class="empty-state-text">Contact your school administrator to link your children to your account.</div>
      </div>`; return;
    }
    container.innerHTML = children.map(c => {
      const scoreBand = c.readiness_band || '—';
      const score = c.overall_ufit_score != null ? Math.round(c.overall_ufit_score) : null;
      const scoreColor = scoreBand === 'Advanced' ? '#22c55e' : scoreBand === 'Proficient' ? '#1E40AF' : scoreBand === 'Developing' ? '#f59e0b' : '#ef4444';
      const bandBg = scoreBand === 'Advanced' ? '#dcfce7' : scoreBand === 'Proficient' ? '#dbeafe' : scoreBand === 'Developing' ? '#fef3c7' : '#fee2e2';

      const domainIcons = { physical: '🏃', psychomotor: '🏃', sel: '🤝', behavior: '🤝', cognitive: '🧠' };
      const getDomainIcon = name => {
        const key = (name || '').toLowerCase();
        for (const [k, v] of Object.entries(domainIcons)) { if (key.includes(k)) return v; }
        return '📊';
      };

      const skillsHtml = c.assessment_summary?.length ? `
        <div style="margin-top:20px;">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-muted);margin-bottom:10px;">Skill Levels</div>
          <div style="display:flex;flex-direction:column;gap:10px;">
            ${c.assessment_summary.map(a => {
              const pct = a.avg_raw_level != null ? ((a.avg_raw_level - 1) / 4) * 100 : 0;
              const lvl = a.avg_raw_level != null ? Number(a.avg_raw_level).toFixed(1) : '—';
              return `
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                  <span style="font-size:13px;font-weight:500;color:var(--color-text);">${getDomainIcon(a.domain_name)} ${esc(fmtSkillName(a.domain_name))}</span>
                  <span style="font-size:13px;font-weight:700;color:var(--color-text);">${lvl} <span style="font-weight:400;color:var(--color-text-muted);">/ 5</span></span>
                </div>
                <div style="height:6px;border-radius:3px;background:#e5e7eb;overflow:hidden;">
                  <div style="height:100%;border-radius:3px;background:${scoreColor};width:${pct}%;transition:width .4s;"></div>
                </div>
              </div>`;
            }).join('')}
          </div>
        </div>` : `<div style="margin-top:16px;font-size:13px;color:var(--color-text-muted);">No assessments recorded yet.</div>`;

      const sessionsHtml = c.recent_sessions?.length ? `
        <div style="margin-top:20px;">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-muted);margin-bottom:10px;">Recent Sessions</div>
          <div style="display:flex;flex-direction:column;gap:6px;">
            ${c.recent_sessions.slice(0,5).map(s => {
              const present = (s.attendance_status || '').toLowerCase() === 'present';
              const absent  = (s.attendance_status || '').toLowerCase() === 'absent';
              const dotColor = present ? '#22c55e' : absent ? '#ef4444' : '#9ca3af';
              const label = fmtLabel(s.attendance_status || 'Unknown');
              return `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--color-border);">
                <span style="font-size:13px;color:var(--color-text);">${fmtDate(s.session_date)}</span>
                <span style="display:flex;align-items:center;gap:5px;font-size:13px;font-weight:600;color:${dotColor};">
                  <span style="width:7px;height:7px;border-radius:50%;background:${dotColor};display:inline-block;"></span>
                  ${label}
                </span>
              </div>`;
            }).join('')}
          </div>
        </div>` : '';

      return `
      <div class="card" style="margin-bottom:20px;padding:20px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
          <div>
            <div style="font-size:18px;font-weight:700;color:var(--color-text);">${esc(c.first_name)} ${esc(c.last_name)}</div>
            <div style="font-size:13px;color:var(--color-text-muted);margin-top:2px;">Grade ${esc(c.grade_level || '—')} &mdash; ${esc(c.school_name || '—')}</div>
          </div>
          <div style="display:flex;align-items:center;gap:10px;">
            ${score != null ? `
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:800;color:${scoreColor};line-height:1;">${score}</div>
              <span style="display:inline-block;margin-top:4px;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;background:${bandBg};color:${scoreColor};">${esc(scoreBand)}</span>
            </div>` : ''}
            <button class="btn btn-ghost btn-sm" onclick="openStudentProgressModal(${c.student_id})">Details</button>
          </div>
        </div>
        ${skillsHtml}
        ${sessionsHtml}
      </div>`;
    }).join('');
  } catch (err) { container.innerHTML = errorCard(err.message); }
}

/* ============================================================
   24. SETTINGS PAGE
   ============================================================ */
function renderSettingsPage() {
  const user = state.user;
  const name = user?.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : 'User';
  const isAdmin = ADMIN_ROLES.has((user?.role || '').toLowerCase());
  return `
    <div class="text-h2" style="margin-bottom:20px;">Settings</div>
    <div class="cards-grid">
      <div class="card">
        <div class="card-header"><div class="card-title">Profile</div></div>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">Name</span><span class="kv-val">${esc(name)}</span></div>
          <div class="kv-row"><span class="kv-key">Email</span><span class="kv-val">${esc(user?.email || '—')}</span></div>
          <div class="kv-row"><span class="kv-key">Role</span><span class="kv-val"><span class="badge">${fmtLabel(user?.role || '—')}</span></span></div>
          ${user?.school_name ? `<div class="kv-row"><span class="kv-key">School</span><span class="kv-val">${esc(user.school_name)}</span></div>` : ''}
        </div>
      </div>
      <div class="card">
        <div class="card-header"><div class="card-title">Change Password</div></div>
        <form id="change-pw-form" class="form-stack" style="gap:12px;">
          <div class="form-group">
            <label class="form-label">Current Password</label>
            <input class="form-input" type="password" name="current_password" autocomplete="current-password" required />
          </div>
          <div class="form-group">
            <label class="form-label">New Password</label>
            <input class="form-input" type="password" name="new_password" autocomplete="new-password" minlength="8" placeholder="Min 8 characters" required />
          </div>
          <div class="form-group">
            <label class="form-label">Confirm New Password</label>
            <input class="form-input" type="password" name="confirm_password" autocomplete="new-password" minlength="8" required />
          </div>
          <button class="btn btn-primary" type="submit" id="change-pw-btn">Update Password</button>
        </form>
      </div>
      ${isAdmin ? `
      <div class="card">
        <div class="card-header"><div class="card-title">Reset User Password</div><div class="text-caption">Admin only</div></div>
        <form id="reset-pw-form" class="form-stack" style="gap:12px;">
          <div class="form-group">
            <label class="form-label">User ID</label>
            <input class="form-input" type="number" name="user_id" placeholder="Enter user ID" min="1" required />
          </div>
          <div class="form-group">
            <label class="form-label">New Password</label>
            <input class="form-input" type="password" name="new_password" autocomplete="new-password" minlength="8" placeholder="Min 8 characters" required />
          </div>
          <button class="btn btn-primary" type="submit" id="reset-pw-btn">Reset Password</button>
        </form>
      </div>` : ''}
      <div class="card">
        <div class="card-header"><div class="card-title">Account</div></div>
        <div class="form-stack" style="gap:8px;">
          <button class="btn btn-danger btn-full" id="settings-logout" type="button" style="justify-content:flex-start;">${iconLogout()} Sign Out</button>
        </div>
      </div>
    </div>`;
}

function attachSettingsListeners() {
  document.getElementById('change-pw-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('change-pw-btn');
    const fd = new FormData(e.target);
    const np = fd.get('new_password');
    if (np !== fd.get('confirm_password')) { showAlert('Passwords do not match.', 'error'); return; }
    btn.disabled = true; btn.innerHTML = 'Saving…';
    try {
      await api('POST', '/api/auth/change-password', {
        current_password: fd.get('current_password'),
        new_password: np,
      });
      showAlert('Password updated.', 'success');
      e.target.reset();
    } catch (err) {
      showAlert(err.message, 'error');
    } finally { btn.disabled = false; btn.innerHTML = 'Update Password'; }
  });

  document.getElementById('reset-pw-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('reset-pw-btn');
    const fd = new FormData(e.target);
    const uid = parseInt(fd.get('user_id'), 10);
    btn.disabled = true; btn.innerHTML = 'Saving…';
    try {
      await api('PATCH', `/api/users/${uid}`, { password: fd.get('new_password') });
      showAlert(`Password reset for user ${uid}.`, 'success');
      e.target.reset();
    } catch (err) {
      showAlert(err.message, 'error');
    } finally { btn.disabled = false; btn.innerHTML = 'Reset Password'; }
  });
}

/* ============================================================
   25. COMING SOON + ERROR HELPERS
   ============================================================ */
function renderComingSoon(title, msg) {
  return `<div class="coming-soon-page">
    <div class="coming-soon-badge">Coming Soon</div>
    <div class="coming-soon-title">${esc(title)}</div>
    <div class="coming-soon-text">${esc(msg)}</div>
    <button class="btn btn-ghost" onclick="navigate('dashboard')">Back to Dashboard</button>
  </div>`;
}

function errorCard(msg) {
  return `<div class="alert alert-error" role="alert">
    <span class="alert-icon">${iconAlert()}</span>
    <span class="alert-body">${esc(msg || 'Something went wrong. Please try again.')}</span>
  </div>`;
}

/* ============================================================
   25a. REPORTS PAGE (admin)
   ============================================================ */
async function loadReportsPage(container) {
  let schools = [];
  try {
    const sd = await api('GET', '/api/admin/schools');
    schools = sd.schools || [];
  } catch (err) {
    showAlert('Could not load school list — school filter unavailable.', 'warning');
  }

  const schoolOpts = schools.map(s => `<option value="${s.school_id}">${esc(s.school_name)}</option>`).join('');
  const today = new Date().toISOString().split('T')[0];
  const thirtyDaysAgo = new Date(Date.now() - 30 * 864e5).toISOString().split('T')[0];

  container.innerHTML = `
    <div style="margin-bottom:20px;">
      <div class="page-header" style="margin-bottom:16px;">
        <h2 style="font-weight:700;font-size:1.25rem;">Reports</h2>
      </div>
      <div class="card" style="padding:16px;">
        <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;">
          <div class="form-group" style="margin:0;flex:1;min-width:160px;">
            <label class="form-label">Report Type</label>
            <select class="form-input" id="rpt-type">
              <option value="eod_compliance">EOD Compliance by Coach</option>
              <option value="sessions">Session Activity by School</option>
              <option value="incidents">Incidents by School</option>
              <option value="student_growth">Student Growth by School</option>
            </select>
          </div>
          <div class="form-group" style="margin:0;flex:1;min-width:140px;">
            <label class="form-label">School</label>
            <select class="form-input" id="rpt-school">
              <option value="">All Schools</option>${schoolOpts}
            </select>
          </div>
          <div class="form-group" style="margin:0;min-width:130px;">
            <label class="form-label">From</label>
            <input class="form-input" type="date" id="rpt-from" value="${thirtyDaysAgo}" />
          </div>
          <div class="form-group" style="margin:0;min-width:130px;">
            <label class="form-label">To</label>
            <input class="form-input" type="date" id="rpt-to" value="${today}" />
          </div>
          <button class="btn btn-primary" id="rpt-run" style="margin-bottom:0;">Run Report</button>
        </div>
      </div>
    </div>
    <div id="rpt-results"><div class="empty-state"><div class="empty-state-title">Select filters and run report</div><div class="empty-state-text">Choose a report type and date range above, then click Run Report.</div></div></div>`;

  async function runReport() {
    const type = document.getElementById('rpt-type')?.value;
    const school = document.getElementById('rpt-school')?.value;
    const from = document.getElementById('rpt-from')?.value;
    const to = document.getElementById('rpt-to')?.value;
    const results = document.getElementById('rpt-results');
    const runBtn = document.getElementById('rpt-run');
    if (!results) return;
    results.innerHTML = renderSkeleton(3);
    if (runBtn) { runBtn.disabled = true; runBtn.textContent = 'Running…'; }
    try {
      const params = new URLSearchParams({ type, from, to });
      if (school) params.set('school_id', school);
      const d = await api('GET', `/api/reports?${params}`);
      results.innerHTML = renderReportTable(type, d);
    } catch (err) {
      results.innerHTML = errorCard(err.message);
    } finally {
      if (runBtn) { runBtn.disabled = false; runBtn.textContent = 'Run Report'; }
    }
  }

  document.getElementById('rpt-run')?.addEventListener('click', runReport);
}

function renderReportTable(type, d) {
  const rows = d.rows || [];
  if (!rows.length) return `<div class="empty-state"><div class="empty-state-title">No data for this period</div><div class="empty-state-text">Try a wider date range or different filters.</div></div>`;

  if (type === 'eod_compliance') {
    const tableRows = rows.map(r => {
      const pct = r.sessions_logged ? Math.round(r.eod_submitted / r.sessions_logged * 100) : 0;
      const onTimePct = r.eod_submitted ? Math.round(r.on_time / r.eod_submitted * 100) : 0;
      return `<tr>
        <td>${esc(r.coach_name)}</td>
        <td>${esc(r.school_name)}</td>
        <td>${r.sessions_logged}</td>
        <td>${r.eod_submitted} <span style="color:var(--color-text-secondary);font-size:0.75rem;">(${pct}%)</span></td>
        <td><span class="badge badge-${r.late > 0 ? 'warning' : 'success'}">${r.on_time} on time</span> ${r.late > 0 ? `<span class="badge badge-error">${r.late} late</span>` : ''}</td>
        <td><span class="badge badge-${onTimePct >= 80 ? 'success' : onTimePct >= 60 ? 'warning' : 'error'}">${onTimePct}%</span></td>
      </tr>`;
    }).join('');
    return `<div class="card"><div class="card-header"><div class="card-title">EOD Compliance by Coach</div><div class="card-subtitle">${d.from} → ${d.to}</div></div>
      <div class="table-container"><table class="table">
        <thead><tr><th>Coach</th><th>School</th><th>Sessions</th><th>EODs Filed</th><th>Timeliness</th><th>Rate</th></tr></thead>
        <tbody>${tableRows}</tbody>
      </table></div></div>`;
  }

  if (type === 'sessions') {
    const tableRows = rows.map(r => `<tr>
      <td>${esc(r.school_name)}</td>
      <td>${r.total_sessions}</td>
      <td>${r.active_days}</td>
      <td>${r.total_attendance}</td>
      <td>${r.avg_attendance ?? '—'}</td>
    </tr>`).join('');
    return `<div class="card"><div class="card-header"><div class="card-title">Session Activity by School</div><div class="card-subtitle">${d.from} → ${d.to}</div></div>
      <div class="table-container"><table class="table">
        <thead><tr><th>School</th><th>Sessions</th><th>Active Days</th><th>Total Attendance</th><th>Avg / Session</th></tr></thead>
        <tbody>${tableRows}</tbody>
      </table></div></div>`;
  }

  if (type === 'incidents') {
    if (!rows.length) return `<div class="empty-state"><div class="empty-state-title">No incidents in this period</div></div>`;
    const tableRows = rows.map(r => `<tr>
      <td>${esc(r.school_name)}</td>
      <td><span class="badge badge-${r.severity_level === 'high' ? 'error' : r.severity_level === 'medium' ? 'warning' : 'secondary'}">${fmtLabel(r.severity_level)}</span></td>
      <td>${fmtLabel(r.incident_type)}</td>
      <td>${r.count}</td>
      <td>${r.open_count > 0 ? `<span class="badge badge-error">${r.open_count} open</span>` : '—'}</td>
    </tr>`).join('');
    return `<div class="card"><div class="card-header"><div class="card-title">Incidents by School</div><div class="card-subtitle">${d.from} → ${d.to}</div></div>
      <div class="table-container"><table class="table">
        <thead><tr><th>School</th><th>Severity</th><th>Type</th><th>Count</th><th>Open</th></tr></thead>
        <tbody>${tableRows}</tbody>
      </table></div></div>`;
  }

  if (type === 'student_growth') {
    const scoreColor = v => v == null ? '' : v >= 70 ? 'var(--color-success)' : v >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
    const tableRows = rows.map(r => `<tr>
      <td>${esc(r.school_name)}</td>
      <td>${r.students_with_scores}</td>
      <td>${r.avg_score != null ? `<span style="font-weight:700;color:${scoreColor(r.avg_score)};">${r.avg_score}</span>` : '—'}</td>
      <td>${r.avg_skill_score != null ? `<span style="font-weight:700;color:${scoreColor(r.avg_skill_score)};">${r.avg_skill_score}</span>` : '—'}</td>
      <td>
        ${r.advanced ? `<span class="badge badge-accent" style="margin:1px;">A:${r.advanced}</span>` : ''}
        ${r.proficient ? `<span class="badge badge-success" style="margin:1px;">P:${r.proficient}</span>` : ''}
        ${r.on_track ? `<span class="badge badge-info" style="margin:1px;">OT:${r.on_track}</span>` : ''}
        ${r.developing ? `<span class="badge badge-warning" style="margin:1px;">D:${r.developing}</span>` : ''}
        ${r.emerging ? `<span class="badge badge-error" style="margin:1px;">E:${r.emerging}</span>` : ''}
      </td>
    </tr>`).join('');
    return `<div class="card"><div class="card-header"><div class="card-title">Student Growth by School</div><div class="card-subtitle">All time · active students with assessments</div></div>
      <div class="table-container"><table class="table">
        <thead><tr><th>School</th><th>Assessed</th><th>Avg Ufit Score</th><th>Avg Skill Score</th><th>Band Distribution</th></tr></thead>
        <tbody>${tableRows}</tbody>
      </table></div></div>`;
  }

  return errorCard('Unknown report type.');
}

/* ============================================================
   25b. STUDENT PROGRESS MODAL (admin + principal + coach)
   ============================================================ */
async function openStudentProgressModal(studentId) {
  openModal(`<div class="modal-header"><h2 class="modal-title">Student Progress</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <div class="modal-body"><div class="spinner"></div><div class="loading-text">Loading…</div></div>`);

  let d;
  try {
    d = await api('GET', `/api/students/${studentId}/progress`);
  } catch (err) {
    const mb = document.querySelector('.modal-body');
    if (mb) mb.innerHTML = errorCard(err.message); return;
  }

  const st = d.student || {};
  const overall = d.overall;
  const domains = d.domains || [];
  const skills = d.skills || [];
  const recent = d.recent_assessments || [];

  const bandColor = b => ({ Emerging: 'error', Developing: 'warning', 'On Track': 'info', Proficient: 'success', Advanced: 'accent', Mastery: 'accent' }[b] || 'secondary');
  const scoreBar = (score, max = 100, color = 'var(--color-primary)') => {
    const pct = Math.min(Math.round(((score ?? 0) / max) * 100), 100);
    return `<div style="display:flex;align-items:center;gap:8px;">
      <div style="flex:1;background:var(--color-border);border-radius:4px;height:8px;">
        <div style="width:${pct}%;background:${color};border-radius:4px;height:8px;transition:width 400ms;"></div>
      </div>
      <span style="min-width:36px;font-size:0.75rem;text-align:right;font-weight:600;">${score ?? '—'}</span>
    </div>`;
  };
  const bandScoreColor = score => score >= 70 ? 'var(--color-success)' : score >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';

  // Derive overall growth from skills
  const skillGrowths = skills.map(sk => sk.growth_amount).filter(g => g != null);
  const totalGrowth = skillGrowths.length ? Math.round(skillGrowths.reduce((a,b) => a+b, 0) / skillGrowths.length * 10) / 10 : null;

  const domainRows = domains.map(dm => {
    const score = dm.current_domain_score;
    const pct = score != null ? Math.min(Math.round(score), 100) : null;
    const growth = dm.growth_amount != null ? (dm.growth_amount > 0 ? `+${dm.growth_amount}` : dm.growth_amount) : null;
    const band = score != null ? (score >= 70 ? 'Proficient' : score >= 50 ? 'On Track' : score >= 30 ? 'Developing' : 'Emerging') : null;
    return `
      <div style="padding:12px 0;border-bottom:1px solid var(--color-border);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <span style="font-weight:600;font-size:0.9rem;">${esc(fmtSkillName(dm.domain_name))}</span>
          <div style="display:flex;gap:8px;align-items:center;">
            ${band != null ? `<span class="badge badge-${bandColor(band)}">${band}</span>` : '<span class="badge badge-secondary">No Data</span>'}
            ${growth != null ? `<span style="font-size:0.8rem;color:${parseFloat(growth) >= 0 ? 'var(--color-success)' : 'var(--color-danger)'};">${growth > 0 ? '↑' : growth < 0 ? '↓' : '→'} ${growth} pts</span>` : ''}
          </div>
        </div>
        ${pct != null ? scoreBar(pct, 100, bandScoreColor(pct)) : '<span style="font-size:0.75rem;color:var(--color-text-secondary);">No scores yet</span>'}
        <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:var(--color-text-secondary);margin-top:2px;"><span>0</span><span>100</span></div>
      </div>`;
  }).join('');

  const skillsByDomain = {};
  skills.forEach(sk => { (skillsByDomain[sk.domain_name] = skillsByDomain[sk.domain_name] || []).push(sk); });
  const skillRows = Object.entries(skillsByDomain).map(([dname, sks]) => `
    <div style="margin-bottom:16px;">
      <div style="font-size:0.7rem;font-weight:700;color:var(--color-text-secondary);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--color-border);">${esc(dname)}</div>
      ${sks.map(sk => {
        const grew = sk.growth_amount > 0;
        const fell = sk.growth_amount < 0;
        const growthLabel = sk.growth_amount != null
          ? `<span style="font-size:0.7rem;color:${grew ? 'var(--color-success)' : fell ? 'var(--color-danger)' : 'var(--color-text-secondary)'};">${grew ? '↑' : fell ? '↓' : '→'} ${sk.growth_amount > 0 ? '+' : ''}${sk.growth_amount}</span>`
          : '';
        return `
        <div style="padding:6px 0;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <span style="font-size:0.85rem;font-weight:500;">${esc(fmtSkillName(sk.skill_name))}</span>
            <div style="display:flex;gap:6px;align-items:center;">
              ${growthLabel}
              <span class="badge badge-${bandColor(sk.performance_band)}" style="font-size:0.65rem;">${esc(sk.performance_band || '—')}</span>
            </div>
          </div>
          ${scoreBar(sk.current_score ?? 0, 100, bandScoreColor(sk.current_score ?? 0))}
          ${sk.baseline_score != null && sk.baseline_score !== sk.current_score ? (() => {
            const diff = (sk.current_score ?? 0) - sk.baseline_score;
            const diffColor = diff > 0 ? 'var(--color-success)' : diff < 0 ? 'var(--color-danger)' : 'var(--color-text-secondary)';
            const diffStr = diff > 0 ? `+${diff}` : `${diff}`;
            return `<div style="font-size:0.7rem;margin-top:3px;display:flex;gap:6px;align-items:center;">
              <span style="color:var(--color-text-secondary);">Baseline <strong>${sk.baseline_score}</strong></span>
              <span style="color:var(--color-text-secondary);">→</span>
              <span>Now <strong style="color:${bandScoreColor(sk.current_score ?? 0)};">${sk.current_score}</strong></span>
              <span style="font-weight:700;color:${diffColor};">(${diffStr})</span>
            </div>`;
          })() : ''}
        </div>`;
      }).join('')}
    </div>`).join('');

  const recentRows = recent.map((a, i) => {
    const isLatest = i === 0;
    const scoreList = (a.scores || []).map(sc => {
      const ns = sc.normalized_score;
      const nsColor = ns == null ? 'inherit' : ns >= 80 ? 'var(--color-success)' : ns >= 60 ? 'var(--color-primary)' : ns >= 40 ? 'var(--color-warning)' : 'var(--color-danger)';
      return `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:0.78rem;">
        <span style="color:var(--color-text-secondary);">${esc(fmtSkillName(sc.skill_name))}</span>
        <div style="display:flex;gap:6px;align-items:center;">
          ${sc.growth_flag ? '<span style="color:var(--color-success);font-size:0.7rem;">↑ Growth</span>' : ''}
          <span style="font-weight:700;min-width:28px;text-align:right;color:${nsColor};">${ns ?? '—'}</span>
        </div>
      </div>`;}).join('');
    return `
      <div style="border:1px solid var(--color-border);border-radius:8px;padding:12px;margin-bottom:10px;${isLatest ? 'border-color:var(--color-primary);' : ''}">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <div>
            <span style="font-weight:600;font-size:0.9rem;">${fmtDate(a.assessment_date)}</span>
            ${isLatest ? '<span class="badge badge-success" style="margin-left:6px;font-size:0.65rem;">Latest</span>' : '<span class="badge badge-secondary" style="margin-left:6px;font-size:0.65rem;">Baseline</span>'}
          </div>
          <span style="font-size:0.75rem;color:var(--color-text-secondary);">${fmtLabel(a.assessment_method)} · ${a.score_count} skill${a.score_count !== 1 ? 's' : ''}</span>
        </div>
        ${a.overall_assessment_notes ? `<div style="font-size:0.8rem;color:var(--color-text-secondary);font-style:italic;margin-bottom:8px;">"${esc(a.overall_assessment_notes)}"</div>` : ''}
        ${scoreList}
      </div>`;
  }).join('');

  const mb = document.querySelector('.modal-body');
  if (!mb) return;
  mb.innerHTML = `
    <div style="padding:0;">
      <div style="margin-bottom:16px;">
        <div style="font-size:1.125rem;font-weight:700;">${esc(st.student_last_name)}, ${esc(st.student_first_name)}</div>
        <div style="font-size:0.8rem;color:var(--color-text-secondary);">Grade ${esc(st.grade_level || '—')} &mdash; ${esc(st.school_name || '—')}</div>
      </div>
      ${overall ? `
      <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
        <div class="stat-card" style="flex:1;min-width:110px;">
          <div class="stat-label">Overall Score</div>
          <div class="stat-value" style="color:${bandScoreColor(overall.overall_ufit_score ?? 0)};">${Math.round(overall.overall_ufit_score ?? overall.overall_skill_score ?? 0)}<span style="font-size:0.75rem;color:var(--color-text-secondary);">/100</span></div>
        </div>
        <div class="stat-card" style="flex:1;min-width:110px;">
          <div class="stat-label">Performance</div>
          <div class="stat-value" style="font-size:1rem;"><span class="badge badge-${bandColor(overall.readiness_band)}">${fmtLabel(overall.readiness_band)}</span></div>
        </div>
        <div class="stat-card" style="flex:1;min-width:110px;">
          <div class="stat-label">Avg Growth</div>
          <div class="stat-value" style="color:${totalGrowth > 0 ? 'var(--color-success)' : totalGrowth < 0 ? 'var(--color-danger)' : 'inherit'};">${totalGrowth != null ? (totalGrowth >= 0 ? '+' : '') + totalGrowth : '—'}<span style="font-size:0.75rem;color:var(--color-text-secondary);"> pts</span></div>
        </div>
      </div>` : `<div class="alert alert-info" style="margin-bottom:16px;">No assessments yet — submit one to see progress.</div>`}
      ${domains.length ? `
      <div style="margin-bottom:20px;">
        <div style="font-weight:700;margin-bottom:10px;">Domain Breakdown</div>
        ${domainRows}
      </div>` : ''}
      ${skills.length ? `
      <div style="margin-bottom:20px;">
        <div style="font-weight:700;margin-bottom:10px;">Skill Detail</div>
        ${skillRows}
      </div>` : ''}
      ${recent.length ? `
      <div>
        <div style="font-weight:700;margin-bottom:10px;">Assessment History</div>
        ${recentRows}
      </div>` : ''}
    </div>`;
}

/* ============================================================
   26_eod. ADMIN EOD REPORTS
   ============================================================ */
async function loadAdminEodPage(container) {
  let schools = [];
  try { const sd = await api('GET', '/api/admin/schools'); schools = sd.schools || []; } catch (_) {}

  const schoolOpts = schools.map(s => `<option value="${s.school_id}">${esc(s.school_name)}</option>`).join('');
  const today = new Date().toISOString().slice(0, 10);
  const thirtyAgo = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);

  container.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px;">
      <div class="text-h2">EOD Reports</div>
    </div>
    <div class="card" style="margin-bottom:16px;">
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;">
        <div class="form-group" style="margin:0;flex:1;min-width:140px;">
          <label class="form-label">School</label>
          <select class="form-input" id="eod-school-filter">
            <option value="">All Schools</option>${schoolOpts}
          </select>
        </div>
        <div class="form-group" style="margin:0;min-width:130px;">
          <label class="form-label">From</label>
          <input class="form-input" type="date" id="eod-from" value="${thirtyAgo}" />
        </div>
        <div class="form-group" style="margin:0;min-width:130px;">
          <label class="form-label">To</label>
          <input class="form-input" type="date" id="eod-to" value="${today}" />
        </div>
        <div class="form-group" style="margin:0;min-width:110px;">
          <label class="form-label">Status</label>
          <select class="form-input" id="eod-status-filter">
            <option value="">All</option>
            <option value="ontime">On Time</option>
            <option value="late">Late</option>
          </select>
        </div>
        <button class="btn btn-primary" id="eod-run-btn" style="align-self:flex-end;">Search</button>
      </div>
    </div>
    <div id="eod-admin-results">${renderSkeleton(5)}</div>`;

  async function runEodSearch() {
    const schoolId = document.getElementById('eod-school-filter')?.value || '';
    const from = document.getElementById('eod-from')?.value || thirtyAgo;
    const to = document.getElementById('eod-to')?.value || today;
    const status = document.getElementById('eod-status-filter')?.value || '';
    const res = document.getElementById('eod-admin-results');
    if (!res) return;
    res.innerHTML = renderSkeleton(5);

    try {
      const params = new URLSearchParams({ from, to, per_page: 100 });
      if (schoolId) params.set('school_id', schoolId);
      const d = await api('GET', `/api/eod-reports?${params}`);
      let reports = d.reports || [];
      if (status === 'ontime') reports = reports.filter(r => r.submitted_on_time);
      if (status === 'late')   reports = reports.filter(r => !r.submitted_on_time);

      if (!reports.length) {
        res.innerHTML = `<div class="empty-state"><div class="empty-state-title">No EOD reports found</div><div class="empty-state-text">Try adjusting the date range or filters.</div></div>`;
        return;
      }

      // Summary bar
      const total = reports.length;
      const ontime = reports.filter(r => r.submitted_on_time).length;
      const late = total - ontime;
      const flags = reports.filter(r => r.injury_incident_flag).length;
      const followups = reports.filter(r => r.followup_needed).length;

      res.innerHTML = `
        <div class="stats-grid" style="margin-bottom:16px;">
          ${statCard('Total Reports', total, iconEod(), '')}
          ${statCard('On Time', ontime, iconEod(), 'success')}
          ${statCard('Late', late, iconEod(), late > 0 ? 'error' : '')}
          ${statCard('Flags / Incidents', flags, iconIncidents(), flags > 0 ? 'error' : '')}
          ${statCard('Follow-ups Needed', followups, iconIncidents(), followups > 0 ? 'accent' : '')}
        </div>
        <div class="card">
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr>
                <th>Date</th><th>Coach</th><th>School</th>
                <th>Submitted</th><th>Incident</th><th>Follow-up</th><th>School Concern</th><th></th>
              </tr></thead>
              <tbody>${reports.map(r => {
                const _rid = _modalStore.set(r);
                const timely = r.submitted_on_time
                  ? '<span class="badge badge-success">On Time</span>'
                  : '<span class="badge badge-error">Late</span>';
                const incident = r.injury_incident_flag
                  ? '<span class="badge badge-error">⚠ Yes</span>' : '<span class="text-muted">—</span>';
                const fu = r.followup_needed
                  ? '<span class="badge badge-accent">Yes</span>' : '<span class="text-muted">—</span>';
                const concern = r.school_concerns
                  ? '<span class="badge badge-warning">Yes</span>' : '<span class="text-muted">—</span>';
                return `<tr>
                  <td style="white-space:nowrap;">${fmtDate(r.report_date)}</td>
                  <td>${esc(r.coach_name || '—')}</td>
                  <td>${esc(r.school_name || '—')}</td>
                  <td>${timely}</td>
                  <td>${incident}</td>
                  <td>${fu}</td>
                  <td>${concern}</td>
                  <td><button class="btn btn-ghost btn-sm" onclick="openEodDetailModal(_modalStore.get(${_rid}))">View</button></td>
                </tr>`;
              }).join('')}</tbody>
            </table>
          </div>
        </div>`;
    } catch (err) {
      res.innerHTML = errorCard(err.message);
    }
  }

  document.getElementById('eod-run-btn')?.addEventListener('click', runEodSearch);
  // Auto-run with defaults
  runEodSearch();
}

/* ============================================================
   26a. ASSESSMENT WINDOWS (admin)
   ============================================================ */
async function loadWindowsPage(container) {
  container.innerHTML = renderSkeleton(4);
  let windows = [], schools = [];
  try {
    const [wd, sd] = await Promise.all([
      api('GET', '/api/assessment-windows'),
      api('GET', '/api/admin/schools'),
    ]);
    windows = wd.windows || [];
    schools = sd.schools || [];
  } catch (err) {
    container.innerHTML = errorCard(err.message); return;
  }

  const statusBadge = s => {
    const map = { active: 'success', upcoming: 'info', closed: 'secondary' };
    return `<span class="badge badge-${map[s] || 'secondary'}">${esc(s)}</span>`;
  };

  const rows = windows.map(w => { const _wid = _modalStore.set(w); return `
    <tr>
      <td>${esc(w.window_name)}</td>
      <td>${esc(w.school_name || '—')}</td>
      <td style="white-space:nowrap;">${esc(w.start_date)} – ${esc(w.end_date)}</td>
      <td>${esc(w.assessment_focus || '—')}</td>
      <td>${statusBadge(w.status)}</td>
      <td style="display:flex;gap:4px;">
        <button class="btn btn-ghost btn-sm" onclick="openEditWindowModal(_modalStore.get(${_wid}))" title="Edit">${iconEdit()}</button>
        ${w.status !== 'closed' ? `<button class="btn btn-ghost btn-sm" onclick="patchWindow(${w.window_id},'${w.status === 'active' ? 'closed' : 'active'}',this)">
          ${w.status === 'active' ? 'Close' : 'Activate'}
        </button>` : ''}
      </td>
    </tr>`; }).join('');

  const schoolOpts = schools.map(s => `<option value="${s.school_id}">${esc(s.school_name)}</option>`).join('');

  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">Assessment Windows</h2>
        <button class="btn btn-primary btn-sm" onclick="document.getElementById('new-window-form').style.display='block'">+ New Window</button>
      </div>
      <form id="new-window-form" class="form-stack" style="display:none;padding:16px;border-top:1px solid var(--color-border);" onsubmit="submitNewWindow(event)">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Window Name *</label>
            <input class="form-input" name="window_name" required maxlength="120" placeholder="e.g. Spring 2026 Assessment" />
          </div>
          <div class="form-group">
            <label class="form-label">School *</label>
            <select class="form-input" name="school_id" required><option value="">— Select —</option>${schoolOpts}</select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Start Date *</label>
            <input class="form-input" type="date" name="start_date" required />
          </div>
          <div class="form-group">
            <label class="form-label">End Date *</label>
            <input class="form-input" type="date" name="end_date" required />
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Assessment Focus</label>
          <textarea class="form-input form-textarea" name="assessment_focus" rows="2" maxlength="500"></textarea>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-primary" type="submit">Create Window</button>
          <button class="btn btn-ghost" type="button" onclick="document.getElementById('new-window-form').style.display='none'">Cancel</button>
        </div>
      </form>
      ${windows.length ? `
      <div class="table-container">
        <table class="table">
          <thead><tr><th>Name</th><th>School</th><th>Dates</th><th>Focus</th><th>Status</th><th></th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>` : `<div class="empty-state"><div class="empty-state-title">No assessment windows yet</div><div class="empty-state-text">Create a window to let coaches submit assessments for a specific period.</div></div>`}
    </div>`;
}

async function submitNewWindow(e) {
  e.preventDefault();
  const btn = e.target.querySelector('[type="submit"]');
  btn.disabled = true; btn.textContent = 'Creating…';
  const fd = new FormData(e.target);
  try {
    await api('POST', '/api/assessment-windows', {
      window_name: fd.get('window_name').trim(),
      school_id: parseInt(fd.get('school_id'), 10),
      start_date: fd.get('start_date'),
      end_date: fd.get('end_date'),
      assessment_focus: fd.get('assessment_focus').trim() || null,
    });
    showAlert('Window created.', 'success');
    loadWindowsPage(document.getElementById('page-main'));
  } catch (err) {
    showAlert(err.message, 'error');
    btn.disabled = false; btn.textContent = 'Create Window';
  }
}

function openEditWindowModal(w) {
  openModal(`
    <div class="modal-header"><h2 class="modal-title">Edit Window</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <form id="edit-window-form" class="modal-body form-stack">
      <div class="form-group">
        <label class="form-label">Window Name *</label>
        <input class="form-input" name="window_name" value="${esc(w.window_name)}" required maxlength="200" />
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Start Date *</label>
          <input class="form-input" type="date" name="start_date" value="${esc(w.start_date)}" required />
        </div>
        <div class="form-group">
          <label class="form-label">End Date *</label>
          <input class="form-input" type="date" name="end_date" value="${esc(w.end_date)}" required />
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Status</label>
        <select class="form-input form-select" name="status">
          <option value="upcoming" ${w.status === 'upcoming' ? 'selected' : ''}>Upcoming</option>
          <option value="active" ${w.status === 'active' ? 'selected' : ''}>Active</option>
          <option value="closed" ${w.status === 'closed' ? 'selected' : ''}>Closed</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Assessment Focus</label>
        <textarea class="form-input form-textarea" name="assessment_focus" rows="2" maxlength="500">${esc(w.assessment_focus || '')}</textarea>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="edit-window-submit">Save Changes</button>
      </div>
    </form>`);

  document.getElementById('edit-window-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('edit-window-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    const fd = new FormData(e.target);
    try {
      await api('PATCH', `/api/assessment-windows/${w.window_id}`, {
        window_name: fd.get('window_name').trim(),
        start_date: fd.get('start_date'),
        end_date: fd.get('end_date'),
        status: fd.get('status'),
        assessment_focus: fd.get('assessment_focus').trim() || null,
      });
      closeModal();
      showAlert('Window updated.', 'success');
      loadWindowsPage(document.getElementById('page-main'));
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.textContent = 'Save Changes';
    }
  });
}

async function patchWindow(windowId, newStatus, btn) {
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
  try {
    await api('PATCH', `/api/assessment-windows/${windowId}`, { status: newStatus });
    showAlert(`Window ${newStatus}.`, 'success');
    loadWindowsPage(document.getElementById('page-main'));
  } catch (err) {
    showAlert(err.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = newStatus === 'active' ? 'Activate' : 'Close'; }
  }
}

/* ============================================================
   26b. BEHAVIOR OBSERVATIONS (coach)
   ============================================================ */
async function loadBehaviorObsPage(container) {
  container.innerHTML = renderSkeleton(3);
  let observations = [], students = [];
  try {
    const [od, sd] = await Promise.all([
      api('GET', '/api/behavior-observations'),
      api('GET', '/api/my-students'),
    ]);
    observations = od.observations || [];
    students = sd.students || [];
  } catch (err) {
    container.innerHTML = errorCard(err.message); return;
  }

  const scoreChip = (label, val) => val != null
    ? `<span style="font-size:0.75rem;background:var(--color-bg);border:1px solid var(--color-border);border-radius:6px;padding:2px 6px;">${label} ${val}</span>`
    : '';

  const rows = observations.map(o => `
    <div class="card" style="padding:12px 16px;margin-bottom:8px;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div>
          <div style="font-weight:600;">${esc(o.student_last_name || '')}, ${esc(o.student_first_name || '')}</div>
          <div style="font-size:0.75rem;color:var(--color-text-secondary);">${esc(o.observation_date)}</div>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;">
          ${scoreChip('🤝', o.teamwork_score)}
          ${scoreChip('💪', o.effort_score)}
          ${scoreChip('🧘', o.self_control_score)}
          ${scoreChip('👂', o.listening_score)}
          ${scoreChip('🏅', o.sportsmanship_score)}
          ${scoreChip('⭐', o.confidence_score)}
        </div>
      </div>
      ${o.notes ? `<div style="margin-top:6px;font-size:0.8rem;color:var(--color-text-secondary);">${esc(o.notes)}</div>` : ''}
    </div>`).join('');

  const studentOpts = students.map(s => `<option value="${s.student_id}">${esc(s.student_last_name)}, ${esc(s.student_first_name)} (Gr ${s.grade_level || '?'})</option>`).join('');

  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-weight:700;font-size:1.125rem;">Behavior Observations</h2>
      <button class="btn btn-primary" id="new-obs-btn">+ New Observation</button>
    </div>
    ${observations.length ? rows : `<div class="empty-state"><div class="empty-state-title">No observations yet</div><div class="empty-state-text">Log a student's SEL behavior scores after class.</div></div>`}`;

  document.getElementById('new-obs-btn')?.addEventListener('click', () => openBehaviorObsModal(students));
}

async function loadMyPerformancePage(container) {
  container.innerHTML = `
    <div class="page-header">
      <div><div class="text-h2">My Performance</div>
           <div class="text-caption">Your rolling 30-day score</div></div>
    </div>
    <div id="my-score-content">${renderSkeleton(3)}</div>`;

  try {
    const d = await api('GET', '/api/coach/my-score');
    const sc = d.scorecard || {};
    const snaps = d.snapshots || [];
    const el = document.getElementById('my-score-content');
    if (!el) return;

    const overall = sc.overall_score != null ? Math.round(sc.overall_score) : null;
    const bandClass = {'Exceptional':'badge-success','Strong':'badge-success','Meeting Expectations':'','Developing':'badge-warning','Needs Improvement':'badge-error'}[sc.performance_band] || '';

    const pillarBar = (label, score, detail) => {
      const pct = score != null ? Math.round(score) : 0;
      const color = pct >= 75 ? 'var(--color-success)' : pct >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
      return `
        <div class="card" style="padding:16px;margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="font-weight:600;font-size:1rem;">${label}</span>
            <span style="font-size:1.25rem;font-weight:700;">${score != null ? Math.round(score) : 'N/A'}<span style="font-size:0.75rem;color:var(--color-text-secondary)">/100</span></span>
          </div>
          <div style="background:var(--color-border);border-radius:6px;height:10px;">
            <div style="width:${pct}%;background:${color};border-radius:6px;height:10px;transition:width 0.5s;"></div>
          </div>
          ${detail ? `<div class="text-caption" style="margin-top:6px;">${detail}</div>` : ''}
        </div>`;
    };

    const fmtRate = r => r != null ? Math.round(r) + '%' : 'N/A';
    const complianceDetail = [
      `EOD on-time: ${fmtRate(sc.eod_ontime_rate)}`,
      `Sessions logged: ${fmtRate(sc.session_log_rate)}`,
      sc.incident_file_rate != null ? `Incidents filed: ${fmtRate(sc.incident_file_rate)}` : null,
      sc.assessment_part_rate != null ? `Assessment: ${fmtRate(sc.assessment_part_rate)}` : null,
    ].filter(Boolean).join(' · ');

    const outcomesDetail = [
      sc.avg_growth != null ? `Avg student growth: ${sc.avg_growth > 0 ? '+' : ''}${sc.avg_growth}pts` : null,
      `Attendance: ${fmtRate(sc.participation_rate)}`,
    ].filter(Boolean).join(' · ');

    const historyRows = snaps.length
      ? snaps.map(s => `<tr>
          <td>${esc(s.period_start)} – ${esc(s.period_end)}</td>
          <td><strong>${s.overall_score != null ? Math.round(s.overall_score) : '—'}</strong></td>
          <td><span class="badge">${esc(s.performance_band || '—')}</span></td>
        </tr>`).join('')
      : `<tr><td colspan="3" class="text-muted" style="padding:12px;">No history yet.</td></tr>`;

    el.innerHTML = `
      <div class="card" style="text-align:center;padding:32px 16px;margin-bottom:20px;">
        <div style="font-size:3.5rem;font-weight:800;color:var(--color-primary);line-height:1;">${overall != null ? overall : '—'}</div>
        <div style="margin-top:8px;"><span class="badge ${bandClass}" style="font-size:1rem;padding:6px 16px;">${esc(sc.performance_band || 'No data yet')}</span></div>
        <div class="text-caption" style="margin-top:8px;">Last 30 days · updated ${esc(sc.period_end || 'today')}</div>
      </div>
      ${pillarBar('Compliance', sc.compliance_score, complianceDetail)}
      ${pillarBar('Student Outcomes', sc.outcomes_score, outcomesDetail)}
      ${pillarBar('Supervisor Observations', sc.observations_score,
          sc.observation_count ? `Based on ${sc.observation_count} observation${sc.observation_count > 1 ? 's' : ''}` : 'No observations on record yet')}
      ${snaps.length ? `
        <div class="card" style="padding:16px;margin-top:8px;">
          <div style="font-weight:600;margin-bottom:12px;">Score History</div>
          <table class="data-table">
            <thead><tr><th>Period</th><th>Score</th><th>Band</th></tr></thead>
            <tbody>${historyRows}</tbody>
          </table>
        </div>` : ''}`;
  } catch (err) {
    const el = document.getElementById('my-score-content');
    if (el) el.innerHTML = errorCard(err.message);
  }
}

function openBehaviorObsModal(students) {
  const todayStr = new Date().toISOString().split('T')[0];
  const studentOpts = students.map(s => `<option value="${s.student_id}">${esc(s.student_last_name)}, ${esc(s.student_first_name)} (Gr ${s.grade_level || '?'})</option>`).join('');
  const dimField = (name, label) => `
    <div class="form-group">
      <label class="form-label">${label} (1–5)</label>
      <select class="form-input" name="${name}">
        <option value="">—</option>
        <option value="1">1 — Rarely</option>
        <option value="2">2 — Sometimes</option>
        <option value="3">3 — Usually</option>
        <option value="4">4 — Consistently</option>
        <option value="5">5 — Exemplary</option>
      </select>
    </div>`;

  openModal(`
    <div class="modal-header">
      <h2 class="modal-title">New Behavior Observation</h2>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <form id="behavior-form" class="modal-body form-stack">
      <div class="form-group">
        <label class="form-label">Student *</label>
        <select class="form-input" name="student_id" required>
          <option value="">— Select student —</option>${studentOpts}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Date *</label>
        <input class="form-input" type="date" name="observation_date" value="${todayStr}" max="${todayStr}" required />
      </div>
      ${dimField('teamwork_score', '🤝 Teamwork')}
      ${dimField('effort_score', '💪 Effort')}
      ${dimField('self_control_score', '🧘 Self Control')}
      ${dimField('listening_score', '👂 Listening')}
      ${dimField('sportsmanship_score', '🏅 Sportsmanship')}
      ${dimField('confidence_score', '⭐ Confidence')}
      <div class="form-group">
        <label class="form-label">Notes</label>
        <textarea class="form-input form-textarea" name="notes" rows="2" maxlength="1000" placeholder="Any notable observations…"></textarea>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="behavior-submit">Save Observation</button>
      </div>
    </form>`);

  document.getElementById('behavior-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('behavior-submit');
    btn.disabled = true; btn.textContent = 'Saving…';
    const fd = new FormData(e.target);
    const body = {
      student_id: parseInt(fd.get('student_id'), 10),
      observation_date: fd.get('observation_date'),
      notes: fd.get('notes').trim() || null,
    };
    const dims = ['teamwork_score','effort_score','self_control_score','listening_score','sportsmanship_score','confidence_score'];
    dims.forEach(d => { const v = fd.get(d); if (v) body[d] = parseInt(v, 10); });
    try {
      await api('POST', '/api/behavior-observations', body);
      closeModal();
      showAlert('Observation saved.', 'success');
      loadBehaviorObsPage(document.getElementById('page-main'));
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.textContent = 'Save Observation';
    }
  });
}

/* ============================================================
   26. NOTIFICATIONS
   ============================================================ */
async function loadNotifications() {
  if (!state.user) return;
  try {
    const d = await api('GET', '/api/notifications');
    state.notifications = d.notifications || [];
    const bellBtn = document.getElementById('bell-btn');
    if (bellBtn) {
      const unread = state.notifications.filter(n => !n.is_read).length;
      const badge = unread > 0
        ? `<span style="position:absolute;top:2px;right:2px;background:var(--color-error,#dc2626);color:#fff;border-radius:50%;width:14px;height:14px;font-size:9px;display:flex;align-items:center;justify-content:center;font-weight:700;">${unread > 9 ? '9+' : unread}</span>`
        : '';
      bellBtn.innerHTML = iconBell() + badge;
    }
  } catch (_) {}
}

function showNotificationsPanel() {
  const notifs = state.notifications;
  if (!notifs.length) {
    showAlert('No notifications.', 'info');
    return;
  }
  const unreadNotifs = notifs.filter(n => !n.is_read);
  const readNotifs   = notifs.filter(n =>  n.is_read);
  const renderNotif = n => `
    <div style="padding:12px 16px;border-bottom:1px solid var(--color-border);${!n.is_read ? 'background:var(--color-primary-pale,#eff6ff);' : ''}display:flex;gap:10px;align-items:flex-start;">
      <div style="flex:1;">
        <div style="font-size:0.8rem;font-weight:${!n.is_read ? '600' : '400'};color:var(--color-text);">${esc(n.message)}</div>
        <div style="font-size:0.72rem;color:var(--color-text-secondary);margin-top:2px;">${fmtDate(n.created_at)}</div>
      </div>
      ${!n.is_read ? `<button class="btn btn-ghost btn-sm" style="flex-shrink:0;font-size:0.72rem;" onclick="markNotificationRead(${n.notification_id})">Mark read</button>` : ''}
    </div>`;

  openModal(`
    <div class="modal-header">
      <h2 class="modal-title">Notifications</h2>
      <button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button>
    </div>
    <div class="modal-body" style="padding:0;max-height:420px;overflow-y:auto;">
      ${unreadNotifs.length ? `<div style="padding:8px 16px;font-size:0.72rem;font-weight:700;color:var(--color-text-secondary);text-transform:uppercase;letter-spacing:.05em;">Unread (${unreadNotifs.length})</div>` : ''}
      ${unreadNotifs.map(renderNotif).join('')}
      ${readNotifs.length ? `<div style="padding:8px 16px;font-size:0.72rem;font-weight:700;color:var(--color-text-secondary);text-transform:uppercase;letter-spacing:.05em;border-top:1px solid var(--color-border);">Earlier</div>` : ''}
      ${readNotifs.map(renderNotif).join('')}
      ${!notifs.length ? `<div class="empty-state"><div class="empty-state-title">No notifications</div></div>` : ''}
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Close</button>
    </div>`);
}

async function markNotificationRead(notifId) {
  try {
    await api('POST', `/api/notifications/${notifId}/read`);
    state.notifications = state.notifications.map(n =>
      n.notification_id === notifId ? { ...n, is_read: true } : n
    );
    loadNotifications();
    closeModal();
    showNotificationsPanel();
  } catch (err) {
    showAlert(err.message, 'error');
  }
}

/* ============================================================
   27. PROGRAMS (Admin)
   ============================================================ */
async function loadProgramsPage(container) {
  container.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
      <div class="text-h2">Programs</div>
      <button class="btn btn-primary" onclick="openAddProgramModal()">${iconPlus()} Add Program</button>
    </div>
    <div id="programs-content">${renderSkeleton(4)}</div>`;

  let schools = [], programs = [];
  try {
    const [sd, pd] = await Promise.all([
      api('GET', '/api/admin/schools'),
      api('GET', '/api/programs'),
    ]);
    schools = sd.schools || [];
    programs = pd.programs || [];
  } catch (err) {
    document.getElementById('programs-content').innerHTML = errorCard(err.message);
    return;
  }

  const schoolOpts = schools.map(s => `<option value="${s.school_id}">${esc(s.school_name)}</option>`).join('');

  function renderPrograms(list) {
    const pc = document.getElementById('programs-list');
    if (!pc) return;
    if (!list.length) { pc.innerHTML = `<div class="empty-state"><div class="empty-state-title">No programs found</div></div>`; return; }
    pc.innerHTML = `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>Program Name</th><th>School</th><th>Type</th>
            <th>Grade Band</th><th>Dates</th><th>Coaches</th><th>Students</th><th>Status</th><th></th>
          </tr></thead>
          <tbody>${list.map(p => { const _pid = _modalStore.set(p); return `
            <tr>
              <td><strong>${esc(p.program_name)}</strong>${p.notes ? `<div class="text-caption">${esc(p.notes.slice(0, 60))}${p.notes.length > 60 ? '…' : ''}</div>` : ''}</td>
              <td>${esc(p.school_name || '—')}</td>
              <td><span class="badge">${fmtLabel(p.program_type)}</span></td>
              <td>${esc(p.grade_band || '—')}</td>
              <td style="white-space:nowrap;">${fmtDate(p.start_date)}${p.end_date ? ' – ' + fmtDate(p.end_date) : ''}</td>
              <td>${p.coach_count ?? 0}</td>
              <td>${p.student_count ?? 0}</td>
              <td><span class="badge ${p.program_status === 'active' ? 'badge-green' : 'badge-error'}">${fmtLabel(p.program_status)}</span></td>
              <td style="white-space:nowrap;">
                <button class="btn btn-ghost btn-sm" aria-label="Edit program" onclick="openEditProgramModal(_modalStore.get(${_pid}))">${iconEdit()}</button>
              </td>
            </tr>`; }).join('')}
          </tbody>
        </table>
      </div>`;
  }

  const gc = document.getElementById('programs-content');
  if (!gc) return;
  gc.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div class="card-title">All Programs</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <select class="form-input" id="prog-school-filter" style="width:auto;">
            <option value="">All Schools</option>${schoolOpts}
          </select>
          <select class="form-input" id="prog-status-filter" style="width:auto;">
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>
      <div id="programs-list">${renderSkeleton(3)}</div>
    </div>`;

  renderPrograms(programs);

  document.getElementById('prog-school-filter')?.addEventListener('change', e => {
    const sid = e.target.value ? parseInt(e.target.value) : null;
    const status = document.getElementById('prog-status-filter')?.value || '';
    renderPrograms(programs.filter(p =>
      (!sid || p.school_id === sid) && (!status || p.program_status === status)
    ));
  });
  document.getElementById('prog-status-filter')?.addEventListener('change', e => {
    const status = e.target.value;
    const sid = document.getElementById('prog-school-filter')?.value ? parseInt(document.getElementById('prog-school-filter').value) : null;
    renderPrograms(programs.filter(p =>
      (!sid || p.school_id === sid) && (!status || p.program_status === status)
    ));
  });
}

async function openAddProgramModal() {
  let schools = [];
  try { const d = await api('GET', '/api/admin/schools'); schools = d.schools || []; } catch (_) {}
  const schoolOpts = schools.map(s => `<option value="${s.school_id}">${esc(s.school_name)}</option>`).join('');
  const today = new Date().toISOString().slice(0, 10);

  openModal(`
    <div class="modal-header"><h2 class="modal-title">Add Program</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <form id="add-program-form" class="modal-body form-stack">
      <div class="form-group">
        <label class="form-label">School *</label>
        <select class="form-input form-select" name="school_id" required><option value="">Select school…</option>${schoolOpts}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Program Name *</label>
        <input class="form-input" name="program_name" placeholder="e.g. Lincoln After School Sports" required maxlength="200" />
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Program Type *</label>
          <select class="form-input form-select" name="program_type">
            <option value="pe_support">PE Support</option>
            <option value="lunch_sports">Lunch Sports</option>
            <option value="after_school_sports">After School Sports</option>
            <option value="psychomotor">Psychomotor</option>
            <option value="middle_school_skill_development">Middle School Skill Dev</option>
            <option value="tournament_program">Tournament Program</option>
            <option value="wellness_enrichment">Wellness Enrichment</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Grade Band</label>
          <select class="form-input form-select" name="grade_band">
            <option value="">Any</option>
            <option value="K-2">K–2</option>
            <option value="3-5">3–5</option>
            <option value="6-8">6–8</option>
            <option value="K-8">K–8</option>
          </select>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Start Date *</label>
          <input class="form-input" type="date" name="start_date" value="${today}" required />
        </div>
        <div class="form-group">
          <label class="form-label">End Date</label>
          <input class="form-input" type="date" name="end_date" />
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Reporting Cycle</label>
          <select class="form-input form-select" name="reporting_cycle">
            <option value="weekly">Weekly</option>
            <option value="biweekly">Biweekly</option>
            <option value="monthly">Monthly</option>
            <option value="quarterly" selected>Quarterly</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Frequency</label>
          <input class="form-input" name="frequency" placeholder="e.g. 3x/week" maxlength="100" />
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Notes</label>
        <textarea class="form-input form-textarea" name="notes" rows="2" maxlength="1000" placeholder="Any additional details…"></textarea>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="add-program-submit">Add Program</button>
      </div>
    </form>`);

  document.getElementById('add-program-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('add-program-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    const fd = new FormData(e.target);
    try {
      await api('POST', '/api/programs', {
        school_id: parseInt(fd.get('school_id')),
        program_name: fd.get('program_name').trim(),
        program_type: fd.get('program_type'),
        grade_band: fd.get('grade_band') || null,
        start_date: fd.get('start_date'),
        end_date: fd.get('end_date') || null,
        reporting_cycle: fd.get('reporting_cycle'),
        frequency: fd.get('frequency').trim() || null,
        notes: fd.get('notes').trim() || null,
      });
      closeModal();
      showAlert('Program created successfully!', 'success');
      loadProgramsPage(document.getElementById('page-main'));
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.textContent = 'Add Program';
    }
  });
}

function openEditProgramModal(p) {
  if (!p) return;
  const sel = (name, val) => `selected="${val}"`;
  openModal(`
    <div class="modal-header"><h2 class="modal-title">Edit Program</h2><button class="modal-close btn btn-ghost btn-sm" aria-label="Close" onclick="closeModal()">${iconClose()}</button></div>
    <form id="edit-program-form" class="modal-body form-stack">
      <div class="form-group">
        <label class="form-label">Program Name *</label>
        <input class="form-input" name="program_name" value="${esc(p.program_name || '')}" required maxlength="200" />
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Program Type</label>
          <select class="form-input form-select" name="program_type">
            <option value="pe_support" ${p.program_type==='pe_support'?'selected':''}>PE Support</option>
            <option value="lunch_sports" ${p.program_type==='lunch_sports'?'selected':''}>Lunch Sports</option>
            <option value="after_school_sports" ${p.program_type==='after_school_sports'?'selected':''}>After School Sports</option>
            <option value="psychomotor" ${p.program_type==='psychomotor'?'selected':''}>Psychomotor</option>
            <option value="middle_school_skill_development" ${p.program_type==='middle_school_skill_development'?'selected':''}>Middle School Skill Dev</option>
            <option value="tournament_program" ${p.program_type==='tournament_program'?'selected':''}>Tournament Program</option>
            <option value="wellness_enrichment" ${p.program_type==='wellness_enrichment'?'selected':''}>Wellness Enrichment</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Grade Band</label>
          <select class="form-input form-select" name="grade_band">
            <option value="" ${!p.grade_band?'selected':''}>Any</option>
            <option value="K-2" ${p.grade_band==='K-2'?'selected':''}>K–2</option>
            <option value="3-5" ${p.grade_band==='3-5'?'selected':''}>3–5</option>
            <option value="6-8" ${p.grade_band==='6-8'?'selected':''}>6–8</option>
            <option value="K-8" ${p.grade_band==='K-8'?'selected':''}>K–8</option>
          </select>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Start Date</label>
          <input class="form-input" type="date" name="start_date" value="${p.start_date || ''}" />
        </div>
        <div class="form-group">
          <label class="form-label">End Date</label>
          <input class="form-input" type="date" name="end_date" value="${p.end_date || ''}" />
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Status</label>
          <select class="form-input form-select" name="program_status">
            <option value="active" ${p.program_status==='active'?'selected':''}>Active</option>
            <option value="inactive" ${p.program_status==='inactive'?'selected':''}>Inactive</option>
            <option value="completed" ${p.program_status==='completed'?'selected':''}>Completed</option>
            <option value="paused" ${p.program_status==='paused'?'selected':''}>Paused</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Reporting Cycle</label>
          <select class="form-input form-select" name="reporting_cycle">
            <option value="weekly" ${p.reporting_cycle==='weekly'?'selected':''}>Weekly</option>
            <option value="biweekly" ${p.reporting_cycle==='biweekly'?'selected':''}>Biweekly</option>
            <option value="monthly" ${p.reporting_cycle==='monthly'?'selected':''}>Monthly</option>
            <option value="quarterly" ${p.reporting_cycle==='quarterly'?'selected':''}>Quarterly</option>
          </select>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Frequency</label>
        <input class="form-input" name="frequency" value="${esc(p.frequency || '')}" placeholder="e.g. 3x/week" maxlength="100" />
      </div>
      <div class="form-group">
        <label class="form-label">Notes</label>
        <textarea class="form-input form-textarea" name="notes" rows="2" maxlength="1000">${esc(p.notes || '')}</textarea>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="edit-program-submit">Save Changes</button>
      </div>
    </form>`);

  document.getElementById('edit-program-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('edit-program-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    const fd = new FormData(e.target);
    try {
      await api('PATCH', `/api/programs/${p.program_id}`, {
        program_name: fd.get('program_name').trim(),
        program_type: fd.get('program_type') || null,
        grade_band: fd.get('grade_band') || null,
        start_date: fd.get('start_date') || null,
        end_date: fd.get('end_date') || null,
        program_status: fd.get('program_status') || null,
        reporting_cycle: fd.get('reporting_cycle') || null,
        frequency: fd.get('frequency').trim() || null,
        notes: fd.get('notes').trim() || null,
      });
      closeModal();
      showAlert('Program updated!', 'success');
      loadProgramsPage(document.getElementById('page-main'));
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.textContent = 'Save Changes';
    }
  });
}

/* ============================================================
   28. LOGOUT
   ============================================================ */
async function handleLogout() {
  try { await api('POST', '/api/auth/logout'); } catch (_) {}
  state.user = null;
  state.currentPage = 'login';
  state._loginPortal = 'admin';
  state._studentSearch = '';
  state.notifications = [];
  window.history.replaceState({}, '', '/');
  render();
  showAlert('You have been signed out.', 'success');
}

/* ============================================================
   27. GLOBAL EVENT DELEGATION
   ============================================================ */
document.addEventListener('click', e => {
  if (e.target.closest('#settings-logout')) handleLogout();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeSidebar(); closeModal(); } });

/* ============================================================
   28. INIT
   ============================================================ */
async function init() {
  const app = document.getElementById('app');

  // If the URL contains ?reset_token=..., intercept and show the set-password screen.
  const urlParams = new URLSearchParams(window.location.search);
  const resetToken = urlParams.get('reset_token');
  if (resetToken) {
    history.replaceState(null, '', window.location.pathname); // strip token from URL bar
    if (app) renderSetPasswordScreen(app, resetToken);
    return;
  }

  if (app) app.innerHTML = `<div class="loading-overlay" style="min-height:100vh;"><div class="spinner spinner-lg"></div><div class="loading-text">Loading Ufit Motion…</div></div>`;
  try {
    const data = await api('GET', '/api/auth/session');
    if (data?.user || data?.email) {
      state.user = data.user || data;
      const urlPage = new URLSearchParams(window.location.search).get('page');
      state.currentPage = urlPage || 'dashboard';
    } else { state.currentPage = 'login'; }
  } catch (_) {
    state.currentPage = 'login';
    const stack = document.getElementById('alert-stack');
    if (stack) stack.innerHTML = '';
  }
  render();
  if (state.user) loadNotifications();
}

function renderSetPasswordScreen(app, token) {
  app.innerHTML = `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--color-background);padding:24px;">
      <div style="width:100%;max-width:400px;">
        <div style="background:var(--color-primary);padding:24px;border-radius:8px 8px 0 0;text-align:center;">
          <span style="color:#fff;font-size:1.5rem;font-weight:700;letter-spacing:0.04em;">UFIT MOTION</span>
        </div>
        <div style="background:var(--color-surface);border:1px solid var(--color-border);border-top:none;padding:32px;border-radius:0 0 8px 8px;">
          <h2 style="margin:0 0 6px;font-size:1.25rem;">Set your password</h2>
          <p style="margin:0 0 24px;color:var(--color-text-secondary);font-size:0.875rem;">Choose a password to activate your Ufit Motion account.</p>
          <div id="set-pw-alert" style="margin-bottom:12px;"></div>
          <form id="set-pw-form" class="form-stack">
            <div class="form-group">
              <label class="form-label">New Password</label>
              <input class="form-input" type="password" id="set-pw-input" minlength="8" placeholder="At least 8 characters" required autofocus />
            </div>
            <div class="form-group">
              <label class="form-label">Confirm Password</label>
              <input class="form-input" type="password" id="set-pw-confirm" minlength="8" placeholder="Repeat password" required />
            </div>
            <button class="btn btn-primary btn-full" type="submit" id="set-pw-btn">Set Password &amp; Sign In</button>
          </form>
        </div>
      </div>
    </div>`;

  document.getElementById('set-pw-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const pw = document.getElementById('set-pw-input').value;
    const confirm = document.getElementById('set-pw-confirm').value;
    const alertEl = document.getElementById('set-pw-alert');
    const btn = document.getElementById('set-pw-btn');

    if (pw !== confirm) {
      alertEl.innerHTML = `<div class="alert alert-error">Passwords do not match.</div>`;
      return;
    }
    if (pw.length < 8) {
      alertEl.innerHTML = `<div class="alert alert-error">Password must be at least 8 characters.</div>`;
      return;
    }

    btn.disabled = true; btn.textContent = 'Setting password…';
    try {
      await api('POST', '/api/auth/reset-password', { token, password: pw });
      alertEl.innerHTML = `<div class="alert alert-success">Password set! Signing you in…</div>`;
      // Auto-login after short delay so the user sees the success message
      setTimeout(() => { window.location.href = '/'; }, 1200);
    } catch (err) {
      alertEl.innerHTML = `<div class="alert alert-error">${esc(err.message || 'Something went wrong. The link may have expired.')}</div>`;
      btn.disabled = false; btn.textContent = 'Set Password & Sign In';
    }
  });
}

document.addEventListener('DOMContentLoaded', init);
