/* ============================================================
   UFIT MOTION — Vanilla JS SPA
   No framework dependencies. Mobile-first for coaches.
   ============================================================ */

'use strict';

/* ============================================================
   1. STATE
   ============================================================ */
const state = {
  user: null,
  portal: 'admin',         // 'admin' | 'coach' | 'staff'
  currentPage: 'login',
  notifications: [],
  schools: [],
  loading: false,
  error: null,
};

/* ============================================================
   2. CONSTANTS
   ============================================================ */
const NAV_CONFIG = {
  admin: [
    { page: 'dashboard',   label: 'Dashboard',  icon: iconDashboard  },
    { page: 'schools',     label: 'Schools',    icon: iconSchools    },
    { page: 'coaches',     label: 'Coaches',    icon: iconCoaches    },
    { page: 'students',    label: 'Students',   icon: iconStudents   },
    { page: 'incidents',   label: 'Incidents',  icon: iconIncidents  },
    { page: 'reports',     label: 'Reports',    icon: iconReports    },
    { page: 'settings',    label: 'Settings',   icon: iconSettings   },
  ],
  coach: [
    { page: 'dashboard',    label: 'Dashboard',     icon: iconDashboard },
    { page: 'sessions',     label: 'My Sessions',   icon: iconSessions  },
    { page: 'eod-reports',  label: 'EOD Reports',   icon: iconReports   },
    { page: 'assessments',  label: 'Assessments',   icon: iconAssess    },
    { page: 'students',     label: 'Students',      icon: iconStudents  },
    { page: 'incidents',    label: 'Incidents',     icon: iconIncidents },
  ],
  staff: [
    { page: 'dashboard',  label: 'Dashboard',    icon: iconDashboard },
    { page: 'students',   label: 'My Students',  icon: iconStudents  },
    { page: 'reports',    label: 'Reports',      icon: iconReports   },
  ],
};

const MOBILE_NAV_CONFIG = [
  { page: 'dashboard',   label: 'Home',      icon: iconDashboard },
  { page: 'sessions',    label: 'Sessions',  icon: iconSessions  },
  { page: 'students',    label: 'Students',  icon: iconStudents  },
  { page: 'incidents',   label: 'Incidents', icon: iconIncidents },
  { page: 'settings',    label: 'Settings',  icon: iconSettings  },
];

const PORTAL_LABELS = {
  admin: 'Admin',
  coach: 'Coach',
  staff: 'Staff',
};

const STAT_CARD_DATA = [
  {
    label: 'Schools',
    value: '12',
    icon: iconSchools,
    colorClass: '',
    trend: '+2 this quarter',
  },
  {
    label: 'Students',
    value: '1,847',
    icon: iconStudents,
    colorClass: 'accent',
    trend: '+43 this week',
  },
  {
    label: 'Sessions Today',
    value: '8',
    icon: iconSessions,
    colorClass: 'success',
    trend: '3 in progress',
  },
  {
    label: 'Open Incidents',
    value: '3',
    icon: iconIncidents,
    colorClass: 'error',
    trend: '1 needs review',
  },
];

/* ============================================================
   3. SVG ICON HELPERS
   ============================================================ */
