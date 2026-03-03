const whoami = document.getElementById('whoami');
const logoutBtn = document.getElementById('logoutBtn');
const smtpForm = document.getElementById('smtpForm');
const workflowForm = document.getElementById('workflowForm');
const reportForm = document.getElementById('reportForm');
const feedback = document.getElementById('feedback');
const workflowFeedback = document.getElementById('workflowFeedback');
const reportFeedback = document.getElementById('reportFeedback');
const reportsList = document.getElementById('reportsList');
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

  rName: document.getElementById('r_name'),
  rStatuses: document.getElementById('r_statuses'),
  rPriorities: document.getElementById('r_priorities'),
  rRoles: document.getElementById('r_roles'),
  rWeekdays: document.getElementById('r_weekdays'),
  rRunTime: document.getElementById('r_run_time'),
  rMessage: document.getElementById('r_message'),
  rActive: document.getElementById('r_active'),
};

let meta = { statuses: [], roles: [] };

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

function checkedValues(container) {
  return Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map((el) => el.value);
}

function renderReportMeta() {
  f.rStatuses.innerHTML = meta.statuses.map((s) => `<label class="inline-check"><input type="checkbox" value="${s}" /> <span>${s}</span></label>`).join('');
  f.rRoles.innerHTML = meta.roles.map((r) => `<label class="inline-check"><input type="checkbox" value="${r}" /> <span>${r}</span></label>`).join('');
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

async function loadReports() {
  const d = await api('/api/admin/reports');
  meta.statuses = d.statuses || [];
  meta.roles = d.roles || [];
  renderReportMeta();

  if (!d.reports?.length) {
    reportsList.textContent = 'Nenhum relatório cadastrado.';
    return;
  }

  reportsList.innerHTML = `<table>
    <tr><th>Nome</th><th>Dias</th><th>Hora</th><th>Ativo</th><th>Ações</th></tr>
    ${d.reports.map((r) => `<tr>
      <td>${r.name}</td>
      <td>${(r.weekdays || []).join(', ')}</td>
      <td>${r.run_time}</td>
      <td>${Number(r.active) === 1 ? 'Sim' : 'Não'}</td>
      <td>
        <button class="secondary" data-run="${r.id}">Rodar agora</button>
        <button class="danger" data-del="${r.id}">Excluir</button>
      </td>
    </tr>`).join('')}
  </table>`;

  reportsList.querySelectorAll('[data-run]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api(`/api/admin/reports/${btn.dataset.run}/run`, { method: 'POST' });
        reportFeedback.textContent = 'Relatório executado manualmente ✅';
      } catch (e) {
        reportFeedback.textContent = e.message;
      }
    };
  });

  reportsList.querySelectorAll('[data-del]').forEach((btn) => {
    btn.onclick = async () => {
      if (!confirm('Excluir este relatório periódico?')) return;
      try {
        await api(`/api/admin/reports/${btn.dataset.del}`, { method: 'DELETE' });
        await loadReports();
        reportFeedback.textContent = 'Relatório excluído.';
      } catch (e) {
        reportFeedback.textContent = e.message;
      }
    };
  });
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

reportForm.onsubmit = async (e) => {
  e.preventDefault();
  reportFeedback.textContent = '';
  try {
    await api('/api/admin/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: f.rName.value,
        statuses: checkedValues(f.rStatuses),
        priorities: checkedValues(f.rPriorities),
        roles: checkedValues(f.rRoles),
        weekdays: checkedValues(f.rWeekdays),
        run_time: f.rRunTime.value,
        message: f.rMessage.value,
        active: f.rActive.checked,
      }),
    });
    reportFeedback.textContent = 'Relatório periódico criado ✅';
    reportForm.reset();
    await loadReports();
  } catch (err) {
    reportFeedback.textContent = err.message;
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
    await Promise.all([loadSettings(), loadReports()]);
  } catch {
    location.href = '/';
  }
})();
