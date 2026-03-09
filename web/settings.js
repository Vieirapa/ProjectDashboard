const logoutBtn = document.getElementById('logoutBtn');
const smtpForm = document.getElementById('smtpForm');
const workflowForm = document.getElementById('workflowForm');
const reportForm = document.getElementById('reportForm');
const backupForm = document.getElementById('backupForm');
const diagForm = document.getElementById('diagForm');
const deletedPolicyForm = document.getElementById('deletedPolicyForm');
const feedback = document.getElementById('feedback');
const workflowFeedback = document.getElementById('workflowFeedback');
const reportFeedback = document.getElementById('reportFeedback');
const backupFeedback = document.getElementById('backupFeedback');
const diagFeedback = document.getElementById('diagFeedback');
const deletedPolicyFeedback = document.getElementById('deletedPolicyFeedback');
const reportsList = document.getElementById('reportsList');
const deletedDocumentsList = document.getElementById('deletedDocumentsList');
const deletedDocumentsPager = document.getElementById('deletedDocumentsPager');
const deletedFiltersState = document.getElementById('deletedFiltersState');
const reportPreview = document.getElementById('reportPreview');
const diagOutput = document.getElementById('diagOutput');
const testSmtpBtn = document.getElementById('testSmtpBtn');
const runBackupNowBtn = document.getElementById('runBackupNowBtn');
const testBackupPathBtn = document.getElementById('testBackupPathBtn');
const refreshBackupListBtn = document.getElementById('refreshBackupListBtn');
const restoreBackupBtn = document.getElementById('restoreBackupBtn');
const backupRestoreList = document.getElementById('backupRestoreList');
const runDiagBtn = document.getElementById('runDiagBtn');
const refreshDeletedBtn = document.getElementById('refreshDeletedBtn');
const applyDeletedFiltersBtn = document.getElementById('applyDeletedFiltersBtn');
const clearDeletedFiltersBtn = document.getElementById('clearDeletedFiltersBtn');

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
  deletedRetentionDays: document.getElementById('deleted_retention_days'),
  deletedFilterQ: document.getElementById('deleted_filter_q'),
  deletedFilterBy: document.getElementById('deleted_filter_by'),
  deletedFilterFrom: document.getElementById('deleted_filter_from'),
  deletedFilterTo: document.getElementById('deleted_filter_to'),

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
let deletedFilters = {
  q: '',
  deleted_by: '',
  deleted_from: '',
  deleted_to: '',
};
let deletedPager = {
  page: 1,
  page_size: 10,
  total: 0,
  total_pages: 1,
};
let backupSnapshots = [];

async function api(url, opts = {}) {
  const r = await fetch(url, opts);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(d.error || `Erro HTTP ${r.status}`);
    err.data = d;
    err.status = r.status;
    throw err;
  }
  return d;
}