function icon(path, extraAttrs = '') {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
    viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
    ${extraAttrs}>${path}</svg>`;
}

function iconDashboard() {
  return icon('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>');
}
function iconSchools() {
  return icon('<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>');
}
function iconCoaches() {
  return icon('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>');
}
function iconStudents() {
  return icon('<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>');
}
function iconSessions() {
  return icon('<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>');
}
function iconReports() {
  return icon('<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>');
}
function iconAssess() {
  return icon('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>');
}
function iconIncidents() {
  return icon('<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>');
}
function iconSettings() {
  return icon('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>');
}
function iconLogout() {
  return icon('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>');
}
function iconBell() {
  return icon('<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>', 'width="20" height="20"');
}
function iconMenu() {
  return icon('<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>', 'width="22" height="22"');
}
function iconClose() {
  return icon('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>', 'width="22" height="22"');
}
function iconCheck() {
  return icon('<polyline points="20 6 9 17 4 12"/>');
}
function iconAlert() {
  return icon('<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>');
}

/* ============================================================
   4. UTILITY HELPERS
   ============================================================ */
function $(selector, ctx = document) {
  return ctx.querySelector(selector);
}

function $$(selector, ctx = document) {
  return [...ctx.querySelectorAll(selector)];
}

function el(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, val] of Object.entries(attrs)) {
    if (key === 'class') element.className = val;
    else if (key.startsWith('on')) element.addEventListener(key.slice(2).toLowerCase(), val);
    else element.setAttribute(key, val);
  }
  for (const child of children) {
    if (typeof child === 'string') element.insertAdjacentHTML('beforeend', child);
    else if (child instanceof Node) element.appendChild(child);
  }
  return element;
}

function getInitials(name = '') {
  return name
    .split(' ')
    .slice(0, 2)
    .map(w => w[0] || '')
    .join('')
    .toUpperCase();
}

function formatDate(date = new Date()) {
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function getPortalRole(user) {
  if (!user) return state.portal;
  const role = (user.role || '').toLowerCase();
  if (role.includes('admin') || role.includes('ceo') || role.includes('director')) return 'admin';
  if (role.includes('coach') || role.includes('trainer')) return 'coach';
  return 'staff';
}

/* ============================================================
   5. API HELPER
   ============================================================ */
async function api(method, path, body = null) {
  state.loading = true;
  state.error = null;

  const options = {
    method: method.toUpperCase(),
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    credentials: 'same-origin',
  };

  if (body && method.toUpperCase() !== 'GET') {
    options.body = JSON.stringify(body);
  }

  try {
    const res = await fetch(path, options);
    const contentType = res.headers.get('content-type') || '';
    let data = null;

    if (contentType.includes('application/json')) {
      data = await res.json();
    } else {
      data = { message: await res.text() };
    }

    if (!res.ok) {
      const message = data?.error || data?.message || `Request failed (${res.status})`;
      throw new Error(message);
    }

    return data;
  } catch (err) {
    state.error = err.message;
    showAlert(err.message, 'error');
    throw err;
  } finally {
    state.loading = false;
  }
}

/* ============================================================
   6. ALERT / NOTIFICATION SYSTEM
   ============================================================ */
function ensureAlertStack() {
  let stack = $('#alert-stack');
  if (!stack) {
    stack = document.createElement('div');
    stack.id = 'alert-stack';
    stack.className = 'alert-stack';
    document.body.appendChild(stack);
  }
  return stack;
}

function showAlert(message, type = 'info', duration = 4000) {
  const stack = ensureAlertStack();
  const id = 'alert-' + Date.now();

  const iconMap = {
    error: iconAlert(),
    success: iconCheck(),
    warning: iconAlert(),
    info: iconAlert(),
  };

  const alertEl = document.createElement('div');
  alertEl.id = id;
  alertEl.className = `alert alert-${type}`;
  alertEl.setAttribute('role', 'alert');
  alertEl.innerHTML = `
    <span class="alert-icon">${iconMap[type] || ''}</span>
    <span class="alert-body">${escapeHtml(message)}</span>
    <button class="alert-dismiss" aria-label="Dismiss">&times;</button>
  `;

  alertEl.querySelector('.alert-dismiss').addEventListener('click', () => {
    dismissAlert(id);
  });

  stack.appendChild(alertEl);

  if (duration > 0) {
    setTimeout(() => dismissAlert(id), duration);
  }

  return id;
}

function dismissAlert(id) {
  const alertEl = document.getElementById(id);
  if (!alertEl) return;
  alertEl.style.opacity = '0';
  alertEl.style.transform = 'translateY(-8px)';
  alertEl.style.transition = 'opacity 200ms, transform 200ms';
  setTimeout(() => alertEl.remove(), 200);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ============================================================
   7. ROUTER / RENDER DISPATCHER
   ============================================================ */
function navigate(page) {
  state.currentPage = page;
  render();
  // Scroll to top on navigation
  window.scrollTo({ top: 0, behavior: 'instant' });
}

function render() {
  const app = document.getElementById('app');
  if (!app) return;

  if (state.currentPage === 'login' || !state.user) {
    app.innerHTML = renderLogin();
    attachLoginListeners();
    return;
  }

  app.innerHTML = renderShell();
  attachShellListeners();
  renderPageContent();
}

function renderPageContent() {
  const main = document.getElementById('page-main');
  if (!main) return;

  switch (state.currentPage) {
    case 'dashboard':
      main.innerHTML = renderDashboard();
      break;
    case 'sessions':
      main.innerHTML = renderStub('My Sessions', 'Session scheduling and tracking is coming in Week 2.', iconSessions());
      break;
    case 'eod-reports':
      main.innerHTML = renderStub('EOD Reports', 'End-of-day report submission is coming in Week 2.', iconReports());
      break;
    case 'assessments':
      main.innerHTML = renderStub('Assessments', 'Student assessment tools are coming in Week 2.', iconAssess());
      break;
    case 'students':
      main.innerHTML = renderStudents();
      break;
    case 'incidents':
      main.innerHTML = renderIncidents();
      break;
    case 'settings':
      main.innerHTML = renderSettings();
      break;
    case 'schools':
      main.innerHTML = renderStub('Schools', 'School management is coming in Week 2.', iconSchools());
      break;
    case 'coaches':
      main.innerHTML = renderStub('Coaches', 'Coach management is coming in Week 2.', iconCoaches());
      break;
    case 'reports':
      main.innerHTML = renderStub('Reports', 'Advanced reporting is coming in Week 2.', iconReports());
      break;
    default:
      main.innerHTML = renderDashboard();
  }

  // Update active state in sidebar and mobile nav
  $$('.nav-item').forEach(item => {
    const page = item.dataset.page;
    item.classList.toggle('active', page === state.currentPage);
  });
  $$('.mobile-nav-btn').forEach(btn => {
    const page = btn.dataset.page;
    btn.classList.toggle('active', page === state.currentPage);
  });
}

/* ============================================================
   8. LOGIN PAGE
   ============================================================ */
function renderLogin() {
  const portals = [
    { key: 'admin', label: 'Admin\nPortal',  emoji: '🏢' },
    { key: 'coach', label: 'Coach\nPortal',  emoji: '🏃' },
    { key: 'staff', label: 'Staff /\nParent', emoji: '👤' },
  ];

  const portalButtons = portals.map(p => `
    <button
      class="portal-btn ${state.portal === p.key ? 'active' : ''}"
      data-portal="${p.key}"
      type="button"
    >
      <div class="portal-btn-icon">${p.emoji}</div>
      ${p.label.replace('\n', '<br>')}
    </button>
  `).join('');

  return `
    <div class="login-page">
      <div class="login-card">
        <div class="login-logo">
          <div class="login-logo-mark">
            <span class="login-logo-ufit">UFIT</span>
            <span class="login-logo-motion">MOTION</span>
          </div>
          <div class="login-logo-tagline">School Fitness Platform</div>
        </div>

        <div class="portal-selector-label">Select your portal</div>
        <div class="portal-selector" id="portal-selector">
          ${portalButtons}
        </div>

        <form id="login-form" novalidate>
          <div class="form-stack">
            <div id="login-alert-area"></div>

            <div class="form-group">
              <label class="form-label" for="email">Email address</label>
              <input
                class="form-input"
                type="email"
                id="email"
                name="email"
                placeholder="you@school.edu"
                autocomplete="username"
                inputmode="email"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label" for="password">Password</label>
              <input
                class="form-input"
                type="password"
                id="password"
                name="password"
                placeholder="Enter your password"
                autocomplete="current-password"
                required
              />
            </div>

            <button class="btn btn-primary btn-full" type="submit" id="signin-btn">
              Sign In
            </button>
          </div>
        </form>

        <div class="login-footer-text">
          Ufit Motion &mdash; &copy; ${new Date().getFullYear()} Ufit Online
        </div>
      </div>
    </div>
  `;
}

function attachLoginListeners() {
  // Portal selector
  $$('.portal-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      state.portal = btn.dataset.portal;
      $$('.portal-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });

  // Login form submission
  const form = document.getElementById('login-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearLoginError();

    const email = form.querySelector('#email').value.trim();
    const password = form.querySelector('#password').value;

    if (!email || !password) {
      showLoginError('Please enter your email and password.');
      return;
    }

    const btn = document.getElementById('signin-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner spinner-white"></span> Signing in…`;

    try {
      const data = await api('POST', '/api/auth/login', {
        email,
        password,
        portal: state.portal,
      });

      state.user = data.user || data;
      state.currentPage = 'dashboard';
      render();
    } catch (err) {
      showLoginError(err.message || 'Invalid email or password. Please try again.');
      btn.disabled = false;
      btn.innerHTML = 'Sign In';
    }
  });
}

