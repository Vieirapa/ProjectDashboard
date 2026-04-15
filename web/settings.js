/*
 * settings.js
 * ===========
 *
 * Responsável pela tela de configurações administrativas do sistema.
 *
 * Papel deste arquivo
 * -------------------
 * - Carregar configurações persistidas.
 * - Orquestrar SMTP, workflow, backup, diagnóstico, relatórios e roles.
 * - Coordenar ações administrativas disparadas a partir da UI.
 *
 * Como deve ser tratado no restante da aplicação
 * ----------------------------------------------
 * - Este arquivo deve permanecer como orquestrador da tela administrativa.
 * - Regras e validações de negócio continuam preferencialmente no backend.
 * - Mudanças nele exigem cuidado porque impactam várias capacidades do sistema.
 */

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
const backupNextRun = document.getElementById('backupNextRun');
const diagFeedback = document.getElementById('diagFeedback');
const deletedPolicyFeedback = document.getElementById('deletedPolicyFeedback');
const reportsList = document.getElementById('reportsList');
const deletedDocumentsList = document.getElementById('deletedDocumentsList');
const deletedDocumentsPager = document.getElementById('deletedDocumentsPager');
const deletedFiltersState = document.getElementById('deletedFiltersState');
const reportPreview = document.getElementById('reportPreview');
const diagOutput = document.getElementById('diagOutput');
const diagHealthSummary = document.getElementById('diagHealthSummary');
const diagHealthText = document.getElementById('diagHealthText');
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
const rolesRefreshBtn = document.getElementById('rolesRefreshBtn');
const rolesSaveBtn = document.getElementById('rolesSaveBtn');
const rolesSyncCatalogBtn = document.getElementById('rolesSyncCatalogBtn');
const rolesFeedback = document.getElementById('rolesFeedback');
const rolesMatrixWrap = document.getElementById('rolesMatrixWrap');
const roleCreateForm = document.getElementById('roleCreateForm');
const roleKeyInput = document.getElementById('roleKeyInput');
const roleDisplayNameInput = document.getElementById('roleDisplayNameInput');
const roleCreateBtn = document.getElementById('roleCreateBtn');
const rolesCatalogWrap = document.getElementById('rolesCatalogWrap');
const deletedDocumentsCount = document.getElementById('deletedDocumentsCount');
const reportsCount = document.getElementById('reportsCount');
const rolesCount = document.getElementById('rolesCount');

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
  dependencyMaxStatus: document.getElementById('dependency_max_status'),
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
let rolesModulesMeta = [];
let rolesMatrix = [];
let rolesCatalogItems = [];
let canManageRoles = false;
let allowedModules = new Set();
let lastPersistedBackupPath = '';

// ---------------------------------------------------------------------------
// Helper HTTP JSON da tela de settings
// ---------------------------------------------------------------------------
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

function hasModule(moduleId) {
  return allowedModules.has(moduleId);
}

function applyModuleVisibility() {
  document.querySelectorAll('[data-module-id]').forEach((el) => {
    const moduleId = String(el.dataset.moduleId || '').trim();
    if (!moduleId) return;
    el.style.display = hasModule(moduleId) ? '' : 'none';
  });
}

// ---------------------------------------------------------------------------
// Carregamento das permissões da página administrativa
// ---------------------------------------------------------------------------
async function loadPermissions() {
  const d = await api('/api/me/permissions');
  const perms = d.permissions || {};
  allowedModules = new Set(perms.allowedModules || []);
  if (!(perms.allowedPages || []).includes('settings.html')) {
    throw new Error('Sem acesso à página de configurações');
  }
  applyModuleVisibility();
}

function getSetting(settings, key, fallback = '') {
  return settings?.[key]?.value ?? fallback;
}

const askSettingsAction = window.ProjectDashboardUI?.bindActionDialog({
  dialogId: 'settingsActionDialog',
  titleId: 'settingsActionDialogTitle',
  messageId: 'settingsActionDialogMessage',
  eyebrowId: 'settingsActionDialogEyebrow',
  inputWrapId: 'settingsActionDialogInputWrap',
  inputLabelId: 'settingsActionDialogInputLabel',
  inputId: 'settingsActionDialogInput',
  cancelId: 'settingsActionDialogCancel',
  confirmId: 'settingsActionDialogConfirm',
}) || (async (options = {}) => ({ confirmed: true, value: String(options.inputValue || '') }));

function wrapTable(html) {
  return `<div class="table-shell">${html}</div>`;
}

function setCountLabel(el, count, singular, plural) {
  if (el) el.textContent = `${count} ${count === 1 ? singular : plural}`;
}

