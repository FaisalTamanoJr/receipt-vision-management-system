/* Settings page logic. Values persist in localStorage via App.saveSettings.
   Backend hooks are marked TODO. */
const $ = (id) => document.getElementById(id);
const tabs = [...document.querySelectorAll('[data-tab]')];
let s = App.getSettings();

function show(name) {
  if (!document.getElementById(name)) name = 'general';
  tabs.forEach((t) => t.setAttribute('aria-selected', String(t.dataset.tab === name)));
  document.querySelectorAll('.panel').forEach((p) => (p.hidden = p.id !== name));
  history.replaceState(null, '', '#' + name);
}
tabs.forEach((t) => t.addEventListener('click', () => show(t.dataset.tab)));
show(location.hash.slice(1) || 'general');

/* Switches */
['darkMode', 'llmEnabled', 'notifyScan', 'notifyReview', 'notifyStorage'].forEach((id) => {
  $(id).checked = !!s[id];
  $(id).addEventListener('change', (e) => {
    App.saveSettings({ [id]: e.target.checked });
    if (id === 'darkMode') App.applyTheme();
    App.toast('Saved');
  });
});
/* Dropdowns */
['dateFormat', 'autoSignOut', 'llmModel'].forEach((id) => {
  $(id).value = s[id];
  $(id).addEventListener('change', (e) => { App.saveSettings({ [id]: e.target.value }); App.toast('Saved'); });
});
/* Display name */
$('username').value = s.username === 'User' ? '' : s.username;
$('username').placeholder = 'Your name';
$('username').addEventListener('change', (e) => {
  App.saveSettings({ username: e.target.value.trim() || 'User' }); renderSecurity(); App.toast('Saved');
});

/* Security */
function renderSecurity() {
  s = App.getSettings();
  $('pwDate').textContent = 'Last changed: ' + (s.passwordChanged
    ? new Date(s.passwordChanged).toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' }) : 'never');
  $('unameShow').textContent = s.username;
}
renderSecurity();

document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => b.closest('dialog').close()));

$('pwOpen').addEventListener('click', () => {
  ['pwCur', 'pwNew', 'pwCon'].forEach((i) => ($(i).value = '')); $('pwErr').textContent = ''; $('pwDlg').showModal();
});
$('pwSave').addEventListener('click', () => {
  const cur = $('pwCur').value, nw = $('pwNew').value, con = $('pwCon').value;
  if (!cur) return ($('pwErr').textContent = 'Enter your current password.');
  if (nw.length < 8) return ($('pwErr').textContent = 'Use at least 8 characters for the new password.');
  if (nw === cur) return ($('pwErr').textContent = 'Choose a password you haven\'t used before.');
  if (nw !== con) return ($('pwErr').textContent = 'The new passwords don\'t match.');
  /* TODO (auth): send cur + nw to the auth API; show its error if the current password is wrong. */
  App.saveSettings({ passwordChanged: new Date().toISOString() });
  $('pwDlg').close(); renderSecurity(); App.toast('Password changed');
});

$('unOpen').addEventListener('click', () => { $('unNew').value = ''; $('unErr').textContent = ''; $('unDlg').showModal(); });
$('unSave').addEventListener('click', () => {
  const v = $('unNew').value.trim();
  if (v.length < 3) return ($('unErr').textContent = 'Use at least 3 characters.');
  /* TODO (auth): update the username through the auth API. */
  App.saveSettings({ username: v }); $('username').value = v;
  $('unDlg').close(); renderSecurity(); App.toast('Username changed');
});

/* Data management */
$('storagePath').value = s.storagePath;
$('pathSave').addEventListener('click', () => {
  const v = $('storagePath').value.trim();
  if (!v) return App.toast('Enter a folder path first');
  /* TODO (database): validate the folder and move existing files. */
  App.saveSettings({ storagePath: v }); App.toast('File location saved');
});
$('clearOpen').addEventListener('click', () => { $('clearConfirm').value = ''; $('clearGo').disabled = true; $('clearDlg').showModal(); });
$('clearConfirm').addEventListener('input', (e) => ($('clearGo').disabled = e.target.value.trim() !== 'DELETE'));
$('clearGo').addEventListener('click', async () => {
  /* Deletes the receipt records; TODO (database): also delete the scanned image files. */
  const res = await App.api('clearReceipts');
  $('clearDlg').close();
  App.toast(res ? `${res.deleted} receipts deleted` : 'All files cleared');
});