function showLoginError(message) {
  const area = document.getElementById('login-alert-area');
  if (!area) return;
  area.innerHTML = `
    <div class="alert alert-error" role="alert">
      <span class="alert-icon">${iconAlert()}</span>
      <span class="alert-body">${escapeHtml(message)}</span>
    </div>
  `;
}

function clearLoginError() {
  const area = document.getElementById('login-alert-area');
  if (area) area.innerHTML = '';
}

/* ============================================================
   9. APP SHELL (sidebar + top nav + content area)
   ============================================================ */
function renderShell() {
  const role = getPortalRole(state.user);
  const navItems = NAV_CONFIG[role] || NAV_CONFIG.admin;
  const userName = state.user?.first_name
    ? `${state.user.first_name} ${state.user.last_name || ''}`.trim()
    : state.user?.email || 'User';
  const initials = getInitials(userName);
  const roleLabel = state.user?.role || PORTAL_LABELS[role] || 'User';

  const sidebarItems = navItems.map(item => `
    <div class="nav-item ${item.page === state.currentPage ? 'active' : ''}"
         data-page="${item.page}"
         role="button"
         tabindex="0"
         aria-label="${item.label}">
      <span class="nav-item-icon">${item.icon()}</span>
      <span>${item.label}</span>
    </div>
  `).join('');

  const mobileNavItems = MOBILE_NAV_CONFIG.map(item => `
    <button class="mobile-nav-btn ${item.page === state.currentPage ? 'active' : ''}"
            data-page="${item.page}"
            type="button"
            aria-label="${item.label}">
      <span class="mobile-nav-icon-wrap">
        ${item.icon()}
      </span>
      <span>${item.label}</span>
    </button>
  `).join('');

  const notifDot = state.notifications.length > 0
    ? '<span class="notification-dot"></span>'
    : '';

  const pageTitles = {
    dashboard: 'Dashboard',
    schools: 'Schools',
    coaches: 'Coaches',
    students: 'Students',
    sessions: 'My Sessions',
    'eod-reports': 'EOD Reports',
    assessments: 'Assessments',
    incidents: 'Incidents',
    reports: 'Reports',
    settings: 'Settings',
  };

  return `
    <div class="sidebar-overlay" id="sidebar-overlay"></div>

    <div class="app-layout">
      <!-- SIDEBAR -->
      <aside class="sidebar" id="sidebar" role="navigation" aria-label="Main navigation">
        <div class="nav-logo">
          <div class="nav-logo-text">
            <span class="nav-logo-ufit">Ufit</span>
            <span class="nav-logo-motion">Motion</span>
            <span class="nav-logo-dot"></span>
          </div>
          <div class="nav-logo-subtitle">School Fitness Platform</div>
        </div>

        <nav>
          ${sidebarItems}
        </nav>

        <div class="sidebar-footer">
          <div class="sidebar-user">
            <div class="sidebar-user-avatar">${initials}</div>
            <div>
              <div class="sidebar-user-name truncate">${escapeHtml(userName)}</div>
              <div class="sidebar-user-role">${escapeHtml(roleLabel)}</div>
            </div>
          </div>
        </div>
      </aside>

      <!-- MAIN CONTENT -->
      <div class="main-content">
        <!-- TOP NAV -->
        <header class="top-nav" role="banner">
          <div class="top-nav-left">
            <button class="hamburger-btn" id="hamburger-btn"
                    aria-label="Open navigation" aria-expanded="false">
              ${iconMenu()}
            </button>
            <span class="nav-page-title">
              ${pageTitles[state.currentPage] || 'Dashboard'}
            </span>
          </div>

          <div class="top-nav-right">
            <button class="bell-btn" id="bell-btn" aria-label="Notifications"
                    title="Notifications">
              ${iconBell()}
              ${notifDot}
            </button>

            <button class="user-menu-btn" id="logout-btn"
                    aria-label="Sign out" title="Sign out">
              <div class="user-menu-avatar">${initials}</div>
              <span class="user-menu-name">${escapeHtml(state.user?.first_name || userName)}</span>
              <span style="color:var(--color-text-secondary);margin-left:4px;">
                ${iconLogout()}
              </span>
            </button>
          </div>
        </header>

        <!-- PAGE CONTENT -->
        <main class="page-container" id="page-main" role="main">
          <!-- Rendered by renderPageContent() -->
        </main>
      </div>
    </div>

    <!-- MOBILE BOTTOM NAV -->
    <nav class="mobile-nav" role="navigation" aria-label="Mobile navigation">
      ${mobileNavItems}
    </nav>
  `;
}