function setInlineFeedback(el, message, tone = 'neutral') {
  window.ProjectDashboardUI?.setInlineFeedback(el, message, tone);
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

function summarizeWeekdays(values) {
  const arr = (values || []).map((x) => String(x));
  if (!arr.length) return 'nenhum dia selecionado';
  return arr.map((d) => weekdayLabel(d)).join(', ');
}

function reportConfigLine(r) {
  const statuses = (r.statuses || []).join('; ') || '-';
  const priorities = (r.priorities || []).join('; ') || '-';
  const roles = (r.roles || []).join('; ') || '-';
  const days = (r.weekdays || []).map(weekdayLabel).join(', ') || '-';
  const time = r.run_time ? `${r.run_time}h` : '-';
  return `{${statuses}} {${priorities}} {${roles}} {${days}} {${time}}`;
}

function escHtml(s) {
  return String(s || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatBackupRunMessage(message) {
  const raw = String(message || '').trim();
  const concise = raw.split('| Obs:')[0].trim();
  const m = concise.match(/backup salvo em\s+(.+?)\s*\(/i);
  if (!m) return escHtml(concise || raw || 'Backup manual executado ✅');
  const backupPath = m[1].trim();
  return `Backup salvo em <strong>${escHtml(backupPath)}</strong><br><span class="small">${escHtml(concise)}</span>`;
}

function resolveRelativeBackupPath(inputPath) {
  const raw = String(inputPath || '').trim();
  if (!raw || raw.startsWith('/')) return raw;
  if (!raw.startsWith('./')) return raw;
  const base = String(lastPersistedBackupPath || '').trim();
  const marker = '/data/';
  const idx = base.indexOf(marker);
  if (idx <= 0) return raw;
  const projectRoot = base.slice(0, idx);
  return `${projectRoot}/${raw.slice(2)}`;
}

function fallbackNextRunFromForm() {
  if (!f.backupEnabled.checked) {
    return { enabled: false, weekdays: [], run_time: f.backupRunTime.value || '03:00', next_run_human: null };
  }
  const days = checkedValues(f.backupWeekdays).map((x) => Number(x)).filter((n) => Number.isInteger(n) && n >= 0 && n <= 6);
  if (!days.length) return { enabled: true, weekdays: [], run_time: f.backupRunTime.value || '03:00', next_run_human: null };

  const [hh, mm] = String(f.backupRunTime.value || '03:00').split(':');
  const hour = Number(hh || 3);
  const minute = Number(mm || 0);
  const now = new Date();

  for (let i = 0; i < 15; i++) {
    const d = new Date(now);
    d.setDate(now.getDate() + i);
    const wd = (d.getDay() + 6) % 7; // JS: Sunday=0 -> map to Monday=0
    if (!days.includes(wd)) continue;
    d.setHours(hour, minute, 0, 0);
    if (d <= now) continue;
    const fmt = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    return { enabled: true, weekdays: days.map(String), run_time: f.backupRunTime.value || '03:00', next_run_human: fmt };
  }

  return { enabled: true, weekdays: days.map(String), run_time: f.backupRunTime.value || '03:00', next_run_human: null };
}

// ---------------------------------------------------------------------------
// Atualização da próxima execução prevista de backup
// ---------------------------------------------------------------------------
async function refreshBackupNextRun() {
  if (!backupNextRun || !hasModule('settings.backup')) return;
  try {
    const d = await api('/api/admin/system/backup/next-run');
    const s = d?.schedule || {};
    if (!s.enabled) {
      backupNextRun.innerHTML = '<span class="small">Agendamento automático: <strong>desabilitado</strong></span>';
      return;
    }
    const days = summarizeWeekdays((s.weekdays || []).map((x) => String(x)));
    const when = s.next_run_human || 'indisponível';
    backupNextRun.innerHTML = `<span class="small">Próxima execução prevista: <strong>${escHtml(when)}</strong> · Dias: <strong>${escHtml(days)}</strong> · Horário: <strong>${escHtml(s.run_time || '-')}</strong></span>`;
  } catch {
    const s = fallbackNextRunFromForm();
    if (!s.enabled) {
      backupNextRun.innerHTML = '<span class="small">Agendamento automático: <strong>desabilitado</strong></span>';
      return;
    }
    const days = summarizeWeekdays((s.weekdays || []).map((x) => String(x)));
    const when = s.next_run_human || 'indisponível';
    backupNextRun.innerHTML = `<span class="small">Próxima execução prevista: <strong>${escHtml(when)}</strong> · Dias: <strong>${escHtml(days)}</strong> · Horário: <strong>${escHtml(s.run_time || '-')}</strong></span>`;
  }
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

  const checks = diagnostics?.checks || [];
  let okCount = 0;
  let failCount = 0;
  checks.forEach((c) => {
    if (c.ok) okCount += 1;
    else failCount += 1;
    lines.push(`- ${c.ok ? '✅' : '❌'} ${c.name}: ${c.detail || '-'}`);
  });
  diagOutput.value = lines.join('\n');

  if (!diagHealthSummary || !diagHealthText) return;
  diagHealthSummary.classList.remove('status-neutral', 'status-success', 'status-warning', 'status-danger');

  if (!checks.length) {
    diagHealthSummary.classList.add('status-neutral');
    diagHealthText.textContent = 'Nenhuma verificação retornada pelo diagnóstico.';
    return;
  }

  if (failCount === 0) {
    diagHealthSummary.classList.add('status-success');
    diagHealthText.textContent = `Saudável · ${okCount} verificação(ões) OK e nenhuma falha crítica.`;
    return;
  }

  if (failCount <= 2) {
    diagHealthSummary.classList.add('status-warning');
    diagHealthText.textContent = `Atenção · ${failCount} falha(s) encontrada(s). Revise os detalhes antes de operar.`;
    return;
  }

  diagHealthSummary.classList.add('status-danger');
  diagHealthText.textContent = `Crítico · ${failCount} falha(s) encontrada(s). O ambiente precisa de correção antes de depender deste fluxo.`;
}

// ---------------------------------------------------------------------------
// Carregamento consolidado das configurações persistidas
// ---------------------------------------------------------------------------
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
  f.dependencyMaxStatus.value = getSetting(s, 'workflow.dependency_max_status', 'Backlog');
  f.backupEnabled.checked = String(getSetting(s, 'backup.enabled', 'false')).toLowerCase() === 'true';
  f.backupPath.value = getSetting(s, 'backup.path', '/opt/documentdashboard/data/backups');
  lastPersistedBackupPath = f.backupPath.value || '';
  f.backupRunTime.value = getSetting(s, 'backup.run_time', '03:00');
  f.systemGitRepo.value = getSetting(s, 'system.git_repo', 'https://github.com/Vieirapa/ProjectDashboard.git');
  f.systemGitBranch.value = getSetting(s, 'system.git_branch', 'develop');
  f.deletedRetentionDays.value = getSetting(s, 'deleted.retention_days', '30');

  let days = [];
  try { days = JSON.parse(getSetting(s, 'backup.weekdays', '["0","1","2","3","4","5","6"]')); } catch { days = []; }
  const setDays = new Set((days || []).map(String));
  f.backupWeekdays.querySelectorAll('input[type="checkbox"]').forEach((el) => {
    el.checked = setDays.has(String(el.value));
  });
}

// ---------------------------------------------------------------------------
// Carregamento da lista de snapshots de backup
// ---------------------------------------------------------------------------
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

  backupRestoreList.innerHTML = wrapTable(`<table>
    <thead><tr><th></th><th>Data/Hora</th><th>DB</th><th>Docs</th></tr></thead>
    <tbody>${backupSnapshots.map((b, idx) => `<tr>
      <td><input type="radio" name="backup_stamp" value="${b.stamp}" ${idx === 0 ? 'checked' : ''}></td>
      <td>${b.when || b.stamp}</td>
      <td>${b.db_backup ? '✅' : '—'}</td>
      <td>${b.docs_backup ? '✅' : '—'}</td>
    </tr>`).join('')}</tbody>
  </table>`);
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

// ---------------------------------------------------------------------------
// Carregamento da lista de documentos apagados recuperáveis
// ---------------------------------------------------------------------------
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
      ? 'Nenhum documento apagado encontrado para os filtros informados. Ajuste ou limpe os filtros para ampliar a busca.'
      : 'Nenhum documento apagado disponível para recuperação no momento.';
    renderDeletedPager();
    return;
  }

  setCountLabel(deletedDocumentsCount, filteredRows.length, 'item', 'itens');
  deletedDocumentsList.innerHTML = wrapTable(`<table>
    <thead><tr><th>Nome</th><th>Apagado em</th><th>Apagado por</th><th>Ações</th></tr></thead>
    <tbody>${filteredRows.map((p) => `<tr>
      <td>${p.name || '-'}</td>
      <td>${p.deleted_at || '-'}</td>
      <td>${p.deleted_by || '-'}</td>
      <td>
        <button class="secondary" data-restore="${p.id}">Restaurar</button>
        <button class="danger" data-purge="${p.id}">Apagar permanentemente</button>
      </td>
    </tr>`).join('')}</tbody>
  </table>`);
  renderDeletedPager();

  deletedDocumentsList.querySelectorAll('[data-restore]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api(`/api/admin/deleted-documents/${btn.dataset.restore}/restore`, { method: 'POST' });
        setInlineFeedback(deletedPolicyFeedback, 'Documento restaurado ✅', 'success');
        await Promise.all([loadDeletedDocuments(), loadReports()]);
      } catch (err) {
        setInlineFeedback(deletedPolicyFeedback, err.message, 'danger');
      }
    };
  });

  deletedDocumentsList.querySelectorAll('[data-purge]').forEach((btn) => {
    btn.onclick = async () => {
      const answer = await askSettingsAction({ eyebrow: 'Recuperação', title: 'Apagar item permanentemente', message: 'Este item e seus arquivos associados serão removidos de forma definitiva.', confirmLabel: 'Apagar permanentemente', danger: true });
      if (!answer.confirmed) return;
      try {
        await api(`/api/admin/deleted-documents/${btn.dataset.purge}`, { method: 'DELETE' });
        setInlineFeedback(deletedPolicyFeedback, 'Apagado permanentemente.', 'success');
        await loadDeletedDocuments();
      } catch (err) {
        setInlineFeedback(deletedPolicyFeedback, err.message, 'danger');
      }
    };
  });
}

