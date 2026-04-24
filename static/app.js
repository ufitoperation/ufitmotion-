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
const ADMIN_ROLES  = new Set(['ceo', 'admin', 'coach_overseer']);
const COACH_ROLES  = new Set(['head_coach', 'assistant_coach', 'site_coordinator']);
const SCHOOL_ROLES = new Set(['principal', 'school_staff']);

function getPortal(user) {
  if (!user) return 'login';
  const r = (user.role || '').toLowerCase();
  if (ADMIN_ROLES.has(r))  return 'admin';
  if (COACH_ROLES.has(r))  return 'coach';
  if (r === 'parent')      return 'parent';
  if (SCHOOL_ROLES.has(r)) return 'principal';
  return 'admin';
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
  settings: 'Settings', 'principal-dashboard': 'Dashboard', 'principal-students': 'My Students',
  'parent-home': 'My Children', windows: 'Assessment Windows', behavior: 'Behavior Observations',
  performance: 'My Performance',
};

function navigate(page) {
  state.currentPage = page;
  render();
  window.scrollTo({ top: 0, behavior: 'instant' });
}

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
      case 'incidents': loadIncidentsPage(main);   break;
      case 'windows':   loadWindowsPage(main);     break;
      case 'reports':   loadReportsPage(main); break;
      case 'settings':  main.innerHTML = renderSettingsPage(); attachSettingsListeners(); break;
      default:          loadAdminDashboard(main);
    }
  } else if (portal === 'coach') {
    switch (state.currentPage) {
      case 'dashboard':   loadCoachDashboard(main);   break;
      case 'sessions':    loadSessionsPage(main);     break;
      case 'eod-reports': loadEodPage(main);          break;
      case 'assessments': loadAssessmentsPage(main);  break;
      case 'behavior':    loadBehaviorObsPage(main);  break;
      case 'students':    loadMyStudents(main);        break;
      case 'incidents':   loadCoachIncidents(main);   break;
      case 'performance': loadMyPerformancePage(main); break;
      case 'settings':    main.innerHTML = renderSettingsPage(); attachSettingsListeners(); break;
      default:            loadCoachDashboard(main);
    }
  } else if (portal === 'principal') {
    switch (state.currentPage) {
      case 'dashboard':
      case 'principal-dashboard': loadPrincipalDashboard(main); break;
      case 'students':
      case 'principal-students':  loadPrincipalStudents(main); break;
      case 'settings': main.innerHTML = renderSettingsPage(); attachSettingsListeners(); break;
      default: loadPrincipalDashboard(main);
    }
  } else if (portal === 'parent') {
    loadParentHome(main);
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

/* ============================================================
   11. APP SHELL
   ============================================================ */
function navConfig(portal) {
  if (portal === 'admin') return [
    { page: 'dashboard', label: 'Dashboard', icon: iconDashboard },
    { page: 'schools',   label: 'Schools',   icon: iconSchools   },
    { page: 'coaches',   label: 'Coaches',   icon: iconCoaches   },
    { page: 'students',  label: 'Students',  icon: iconStudents  },
    { page: 'windows',   label: 'Windows',   icon: iconWindows   },
    { page: 'incidents', label: 'Incidents', icon: iconIncidents },
    { page: 'reports',   label: 'Reports',   icon: iconReports   },
    { page: 'settings',  label: 'Settings',  icon: iconSettings  },
  ];
  if (portal === 'coach') return [
    { page: 'dashboard',    label: 'Dashboard',    icon: iconDashboard },
    { page: 'sessions',     label: 'Sessions',     icon: iconSessions  },
    { page: 'eod-reports',  label: 'EOD Reports',  icon: iconEod       },
    { page: 'assessments',  label: 'Assessments',  icon: iconAssess    },
    { page: 'behavior',     label: 'Behavior',     icon: iconBehavior  },
    { page: 'students',     label: 'Students',     icon: iconStudents  },
    { page: 'incidents',    label: 'Incidents',    icon: iconIncidents },
    { page: 'performance',  label: 'My Score',     icon: iconPerformance },
    { page: 'settings',     label: 'Settings',     icon: iconSettings  },
  ];
  if (portal === 'principal') return [
    { page: 'dashboard', label: 'Dashboard', icon: iconDashboard },
    { page: 'students',  label: 'Students',  icon: iconStudents  },
    { page: 'settings',  label: 'Settings',  icon: iconSettings  },
  ];
  return [
    { page: 'dashboard', label: 'My Children', icon: iconStudents },
    { page: 'settings',  label: 'Settings',    icon: iconSettings },
  ];
}

function renderShell() {
  const portal = getPortal(state.user);
  const items = navConfig(portal);
  const name = state.user?.first_name ? `${state.user.first_name} ${state.user.last_name || ''}`.trim() : state.user?.email || 'User';
  const initials = getInitials(name);
  const roleLabel = state.user?.role || 'User';

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
            <button class="bell-btn" id="bell-btn" aria-label="Notifications">${iconBell()}</button>
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
  document.getElementById('bell-btn')?.addEventListener('click', () => showAlert('No new notifications.', 'info'));
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
        <div class="welcome-subtitle"><span class="badge badge-yellow" style="margin-right:8px;">${esc(state.user?.role || 'Admin')}</span>${todayFull()}</div>
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
              <td><span class="badge">${esc(s.school_type || '—')}</span></td>
              <td>${s.city ? esc(s.city) + (s.state ? ', ' + esc(s.state) : '') : '—'}</td>
              <td>${s.coach_count ?? 0}</td>
              <td>${s.session_count_this_week ?? 0}</td>
              <td>${fmtDate(s.last_eod_date)}</td>
              <td><button class="btn btn-ghost btn-sm" data-school-id="${s.school_id}" onclick="openEditSchoolModal(${s.school_id})">${iconEdit()}</button></td>
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
    <div class="modal-header"><h2 class="modal-title">Add School</h2><button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button></div>
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
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Principal Name</label>
          <input class="form-input" name="principal_name" placeholder="Jane Smith" />
        </div>
        <div class="form-group">
          <label class="form-label">Principal Email</label>
          <input class="form-input" type="email" name="principal_email" placeholder="principal@school.edu" />
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="add-school-submit">Add School</button>
      </div>
    </form>`);

  document.getElementById('add-school-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = document.getElementById('add-school-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';

    try {
      let orgId = fd.get('organization_id') ? parseInt(fd.get('organization_id')) : null;
      if (!orgId && fd.get('new_org_name')) {
        const orgRes = await api('POST', '/api/organizations', { organization_name: fd.get('new_org_name').trim() });
        orgId = orgRes.organization?.organization_id;
      }
      if (!orgId) { showAlert('Please select or create an organization.', 'error'); btn.disabled = false; btn.innerHTML = 'Add School'; return; }

      await api('POST', '/api/schools', {
        organization_id: orgId,
        school_name: fd.get('school_name').trim(),
        school_type: fd.get('school_type'),
        city: fd.get('city').trim() || null,
        state: fd.get('state').trim().toUpperCase() || null,
        principal_name: fd.get('principal_name').trim() || null,
        principal_email: fd.get('principal_email').trim().toLowerCase() || null,
      });
      closeModal();
      showAlert('School added successfully!', 'success');
      if (onSuccess) onSuccess();
      else loadSchoolsPage(document.getElementById('page-main'));
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.innerHTML = 'Add School';
    }
  });
}

async function openEditSchoolModal(schoolId) {
  let school = null;
  try {
    const d = await api('GET', '/api/admin/schools');
    school = (d.schools || []).find(s => s.school_id === schoolId);
  } catch (_) {}
  if (!school) { showAlert('Could not load school details.', 'error'); return; }

  openModal(`
    <div class="modal-header"><h2 class="modal-title">Edit School</h2><button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button></div>
    <form id="edit-school-form" class="modal-body form-stack">
      <div class="form-group"><label class="form-label">School Name *</label>
        <input class="form-input" name="school_name" value="${esc(school.school_name)}" required /></div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">City</label>
          <input class="form-input" name="city" value="${esc(school.city || '')}" /></div>
        <div class="form-group"><label class="form-label">State</label>
          <input class="form-input" name="state" value="${esc(school.state || '')}" maxlength="2" style="text-transform:uppercase;" /></div>
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
      <button class="btn btn-primary" id="add-coach-btn" type="button">${iconPlus()} Add Coach</button>
    </div>
    <div id="coaches-content">${renderSkeleton(5)}</div>`;
  document.getElementById('add-coach-btn')?.addEventListener('click', openAddCoachModal);

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
              <td><span class="badge">${esc(c.role)}</span></td>
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
      <button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button>
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
    <div class="modal-header"><h2 class="modal-title">Add Coach</h2><button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button></div>
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
          ${byS.map(s => statCard(esc(s.severity_level || 'Unknown'), s.count, iconIncidents(), sevColor(s.severity_level))).join('')}
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
              <td>${esc(i.incident_type)}</td>
              <td><span class="badge badge-${sevColor(i.severity_level)}">${esc(i.severity_level)}</span></td>
              <td><span class="badge badge-${i.status==='open'?'error':'success'}">${esc(i.status)}</span></td>
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
      <button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button>
    </div>
    <div class="modal-body form-stack">
      <div class="card" style="background:var(--color-bg);padding:12px 16px;margin-bottom:4px;">
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">
          <span class="badge badge-${ {high:'error',critical:'error',medium:'warning',low:'secondary'}[incident.severity_level]||'secondary'}">${esc(incident.severity_level)}</span>
          <span class="badge badge-${incident.status==='open'?'error':'success'}">${esc(incident.status)}</span>
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
        ${isOpen ? `<button class="btn btn-primary" id="resolve-btn" onclick="submitIncidentResolution(${incident.incident_id}, 'resolved')">Mark Resolved</button>` : `<button class="btn btn-ghost btn-sm" onclick="submitIncidentResolution(${incident.incident_id}, 'open')">Reopen</button><button class="btn btn-primary" id="resolve-btn" onclick="submitIncidentResolution(${incident.incident_id}, 'resolved')">Update Notes</button>`}
      </div>
    </div>`);
}