function attachShellListeners() {
  // Sidebar navigation items
  $$('.nav-item[data-page]').forEach(item => {
    item.addEventListener('click', () => {
      navigate(item.dataset.page);
      closeSidebar();
    });
    item.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        navigate(item.dataset.page);
        closeSidebar();
      }
    });
  });

  // Mobile nav buttons
  $$('.mobile-nav-btn[data-page]').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });

  // Hamburger toggle
  const hamburger = document.getElementById('hamburger-btn');
  if (hamburger) {
    hamburger.addEventListener('click', toggleSidebar);
  }

  // Sidebar overlay click to close
  const overlay = document.getElementById('sidebar-overlay');
  if (overlay) {
    overlay.addEventListener('click', closeSidebar);
  }

  // Logout button
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', handleLogout);
  }

  // Bell button
  const bellBtn = document.getElementById('bell-btn');
  if (bellBtn) {
    bellBtn.addEventListener('click', () => {
      showAlert('No new notifications.', 'info', 3000);
    });
  }
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const hamburger = document.getElementById('hamburger-btn');
  const isOpen = sidebar?.classList.contains('open');

  if (isOpen) {
    closeSidebar();
  } else {
    sidebar?.classList.add('open');
    overlay?.classList.add('active');
    hamburger?.setAttribute('aria-expanded', 'true');
    hamburger && (hamburger.innerHTML = iconClose());
  }
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const hamburger = document.getElementById('hamburger-btn');

  sidebar?.classList.remove('open');
  overlay?.classList.remove('active');
  hamburger?.setAttribute('aria-expanded', 'false');
  hamburger && (hamburger.innerHTML = iconMenu());
}