async function ensureAdmin() {
  const d = await api('/api/me');
  if (!d.user || d.user.role !== 'admin') throw new Error('Acesso restrito a admin');
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

function renderDeletedFiltersState() {
  if (!deletedFiltersState) return;
  const labels = [];
  if (String(deletedFilters.q || '').trim()) labels.push(`nome/slug: "${deletedFilters.q}"`);
  if (String(deletedFilters.deleted_by || '').trim()) labels.push(`apagado por: "${deletedFilters.deleted_by}"`);
  if (String(deletedFilters.deleted_from || '').trim()) labels.push(`de: ${deletedFilters.deleted_from}`);
  if (String(deletedFilters.deleted_to || '').trim()) labels.push(`até: ${deletedFilters.deleted_to}`);
  deletedFiltersState.textContent = labels.length
    ? `Filtros ativos → ${labels.join(' | ')}`
    : 'Filtros ativos → nenhum';
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
  lines.push(`Data/Hora: ${diagnostics?.timestamp || '-'}`);
  if (diagnostics?.version) {
    lines.push(`Versão local: ${diagnostics.version.local || 'desconhecida'}`);
    lines.push(`Versão remota (${diagnostics.version.branch || '-'}): ${diagnostics.version.remote || 'desconhecida'}`);
    lines.push(`Atualização disponível: ${diagnostics.version.updateAvailable ? 'SIM' : 'NÃO'}`);
  }
  lines.push('');
  lines.push('Verificações:');
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
  f.backupPath.value = getSetting(s, 'backup.path', '/opt/documentdashboard/data/backups');
  f.backupRunTime.value = getSetting(s, 'backup.run_time', '03:00');
  f.systemGitRepo.value = getSetting(s, 'system.git_repo', 'https://github.com/Vieirapa/ProjectDashboard.git');
  f.systemGitBranch.value = getSetting(s, 'system.git_branch', 'main');
  f.deletedRetentionDays.value = getSetting(s, 'deleted.retention_days', '30');

  let days = [];
  try { days = JSON.parse(getSetting(s, 'backup.weekdays', '["0","1","2","3","4","5","6"]')); } catch { days = []; }
  const setDays = new Set((days || []).map(String));
  f.backupWeekdays.querySelectorAll('input[type="checkbox"]').forEach((el) => {
    el.checked = setDays.has(String(el.value));
  });
}

async function loadBackupSnapshots() {
  const path = (f.backupPath.value || '').trim();
  const q = new URLSearchParams();
  if (path) q.set('path', path);
  const d = await api(`/api/admin/system/backup/available${q.toString() ? `?${q.toString()}` : ''}`);
  backupSnapshots = d.items || [];

  if (!backupSnapshots.length) {
    backupRestoreList.textContent = `Nenhum backup encontrado em ${d.path || path || '(caminho padrão)'}.`;
    return;
  }

  backupRestoreList.innerHTML = `<table>
    <tr><th></th><th>Data/Hora</th><th>DB</th><th>Docs</th></tr>
    ${backupSnapshots.map((b, idx) => `<tr>
      <td><input type="radio" name="backup_stamp" value="${b.stamp}" ${idx === 0 ? 'checked' : ''}></td>
      <td>${b.when || b.stamp}</td>
      <td>${b.db_backup ? '✅' : '—'}</td>
      <td>${b.docs_backup ? '✅' : '—'}</td>
    </tr>`).join('')}
  </table>`;
}

function getSelectedBackupStamp() {
  const el = document.querySelector('input[name="backup_stamp"]:checked');
  return el ? String(el.value || '').trim() : '';
}

function applyDeletedFiltersLocal(rows) {
  const q = String(deletedFilters.q || '').trim().toLowerCase();
  const by = String(deletedFilters.deleted_by || '').trim().toLowerCase();
  const from = String(deletedFilters.deleted_from || '').trim();
  const to = String(deletedFilters.deleted_to || '').trim();

  return (rows || []).filter((r) => {
    const name = String(r?.name || '').toLowerCase();
    const slug = String(r?.slug || '').toLowerCase();
    const deletedBy = String(r?.deleted_by || '').trim().toLowerCase();
    const deletedAt = String(r?.deleted_at || '').trim();

    if (q && !name.includes(q) && !slug.includes(q)) return false;
    if (by && !deletedBy.includes(by)) return false;

    if (from) {
      const fromIso = from.length === 10 ? `${from}T00:00:00Z` : from;
      if (deletedAt && deletedAt < fromIso) return false;
    }
    if (to) {
      const toIso = to.length === 10 ? `${to}T23:59:59Z` : to;
      if (deletedAt && deletedAt > toIso) return false;
    }

    return true;
  });
}

function renderDeletedPager() {
  let pagerEl = deletedDocumentsPager || document.getElementById('deletedDocumentsPager');
  if (!pagerEl && deletedDocumentsList?.parentElement) {
    pagerEl = document.createElement('div');
    pagerEl.id = 'deletedDocumentsPager';
    pagerEl.className = 'small';
    pagerEl.style.marginTop = '8px';
    deletedDocumentsList.parentElement.appendChild(pagerEl);
  }
  if (!pagerEl) return;

  const { page, total_pages, total } = deletedPager;
  if (!total) {
    pagerEl.textContent = '';
    return;
  }
  pagerEl.innerHTML = `
    <div style="display:flex; gap:8px; align-items:center; justify-content:flex-start; flex-wrap:wrap;">
      <button type="button" class="secondary" id="deletedPrevPageBtn" ${page <= 1 ? 'disabled' : ''}>Anterior</button>
      <button type="button" class="secondary" id="deletedNextPageBtn" ${page >= total_pages ? 'disabled' : ''}>Próxima</button>
      <span>Página ${page} de ${total_pages} · Total: ${total} (máx ${deletedPager.page_size}/página)</span>
    </div>
  `;
  const prev = document.getElementById('deletedPrevPageBtn');
  const next = document.getElementById('deletedNextPageBtn');
  if (prev) prev.onclick = async () => { deletedPager.page = Math.max(1, deletedPager.page - 1); await loadDeletedDocuments(); };
  if (next) next.onclick = async () => { deletedPager.page = Math.min(deletedPager.total_pages, deletedPager.page + 1); await loadDeletedDocuments(); };
}

async function loadDeletedDocuments() {
  const params = new URLSearchParams();
  Object.entries(deletedFilters).forEach(([k, v]) => {
    const val = String(v || '').trim();
    if (val) params.set(k, val);
  });
  params.set('page', String(deletedPager.page || 1));
  params.set('page_size', String(deletedPager.page_size || 10));

  const d = await api(`/api/admin/deleted-documents?${params.toString()}`);

  if (d.filters) {
    deletedFilters = { ...deletedFilters, ...d.filters };
  }

  const serverHasPagination =
    d.total !== undefined && d.page !== undefined && d.page_size !== undefined && d.total_pages !== undefined;

  const allRows = applyDeletedFiltersLocal(d.deleted_documents || []);
  let filteredRows = allRows;

  if (serverHasPagination) {
    deletedPager.page = Number(d.page || 1);
    deletedPager.page_size = Number(d.page_size || 10);
    deletedPager.total = Number(d.total || 0);
    deletedPager.total_pages = Number(d.total_pages || 1);
  } else {
    deletedPager.page_size = 10;
    deletedPager.total = allRows.length;
    deletedPager.total_pages = Math.max(1, Math.ceil(deletedPager.total / deletedPager.page_size));
    deletedPager.page = Math.min(Math.max(1, deletedPager.page), deletedPager.total_pages);
    const start = (deletedPager.page - 1) * deletedPager.page_size;
    filteredRows = allRows.slice(start, start + deletedPager.page_size);
  }

  f.deletedFilterQ.value = deletedFilters.q || '';
  f.deletedFilterBy.value = deletedFilters.deleted_by || '';
  f.deletedFilterFrom.value = deletedFilters.deleted_from || '';
  f.deletedFilterTo.value = deletedFilters.deleted_to || '';
  renderDeletedFiltersState();

  if (!filteredRows.length) {
    const hasFilter = Object.values(deletedFilters).some((x) => String(x || '').trim());
    deletedDocumentsList.textContent = hasFilter
      ? 'Nenhum documento apagado encontrado para os filtros informados.'
      : 'Nenhum documento apagado.';
    renderDeletedPager();
    return;
  }

  deletedDocumentsList.innerHTML = `<table>
    <tr><th>Nome</th><th>Apagado em</th><th>Apagado por</th><th>Ações</th></tr>
    ${filteredRows.map((p) => `<tr>
      <td>${p.name || '-'}</td>
      <td>${p.deleted_at || '-'}</td>
      <td>${p.deleted_by || '-'}</td>
      <td>
        <button class="secondary" data-restore="${p.id}">Restaurar</button>
        <button class="danger" data-purge="${p.id}">Apagar permanentemente</button>
      </td>
    </tr>`).join('')}
  </table>`;
  renderDeletedPager();

  deletedDocumentsList.querySelectorAll('[data-restore]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api(`/api/admin/deleted-documents/${btn.dataset.restore}/restore`, { method: 'POST' });
        deletedPolicyFeedback.textContent = 'Documento restaurado ✅';
        await Promise.all([loadDeletedDocuments(), loadReports()]);
      } catch (err) {
        deletedPolicyFeedback.textContent = err.message;
      }
    };
  });

  deletedDocumentsList.querySelectorAll('[data-purge]').forEach((btn) => {
    btn.onclick = async () => {
      if (!confirm('Permanently delete this item and associated files?')) return;
      try {
        await api(`/api/admin/deleted-documents/${btn.dataset.purge}`, { method: 'DELETE' });
        deletedPolicyFeedback.textContent = 'Apagado permanentemente.';
        await loadDeletedDocuments();
      } catch (err) {
        deletedPolicyFeedback.textContent = err.message;
      }
    };
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

deletedPolicyForm.onsubmit = async (e) => {
  e.preventDefault();
  deletedPolicyFeedback.textContent = '';
  try {
    await api('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        'deleted.retention_days': String(f.deletedRetentionDays.value || '30'),
      }),
    });
    deletedPolicyFeedback.textContent = 'Retenção de documentos apagados salva ✅';
  } catch (err) {
    deletedPolicyFeedback.textContent = err.message;
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

testBackupPathBtn.onclick = async () => {
  backupFeedback.textContent = '';
  try {
    const d = await api('/api/admin/system/backup/test-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: f.backupPath.value || '' }),
    });
    backupFeedback.textContent = d.message || 'Caminho de backup validado ✅';
  } catch (err) {
    if (err?.status === 404) {
      backupFeedback.textContent = 'Este servidor ainda não tem o endpoint de teste de permissões. Atualize/reinicie a instância com a versão mais recente do ProjectDashboard e tente novamente.';
      return;
    }
    if (String(err?.message || '').includes('Permission') || String(err?.message || '').includes('Permissão')) {
      const p = (f.backupPath.value || '').trim() || '/var/backups/projectdashboard';
      backupFeedback.textContent = `${err.message} | Sugestão: sudo mkdir -p ${p} && sudo chown -R <usuario_servico>:<grupo_servico> ${p} && sudo chmod -R 775 ${p}`;
      return;
    }
    backupFeedback.textContent = err?.message || 'Falha ao testar permissões do caminho de backup.';
  }
};

