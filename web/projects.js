/*
 * projects.js
 * ===========
 *
 * Responsável pela tela de gestão de projetos.
 *
 * Papel deste arquivo
 * -------------------
 * - Carregar o catálogo de projetos.
 * - Permitir criação, edição, clonagem e exclusão de projetos.
 * - Gerenciar roles com acesso ao projeto.
 * - Exibir os cards vinculados ao projeto selecionado.
 *
 * Como deve ser tratado no restante da aplicação
 * ----------------------------------------------
 * - Deve permanecer centrado no ciclo da tela de projetos.
 * - Regras estruturais de negócio devem continuar no backend.
 * - Este arquivo coordena UI, estado local e chamadas de API.
 */

const logoutBtn = document.getElementById('logoutBtn');

const projectId = document.getElementById('projectId');
const projectName = document.getElementById('projectName');
const isTemplate = document.getElementById('isTemplate');
const startDate = document.getElementById('startDate');
const notes = document.getElementById('notes');
const allowedRolesBox = document.getElementById('allowedRolesBox');
const feedback = document.getElementById('feedback');
const projectsList = document.getElementById('projectsList');
const projectCardsList = document.getElementById('projectCardsList');
const templateFilter = document.getElementById('templateFilter');
const projectSearchInput = document.getElementById('projectSearchInput');
const projectCardsSearchInput = document.getElementById('projectCardsSearchInput');
const projectCardsCount = document.getElementById('projectCardsCount');
const projectsCount = document.getElementById('projectsCount');
const templatesCount = document.getElementById('templatesCount');

const newBtn = document.getElementById('newBtn');
const saveBtn = document.getElementById('saveBtn');
const cloneBtn = document.getElementById('cloneBtn');
const deleteBtn = document.getElementById('deleteBtn');

let me = null;
let projects = [];
let selectedProjectId = null;
let allowedModules = new Set();
let projectRolesCatalog = [];
let currentProjectCards = [];

function setFeedback(message, tone = 'neutral') {
  if (!feedback) return;
  const safeTone = ['neutral', 'success', 'warning', 'danger'].includes(tone) ? tone : 'neutral';
  feedback.className = `settings-inline-feedback status-${safeTone} projects-feedback`;
  feedback.innerHTML = `<strong>Status</strong><span>${esc(message || 'Sem atualizações no momento.')}</span>`;
}

const projectsActionDialog = document.getElementById('projectsActionDialog');
const projectsActionDialogTitle = document.getElementById('projectsActionDialogTitle');
const projectsActionDialogMessage = document.getElementById('projectsActionDialogMessage');
const projectsActionDialogEyebrow = document.getElementById('projectsActionDialogEyebrow');
const projectsActionDialogInputWrap = document.getElementById('projectsActionDialogInputWrap');
const projectsActionDialogInputLabel = document.getElementById('projectsActionDialogInputLabel');
const projectsActionDialogInput = document.getElementById('projectsActionDialogInput');
const projectsActionDialogCancel = document.getElementById('projectsActionDialogCancel');
const projectsActionDialogConfirm = document.getElementById('projectsActionDialogConfirm');

function setCardsCountLabel(count) {
  if (projectCardsCount) projectCardsCount.textContent = `${count} ${count === 1 ? 'card' : 'cards'}`;
}

function wrapTable(html) {
  return `<div class="table-shell">${html}</div>`;
}

function getProjectSearchTerm() {
  return String(projectSearchInput?.value || '').trim().toLowerCase();
}

function getProjectCardsSearchTerm() {
  return String(projectCardsSearchInput?.value || '').trim().toLowerCase();
}

