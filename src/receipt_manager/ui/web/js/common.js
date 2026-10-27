/* Shared helpers: Python bridge, settings storage, theme, icons, toast.
   Load this in <head> so the theme applies before the page paints.
   Inside the app, settings come from Python (window.__SETTINGS__) and are saved
   through the bridge. Opened straight in a browser, they fall back to localStorage. */
(function () {
  const KEY = 'receipts.settings';
  const defaults = {
    username: 'User', darkMode: false, dateFormat: 'MMM DD, YYYY',
    passwordChanged: null, autoSignOut: '30',
    llmEnabled: true, llmModel: 'claude-sonnet-5-5',
    storagePath: 'C:/Receipts',
    notifyScan: true, notifyReview: true, notifyStorage: false
  };
  const App = (window.App = {});

  /* Resolves to the Python bridge (ui/bridge.py), or null outside the app. */
  App.bridge = new Promise((resolve) => {
    document.addEventListener('DOMContentLoaded', () => {
      if (!window.qt || !window.QWebChannel) return resolve(null);
      new QWebChannel(qt.webChannelTransport, (ch) => resolve(ch.objects.bridge));
    });
  });
  /* Calls a bridge slot and parses its JSON, e.g. await App.api('getStats').
     Resolves to null outside the app so pages can use sample data. */
  App.api = async (name, ...args) => {
    const b = await App.bridge;
    if (!b) return null;
    return new Promise((resolve) => b[name](...args, (res) => resolve(JSON.parse(res))));
  };

  App.getSettings = () => {
    if (window.__SETTINGS__) return { ...defaults, ...window.__SETTINGS__ };
    try { return { ...defaults, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; }
    catch { return { ...defaults }; }
  };
  App.saveSettings = (patch) => {
    const next = { ...App.getSettings(), ...patch };
    if (window.__SETTINGS__) {
      window.__SETTINGS__ = next;
      App.api('saveSettings', JSON.stringify(next));
    } else {
      try { localStorage.setItem(KEY, JSON.stringify(next)); } catch {}
    }
    return next;
  };
  App.applyTheme = () =>
    document.documentElement.setAttribute('data-theme', App.getSettings().darkMode ? 'dark' : 'light');
  App.applyTheme();

  const paths = {
    file:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    calendar:'<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    tag:'<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8z"/><circle cx="7" cy="7" r="1.5"/>',
    database:'<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/>',
    search:'<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
    trash:'<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6"/>',
    gear:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    logout:'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    chevron:'<path d="m9 18 6-6-6-6"/>',
    back:'<path d="M19 12H5M12 19l-7-7 7-7"/>',
    moon:'<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    lock:'<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    chat:'<path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-6.4A8 8 0 1 1 21 12z"/>',
    bell:'<path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
    key:'<circle cx="7.5" cy="15.5" r="4.5"/><path d="m10.7 12.3 9.8-9.8M16 7l3 3"/>',
    image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
    user:'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    folder:'<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'
  };
  document.addEventListener('DOMContentLoaded', () => {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('class', 'sr'); s.setAttribute('aria-hidden', 'true');
    s.innerHTML = Object.entries(paths).map(([k, v]) => `<symbol id="i-${k}" viewBox="0 0 24 24">${v}</symbol>`).join('');
    document.body.prepend(s);
  });

  App.toast = (msg) => {
    let t = document.querySelector('.toast');
    if (!t) { t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); document.body.append(t); }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 2200);
  };
  App.peso = (n) => '₱' + Number(n).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  /* TODO (auth): replace with the real sign-out once login.html exists. */
  App.signOut = () => { window.location.href = 'login.html'; };
})();