runBackupNowBtn.onclick = async () => {
  backupFeedback.textContent = '';
  try {
    const d = await api('/api/admin/system/backup/run', { method: 'POST' });
    backupFeedback.textContent = d.message || 'Backup manual executado ✅';
    await loadBackupSnapshots();
  } catch (err) {
    backupFeedback.textContent = err.message;
  }
};

refreshBackupListBtn.onclick = async () => {
  backupFeedback.textContent = '';
  try {
    await loadBackupSnapshots();
    backupFeedback.textContent = 'Lista de backups atualizada.';
  } catch (err) {
    backupFeedback.textContent = err.message;
  }
};

restoreBackupBtn.onclick = async () => {
  backupFeedback.textContent = '';
  const stamp = getSelectedBackupStamp();
  if (!stamp) {
    backupFeedback.textContent = 'Selecione um backup na lista.';
    return;
  }
  const confirmText = prompt(`Você vai restaurar o snapshot ${stamp}.\nIsso pode sobrescrever dados atuais.\nDigite RESTAURAR para confirmar:`) || '';
  if (String(confirmText).trim().toUpperCase() !== 'RESTAURAR') {
    backupFeedback.textContent = 'Restauração cancelada (confirmação não informada).';
    return;
  }

  try {
    const d = await api('/api/admin/system/backup/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        stamp,
        path: f.backupPath.value || '',
        confirm_text: confirmText,
      }),
    });
    backupFeedback.textContent = d.message || `Restore do backup ${stamp} concluído ✅`;
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