/* ============================================================
   10. DASHBOARD VIEW
   ============================================================ */
function renderDashboard() {
  const user = state.user;
  const firstName = user?.first_name || user?.email?.split('@')[0] || 'Coach';
  const role = getPortalRole(user);
  const roleLabel = user?.role || PORTAL_LABELS[role] || 'User';

  const statCards = STAT_CARD_DATA.map(s => `
    <div class="stat-card ${s.colorClass}">
      <div class="stat-icon ${s.colorClass}">${s.icon()}</div>
      <div class="stat-value">${s.value}</div>
      <div class="stat-label">${s.label}</div>
      <div class="stat-trend">${s.trend}</div>
    </div>
  `).join('');

  return `
    <div class="welcome-card">
      <div class="welcome-greeting">Welcome back, ${escapeHtml(firstName)}! 👋</div>
      <div class="welcome-subtitle">
        <span class="badge badge-yellow" style="margin-right:8px;">${escapeHtml(roleLabel)}</span>
        Here's what's happening today.
      </div>
      <div class="welcome-date">${formatDate()}</div>
    </div>

    <div class="stats-grid">
      ${statCards}
    </div>

    <div class="cards-grid">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Recent Activity</div>
            <div class="card-subtitle">Latest updates across your schools</div>
          </div>
        </div>
        <div class="empty-state">
          <div class="empty-state-icon">📋</div>
          <div class="empty-state-title">Activity feed coming soon</div>
          <div class="empty-state-text">
            Real-time activity from sessions, incidents, and assessments will appear here in Week 2.
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Quick Actions</div>
            <div class="card-subtitle">Common tasks for today</div>
          </div>
        </div>
        <div class="form-stack">
          ${renderQuickActions(role)}
        </div>
      </div>
    </div>
  `;
}

