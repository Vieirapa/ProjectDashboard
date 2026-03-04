const whoami = document.getElementById('whoami');
const logoutBtn = document.getElementById('logoutBtn');
const smtpForm = document.getElementById('smtpForm');
const workflowForm = document.getElementById('workflowForm');
const reportForm = document.getElementById('reportForm');
const backupForm = document.getElementById('backupForm');
const diagForm = document.getElementById('diagForm');
const feedback = document.getElementById('feedback');
const workflowFeedback = document.getElementById('workflowFeedback');
const reportFeedback = document.getElementById('reportFeedback');
const backupFeedback = document.getElementById('backupFeedback');
const diagFeedback = document.getElementById('diagFeedback');
const reportsList = document.getElementById('reportsList');
const reportPreview = document.getElementById('reportPreview');
const diagOutput = document.getElementById('diagOutput');
const testSmtpBtn = document.getElementById('testSmtpBtn');
const runBackupNowBtn = document.getElementById('runBackupNowBtn');
const runDiagBtn = document.getElementById('runDiagBtn');

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
  backupEnabled: document.getElementById('backup_enabled'),
  backupPath: document.getElementById('backup_path'),
  backupWeekdays: document.getElementById('backup_weekdays'),
  backupRunTime: document.getElementById('backup_run_time'),
  systemGitRepo: document.getElementById('system_git_repo'),
  systemGitBranch: document.getElementById('system_git_branch'),

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
  if (!r.ok) {
    const err = new Error(d.error || 'Erro');
    err.data = d;
    throw err;
  }
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

function weekdayLabel(v) {
  const m = {
    '0': 'segunda',
    '1': 'terça',
    '2': 'quarta',
    '3': 'quinta',
    '4': 'sexta',
    '5': 'sábado',
    '6': 'domingo',
  };
  return m[String(v)] || String(v);
}

function reportConfigLine(r) {
  const statuses = (r.statuses || []).join('; ') || '-';
  const priorities = (r.priorities || []).join('; ') || '-';
  const roles = (r.roles || []).join('; ') || '-';
  const days = (r.weekdays || []).map(weekdayLabel).join(', ') || '-';
  const time = r.run_time ? `${r.run_time}h` : '-';
  return `{${statuses}} {${priorities}} {${roles}} {${days}} {${time}}`;
}

function renderDiagnostics(diagnostics) {
  const lines = [];
  lines.push(`Timestamp: ${diagnostics?.timestamp || '-'}`);
  if (diagnostics?.version) {
    lines.push(`Local: ${diagnostics.version.local || 'unknown'}`);
    lines.push(`Remote (${diagnostics.version.branch || '-'}): ${diagnostics.version.remote || 'unknown'}`);
    lines.push(`Update available: ${diagnostics.version.updateAvailable ? 'SIM' : 'NÃO'}`);
  }
  lines.push('');
  lines.push('Checks:');
  (diagnostics?.checks || []).forEach((c) => {
    lines.push(`- ${c.ok ? '✅' : '❌'} ${c.name}: ${c.detail || '-'}`);
  });
  diagOutput.value = lines.join('\n');
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
  f.backupEnabled.checked = String(getSetting(s, 'backup.enabled', 'false')).toLowerCase() === 'true';
  f.backupPath.value = getSetting(s, 'backup.path', '/var/backups/projectdashboard');
  f.backupRunTime.value = getSetting(s, 'backup.run_time', '03:00');
  f.systemGitRepo.value = getSetting(s, 'system.git_repo', 'https://github.com/Vieirapa/ProjectDashboard.git');
  f.systemGitBranch.value = getSetting(s, 'system.git_branch', 'main');

  let days = [];
  try { days = JSON.parse(getSetting(s, 'backup.weekdays', '["0","1","2","3","4","5","6"]')); } catch { days = []; }
  const setDays = new Set((days || []).map(String));
  f.backupWeekdays.querySelectorAll('input[type="checkbox"]').forEach((el) => {
    el.checked = setDays.has(String(el.value));
  });
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
      <td>
        <div>${r.name}</div>
        <div class="small" style="margin-top:4px; color:#4b5563;">${reportConfigLine(r)}</div>
      </td>
      <td>${(r.weekdays || []).map(weekdayLabel).join(', ')}</td>
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
        const d = await api(`/api/admin/reports/${btn.dataset.run}/run`, { method: 'POST' });
        reportPreview.value = d.previewText || '';
        reportFeedback.textContent = `Relatório executado manualmente ✅ (destinatários: ${d.recipients ?? 0})`;
      } catch (e) {
        const msg = String(e.message || 'Erro');
        if (e?.data?.previewText) reportPreview.value = e.data.previewText;
        reportFeedback.textContent = msg;
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

backupForm.onsubmit = async (e) => {
  e.preventDefault();
  backupFeedback.textContent = '';
  try {
    await api('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        'backup.enabled': f.backupEnabled.checked ? 'true' : 'false',
        'backup.path': f.backupPath.value,
        'backup.weekdays': JSON.stringify(checkedValues(f.backupWeekdays)),
        'backup.run_time': f.backupRunTime.value,
      }),
    });
    backupFeedback.textContent = 'Política de backup salva ✅';
  } catch (err) {
    backupFeedback.textContent = err.message;
  }
};

diagForm.onsubmit = async (e) => {
  e.preventDefault();
  diagFeedback.textContent = '';
  try {
    await api('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        'system.git_repo': f.systemGitRepo.value,
        'system.git_branch': f.systemGitBranch.value,
      }),
    });
    diagFeedback.textContent = 'Fonte de versão salva ✅';
  } catch (err) {
    diagFeedback.textContent = err.message;
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

runBackupNowBtn.onclick = async () => {
  backupFeedback.textContent = '';
  try {
    const d = await api('/api/admin/system/backup/run', { method: 'POST' });
    backupFeedback.textContent = d.message || 'Backup manual executado ✅';
  } catch (err) {
    backupFeedback.textContent = err.message;
  }
};

runDiagBtn.onclick = async () => {
  diagFeedback.textContent = '';
  try {
    const d = await api('/api/admin/system/diagnostics');
    renderDiagnostics(d.diagnostics || {});
    diagFeedback.textContent = 'Diagnóstico executado ✅';
  } catch (err) {
    diagFeedback.textContent = err.message;
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
    try {
      const d = await api('/api/admin/system/diagnostics');
      renderDiagnostics(d.diagnostics || {});
    } catch (_) {
      // diagnóstico pode falhar sem bloquear tela
    }
  } catch {
    location.href = '/';
  }
})();