refreshDeletedBtn.onclick = async () => {
  deletedPolicyFeedback.textContent = '';
  try {
    await loadDeletedDocuments();
    deletedPolicyFeedback.textContent = 'Lista de documentos apagados atualizada.';
  } catch (err) {
    deletedPolicyFeedback.textContent = err.message;
  }
};

applyDeletedFiltersBtn.onclick = async () => {
  deletedPolicyFeedback.textContent = '';
  deletedFilters = {
    q: f.deletedFilterQ.value,
    deleted_by: f.deletedFilterBy.value,
    deleted_from: f.deletedFilterFrom.value,
    deleted_to: f.deletedFilterTo.value,
  };
  deletedPager.page = 1;
  try {
    await loadDeletedDocuments();
    deletedPolicyFeedback.textContent = 'Filtros aplicados.';
  } catch (err) {
    deletedPolicyFeedback.textContent = err.message;
  }
};

clearDeletedFiltersBtn.onclick = async () => {
  deletedPolicyFeedback.textContent = '';
  deletedFilters = { q: '', deleted_by: '', deleted_from: '', deleted_to: '' };
  deletedPager.page = 1;
  f.deletedFilterQ.value = '';
  f.deletedFilterBy.value = '';
  f.deletedFilterFrom.value = '';
  f.deletedFilterTo.value = '';
  try {
    await loadDeletedDocuments();
    deletedPolicyFeedback.textContent = 'Filtros limpos.';
  } catch (err) {
    deletedPolicyFeedback.textContent = err.message;
  }
};

logoutBtn.onclick = async () => {
  await api('/api/logout', { method: 'POST' });
  location.href = '/login.html';
};

(async () => {
  try {
    await ensureAdmin();
  } catch {
    location.href = '/';
    return;
  }

  try {
    await Promise.all([loadSettings(), loadReports(), loadDeletedDocuments()]);
  } catch (e) {
    backupFeedback.textContent = e?.message || 'Falha ao carregar configurações iniciais.';
  }

  try {
    await loadBackupSnapshots();
  } catch (e) {
    backupRestoreList.textContent = 'Não foi possível carregar a lista de backups nesta instância (endpoint indisponível ou serviço desatualizado).';
  }

  try {
    const d = await api('/api/admin/system/diagnostics');
    renderDiagnostics(d.diagnostics || {});
  } catch (_) {
    // diagnóstico pode falhar sem bloquear tela
  }
})();