function askProjectAction({ title, message, confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', eyebrow = 'Confirmação', inputLabel = '', inputValue = '', inputType = 'text', danger = false }) {
  if (!projectsActionDialog) return Promise.resolve({ confirmed: true, value: String(inputValue || '') });
  projectsActionDialogTitle.textContent = title || 'Confirmar ação';
  projectsActionDialogMessage.innerHTML = message || 'Revise a ação antes de continuar.';
  projectsActionDialogEyebrow.textContent = eyebrow || 'Confirmação';
  projectsActionDialogCancel.textContent = cancelLabel;
  projectsActionDialogConfirm.textContent = confirmLabel;
  projectsActionDialogConfirm.className = danger ? 'danger' : '';
  const needsInput = !!String(inputLabel || '').trim();
  projectsActionDialogInputWrap.classList.toggle('hidden', !needsInput);
  projectsActionDialogInputLabel.textContent = inputLabel || 'Valor';
  projectsActionDialogInput.type = inputType || 'text';
  projectsActionDialogInput.value = String(inputValue || '');
  return new Promise((resolve) => {
    const cleanup = (payload) => {
      projectsActionDialogConfirm.onclick = null;
      projectsActionDialogCancel.onclick = null;
      projectsActionDialog.oncancel = null;
      if (projectsActionDialog.open) projectsActionDialog.close();
      resolve(payload);
    };
    projectsActionDialogConfirm.onclick = () => cleanup({ confirmed: true, value: projectsActionDialogInput.value });
    projectsActionDialogCancel.onclick = () => cleanup({ confirmed: false, value: projectsActionDialogInput.value });
    projectsActionDialog.oncancel = () => cleanup({ confirmed: false, value: projectsActionDialogInput.value });
    projectsActionDialog.showModal();
    if (needsInput) projectsActionDialogInput.focus();
    else projectsActionDialogConfirm.focus();
  });
}

function renderProjectCardsTable(docs) {
  const term = getProjectCardsSearchTerm();
  const filteredDocs = (docs || []).filter((doc) => {
    if (!term) return true;
    const hay = `${doc.name || ''} ${doc.slug || ''} ${doc.owner || ''} ${doc.status || ''}`.toLowerCase();
    return hay.includes(term);
  });
  setCardsCountLabel(filteredDocs.length);
  if (!filteredDocs.length) {
    projectCardsList.innerHTML = '<div class="empty-state">Nenhum card encontrado para o projeto e filtros atuais.</div>';
    return;
  }

  projectCardsList.innerHTML = wrapTable(`<table>
    <thead><tr><th>Nome</th><th>Criado em</th><th>Status</th><th>Responsável</th><th>Ações</th></tr></thead>
    <tbody>
      ${filteredDocs.map(doc => `
        <tr data-slug="${esc(doc.slug)}">
          <td>${esc(doc.name)}</td>
          <td>${esc(fmtDate(doc.openedAt || doc.updatedAt))}</td>
          <td>${esc(doc.status || '-')}</td>
          <td>${esc(doc.owner || '-')}</td>
          <td>${hasModule('projects.create_edit') ? `<button type="button" class="danger card-delete-btn" data-slug="${esc(doc.slug)}">Excluir</button>` : '-'}</td>
        </tr>
      `).join('')}
    </tbody>
  </table>`);

  projectCardsList.querySelectorAll('.card-delete-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const slug = btn.dataset.slug;
      if (!slug) return;
      const answer = await askProjectAction({
        eyebrow: 'Cards vinculados',
        title: 'Excluir card do projeto',
        message: `O card <strong>${esc(slug)}</strong> será removido deste projeto.`,
        confirmLabel: 'Excluir card',
        danger: true,
      });
      if (!answer.confirmed) return;
      try {
        await api(`/api/documents/${encodeURIComponent(slug)}?project_id=${encodeURIComponent(String(selectedProjectId))}`, { method: 'DELETE' });
        setFeedback(`Card ${slug} apagado com sucesso.`, 'success');
        await loadCardsForSelectedProject();
      } catch (e) {
        setFeedback(e.message, 'danger');
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Normalização de catálogo de roles para uso na UI
// ---------------------------------------------------------------------------
function normalizeRoleCatalog(items) {
  const out = [];
  const seen = new Set();
  (Array.isArray(items) ? items : []).forEach((item) => {
    const roleKey = String(item?.role_key ?? item?.role ?? item ?? '').trim().toLowerCase();
    if (!roleKey || roleKey === 'admin' || seen.has(roleKey)) return;
    seen.add(roleKey);
    const displayName = String(item?.display_name ?? item?.displayName ?? roleKey).trim() || roleKey;
    out.push({ role_key: roleKey, display_name: displayName });
  });
  return out;
}

// ---------------------------------------------------------------------------
// Helper HTTP JSON da tela de projetos
// ---------------------------------------------------------------------------
async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Erro na API');
  return data;
}

function esc(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function fmtDate(v) {
  const raw = String(v || '').trim();
  if (!raw) return '-';
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleString('pt-BR');
}

// ---------------------------------------------------------------------------
// Renderização dos checkboxes de roles com acesso ao projeto
// ---------------------------------------------------------------------------
function renderAllowedRolesChecks(roles) {
  projectRolesCatalog = normalizeRoleCatalog(roles);

  if (!allowedRolesBox) return;
  if (!projectRolesCatalog.length) {
    allowedRolesBox.innerHTML = '<span class="small">Nenhuma role disponível.</span>';
    return;
  }

  allowedRolesBox.innerHTML = projectRolesCatalog.map((role) => (
    `<label class="inline-check"><input type="checkbox" class="allowed-role" value="${esc(role.role_key)}" /> ${esc(role.display_name)} <span class="small">(${esc(role.role_key)})</span></label>`
  )).join('');
}

// ---------------------------------------------------------------------------
// Carregamento do catálogo dinâmico de roles para a tela
// ---------------------------------------------------------------------------
async function loadProjectRolesCatalog() {
  try {
    const d = await api('/api/admin/roles');
    const activeItems = (d?.items || []).filter((r) => !!r?.active && String(r?.role_key || '').toLowerCase() !== 'admin');
    renderAllowedRolesChecks(activeItems.length ? activeItems : (d?.roles || []));
    return;
  } catch (errPrimary) {
    // Compat fallback para versões que ainda não expõem /api/admin/roles
    try {
      const dUsers = await api('/api/admin/users');
      if (Array.isArray(dUsers?.roles) && dUsers.roles.length) {
        renderAllowedRolesChecks(dUsers.roles);
        return;
      }
    } catch (errSecondary) {
      console.warn('Falha ao carregar catálogo dinâmico de roles:', errPrimary, errSecondary);
    }

    // fallback seguro final para não bloquear a tela
    renderAllowedRolesChecks([]);
  }
}

function setAllowedRolesChecks(csvValue) {
  const selectedRoles = Array.from(new Set(
    String(csvValue || '')
      .split(',')
      .map((x) => x.trim().toLowerCase())
      .filter(Boolean),
  ));

  const selectedSet = new Set(selectedRoles);
  const checks = allowedRolesBox?.querySelectorAll('.allowed-role') || [];
  checks.forEach((c) => {
    c.checked = selectedSet.has(String(c.value || '').toLowerCase());
  });
}

function getAllowedRolesFromChecks() {
  const checks = allowedRolesBox?.querySelectorAll('.allowed-role:checked') || [];
  const vals = Array.from(checks).map((c) => String(c.value || '').trim().toLowerCase()).filter(Boolean);
  return vals.join(',');
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

async function loadMe() {
  const [d, p] = await Promise.all([api('/api/me'), api('/api/me/permissions')]);
  me = d.user;
  allowedModules = new Set(p?.permissions?.allowedModules || []);

  if (!(p?.permissions?.allowedPages || []).includes('projects.html')) {
    alert('Sem acesso à página de projetos.');
    window.location.href = '/';
    return;
  }

  applyModuleVisibility();
}

// ---------------------------------------------------------------------------
// Preenchimento do formulário principal da tela
// ---------------------------------------------------------------------------
function setForm(p = null) {
  selectedProjectId = p?.project_id ? Number(p.project_id) : null;
  projectId.value = p?.project_id || '';
  projectName.value = p?.project_name || '';
  startDate.value = p?.start_date?.slice(0, 10) || '';
  isTemplate.checked = Boolean(p?.is_template);
  notes.value = p?.notes || '';
  setAllowedRolesChecks(p?.allowed_roles || '');

  const canEditProjectModule = hasModule('projects.create_edit');
  [projectName, startDate, notes, isTemplate].forEach((el) => {
    if (el) el.disabled = !canEditProjectModule;
  });
  (allowedRolesBox?.querySelectorAll('input') || []).forEach((el) => { el.disabled = !canEditProjectModule; });
  newBtn.disabled = !canEditProjectModule;
  saveBtn.disabled = !canEditProjectModule;

  deleteBtn.disabled = !p || !canEditProjectModule;
  if (cloneBtn) cloneBtn.disabled = !(p && p.is_template && canEditProjectModule);

  if (selectedProjectId) {
    const u = new URL(window.location.href);
    u.searchParams.set('project_id', String(selectedProjectId));
    window.history.replaceState({}, '', `${u.pathname}?${u.searchParams.toString()}`);
  }

  loadCardsForSelectedProject();
}

function filteredProjects() {
  const mode = String(templateFilter?.value || 'all');
  const search = getProjectSearchTerm();
  return projects.filter((p) => {
    const modeOk = mode === 'template' ? !!p.is_template : mode === 'non-template' ? !p.is_template : true;
    if (!modeOk) return false;
    if (!search) return true;
    const hay = `${p.project_id || ''} ${p.project_name || ''} ${p.allowed_roles || ''}`.toLowerCase();
    return hay.includes(search);
  });
}

// ---------------------------------------------------------------------------
// Renderização da tabela/lista de projetos
// ---------------------------------------------------------------------------
function renderList() {
  const shown = filteredProjects();
  if (projectsCount) projectsCount.textContent = String(shown.length);
  if (templatesCount) templatesCount.textContent = String(projects.filter((p) => !!p.is_template).length);
  if (!shown.length) {
    projectsList.innerHTML = '<div class="empty-state">Nenhum projeto encontrado neste filtro. Ajuste o recorte ou crie um novo projeto para começar.</div>';
    return;
  }
  projectsList.innerHTML = wrapTable(`<table>
    <thead><tr><th class="template-flag-col"></th><th>ID</th><th>Nome</th><th>Início</th><th>Roles</th></tr></thead>
    <tbody>${shown.map(p => `<tr data-id="${p.project_id}"><td class="template-flag-col">${p.is_template ? '<span class="template-chip">Template</span>' : ''}</td><td>${p.project_id}</td><td>${esc(p.project_name)}</td><td>${esc((p.start_date || '').slice(0,10))}</td><td>${esc(p.allowed_roles || '')}</td></tr>`).join('')}</tbody>
  </table>`);
  projectsList.querySelectorAll('tr[data-id]').forEach(tr => {
    tr.style.cursor = 'pointer';
    tr.onclick = () => {
      const id = Number(tr.dataset.id);
      const found = projects.find(x => Number(x.project_id) === id);
      setForm(found || null);
    };
  });
}

// ---------------------------------------------------------------------------
// Carregamento dos cards vinculados ao projeto selecionado
// ---------------------------------------------------------------------------
async function loadCardsForSelectedProject() {
  if (!selectedProjectId) {
    setCardsCountLabel(0);
    projectCardsList.innerHTML = '<div class="empty-state">Selecione um projeto no catálogo para revisar os cards vinculados, responsáveis e últimas atualizações.</div>';
    return;
  }
  try {
    projectCardsList.innerHTML = '<div class="loading-state">Carregando cards do projeto selecionado...</div>';
    const d = await api(`/api/documents?project_id=${encodeURIComponent(String(selectedProjectId))}`);
    currentProjectCards = d.documents || [];
    if (!currentProjectCards.length) {
      setCardsCountLabel(0);
      projectCardsList.innerHTML = '<div class="empty-state">Este projeto ainda não possui cards vinculados. Crie itens no Kanban para começar o acompanhamento operacional.</div>';
      return;
    }

    renderProjectCardsTable(currentProjectCards);
  } catch (e) {
    projectCardsList.innerHTML = `<div class="error-state">Falha ao carregar cards do projeto. ${esc(e.message || e)}</div>`;
  }
}

// ---------------------------------------------------------------------------
// Refresh geral da tela de projetos
// ---------------------------------------------------------------------------
async function refresh(preferredId = null, fallbackToLast = false) {
  const canManageProjects = hasModule('projects.create_edit');
  const d = canManageProjects ? await api('/api/admin/projects') : await api('/api/projects-registry');
  projects = d.projects || [];
  renderList();

  const qsId = Number(new URLSearchParams(window.location.search).get('project_id'));
  const targetId = Number(preferredId || selectedProjectId || (Number.isFinite(qsId) && qsId > 0 ? qsId : 0));
  const found = projects.find((p) => Number(p.project_id) === Number(targetId));
  if (found) {
    setForm(found);
  } else if (fallbackToLast && projects.length) {
    // Fallback for environments still running an older backend response shape
    // (e.g., POST without project_id in payload): keep the newly created item loaded.
    setForm(projects[projects.length - 1]);
  } else {
    setForm(null);
  }
}

newBtn.onclick = () => {
  if (!hasModule('projects.create_edit')) return;
  setFeedback('Formulário limpo. Você pode cadastrar um novo projeto ou revisar outro item do catálogo.', 'neutral');
  setForm(null);
};

saveBtn.onclick = async () => {
  if (!hasModule('projects.create_edit')) return;
  setFeedback('Salvando dados do projeto...', 'neutral');
  try {
    const payload = {
      project_name: projectName.value,
      is_template: isTemplate.checked,
      start_date: startDate.value,
      notes: notes.value,
      allowed_roles: getAllowedRolesFromChecks(),
    };
    const preserveId = Number(projectId.value || selectedProjectId || 0) || null;
    if (projectId.value) {
      await api(`/api/admin/projects/${projectId.value}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setFeedback('Projeto atualizado com sucesso.', 'success');
    } else {
      const created = await api('/api/admin/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (Number(created?.project_id) > 0) {
        selectedProjectId = Number(created.project_id);
      }
      setFeedback('Projeto criado com sucesso e já selecionado no catálogo.', 'success');
    }
    await refresh(Number(projectId.value || selectedProjectId || preserveId || 0) || null, !projectId.value);
  } catch (e) {
    setFeedback(e.message, 'danger');
  }
};

deleteBtn.onclick = async () => {
  if (!hasModule('projects.create_edit')) return;
  if (!projectId.value) return;

  const pid = Number(projectId.value || 0);
  const pname = String(projectName.value || '').trim() || `ID ${pid}`;

  try {
    const docsData = await api(`/api/documents?project_id=${encodeURIComponent(String(pid))}`);
    const cardCount = Array.isArray(docsData?.documents) ? docsData.documents.length : 0;

    const msg = cardCount > 0
      ? `ATENÇÃO: o projeto "${pname}" possui ${cardCount} card(s)/documento(s) anexado(s).\n\nSe você confirmar, todos esses cards serão excluídos permanentemente junto com o projeto, e não poderão ser restaurados.\n\nDeseja continuar?`
      : `Apagar o projeto "${pname}"?`;

    const answer = await askProjectAction({ eyebrow: 'Projeto', title: 'Apagar projeto', message: msg.replaceAll('\n', '<br>'), confirmLabel: 'Apagar projeto', danger: true });
    if (!answer.confirmed) return;

    setFeedback('Apagando projeto selecionado...', 'warning');
    const del = await api(`/api/admin/projects/${pid}`, { method: 'DELETE' });
    const deletedCards = Number(del?.deleted_cards || 0);
    setFeedback(deletedCards > 0
      ? `Projeto apagado com sucesso. ${deletedCards} card(s) também foram removidos.`
      : 'Projeto apagado com sucesso.', 'success');
    setForm(null);
    await refresh();
  } catch (e) {
    setFeedback(e.message, 'danger');
  }
};

if (cloneBtn) {
  cloneBtn.onclick = async () => {
    const pid = Number(projectId.value || selectedProjectId || 0);
    if (!pid) return;
    const selected = projects.find((p) => Number(p.project_id) === pid);
    if (!selected?.is_template) {
      setFeedback('Selecione um projeto template para clonar.', 'warning');
      return;
    }
    const suggested = `${selected.project_name} - Cópia`;
    const answer = await askProjectAction({ eyebrow: 'Template', title: 'Criar projeto a partir do template', message: 'Informe o nome do novo projeto criado a partir do template selecionado.', confirmLabel: 'Criar projeto', inputLabel: 'Nome do novo projeto', inputValue: suggested });
    const newName = String(answer.value || '').trim();
    if (!answer.confirmed || !newName) return;

    setFeedback('Criando novo projeto a partir do template...', 'neutral');
    try {
      const created = await api(`/api/admin/projects/${pid}/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_name: String(newName).trim() }),
      });
      const newProjectId = Number(created?.project_id || 0) || null;
      setFeedback('Projeto criado a partir do template e carregado para revisão.', 'success');
      await refresh(newProjectId, true);
    } catch (e) {
      setFeedback(e.message, 'danger');
    }
  };
}

if (templateFilter) {
  templateFilter.onchange = () => renderList();
}
if (projectSearchInput) projectSearchInput.addEventListener('input', () => renderList());
if (projectCardsSearchInput) projectCardsSearchInput.addEventListener('input', () => renderProjectCardsTable(currentProjectCards));

logoutBtn.onclick = async () => {
  await api('/api/logout', { method: 'POST' });
  window.location.href = '/login.html';
};

(async () => {
  try {
    await loadMe();
    await loadProjectRolesCatalog();
    setFeedback('Tela pronta. Selecione um projeto para revisar ou use o formulário para cadastrar um novo.', 'neutral');
    await refresh();
  } catch {
    window.location.href = '/login.html';
  }
})();
