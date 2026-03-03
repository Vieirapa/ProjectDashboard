const whoami = document.getElementById('whoami');
const logoutBtn = document.getElementById('logoutBtn');
const smtpForm = document.getElementById('smtpForm');
const feedback = document.getElementById('feedback');

const f = {
  host: document.getElementById('smtp_host'),
  port: document.getElementById('smtp_port'),
  user: document.getElementById('smtp_user'),
  pass: document.getElementById('smtp_pass'),
  from: document.getElementById('smtp_from'),
  tls: document.getElementById('smtp_tls'),
};

async function api(url, opts = {}) {
  const r = await fetch(url, opts);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || 'Erro');
  return d;
}

async function ensureAdmin() {
  const d = await api('/api/me');
  if (!d.user || d.user.role !== 'admin') throw new Error('Acesso restrito a admin');
  whoami.textContent = `${d.user.username} (${d.user.role})`;
}

function getSetting(settings, key, fallback = '') {
  return settings?.[key]?.value ?? fallback;
}

async function loadSettings() {
  const d = await api('/api/admin/settings');
  const s = d.settings || {};
  f.host.value = getSetting(s, 'smtp.host', '');
  f.port.value = getSetting(s, 'smtp.port', '587');
  f.user.value = getSetting(s, 'smtp.user', '');
  f.pass.value = getSetting(s, 'smtp.pass', '');
  f.from.value = getSetting(s, 'smtp.from', '');
  f.tls.checked = String(getSetting(s, 'smtp.tls', 'true')).toLowerCase() !== 'false';
}

smtpForm.onsubmit = async (e) => {
  e.preventDefault();
  feedback.textContent = '';
  try {
    await api('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        'smtp.host': f.host.value,
        'smtp.port': f.port.value,
        'smtp.user': f.user.value,
        'smtp.pass': f.pass.value,
        'smtp.from': f.from.value,
        'smtp.tls': f.tls.checked ? 'true' : 'false',
      }),
    });
    feedback.textContent = 'Configurações salvas ✅';
  } catch (err) {
    feedback.textContent = err.message;
  }
};

logoutBtn.onclick = async () => {
  await api('/api/logout', { method: 'POST' });
  location.href = '/login.html';
};

(async () => {
  try {
    await ensureAdmin();
    await loadSettings();
  } catch {
    location.href = '/';
  }
})();