function renderQuickActions(role) {
  const actions = {
    admin: [
      { label: 'View All Schools',   page: 'schools'   },
      { label: 'Manage Coaches',      page: 'coaches'   },
      { label: 'Review Incidents',    page: 'incidents' },
    ],
    coach: [
      { label: 'Log EOD Report',    page: 'eod-reports'  },
      { label: 'Start Session',     page: 'sessions'     },
      { label: 'Record Incident',   page: 'incidents'    },
    ],
    staff: [
      { label: 'View My Students',  page: 'students' },
      { label: 'View Reports',      page: 'reports'  },
    ],
  };

  const items = actions[role] || actions.admin;
  return items.map(a => `
    <button class="btn btn-ghost btn-full" data-page="${a.page}"
            type="button" style="justify-content:flex-start;">
      ${a.label}
    </button>
  `).join('');
}

/* ============================================================
   11. STUB PAGES
   ============================================================ */
function renderStub(title, message, iconSvg = '') {
  return `
    <div class="coming-soon-page">
      <div style="font-size:3rem;opacity:0.5;">${iconSvg}</div>
      <div class="coming-soon-badge">Coming in Week 2</div>
      <div class="coming-soon-title">${escapeHtml(title)}</div>
      <div class="coming-soon-text">${escapeHtml(message)}</div>
      <button class="btn btn-ghost" type="button"
              onclick="navigate('dashboard')">
        Back to Dashboard
      </button>
    </div>
  `;
}

