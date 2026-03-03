const whoami = document.getElementById('whoami');
const logoutBtn = document.getElementById('logoutBtn');
const smtpForm = document.getElementById('smtpForm');
const workflowForm = document.getElementById('workflowForm');
const feedback = document.getElementById('feedback');
const workflowFeedback = document.getElementById('workflowFeedback');
const testSmtpBtn = document.getElementById('testSmtpBtn');

const f = {
  host: document.getElementById('smtp_host'),
  port: document.getElementById('smtp_port'),
  user: document.getElementById('smtp_user'),
  pass: document.getElementById('smtp_pass'),
  from: document.getElementById('smtp_from'),
  tls: document.getElementById('smtp_tls'),
  inviteDefaultMessage: document.getElementById('invite_default_message'),
  smtpTestTo: document.getElementById('smtp_test_to'),
  defaultDueDays: document.getElementById('default_due_days'),
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
  f.inviteDefaultMessage.value = getSetting(s, 'invite.default_message', '');
  f.defaultDueDays.value = getSetting(s, 'workflow.default_due_days', '7');
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
        'invite.default_message': f.inviteDefaultMessage.value,
      }),
    });
    feedback.textContent = 'Configurações salvas ✅';
  } catch (err) {
    feedback.textContent = err.message;
  }
};

workflowForm.onsubmit = async (e) => {
  e.preventDefault();
  workflowFeedback.textContent = '';
  try {
    await api('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        'workflow.default_due_days': f.defaultDueDays.value,
      }),
    });
    workflowFeedback.textContent = 'Comportamento salvo ✅';
  } catch (err) {
    workflowFeedback.textContent = err.message;
  }
};

testSmtpBtn.onclick = async () => {
  feedback.textContent = '';
  try {
    const to = (f.smtpTestTo.value || '').trim();
    if (!to) {
      feedback.textContent = 'Informe um e-mail para teste SMTP.';
      return;
    }
    await api('/api/admin/settings/test-smtp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to }),
    });
    feedback.textContent = `Teste SMTP enviado para ${to} ✅`;
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