async function submitIncidentResolution(incidentId, status) {
  const btn = document.getElementById('resolve-btn');
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
    if (btn) { btn.disabled = false; btn.textContent = 'Mark Resolved'; }
  }
}

/* ============================================================
   16. STUDENTS GROWTH (Admin)
   ============================================================ */
async function loadStudentsGrowth(container) {
  container.innerHTML = `<div class="text-h2" style="margin-bottom:16px;">Student Growth</div><div id="growth-content">${renderSkeleton(4)}</div>`;
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
      const params = new URLSearchParams({ per_page: 50 });
      if (schoolId) params.set('school_id', schoolId);
      if (search) params.set('search', search);
      const sd2 = await api('GET', `/api/students?${params}`);
      const sts = sd2.students || [];
      sl.innerHTML = sts.length ? `
        <div class="table-container">
          <table class="table">
            <thead><tr><th>Name</th><th>Grade</th><th>School</th><th></th></tr></thead>
            <tbody>${sts.map(s => `<tr>
              <td>${esc(s.student_last_name)}, ${esc(s.student_first_name)}</td>
              <td>${esc(s.grade_level || '—')}</td>
              <td>${esc(s.school_name || '—')}</td>
              <td><button class="btn btn-ghost btn-sm" onclick="openStudentProgressModal(${s.student_id})">Progress</button></td>
            </tr>`).join('')}</tbody>
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

/* ============================================================
   17. COACH DASHBOARD
   ============================================================ */
async function loadCoachDashboard(container) {
  container.innerHTML = renderSkeleton(4);
  try {
    const [sessRes, eodRes] = await Promise.allSettled([
      api('GET', '/api/sessions?per_page=5'),
      api('GET', '/api/eod-reports?per_page=5'),
    ]);
    const sessions = sessRes.status === 'fulfilled' ? (sessRes.value.sessions || []) : [];
    const eods = eodRes.status === 'fulfilled' ? (eodRes.value.reports || []) : [];
    const todayStr = new Date().toISOString().split('T')[0];
    const todayEod = eods.find(e => e.report_date === todayStr);

    container.innerHTML = `
      <div class="welcome-card">
        <div class="welcome-greeting">Hey ${esc(state.user?.first_name || 'Coach')}! 👋</div>
        <div class="welcome-subtitle"><span class="badge badge-yellow" style="margin-right:8px;">${esc(state.user?.role || 'Coach')}</span>${todayFull()}</div>
      </div>
      <div class="stats-grid">
        ${statCard('Sessions Logged', sessions.length, iconSessions(), '')}
        ${statCard("Today's EOD", todayEod ? 'Submitted ✓' : 'Pending', iconEod(), todayEod ? 'success' : 'error')}
      </div>
      <div class="cards-grid">
        <div class="card">
          <div class="card-header"><div class="card-title">Quick Actions</div></div>
          <div class="form-stack" style="gap:8px;">
            <button class="btn btn-primary btn-full" data-page="sessions" type="button" style="justify-content:flex-start;">${iconSessions()} Log Today's Session</button>
            <button class="btn btn-ghost btn-full" data-page="eod-reports" type="button" style="justify-content:flex-start;">${iconEod()} Submit EOD Report</button>
            <button class="btn btn-ghost btn-full" data-page="incidents" type="button" style="justify-content:flex-start;">${iconIncidents()} File an Incident</button>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><div class="card-title">Recent Sessions</div></div>
          ${sessions.length ? `<div class="kv-list">${sessions.slice(0, 5).map(s => `
            <div class="kv-row"><span class="kv-key">${fmtDate(s.session_date)}</span><span class="kv-val">${esc(s.session_type || '—')}</span></div>`).join('')}
          </div>` : `<div class="empty-state-sm">No sessions logged yet.</div>`}
        </div>
      </div>`;
    $$('[data-page]', container).forEach(el => el.addEventListener('click', () => navigate(el.dataset.page)));
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
          <thead><tr><th>Date</th><th>Type</th><th>School</th><th>Students</th><th>EOD Filed</th></tr></thead>
          <tbody>${sessions.map(s => `<tr>
            <td>${fmtDate(s.session_date)}</td>
            <td><span class="badge">${esc(s.session_type || '—')}</span></td>
            <td>${esc(s.school_name || '—')}</td>
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
    <div class="modal-header"><h2 class="modal-title">Log Session</h2><button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button></div>
    <form id="log-session-form" class="modal-body form-stack">
      <div class="form-row">
        <div class="form-group"><label class="form-label">Date *</label>
          <input class="form-input" type="date" name="session_date" value="${todayStr}" required /></div>
        <div class="form-group"><label class="form-label">Type *</label>
          <select class="form-input form-select" name="session_type" required>
            <option value="pe_class">PE Class</option>
            <option value="after_school">After School</option>
            <option value="recess">Recess</option>
            <option value="sports">Sports</option>
            <option value="other">Other</option>
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
    try {
      await api('POST', '/api/sessions', {
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
          <thead><tr><th>Date</th><th>Session</th><th>On Time</th><th>Submitted</th></tr></thead>
          <tbody>${reports.map(r => `<tr>
            <td>${fmtDate(r.report_date)}</td>
            <td>${esc(r.session_type || '—')}</td>
            <td>${r.submitted_on_time ? '<span class="text-success">✓ On Time</span>' : '<span class="text-error">Late</span>'}</td>
            <td>${fmtDate(r.created_at)}</td>
          </tr>`).join('')}</tbody>
        </table>
      </div>`;
  } catch (err) {
    const ec = document.getElementById('eod-content');
    if (ec) ec.innerHTML = errorCard(err.message);
  }
}

function openEodModal(onSuccess) {
  const todayStr = new Date().toISOString().split('T')[0];
  openModal(`
    <div class="modal-header"><h2 class="modal-title">Submit EOD Report</h2><button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button></div>
    <form id="eod-form" class="modal-body form-stack">
      <div class="form-group"><label class="form-label">Report Date *</label>
        <input class="form-input" type="date" name="report_date" value="${todayStr}" required /></div>
      <div class="form-group"><label class="form-label">Overall Activities</label>
        <textarea class="form-input form-textarea" name="overall_activities" placeholder="What activities were covered?" rows="3"></textarea></div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Engagement Level (1–5)</label>
          <select class="form-input form-select" name="student_engagement_level">
            <option value="5">5 – Excellent</option><option value="4">4 – Good</option>
            <option value="3" selected>3 – Average</option><option value="2">2 – Below Average</option><option value="1">1 – Poor</option>
          </select></div>
        <div class="form-group"><label class="form-label">Behavior (1–5)</label>
          <select class="form-input form-select" name="behavior_rating">
            <option value="5">5 – Excellent</option><option value="4">4 – Good</option>
            <option value="3" selected>3 – Average</option><option value="2">2 – Below Average</option><option value="1">1 – Poor</option>
          </select></div>
      </div>
      <div class="form-group"><label class="form-label">Coach Notes</label>
        <textarea class="form-input form-textarea" name="coach_notes" placeholder="Any highlights, concerns, or follow-ups?" rows="3"></textarea></div>
      <div class="modal-footer">
        <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" type="submit" id="eod-submit">Submit Report</button>
      </div>
    </form>`);

  document.getElementById('eod-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = document.getElementById('eod-submit');
    btn.disabled = true; btn.innerHTML = '<span class="spinner spinner-white"></span>';
    try {
      await api('POST', '/api/eod-reports', {
        report_date: fd.get('report_date'),
        overall_activities: fd.get('overall_activities').trim() || null,
        student_engagement_level: parseInt(fd.get('student_engagement_level')),
        behavior_rating: parseInt(fd.get('behavior_rating')),
        coach_notes: fd.get('coach_notes').trim() || null,
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
          <tbody>${students.map(s => `<tr>
            <td>${esc(s.first_name)} ${esc(s.last_name)}</td>
            <td>${esc(s.grade_level || '—')}</td>
            <td>${fmtDate(s.latest_assessment_date)}</td>
            <td>${s.avg_raw_level ?? '—'}</td>
          </tr>`).join('')}</tbody>
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
            <td>${esc(i.incident_type || '—')}</td>
            <td><span class="badge ${i.severity_level === 'high' || i.severity_level === 'critical' ? 'badge-error' : ''}">${esc(i.severity_level || '—')}</span></td>
            <td><span class="badge ${i.status === 'resolved' ? 'badge-success' : ''}">${esc(i.status || 'open')}</span></td>
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
      <button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button>
    </div>
    <div class="modal-body form-stack">
      <div class="form-row">
        <div class="form-group"><label class="form-label">Date</label><div>${fmtDate(i.report_date)}</div></div>
        <div class="form-group"><label class="form-label">Status</label><div><span class="badge ${statusClass}">${esc(i.status || 'open')}</span></div></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Type</label><div>${esc(i.incident_type || '—')}</div></div>
        <div class="form-group"><label class="form-label">Severity</label><div><span class="badge ${severityClass}">${esc(i.severity_level || '—')}</span></div></div>
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
    <div class="modal-header"><h2 class="modal-title">File Incident Report</h2><button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button></div>
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
          <option value="other">Other</option>
        </select></div>
      <div class="form-group"><label class="form-label">Description *</label>
        <textarea class="form-input form-textarea" name="description" rows="4" placeholder="Describe what happened…" required></textarea></div>
      <div class="form-group"><label class="form-label">Action Taken</label>
        <textarea class="form-input form-textarea" name="action_taken" rows="2" placeholder="What action was taken?"></textarea></div>
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
        report_date: fd.get('report_date'),
        severity_level: fd.get('severity_level'),
        incident_type: fd.get('incident_type'),
        description: fd.get('description').trim(),
        action_taken: fd.get('action_taken').trim() || null,
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
    ac.innerHTML = `<div class="table-wrap"><table class="data-table">
      <thead><tr><th>Date</th><th>Student</th><th>Method</th><th>Scores</th></tr></thead>
      <tbody>${items.map(a => `<tr>
        <td>${fmtDate(a.assessment_date)}</td>
        <td>${esc(a.student_id)}</td>
        <td>${esc(a.assessment_method || 'observational')}</td>
        <td>${a.scores?.length ? a.scores.map(s => `${esc(s.skill_name || s.skill_id)}: ${s.raw_level}`).join(', ') : '—'}</td>
      </tr>`).join('')}
      </tbody></table></div>`;
  } catch (err) {
    const ac = document.getElementById('assess-content');
    if (ac) ac.innerHTML = errorCard(err.message);
  }
}

async function openNewAssessmentModal(onSuccess) {
  openModal(`<div class="modal-header"><h2 class="modal-title">New Assessment</h2><button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button></div>
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
  const scoreRows = skillsWithDomain.map(s => `
    <div class="form-group">
      <label class="form-label">${esc(s.domain_name)} — ${esc(s.skill_name)}</label>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <select class="form-input" name="skill_${s.skill_id}" style="flex:1;min-width:160px;" required>
          <option value="">— Score —</option>
          <option value="1">1 — Beginning</option>
          <option value="2">2 — Developing</option>
          <option value="3">3 — Proficient</option>
          <option value="4">4 — Advanced</option>
          <option value="5">5 — Mastery</option>
        </select>
        <select class="form-input" name="obs_tag_${s.skill_id}" style="flex:1;min-width:160px;">
          <option value="">— Observation tag —</option>
          <option value="independent">Independent</option>
          <option value="needs_prompt">Needs Prompt</option>
          <option value="inconsistent">Inconsistent</option>
          <option value="strong_control">Strong Control</option>
          <option value="low_confidence">Low Confidence</option>
          <option value="gameplay_transfer_observed">Gameplay Transfer</option>
        </select>
      </div>
    </div>`).join('');

  const mb = document.querySelector('.modal-body');
  if (!mb) return;
  mb.outerHTML = `<form id="assess-form" class="modal-body form-stack">
    <div class="form-group">
      <label class="form-label">Student *</label>
      <select class="form-input" name="student_id" required>
        <option value="">— Select student —</option>
        ${students.map(s => `<option value="${s.student_id}">${esc(s.student_last_name)}, ${esc(s.student_first_name)} (Grade ${esc(s.grade_level || '?')})</option>`).join('')}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Assessment Date *</label>
      <input class="form-input" type="date" name="assessment_date" value="${todayStr}" max="${todayStr}" required />
    </div>
    ${scoreRows}
    <div class="form-group">
      <label class="form-label">Notes</label>
      <textarea class="form-input form-textarea" name="notes" placeholder="Overall observations…" rows="3" maxlength="2000"></textarea>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" type="button" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" type="submit" id="assess-submit">Submit Assessment</button>
    </div>
  </form>`;

  document.getElementById('assess-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('assess-submit');
    btn.disabled = true; btn.innerHTML = 'Saving…';
    const fd = new FormData(e.target);
    const scores = skillsWithDomain
      .map(s => {
        const raw_score = parseInt(fd.get(`skill_${s.skill_id}`), 10);
        const obs_tag = fd.get(`obs_tag_${s.skill_id}`) || null;
        return { skill_id: s.skill_id, raw_score, observation_tag: obs_tag || undefined };
      })
      .filter(s => !isNaN(s.raw_score));
    try {
      await api('POST', '/api/assessments', {
        student_id: parseInt(fd.get('student_id'), 10),
        assessment_date: fd.get('assessment_date'),
        scores,
        overall_assessment_notes: fd.get('notes').trim() || null,
        assessment_method: 'observational',
      });
      closeModal();
      showAlert('Assessment saved.', 'success');
      if (onSuccess) onSuccess();
    } catch (err) {
      showAlert(err.message, 'error');
      btn.disabled = false; btn.innerHTML = 'Submit Assessment';
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
    const eodPct = d.eod_compliance_rate != null ? Math.round(d.eod_compliance_rate * 100) : 0;
    container.innerHTML = `
      <div class="welcome-card">
        <div class="welcome-greeting">${esc(school.school_name || 'Your School')}</div>
        <div class="welcome-subtitle">${school.city ? esc(school.city) + (school.state ? ', ' + esc(school.state) : '') : ''} &mdash; ${todayFull()}</div>
      </div>
      <div class="stats-grid">
        ${statCard('Total Students', d.students_total ?? 0, iconStudents(), '')}
        ${statCard('Assessed', d.students_assessed ?? 0, iconAssess(), 'accent')}
        ${statCard('Sessions This Week', d.sessions_this_week ?? 0, iconSessions(), 'success')}
        ${statCard('EOD Compliance', eodPct + '%', iconEod(), eodPct < 70 ? 'error' : 'success')}
        ${statCard('Open Incidents', d.open_incidents ?? 0, iconIncidents(), d.open_incidents > 0 ? 'error' : '')}
      </div>
      ${d.coaches?.length ? `
        <div class="card">
          <div class="card-header">
            <div class="card-title">Coaches at ${esc(school.school_name || 'Your School')}</div>
            <button class="btn btn-ghost btn-sm" data-page="students" onclick="navigate('students')">View Students</button>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>Name</th><th>Role</th></tr></thead>
              <tbody>${d.coaches.map(c => `<tr>
                <td>${esc(c.first_name)} ${esc(c.last_name)}</td>
                <td><span class="badge">${esc(c.role)}</span></td>
              </tr>`).join('')}</tbody>
            </table>
          </div>
        </div>` : ''}`;
  } catch (err) {
    container.innerHTML = errorCard(err.message);
  }
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
              <tbody>${students.map(s => `<tr style="cursor:pointer;" onclick="openStudentProgressModal(${s.student_id})">
                <td>${esc(s.first_name)} ${esc(s.last_name)}</td>
                <td>${esc(s.grade_level || '—')}</td>
                <td>${fmtDate(s.latest_assessment_date)}</td>
                <td>${s.avg_raw_level ?? '—'}</td>
                <td><span style="color:var(--color-primary);font-size:0.8rem;">View →</span></td>
              </tr>`).join('')}</tbody>
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
    container.innerHTML = children.map(c => `
      <div class="card" style="margin-bottom:16px;">
        <div class="card-header">
          <div><div class="card-title">${esc(c.first_name)} ${esc(c.last_name)}</div>
          <div class="text-caption">Grade ${esc(c.grade_level || '—')} &mdash; ${esc(c.school_name || '—')}</div></div>
        </div>
        ${c.assessment_summary?.length ? `
          <div style="margin-top:12px;">
            <div class="text-caption" style="margin-bottom:8px;">Skill Levels</div>
            <div class="kv-list">${c.assessment_summary.map(a => `
              <div class="kv-row"><span class="kv-key">${esc(a.domain_name)}</span><span class="kv-val">${a.avg_raw_level ?? '—'} / 5</span></div>`).join('')}
            </div>
          </div>` : '<div class="text-caption" style="margin-top:8px;">No assessments yet</div>'}
        ${c.recent_sessions?.length ? `
          <div style="margin-top:12px;">
            <div class="text-caption" style="margin-bottom:8px;">Recent Sessions</div>
            <div class="kv-list">${c.recent_sessions.slice(0,5).map(s => `
              <div class="kv-row"><span class="kv-key">${fmtDate(s.session_date)}</span><span class="kv-val">${esc(s.attendance_status || '—')}</span></div>`).join('')}
            </div>
          </div>` : ''}
      </div>`).join('');
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
          <div class="kv-row"><span class="kv-key">Role</span><span class="kv-val"><span class="badge">${esc(user?.role || '—')}</span></span></div>
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
  } catch (_) {}

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
    <div id="rpt-results">${renderSkeleton(3)}</div>`;

  async function runReport() {
    const type = document.getElementById('rpt-type')?.value;
    const school = document.getElementById('rpt-school')?.value;
    const from = document.getElementById('rpt-from')?.value;
    const to = document.getElementById('rpt-to')?.value;
    const results = document.getElementById('rpt-results');
    if (!results) return;
    results.innerHTML = renderSkeleton(3);
    try {
      const params = new URLSearchParams({ type, from, to });
      if (school) params.set('school_id', school);
      const d = await api('GET', `/api/reports?${params}`);
      results.innerHTML = renderReportTable(type, d);
    } catch (err) {
      results.innerHTML = errorCard(err.message);
    }
  }

  document.getElementById('rpt-run')?.addEventListener('click', runReport);
  runReport();
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
      <td><span class="badge badge-${r.severity_level === 'high' ? 'error' : r.severity_level === 'medium' ? 'warning' : 'secondary'}">${esc(r.severity_level)}</span></td>
      <td>${esc(r.incident_type)}</td>
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
    const tableRows = rows.map(r => `<tr>
      <td>${esc(r.school_name)}</td>
      <td>${r.students_with_scores}</td>
      <td>${r.avg_score ?? '—'}</td>
      <td>${r.avg_growth != null ? (r.avg_growth >= 0 ? '+' : '') + r.avg_growth : '—'}</td>
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
        <thead><tr><th>School</th><th>Assessed</th><th>Avg Score</th><th>Avg Growth</th><th>Band Distribution</th></tr></thead>
        <tbody>${tableRows}</tbody>
      </table></div></div>`;
  }

  return errorCard('Unknown report type.');
}

/* ============================================================
   25b. STUDENT PROGRESS MODAL (admin + principal + coach)
   ============================================================ */
async function openStudentProgressModal(studentId) {
  openModal(`<div class="modal-header"><h2 class="modal-title">Student Progress</h2><button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button></div>
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

  const bandColor = b => ({ Emerging: 'error', Developing: 'warning', 'On Track': 'info', Proficient: 'success', Advanced: 'accent' }[b] || 'secondary');
  const scoreBar = (score, max = 100) => {
    const pct = Math.min(Math.round((score / max) * 100), 100);
    return `<div style="display:flex;align-items:center;gap:8px;">
      <div style="flex:1;background:var(--color-border);border-radius:4px;height:8px;">
        <div style="width:${pct}%;background:var(--color-primary);border-radius:4px;height:8px;transition:width 400ms;"></div>
      </div>
      <span style="min-width:36px;font-size:0.75rem;text-align:right;">${score ?? '—'}</span>
    </div>`;
  };

  const domainRows = domains.map(dm => {
    const pct = dm.current_domain_score != null ? Math.min(Math.round(dm.current_domain_score), 100) : null;
    const growth = dm.growth_amount != null ? (dm.growth_amount >= 0 ? `+${dm.growth_amount}` : dm.growth_amount) : '—';
    return `
      <div style="padding:10px 0;border-bottom:1px solid var(--color-border);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
          <span style="font-weight:600;font-size:0.875rem;">${esc(dm.domain_name)}</span>
          <div style="display:flex;gap:6px;align-items:center;">
            <span class="badge badge-${bandColor(dm.performance_band)}">${esc(dm.performance_band || '—')}</span>
            <span style="font-size:0.75rem;color:var(--color-text-secondary);">Growth: ${growth}</span>
          </div>
        </div>
        ${pct != null ? scoreBar(pct) : '<span style="font-size:0.75rem;color:var(--color-text-secondary);">No scores yet</span>'}
      </div>`;
  }).join('');

  const skillsByDomain = {};
  skills.forEach(sk => {
    (skillsByDomain[sk.domain_name] = skillsByDomain[sk.domain_name] || []).push(sk);
  });
  const skillRows = Object.entries(skillsByDomain).map(([dname, sks]) => `
    <div style="margin-bottom:12px;">
      <div style="font-size:0.75rem;font-weight:700;color:var(--color-text-secondary);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">${esc(dname)}</div>
      ${sks.map(sk => `
        <div style="display:flex;align-items:center;gap:8px;padding:4px 0;">
          <span style="min-width:140px;font-size:0.8rem;">${esc(sk.skill_name)}</span>
          <div style="flex:1;">${scoreBar(sk.current_score ?? 0)}</div>
          <span class="badge badge-${bandColor(sk.performance_band)}" style="font-size:0.65rem;">${esc(sk.performance_band || '—')}</span>
        </div>`).join('')}
    </div>`).join('');

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
        <div class="stat-card" style="flex:1;min-width:120px;">
          <div class="stat-label">Overall Score</div>
          <div class="stat-value">${overall.overall_score ?? '—'}</div>
        </div>
        <div class="stat-card" style="flex:1;min-width:120px;">
          <div class="stat-label">Performance</div>
          <div class="stat-value" style="font-size:1rem;"><span class="badge badge-${bandColor(overall.performance_band)}">${esc(overall.performance_band || '—')}</span></div>
        </div>
        <div class="stat-card" style="flex:1;min-width:120px;">
          <div class="stat-label">Total Growth</div>
          <div class="stat-value">${overall.growth_amount != null ? (overall.growth_amount >= 0 ? '+' : '') + overall.growth_amount : '—'}</div>
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
        <div style="font-weight:700;margin-bottom:8px;">Assessment History</div>
        <div class="kv-list">${recent.map(a => `
          <div class="kv-row">
            <span class="kv-key">${fmtDate(a.assessment_date)}</span>
            <span class="kv-val">${a.score_count} skill${a.score_count !== 1 ? 's' : ''} scored</span>
          </div>`).join('')}
        </div>
      </div>` : ''}
    </div>`;
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

  const rows = windows.map(w => `
    <tr>
      <td>${esc(w.window_name)}</td>
      <td>${esc(w.school_name || '—')}</td>
      <td>${esc(w.start_date)} – ${esc(w.end_date)}</td>
      <td>${statusBadge(w.status)}</td>
      <td>
        ${w.status !== 'closed' ? `<button class="btn btn-ghost btn-sm" onclick="patchWindow(${w.window_id},'${w.status === 'active' ? 'closed' : 'active'}')">
          ${w.status === 'active' ? 'Close' : 'Activate'}
        </button>` : ''}
      </td>
    </tr>`).join('');

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
          <label class="form-label">Description</label>
          <textarea class="form-input form-textarea" name="description" rows="2" maxlength="500"></textarea>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-primary" type="submit">Create Window</button>
          <button class="btn btn-ghost" type="button" onclick="document.getElementById('new-window-form').style.display='none'">Cancel</button>
        </div>
      </form>
      ${windows.length ? `
      <div class="table-container">
        <table class="table">
          <thead><tr><th>Name</th><th>School</th><th>Dates</th><th>Status</th><th></th></tr></thead>
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
      description: fd.get('description').trim() || null,
    });
    showAlert('Window created.', 'success');
    loadWindowsPage(document.getElementById('page-main'));
  } catch (err) {
    showAlert(err.message, 'error');
    btn.disabled = false; btn.textContent = 'Create Window';
  }
}

async function patchWindow(windowId, newStatus) {
  try {
    await api('PATCH', `/api/assessment-windows/${windowId}`, { status: newStatus });
    showAlert(`Window ${newStatus}.`, 'success');
    loadWindowsPage(document.getElementById('page-main'));
  } catch (err) {
    showAlert(err.message, 'error');
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
      <button class="modal-close btn btn-ghost btn-sm" onclick="closeModal()">${iconClose()}</button>
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
   26. LOGOUT
   ============================================================ */
async function handleLogout() {
  try { await api('POST', '/api/auth/logout'); } catch (_) {}
  state.user = null; state.currentPage = 'login';
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
  if (app) app.innerHTML = `<div class="loading-overlay" style="min-height:100vh;"><div class="spinner spinner-lg"></div><div class="loading-text">Loading Ufit Motion…</div></div>`;
  try {
    const data = await api('GET', '/api/auth/session');
    if (data?.user || data?.email) {
      state.user = data.user || data;
      state.currentPage = 'dashboard';
    } else { state.currentPage = 'login'; }
  } catch (_) {
    state.currentPage = 'login';
    const stack = document.getElementById('alert-stack');
    if (stack) stack.innerHTML = '';
  }
  render();
}

document.addEventListener('DOMContentLoaded', init);