function renderStudents() {
  const rows = [
    { name: 'Aria Thompson',   school: 'Lincoln High',    grade: '9th',  status: 'Active'   },
    { name: 'Marcus Webb',     school: 'Westview Middle',  grade: '7th',  status: 'Active'   },
    { name: 'Priya Nair',      school: 'Lincoln High',    grade: '11th', status: 'Inactive' },
    { name: 'Devon Clarke',    school: 'Eastside Prep',   grade: '10th', status: 'Active'   },
    { name: 'Sofia Reyes',     school: 'Westview Middle',  grade: '8th',  status: 'Active'   },
  ];

  const statusBadge = s => s === 'Active'
    ? `<span class="badge badge-green">${s}</span>`
    : `<span class="badge badge-gray">${s}</span>`;

  const tableRows = rows.map(r => `
    <tr>
      <td><strong>${escapeHtml(r.name)}</strong></td>
      <td>${escapeHtml(r.school)}</td>
      <td>${escapeHtml(r.grade)}</td>
      <td>${statusBadge(r.status)}</td>
      <td>
        <div class="td-actions">
          <button class="btn btn-ghost btn-sm" type="button">View</button>
        </div>
      </td>
    </tr>
  `).join('');

  return `
    <div class="card-header" style="margin-bottom:20px;">
      <div>
        <div class="text-h2">Students</div>
        <div class="text-caption">Manage student records across all schools</div>
      </div>
      <button class="btn btn-primary btn-sm" type="button">+ Add Student</button>
    </div>

    <div class="card" style="padding:0;overflow:hidden;">
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>School</th>
              <th>Grade</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${tableRows}
          </tbody>
        </table>
      </div>
    </div>

    <div style="margin-top:16px;text-align:center;">
      <span class="text-caption">Showing 5 of 1,847 students — full pagination coming in Week 2</span>
    </div>
  `;
}

function renderIncidents() {
  const incidents = [
    { id: 'INC-001', student: 'Marcus Webb',  type: 'Injury',   severity: 'Low',    date: 'Apr 17', status: 'Open'     },
    { id: 'INC-002', student: 'Aria Thompson', type: 'Behavior', severity: 'Medium', date: 'Apr 16', status: 'Reviewed' },
    { id: 'INC-003', student: 'Devon Clarke',  type: 'Injury',   severity: 'High',   date: 'Apr 15', status: 'Open'     },
  ];

  const severityBadge = s => {
    if (s === 'High')   return `<span class="badge badge-red">${s}</span>`;
    if (s === 'Medium') return `<span class="badge badge-yellow">${s}</span>`;
    return `<span class="badge badge-gray">${s}</span>`;
  };

  const statusBadge = s => s === 'Open'
    ? `<span class="badge badge-blue">${s}</span>`
    : `<span class="badge badge-green">${s}</span>`;

  const rows = incidents.map(r => `
    <tr>
      <td><code style="font-size:12px;color:var(--color-text-secondary);">${r.id}</code></td>
      <td><strong>${escapeHtml(r.student)}</strong></td>
      <td>${escapeHtml(r.type)}</td>
      <td>${severityBadge(r.severity)}</td>
      <td>${statusBadge(r.status)}</td>
      <td>${escapeHtml(r.date)}</td>
      <td>
        <div class="td-actions">
          <button class="btn btn-ghost btn-sm" type="button">View</button>
        </div>
      </td>
    </tr>
  `).join('');

  return `
    <div class="card-header" style="margin-bottom:20px;">
      <div>
        <div class="text-h2">Incidents</div>
        <div class="text-caption">Track and resolve student incidents</div>
      </div>
      <button class="btn btn-danger btn-sm" type="button">+ Log Incident</button>
    </div>

    <div class="alert alert-warning" style="margin-bottom:16px;">
      <span class="alert-icon">${iconIncidents()}</span>
      <span class="alert-body">
        <strong>3 open incidents</strong> require attention — 1 is high severity.
      </span>
    </div>

    <div class="card" style="padding:0;overflow:hidden;">
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Student</th>
              <th>Type</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Date</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
}

function renderSettings() {
  const user = state.user;
  const userName = user?.first_name
    ? `${user.first_name} ${user.last_name || ''}`.trim()
    : 'User';

  return `
    <div class="text-h2" style="margin-bottom:20px;">Settings</div>

    <div class="cards-grid">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Profile</div>
        </div>
        <div class="form-stack">
          <div class="form-group">
            <label class="form-label">Full Name</label>
            <input class="form-input" type="text"
                   value="${escapeHtml(userName)}" disabled />
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input class="form-input" type="email"
                   value="${escapeHtml(user?.email || '')}" disabled />
          </div>
          <div class="form-group">
            <label class="form-label">Role</label>
            <input class="form-input" type="text"
                   value="${escapeHtml(user?.role || PORTAL_LABELS[state.portal] || '')}"
                   disabled />
          </div>
          <button class="btn btn-ghost btn-sm" type="button" disabled>
            Edit Profile (Coming Soon)
          </button>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div class="card-title">Security</div>
        </div>
        <div class="form-stack">
          <div class="form-group">
            <label class="form-label">Current Password</label>
            <input class="form-input" type="password" placeholder="••••••••" disabled />
          </div>
          <div class="form-group">
            <label class="form-label">New Password</label>
            <input class="form-input" type="password" placeholder="••••••••" disabled />
          </div>
          <button class="btn btn-ghost btn-sm" type="button" disabled>
            Change Password (Coming Soon)
          </button>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px;">
      <div class="card-header">
        <div class="card-title">Danger Zone</div>
      </div>
      <div class="d-flex align-center gap-12">
        <button class="btn btn-danger btn-sm" type="button" id="settings-logout-btn">
          ${iconLogout()} Sign Out
        </button>
        <span class="text-caption">You will be returned to the login screen.</span>
      </div>
    </div>
  `;
}

/* ============================================================
   12. SIDEBAR RENDERER (for role-based nav — also used inline)
   ============================================================ */
function renderSidebar(role) {
  const navItems = NAV_CONFIG[role] || NAV_CONFIG.admin;
  return navItems.map(item => `
    <div class="nav-item ${item.page === state.currentPage ? 'active' : ''}"
         data-page="${item.page}"
         role="button"
         tabindex="0">
      <span class="nav-item-icon">${item.icon()}</span>
      <span>${item.label}</span>
    </div>
  `).join('');
}

/* ============================================================
   13. LOGOUT
   ============================================================ */
async function handleLogout() {
  const btn = document.getElementById('logout-btn')
    || document.getElementById('settings-logout-btn');

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner spinner-white"></span>`;
  }

  try {
    await api('POST', '/api/auth/logout');
  } catch (_) {
    // Logout even if the API call fails
  } finally {
    state.user = null;
    state.currentPage = 'login';
    state.notifications = [];
    state.error = null;
    render();
    showAlert('You have been signed out.', 'success', 3000);
  }
}