// ---------------------------------------------------------------------------
// Carregamento e renderização dos relatórios periódicos
// ---------------------------------------------------------------------------
async function loadReports() {
  const d = await api('/api/admin/reports');
  meta.statuses = d.statuses || [];
  meta.roles = d.roles || [];
  renderReportMeta();

  setCountLabel(reportsCount, (d.reports || []).length, 'relatório', 'relatórios');
  if (!d.reports?.length) {
    reportsList.textContent = 'Nenhum relatório cadastrado.';
    return;
  }

  reportsList.innerHTML = wrapTable(`<table>
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
    </tr>`).join('')}</tbody>
  </table>`);

  reportsList.querySelectorAll('[data-run]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        const d = await api(`/api/admin/reports/${btn.dataset.run}/run`, { method: 'POST' });
        reportPreview.value = d.previewText || '';
        setInlineFeedback(reportFeedback, `Relatório executado manualmente ✅ (destinatários: ${d.recipients ?? 0})`, 'success');
      } catch (e) {
        const msg = String(e.message || 'Erro');
        if (e?.data?.previewText) reportPreview.value = e.data.previewText;
        setInlineFeedback(reportFeedback, msg, 'danger');
      }
    };
  });

  reportsList.querySelectorAll('[data-del]').forEach((btn) => {
    btn.onclick = async () => {
      const answer = await askSettingsAction({ eyebrow: 'Automação', title: 'Excluir relatório periódico', message: 'O agendamento deixará de executar após esta ação.', confirmLabel: 'Excluir relatório', danger: true });
      if (!answer.confirmed) return;
      try {
        await api(`/api/admin/reports/${btn.dataset.del}`, { method: 'DELETE' });
        await loadReports();
        setInlineFeedback(reportFeedback, 'Relatório excluído.', 'success');
      } catch (e) {
        setInlineFeedback(reportFeedback, e.message, 'danger');
      }
    };
  });
}

function escHtml(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderRolesCatalog() {
  if (!rolesCatalogWrap) return;
  if (!rolesCatalogItems.length) {
    rolesCatalogWrap.innerHTML = '<div class="small">Nenhuma role cadastrada.</div>';
    return;
  }

  const rows = rolesCatalogItems.map((r) => {
    const key = String(r.role_key || '');
    const isProtected = key === 'admin' || !!r.is_system || !!r.is_superadmin;
    const status = r.active ? 'Ativa' : 'Inativa';
    const users = Number(r?.usage?.users || 0);
    const modules = Number(r?.usage?.enabled_modules || 0);

    const actionButtons = !canManageRoles
      ? '-'
      : isProtected
        ? '<span class="small">Protegida</span>'
        : [
            `<button type="button" class="secondary role-rename-btn" data-role="${escHtml(key)}">Renomear</button>`,
            `<button type="button" class="secondary role-toggle-btn" data-role="${escHtml(key)}" data-active="${r.active ? '1' : '0'}">${r.active ? 'Inativar' : 'Ativar'}</button>`,
            `<button type="button" class="danger role-delete-btn" data-role="${escHtml(key)}">Apagar</button>`,
          ].join(' ');

    return `<tr>
      <td><strong>${escHtml(key)}</strong></td>
      <td>${escHtml(r.display_name || key)}</td>
      <td>${status}</td>
      <td>${users}</td>
      <td>${modules}</td>
      <td>${actionButtons}</td>
    </tr>`;
  }).join('');

  setCountLabel(rolesCount, rolesCatalogItems.length, 'role', 'roles');
  rolesCatalogWrap.innerHTML = wrapTable(`<table>
    <thead><tr><th>Role key</th><th>Nome</th><th>Status</th><th>Usuários</th><th>Módulos ON</th><th>Ações</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`);

  rolesCatalogWrap.querySelectorAll('.role-rename-btn').forEach((btn) => {
    btn.onclick = async () => {
      const role = String(btn.dataset.role || '').trim();
      if (!role) return;
      const current = rolesCatalogItems.find((x) => String(x.role_key) === role);
      const suggested = String(current?.display_name || role);
      const answer = await askSettingsAction({ eyebrow: 'Autorização', title: `Renomear role ${role}`, message: 'Informe o novo nome de exibição para esta role.', confirmLabel: 'Salvar nome', inputLabel: 'Nome de exibição', inputValue: suggested });
      const name = String(answer.value || '').trim();
      if (!answer.confirmed || !name) return;
      try {
        await api(`/api/admin/roles/${encodeURIComponent(role)}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ display_name: String(name).trim() }),
        });
        setInlineFeedback(rolesFeedback, `Role ${role} renomeada ✅`, 'success');
        await loadRolesAdmin();
      } catch (err) {
        setInlineFeedback(rolesFeedback, err.message, 'danger');
      }
    };
  });

  rolesCatalogWrap.querySelectorAll('.role-toggle-btn').forEach((btn) => {
    btn.onclick = async () => {
      const role = String(btn.dataset.role || '').trim();
      const active = String(btn.dataset.active || '0') === '1';
      if (!role) return;
      try {
        await api(`/api/admin/roles/${encodeURIComponent(role)}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ active: !active }),
        });
        setInlineFeedback(rolesFeedback, `Role ${role} ${active ? 'inativada' : 'ativada'} ✅`, 'success');
        await loadRolesAdmin();
      } catch (err) {
        setInlineFeedback(rolesFeedback, err.message, 'danger');
      }
    };
  });

  rolesCatalogWrap.querySelectorAll('.role-delete-btn').forEach((btn) => {
    btn.onclick = async () => {
      const role = String(btn.dataset.role || '').trim();
      if (!role) return;
      const roleItem = rolesCatalogItems.find((x) => String(x.role_key) === role);
      const users = Number(roleItem?.usage?.users || 0);
      let url = `/api/admin/roles/${encodeURIComponent(role)}`;
      if (users > 0) {
        const answer = await askSettingsAction({
          eyebrow: 'Autorização',
          title: `Reatribuir usuários da role ${role}`,
          message: `A role está em uso por ${users} usuário(s). Informe a role de reatribuição.`,
          confirmLabel: 'Continuar',
          inputLabel: 'Role de reatribuição',
          inputValue: 'member',
        });
        const reassign = String(answer.value || '').trim();
        if (!answer.confirmed || !reassign) return;
      }
      const confirmDelete = await askSettingsAction({ eyebrow: 'Autorização', title: `Apagar role ${role}`, message: 'Esta ação remove a role do catálogo administrativo.', confirmLabel: 'Apagar role', danger: true });
      if (!confirmDelete.confirmed) return;
      try {
        await api(url, { method: 'DELETE' });
        setInlineFeedback(rolesFeedback, `Role ${role} apagada ✅`, 'success');
        await loadRolesAdmin();
      } catch (err) {
        setInlineFeedback(rolesFeedback, err.message, 'danger');
      }
    };
  });
}

function renderRolesMatrix() {
  if (!rolesMatrixWrap) return;
  if (!rolesModulesMeta.length || !rolesMatrix.length) {
    rolesMatrixWrap.innerHTML = '<div class="small">Matriz indisponível no momento.</div>';
    return;
  }

  const headerCols = rolesModulesMeta.map((m) => `<th title="${m.module_id}">${m.label}</th>`).join('');
  const rowsHtml = rolesMatrix.map((row) => {
    const role = row.role;
    const isImmutable = !!row.immutable;
    const cells = rolesModulesMeta.map((m) => {
      const checked = row.permissions?.[m.module_id] ? 'checked' : '';
      const disabled = isImmutable ? 'disabled' : '';
      return `<td style="text-align:center;"><input type="checkbox" data-role="${role}" data-module="${m.module_id}" ${checked} ${disabled}></td>`;
    }).join('');
    return `<tr>
      <td><strong>${role}</strong>${isImmutable ? ' <span class="small">(locked)</span>' : ''}</td>
      ${cells}
    </tr>`;
  }).join('');

  rolesMatrixWrap.innerHTML = `<table>
    <tr><th>Role</th>${headerCols}</tr>
    ${rowsHtml}
  </table>`;
}

async function loadRolesMatrix() {
  const d = await api('/api/roles/modules');
  rolesModulesMeta = d.modules || [];
  rolesMatrix = d.matrix || [];
  renderRolesMatrix();
}

// ---------------------------------------------------------------------------
// Carregamento administrativo de catálogo de roles e matriz de permissões
// ---------------------------------------------------------------------------
async function loadRolesAdmin() {
  const d = await api('/api/admin/roles');
  rolesCatalogItems = d.items || [];
  canManageRoles = !!d.can_manage;

  if (roleCreateBtn) roleCreateBtn.disabled = !canManageRoles;
  if (roleKeyInput) roleKeyInput.disabled = !canManageRoles;
  if (roleDisplayNameInput) roleDisplayNameInput.disabled = !canManageRoles;

  renderRolesCatalog();
  await loadRolesMatrix();
}

// ---------------------------------------------------------------------------
// Persistência da matriz de permissões por role
// ---------------------------------------------------------------------------
async function saveRolesMatrix() {
  if (!rolesMatrixWrap) return;
  const updatesByRole = {};
  rolesMatrixWrap.querySelectorAll('input[type="checkbox"][data-role][data-module]').forEach((el) => {
    if (el.disabled) return;
    const role = String(el.dataset.role || '').trim();
    const moduleId = String(el.dataset.module || '').trim();
    if (!role || !moduleId) return;
    if (!updatesByRole[role]) updatesByRole[role] = { permissions: {} };
    updatesByRole[role].permissions[moduleId] = !!el.checked;
  });

  const roles = Object.keys(updatesByRole);
  if (!roles.length) {
    setInlineFeedback(rolesFeedback, 'Nenhuma alteração para salvar.', 'warning');
    return;
  }

  for (const role of roles) {
    await api(`/api/roles/${encodeURIComponent(role)}/modules`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatesByRole[role]),
    });
  }
}

smtpForm.onsubmit = async (e) => {
  e.preventDefault();
  setInlineFeedback(feedback, 'Atualizando configurações de comunicação...', 'neutral');
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
    setInlineFeedback(feedback, 'Configurações salvas ✅', 'success');
  } catch (err) {
    setInlineFeedback(feedback, err.message, 'danger');
  }
};

workflowForm.onsubmit = async (e) => {
  e.preventDefault();
  setInlineFeedback(workflowFeedback, 'Salvando comportamento do fluxo...', 'neutral');
  try {
    await api('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        'workflow.default_due_days': f.defaultDueDays.value,
        'workflow.dependency_max_status': f.dependencyMaxStatus.value,
      }),
    });
    await loadSettings();
    setInlineFeedback(workflowFeedback, `Comportamento salvo ✅ (máximo com dependências pendentes: ${f.dependencyMaxStatus.value})`, 'success');
  } catch (err) {
    setInlineFeedback(workflowFeedback, err.message, 'danger');
  }
};

backupForm.onsubmit = async (e) => {
  e.preventDefault();
  setInlineFeedback(backupFeedback, 'Processando ação de backup...', 'neutral');

  const submitBtn = backupForm.querySelector('button[type="submit"]');
  if (submitBtn?.disabled) return;

  const selectedDays = checkedValues(f.backupWeekdays);
  if (f.backupEnabled.checked && !selectedDays.length) {
    setInlineFeedback(backupFeedback, 'Selecione ao menos um dia da semana para backup automático.', 'warning');
    return;
  }

  try {
    if (submitBtn) submitBtn.disabled = true;

    const pathToSave = resolveRelativeBackupPath(f.backupPath.value || '');
    const resp = await api('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        'backup.enabled': f.backupEnabled.checked ? 'true' : 'false',
        'backup.path': pathToSave,
        'backup.weekdays': JSON.stringify(selectedDays),
        'backup.run_time': f.backupRunTime.value,
      }),
    });

    // Source of truth after save: reload from backend and build confirmation from reloaded UI state.
    await loadSettings();
    await refreshBackupNextRun();
    const persistedDays = checkedValues(f.backupWeekdays).map((x) => String(x));

    let suffix = '';
    if (Array.isArray(resp?.mismatch) && resp.mismatch.length) {
      suffix = `<br><span class="small" style="color:#b45309;">⚠️ Divergência detectada em: ${escHtml(resp.mismatch.map((m) => m.key).join(', '))}</span>`;
    }

    backupFeedback.innerHTML = `Política de backup salva ✅<br><span class="small">Caminho persistido: <strong>${escHtml(f.backupPath.value)}</strong> · Automático: <strong>${f.backupEnabled.checked ? 'TRUE' : 'FALSE'}</strong> · Horário: <strong>${escHtml(f.backupRunTime.value || '-')}</strong> · Dias: <strong>${escHtml(summarizeWeekdays(persistedDays))}</strong></span>${suffix}`;
  } catch (err) {
    setInlineFeedback(backupFeedback, err.message, 'danger');
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
};

diagForm.onsubmit = async (e) => {
  e.preventDefault();
  setInlineFeedback(diagFeedback, 'Executando diagnóstico do sistema...', 'neutral');
  try {
    await api('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        'system.git_repo': f.systemGitRepo.value,
        'system.git_branch': f.systemGitBranch.value,
      }),
    });
    setInlineFeedback(diagFeedback, `Fonte de versão salva ✅ Repositório: ${f.systemGitRepo.value || '-'} · Branch: ${f.systemGitBranch.value || '-'}`, 'danger');
  } catch (err) {
    setInlineFeedback(diagFeedback, err.message, 'danger');
  }
};

deletedPolicyForm.onsubmit = async (e) => {
  e.preventDefault();
  setInlineFeedback(deletedPolicyFeedback, 'Atualizando política e lista de recuperação...', 'neutral');
  try {
    await api('/api/admin/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        'deleted.retention_days': String(f.deletedRetentionDays.value || '30'),
      }),
    });
    setInlineFeedback(deletedPolicyFeedback, 'Retenção de documentos apagados salva ✅', 'success');
  } catch (err) {
    setInlineFeedback(deletedPolicyFeedback, err.message, 'danger');
  }
};

reportForm.onsubmit = async (e) => {
  e.preventDefault();
  setInlineFeedback(reportFeedback, 'Processando relatório...', 'neutral');
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
    setInlineFeedback(reportFeedback, 'Relatório periódico criado ✅', 'success');
    reportForm.reset();
    await loadReports();
  } catch (err) {
    setInlineFeedback(reportFeedback, err.message, 'danger');
  }
};

testSmtpBtn.onclick = async () => {
  setInlineFeedback(feedback, 'Atualizando configurações de comunicação...', 'neutral');
  try {
    const to = (f.smtpTestTo.value || '').trim();
    if (!to) {
      setInlineFeedback(feedback, 'Informe um e-mail para teste SMTP.', 'danger');
      return;
    }
    await api('/api/admin/settings/test-smtp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to }),
    });
    setInlineFeedback(feedback, `Teste SMTP enviado para ${to} ✅`, 'success');
  } catch (err) {
    setInlineFeedback(feedback, err.message, 'danger');
  }
};

testBackupPathBtn.onclick = async () => {
  setInlineFeedback(backupFeedback, 'Processando ação de backup...', 'neutral');
  try {
    const d = await api('/api/admin/system/backup/test-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: f.backupPath.value || '' }),
    });
    setInlineFeedback(backupFeedback, d.message || 'Caminho de backup validado ✅ Pronto para uso.', 'success');
  } catch (err) {
    if (err?.status === 404) {
      setInlineFeedback(backupFeedback, 'Este servidor ainda não tem o endpoint de teste de permissões. Atualize/reinicie a instância com a versão mais recente do ProjectDashboard e tente novamente.', 'danger');
      return;
    }
    if (String(err?.message || '').includes('Permission') || String(err?.message || '').includes('Permissão')) {
      const p = (f.backupPath.value || '').trim() || '/var/backups/projectdashboard';
      setInlineFeedback(backupFeedback, `${err.message} | Sugestão: sudo mkdir -p ${p} && sudo chown -R <usuario_servico>:<grupo_servico> ${p} && sudo chmod -R 775 ${p}`, 'danger');
      return;
    }
    setInlineFeedback(backupFeedback, err?.message || 'Falha ao testar permissões do caminho de backup.', 'danger');
  }
};

runBackupNowBtn.onclick = async () => {
  setInlineFeedback(backupFeedback, 'Processando ação de backup...', 'neutral');
  try {
    const d = await api('/api/admin/system/backup/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: f.backupPath.value || '' }),
    });
    backupFeedback.innerHTML = formatBackupRunMessage(d.message || 'Backup manual executado ✅');
    await loadBackupSnapshots();
  } catch (err) {
    setInlineFeedback(backupFeedback, err.message, 'danger');
  }
};

refreshBackupListBtn.onclick = async () => {
  setInlineFeedback(backupFeedback, 'Processando ação de backup...', 'neutral');
  try {
    await loadBackupSnapshots();
    setInlineFeedback(backupFeedback, 'Lista de backups atualizada.', 'success');
  } catch (err) {
    setInlineFeedback(backupFeedback, err.message, 'danger');
  }
};

restoreBackupBtn.onclick = async () => {
  setInlineFeedback(backupFeedback, 'Processando ação de backup...', 'neutral');
  const stamp = getSelectedBackupStamp();
  if (!stamp) {
    setInlineFeedback(backupFeedback, 'Selecione um backup na lista.', 'danger');
    return;
  }
  const restoreAnswer = await askSettingsAction({
    eyebrow: 'Resiliência',
    title: `Restaurar snapshot ${stamp}`,
    message: 'Isso pode sobrescrever dados atuais. Digite RESTAURAR para confirmar.',
    confirmLabel: 'Restaurar backup',
    inputLabel: 'Digite RESTAURAR',
    danger: true,
  });
  const confirmText = String(restoreAnswer.value || '');
  if (!restoreAnswer.confirmed || String(confirmText).trim().toUpperCase() !== 'RESTAURAR') {
    setInlineFeedback(backupFeedback, 'Restauração cancelada (confirmação não informada).', 'danger');
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
    setInlineFeedback(backupFeedback, d.message || `Restore do backup ${stamp} concluído ✅ Revise a aplicação e confirme o estado esperado.`, 'success');
  } catch (err) {
    setInlineFeedback(backupFeedback, err.message, 'danger');
  }
};

runDiagBtn.onclick = async () => {
  setInlineFeedback(diagFeedback, 'Executando diagnóstico do sistema...', 'neutral');
  try {
    const d = await api('/api/admin/system/diagnostics');
    renderDiagnostics(d.diagnostics || {});
    setInlineFeedback(diagFeedback, 'Diagnóstico executado ✅ Revise o resumo de saúde e os detalhes abaixo.', 'success');
  } catch (err) {
    setInlineFeedback(diagFeedback, err.message, 'danger');
  }
};

refreshDeletedBtn.onclick = async () => {
  setInlineFeedback(deletedPolicyFeedback, 'Atualizando política e lista de recuperação...', 'neutral');
  try {
    await loadDeletedDocuments();
    setInlineFeedback(deletedPolicyFeedback, 'Lista de documentos apagados atualizada.', 'success');
  } catch (err) {
    setInlineFeedback(deletedPolicyFeedback, err.message, 'danger');
  }
};

applyDeletedFiltersBtn.onclick = async () => {
  setInlineFeedback(deletedPolicyFeedback, 'Atualizando política e lista de recuperação...', 'neutral');
  deletedFilters = {
    q: f.deletedFilterQ.value,
    deleted_by: f.deletedFilterBy.value,
    deleted_from: f.deletedFilterFrom.value,
    deleted_to: f.deletedFilterTo.value,
  };
  deletedPager.page = 1;
  try {
    await loadDeletedDocuments();
    setInlineFeedback(deletedPolicyFeedback, 'Filtros aplicados.', 'success');
  } catch (err) {
    setInlineFeedback(deletedPolicyFeedback, err.message, 'danger');
  }
};

clearDeletedFiltersBtn.onclick = async () => {
  setInlineFeedback(deletedPolicyFeedback, 'Atualizando política e lista de recuperação...', 'neutral');
  deletedFilters = { q: '', deleted_by: '', deleted_from: '', deleted_to: '' };
  deletedPager.page = 1;
  f.deletedFilterQ.value = '';
  f.deletedFilterBy.value = '';
  f.deletedFilterFrom.value = '';
  f.deletedFilterTo.value = '';
  try {
    await loadDeletedDocuments();
    setInlineFeedback(deletedPolicyFeedback, 'Filtros limpos.', 'success');
  } catch (err) {
    setInlineFeedback(deletedPolicyFeedback, err.message, 'danger');
  }
};

if (rolesRefreshBtn) {
  rolesRefreshBtn.onclick = async () => {
    setInlineFeedback(rolesFeedback, 'Processando alterações de roles...', 'neutral');
    try {
      await loadRolesAdmin();
      setInlineFeedback(rolesFeedback, 'Catálogo e matriz atualizados.', 'success');
    } catch (err) {
      setInlineFeedback(rolesFeedback, err.message, 'danger');
    }
  };
}

if (rolesSaveBtn) {
  rolesSaveBtn.onclick = async () => {
    setInlineFeedback(rolesFeedback, 'Processando alterações de roles...', 'neutral');
    try {
      await saveRolesMatrix();
      await loadRolesAdmin();
      setInlineFeedback(rolesFeedback, 'Permissões salvas ✅', 'success');
    } catch (err) {
      setInlineFeedback(rolesFeedback, err.message, 'danger');
    }
  };
}

if (rolesSyncCatalogBtn) {
  rolesSyncCatalogBtn.onclick = async () => {
    setInlineFeedback(rolesFeedback, 'Processando alterações de roles...', 'neutral');
    try {
      await api('/api/modules/catalog/sync', { method: 'POST' });
      await loadRolesAdmin();
      setInlineFeedback(rolesFeedback, 'Catálogo sincronizado ✅', 'success');
    } catch (err) {
      setInlineFeedback(rolesFeedback, err.message, 'danger');
    }
  };
}

if (roleCreateForm) {
  roleCreateForm.onsubmit = async (e) => {
    e.preventDefault();
    setInlineFeedback(rolesFeedback, 'Processando alterações de roles...', 'neutral');
    if (!canManageRoles) {
      setInlineFeedback(rolesFeedback, 'Apenas admin pode criar roles.', 'warning');
      return;
    }

    const roleKey = String(roleKeyInput?.value || '').trim().toLowerCase();
    const displayName = String(roleDisplayNameInput?.value || '').trim();
    if (!roleKey || !displayName) {
      setInlineFeedback(rolesFeedback, 'Preencha role key e nome de exibição.', 'warning');
      return;
    }

    try {
      await api('/api/admin/roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_key: roleKey, display_name: displayName }),
      });
      if (roleKeyInput) roleKeyInput.value = '';
      if (roleDisplayNameInput) roleDisplayNameInput.value = '';
      setInlineFeedback(rolesFeedback, `Role ${roleKey} criada ✅`, 'success');
      await loadRolesAdmin();
    } catch (err) {
      setInlineFeedback(rolesFeedback, err.message, 'danger');
    }
  };
}

logoutBtn.onclick = async () => {
  await api('/api/logout', { method: 'POST' });
  location.href = '/login.html';
};

(async () => {
  try {
    await loadPermissions();
  } catch {
    location.href = '/';
    return;
  }

  const loads = [];
  if (hasModule('settings.smtp') || hasModule('settings.system_behavior') || hasModule('settings.backup') || hasModule('settings.system_diagnostics')) {
    loads.push(loadSettings());
  }
  if (hasModule('settings.periodic_reports')) loads.push(loadReports());
  if (hasModule('settings.recoverable_documents')) loads.push(loadDeletedDocuments());
  if (hasModule('settings.roles_control')) loads.push(loadRolesAdmin());

  try {
    if (loads.length) await Promise.all(loads);
  } catch (e) {
    setInlineFeedback(backupFeedback, e?.message || 'Falha ao carregar configurações iniciais.', 'danger');
  }

  if (hasModule('settings.backup_restore') || hasModule('settings.backup')) {
    try {
      await loadBackupSnapshots();
    } catch (e) {
      backupRestoreList.textContent = 'Não foi possível carregar a lista de backups nesta instância (endpoint indisponível ou serviço desatualizado).';
    }
  }

  if (hasModule('settings.backup')) {
    await refreshBackupNextRun();
  }

  if (hasModule('settings.system_diagnostics')) {
    try {
      const d = await api('/api/admin/system/diagnostics');
      renderDiagnostics(d.diagnostics || {});
    } catch (_) {
      // diagnóstico pode falhar sem bloquear tela
    }
  }
})();