/* ============================================================
   14. QUICK-ACTION BUTTON DELEGATION (after dashboard renders)
   ============================================================ */
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-page]');
  if (btn && btn.classList.contains('btn') && state.user) {
    const page = btn.dataset.page;
    if (page) navigate(page);
  }

  // Settings logout
  if (e.target.closest('#settings-logout-btn')) {
    handleLogout();
  }
});

/* ============================================================
   15. KEYBOARD SHORTCUTS
   ============================================================ */
document.addEventListener('keydown', (e) => {
  // Escape closes sidebar on mobile
  if (e.key === 'Escape') {
    closeSidebar();
  }
});

/* ============================================================
   16. INIT — Check session on load
   ============================================================ */
async function init() {
  // Show a brief loading state
  const app = document.getElementById('app');
  if (app) {
    app.innerHTML = `
      <div class="loading-overlay" style="min-height:100vh;">
        <div class="spinner spinner-lg"></div>
        <div class="loading-text">Loading Ufit Motion…</div>
      </div>
    `;
  }

  try {
    const data = await api('GET', '/api/auth/session');
    if (data && (data.user || data.email || data.id)) {
      state.user = data.user || data;
      state.portal = getPortalRole(state.user);
      state.currentPage = 'dashboard';
    } else {
      state.currentPage = 'login';
    }
  } catch (_) {
    // Not authenticated — show login
    state.currentPage = 'login';
    state.error = null; // Don't show error for a session check
    // Clear any alert that api() may have emitted
    const stack = document.getElementById('alert-stack');
    if (stack) stack.innerHTML = '';
  }

  render();
}

document.addEventListener('DOMContentLoaded', init);
