/*
 * edit.js
 * =======
 *
 * Responsável pela tela de edição detalhada de um documento/card.
 *
 * Papel deste arquivo
 * -------------------
 * - Carregar o documento individual.
 * - Permitir edição de campos principais.
 * - Gerenciar dependências.
 * - Gerenciar upload/anexo e histórico de versões.
 * - Gerenciar notas de revisão e resolução.
 *
 * Como deve ser tratado no restante da aplicação
 * ----------------------------------------------
 * - Deve funcionar como coordenador da tela de detalhe.
 * - Regras de negócio continuam no backend.
 * - Este arquivo integra componentes visuais, estado local e APIs.
 */

const params = new URLSearchParams(location.search);
const slug = params.get('slug');

// ---------------------------------------------------------------------------
// Projeto corrente resolvido a partir da query string
// ---------------------------------------------------------------------------
function currentProjectId() {
  const pid = Number(new URLSearchParams(location.search).get('project_id'));
  return Number.isFinite(pid) && pid > 0 ? pid : 1;
}

function withProjectId(url) {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}project_id=${encodeURIComponent(String(currentProjectId()))}`;
}
const backBtn = document.getElementById('backBtn');
const backLinkBtn = document.getElementById('backLinkBtn');
const logoutBtn = document.getElementById('logoutBtn');
const deleteBtn = document.getElementById('deleteBtn');
const feedback = document.getElementById('feedback');
const formEl = document.getElementById('editForm');
const saveBtn = document.getElementById('saveBtn');
const detailNavStatus = document.getElementById('detailNavStatus');
const saveStateBadge = document.getElementById('saveStateBadge');
const uploadFeedback = document.getElementById('uploadFeedback');
const documentActionSummary = document.getElementById('documentActionSummary');
const reviewNoteInput = document.getElementById('reviewNoteInput');
const addReviewNoteBtn = document.getElementById('addReviewNoteBtn');
const reviewNotesHistory = document.getElementById('reviewNotesHistory');
const ownersList = document.getElementById('ownersList');
const dependsOnSelect = document.getElementById('dependsOn');
const dependsSearch = document.getElementById('dependsSearch');
const dependencyInfo = document.getElementById('dependencyInfo');
const detailMetaSummary = document.getElementById('detailMetaSummary');
const currentDocumentState = document.getElementById('currentDocumentState');
const currentDocumentTitle = document.getElementById('currentDocumentTitle');
const currentDocumentHint = document.getElementById('currentDocumentHint');
const currentDocumentActions = document.getElementById('currentDocumentActions');
const documentVersionsSummary = document.getElementById('documentVersionsSummary');
const reviewSummary = document.getElementById('reviewSummary');
const askEditAction = window.ProjectDashboardUI?.bindActionDialog({
  dialogId: 'editActionDialog',
  titleId: 'editActionDialogTitle',
  messageId: 'editActionDialogMessage',
  eyebrowId: 'editActionDialogEyebrow',
  cancelId: 'editActionDialogCancel',
  confirmId: 'editActionDialogConfirm',
}) || (async () => ({ confirmed: true }));

const f = {
  name: document.getElementById('name'),
  description: document.getElementById('description'),
  status: document.getElementById('status'),
  priority: document.getElementById('priority'),
  owner: document.getElementById('owner'),
  dueDate: document.getElementById('dueDate'),
  documentFile: document.getElementById('documentFile'),
  documentName: document.getElementById('documentName'),
  documentVersions: document.getElementById('documentVersions'),
};

let me = null;
let allowedModules = new Set();
let doc = null;
let isDirty = false;
let isSaving = false;
let scopeBlocked = false;
let dependencyDocs = [];
let dependencySelected = new Set();
let lastActivity = null;
let savePhase = 'idle';
saveBtn.disabled = true;

// ---------------------------------------------------------------------------
// Helper HTTP JSON da tela de edição
// ---------------------------------------------------------------------------
async function api(url, opts={}) {
  const r = await fetch(url, opts);
  const d = await r.json().catch(()=>({}));
  if (!r.ok) {
    const err = new Error(d.error || 'Erro');
    err.status = r.status;
    throw err;
  }
  return d;
}

function hasModule(moduleId) {
  return allowedModules.has(String(moduleId || '').trim());
}

function canEditCard() {
  return ['admin', 'lider_projeto', 'member', 'desenhista', 'colaborador'].includes(me?.role || '') || hasModule('projects.cards_list');
}

function canUploadDocument() {
  return ['admin', 'lider_projeto', 'member', 'desenhista', 'colaborador'].includes(me?.role || '') || hasModule('projects.cards_list');
}

function canAddReviewNotes() {
  return ['admin', 'lider_projeto', 'member', 'desenhista', 'colaborador', 'revisor'].includes(me?.role || '') || hasModule('projects.cards_list');
}

function getMultiSelectedValues(containerEl) {
  if (!containerEl) return [];
  return Array.from(containerEl.querySelectorAll('input[type="checkbox"][data-dep-slug]:checked'))
    .map((el) => String(el.getAttribute('data-dep-slug') || '').trim())
    .filter(Boolean);
}

function canDeleteCard() {
  if (!doc || !me) return false;
  if (['admin', 'lider_projeto'].includes(me.role)) return true;
  if (me.role === 'member') return (doc.createdBy || '').toLowerCase() === (me.username || '').toLowerCase();
  return false;
}

function setDirty(v) {
  isDirty = !!v;
  saveBtn.disabled = scopeBlocked || !isDirty || isSaving || !canEditCard();
  updateNavigationStatus();
  refreshActionFeedback();
}

function setStatusChip(el, variant, message) {
  if (!el) return;
  el.className = `inline-status-chip inline-status-chip-${variant}`;
  el.textContent = message;
}

function updateNavigationStatus() {
  if (!detailNavStatus) return;
  if (scopeBlocked) {
    detailNavStatus.className = 'detail-nav-status small status-danger';
    detailNavStatus.textContent = 'Edição bloqueada por escopo inválido.';
    return;
  }
  if (isSaving) {
    detailNavStatus.className = 'detail-nav-status small status-warning';
    detailNavStatus.textContent = savePhase === 'uploading'
      ? 'Salvando card e enviando nova versão do documento...'
      : 'Salvando alterações do card...';
    return;
  }
  if (isDirty) {
    detailNavStatus.className = 'detail-nav-status small status-warning';
    detailNavStatus.textContent = 'Há alterações pendentes. Salve antes de voltar ao Kanban.';
    return;
  }
  detailNavStatus.className = 'detail-nav-status small';
  detailNavStatus.textContent = 'Sem alterações pendentes.';
}

function refreshActionFeedback() {
  const file = f.documentFile?.files?.[0];
  if (file) {
    setStatusChip(uploadFeedback, 'warning', `Upload pendente: ${file.name}`);
    if (documentActionSummary) {
      documentActionSummary.textContent = 'Novo arquivo selecionado. Ao salvar, a tela vai atualizar o card e criar uma nova versão no histórico do documento.';
    }
  } else {
    setStatusChip(uploadFeedback, 'neutral', 'Nenhum novo arquivo selecionado.');
    if (documentActionSummary) {
      documentActionSummary.textContent = 'Sem upload pendente. Selecione um arquivo apenas quando quiser criar uma nova versão.';
    }
  }

  if (isSaving) {
    setStatusChip(saveStateBadge, 'warning', savePhase === 'uploading' ? 'Enviando arquivo...' : 'Salvando card...');
  } else if (isDirty) {
    setStatusChip(saveStateBadge, 'warning', file ? 'Card + upload pendentes.' : 'Alterações do card pendentes.');
  } else {
    setStatusChip(saveStateBadge, 'neutral', 'Pronto para editar.');
  }
}

function setScopeBlocked(message) {
  scopeBlocked = true;
  isSaving = false;
  isDirty = false;
  [f.name, f.description, f.status, f.priority, f.owner, f.dueDate, f.documentFile, reviewNoteInput, addReviewNoteBtn, deleteBtn, saveBtn].forEach((el) => {
    if (!el) return;
    el.disabled = true;
  });
  updateNavigationStatus();
  setStatusChip(saveStateBadge, 'danger', 'Edição bloqueada.');
  feedback.textContent = message || 'Escopo inválido para este documento.';
}

async function initMe() {
  const [d, permsResp] = await Promise.all([
    api('/api/me'),
    api('/api/me/permissions').catch(() => ({ permissions: { allowedModules: [] } })),
  ]);
  me = d.user;
  allowedModules = new Set((permsResp?.permissions?.allowedModules || []).map((x) => String(x || '').trim()));
  deleteBtn.style.display = 'none';
}

function canEditReviewNotes() {
  return canAddReviewNotes() && (f.status.value || '').trim().toLowerCase() === 'em revisão';
}

function canResolveReviewNotes() {
  const canByRole = ['desenhista', 'colaborador', 'admin', 'lider_projeto'].includes(me?.role || '');
  const canByModule = hasModule('projects.cards_list');
  return (canByRole || canByModule) && (f.status.value || '').trim().toLowerCase() === 'em revisão';
}

function updateReviewNotesAvailability() {
  const enabled = canEditReviewNotes();
  reviewNoteInput.disabled = !enabled;
  addReviewNoteBtn.disabled = !enabled;
  reviewNoteInput.placeholder = enabled
    ? 'Descreva o ajuste solicitado, contexto e critério de aceite...'
    : 'Notas liberadas apenas quando o card estiver em "Em revisão"';
}

function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}

function fmtDateTime(value) {
  if (!value) return 'sem registro';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'sem registro' : date.toLocaleString('pt-BR');
}

function fmtDate(value) {
  if (!value) return 'sem prazo';
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? 'sem prazo' : date.toLocaleDateString('pt-BR');
}

function documentStateLabel(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'release') return 'Release';
  if (normalized === 'em revisão') return 'Em revisão';
  if (normalized === 'em andamento') return 'Em andamento';
  if (normalized === 'sem anexo') return 'Sem anexo';
  return 'Aguardando edição';
}

function mapCardStatusToDocumentState(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'concluído') return 'release';
  if (normalized === 'em revisão') return 'em revisão';
  if (normalized === 'em andamento') return 'em andamento';
  return 'aguardando edição';
}

function renderDetailMeta(document) {
  if (!detailMetaSummary || !document) return;
  const lastActor = lastActivity?.author || document.owner || document.createdBy || 'Sem autor definido';
  const lastLabel = lastActivity?.label || 'Última movimentação ainda não identificada';
  const chips = [
    `<span class="detail-pill detail-pill-soft">Status: ${esc(document.status || '-')}</span>`,
    `<span class="detail-pill detail-pill-soft">Prioridade: ${esc(document.priority || '-')}</span>`,
    `<span class="detail-pill detail-pill-soft">Responsável: ${esc(document.owner || 'Não definido')}</span>`,
    `<span class="detail-pill detail-pill-soft">Prazo: ${esc(fmtDate(document.dueDate))}</span>`,
    `<span class="detail-pill detail-pill-accent">Última atividade: ${esc(lastLabel)}</span>`,
    `<span class="detail-pill detail-pill-soft">Último autor: ${esc(lastActor)}</span>`,
  ];
  detailMetaSummary.innerHTML = chips.join('');
}

function renderCurrentDocumentPanel(document) {
  if (!currentDocumentState || !currentDocumentTitle || !currentDocumentHint || !currentDocumentActions) return;
  const hasDocument = !!String(document?.documentName || '').trim();
  const activityLabel = lastActivity?.label || fmtDateTime(document?.updatedAt);
  const activityAuthor = lastActivity?.author || document?.owner || document?.createdBy || 'Sem autor definido';
  currentDocumentState.textContent = hasDocument ? documentStateLabel(document?.documentStatus) : 'Sem anexo';
  currentDocumentTitle.textContent = hasDocument ? String(document.documentName) : 'Nenhum documento anexado';
  currentDocumentHint.textContent = hasDocument
    ? `Arquivo atual vinculado ao card. Última atividade: ${activityLabel}. Último autor: ${activityAuthor}.`
    : 'Envie um arquivo para iniciar o histórico de versões deste card e deixar a operação rastreável.';

  const actions = [];
  if (hasDocument) {
    actions.push(`<a class="button-link" href="${withProjectId(`/api/documents/${encodeURIComponent(slug)}/document`)}" target="_blank" rel="noopener">Abrir arquivo atual</a>`);
  }
  if (canUploadDocument()) {
    actions.push('<span class="detail-inline-hint">Novo upload cria uma nova versão no histórico. Alterações de card continuam separadas deste bloco.</span>');
  }
  currentDocumentActions.innerHTML = actions.join('');
}

// ---------------------------------------------------------------------------
// Carregamento do histórico de notas de revisão
// ---------------------------------------------------------------------------
function registerLastActivity(candidate) {
  if (!candidate?.at) return;
  const candidateTime = new Date(candidate.at).getTime();
  if (Number.isNaN(candidateTime)) return;
  const currentTime = lastActivity?.at ? new Date(lastActivity.at).getTime() : Number.NEGATIVE_INFINITY;
  if (candidateTime >= currentTime) lastActivity = candidate;
}

async function loadReviewNotes() {
  const d = await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/review-notes`));
  const notes = d.notes || [];
  if (notes[0]?.created_at) {
    registerLastActivity({
      at: notes[0].created_at,
      author: notes[0].created_by || '-',
      label: `nota de revisão em ${fmtDateTime(notes[0].created_at)}`,
    });
  }
  if (!notes.length) {
    reviewNotesHistory.textContent = 'Sem notas registradas. Quando o card entrar em revisão, registre aqui os ajustes combinados.';
    if (reviewSummary) reviewSummary.textContent = 'Nenhuma pendência de revisão registrada.';
    return;
  }

  const pendingCount = notes.filter((n) => Number(n.is_resolved || 0) !== 1).length;
  const resolvedCount = notes.length - pendingCount;
  if (reviewSummary) {
    reviewSummary.textContent = pendingCount
      ? `${pendingCount} pendência(s) aberta(s) e ${resolvedCount} resolvida(s). Use esta trilha para acompanhar retorno e aceite.`
      : `Todas as ${resolvedCount} nota(s) já foram resolvidas. Histórico pronto para auditoria rápida.`;
  }

  const canResolve = canResolveReviewNotes();
  reviewNotesHistory.innerHTML = notes.map((n) => {
    const resolved = Number(n.is_resolved || 0) === 1;
    const createdAt = n.created_at ? new Date(n.created_at).toLocaleString('pt-BR') : '-';
    const resolvedAt = n.resolved_at ? new Date(n.resolved_at).toLocaleString('pt-BR') : '-';
    return `
      <article class="review-note-item ${resolved ? 'is-resolved' : 'is-pending'}">
        <div class="review-note-topbar">
          <label class="inline-check review-note-toggle">
            <input type="checkbox" class="review-note-resolve" data-note-id="${n.id}" ${resolved ? 'checked' : ''} ${!canResolve ? 'disabled' : ''} />
            <span>${resolved ? 'RESOLVIDO' : 'PENDENTE'}</span>
          </label>
        </div>
        <div class="review-note-meta-grid">
          <div><b>usuário:</b> ${n.created_by}</div>
          <div><b>criado em:</b> ${createdAt}</div>
        </div>
        <div class="review-note-body">${n.note}</div>
        <div class="review-note-meta-grid review-note-meta-grid-bottom">
          <div><b>resolvido por:</b> ${n.resolved_by || '-'}</div>
          <div><b>resolvido em:</b> ${resolvedAt}</div>
        </div>
      </article>
    `;
  }).join('');

  reviewNotesHistory.querySelectorAll('.review-note-resolve').forEach((checkbox) => {
    checkbox.addEventListener('change', async (e) => {
      const input = e.currentTarget;
      const nextResolved = !!input.checked;
      try {
        await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/review-notes/${encodeURIComponent(input.dataset.noteId)}`), {
          method: 'PATCH',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ resolved: nextResolved })
        });
        feedback.textContent = nextResolved
          ? 'Item de revisão marcado como resolvido ✅'
          : 'Item de revisão retornou para pendente ↩️';
        await loadReviewNotes();
      } catch (err) {
        input.checked = !nextResolved;
        feedback.textContent = err.message;
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Carregamento do histórico de versões/anexos do documento
// ---------------------------------------------------------------------------
async function loadVersions() {
  try {
    const d = await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/document/versions`));
    const versions = d.versions || [];
    if (!versions.length) {
      if (documentVersionsSummary) {
        documentVersionsSummary.textContent = 'Histórico de versões ainda não iniciado. O primeiro upload aparecerá aqui com data, autor e status do documento.';
      }
      f.documentVersions.textContent = 'Sem revisões ainda. Quando houver nova entrega, a linha do tempo será exibida nesta área.';
      return;
    }
    const latest = versions[0];
    registerLastActivity({
      at: latest.created_at,
      author: latest.created_by || '-',
      label: `upload r${latest.version} em ${fmtDateTime(latest.created_at)}`,
    });
    if (documentVersionsSummary) {
      documentVersionsSummary.textContent = `${versions.length} versão(ões) registrada(s). Última entrega: r${latest.version} em ${fmtDateTime(latest.created_at)} por ${latest.created_by || '-'}.`;
    }
    const items = versions.map((v) => `
      <article class="document-version-item">
        <div class="document-version-head">
          <div>
            <strong>r${v.version}</strong>
            <span class="detail-pill detail-pill-soft">${esc(documentStateLabel(v.document_status))}</span>
          </div>
          <a class="button-link" href="/api/documents/${encodeURIComponent(slug)}/document?version=${v.version}&project_id=${encodeURIComponent(String(currentProjectId()))}" target="_blank" rel="noopener">Abrir versão</a>
        </div>
        <div class="document-version-meta">${esc(v.document_name || 'arquivo sem nome')} · enviado por ${esc(v.created_by || '-')} · ${esc(fmtDateTime(v.created_at))}</div>
      </article>
    `).join('');
    f.documentVersions.innerHTML = items;
  } catch (e) {
    if (e?.status === 404) {
      if (documentVersionsSummary) documentVersionsSummary.textContent = 'Histórico indisponível no backend atual.';
      f.documentVersions.textContent = 'Histórico indisponível (reinicie o backend para ativar controle de revisões).';
      return;
    }
    throw e;
  }
}

// ---------------------------------------------------------------------------
// Renderização visual das dependências possíveis do documento
// ---------------------------------------------------------------------------
function renderDependencyChecklist() {
  if (!dependsOnSelect) return;
  const q = String(dependsSearch?.value || '').trim().toLowerCase();
  const shown = dependencyDocs.filter((d) => {
    if (!q) return true;
    const hay = `${d.name || ''} ${d.status || ''}`.toLowerCase();
    return hay.includes(q);
  });

  if (!shown.length) {
    dependsOnSelect.innerHTML = '<div class="deps-empty">Nenhum card encontrado para este filtro. Limpe a busca para ver todas as opções.</div>';
    return;
  }

  const editable = canEditCard();
  dependsOnSelect.innerHTML = shown
    .map((d) => `
      <label class="small">
        <input type="checkbox" data-dep-slug="${String(d.slug)}" ${dependencySelected.has(String(d.slug)) ? 'checked' : ''} ${editable ? '' : 'disabled'} /> ${d.name} [${d.status}]
      </label>
    `)
    .join('');

  Array.from(dependsOnSelect.querySelectorAll('input[type="checkbox"][data-dep-slug]')).forEach((el) => {
    el.addEventListener('change', () => {
      if (!canEditCard()) return;
      const slug = String(el.getAttribute('data-dep-slug') || '');
      if (!slug) return;
      if (el.checked) dependencySelected.add(slug);
      else dependencySelected.delete(slug);
      setDirty(true);
    });
  });
}

// ---------------------------------------------------------------------------
// Carregamento das opções de dependência disponíveis no projeto atual
// ---------------------------------------------------------------------------
async function loadDependencyOptions(currentSlug, selected = []) {
  if (!dependsOnSelect) return;
  const data = await api(`/api/documents?project_id=${encodeURIComponent(String(currentProjectId()))}`);
  dependencyDocs = (data.documents || [])
    .filter((d) => String(d.slug) !== String(currentSlug))
    .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'pt-BR'));
  dependencySelected = new Set((selected || []).map((s) => String(s || '').trim()).filter(Boolean));
  renderDependencyChecklist();
}

function renderDependencyInfo(document) {
  if (!dependencyInfo) return;
  const deps = Array.isArray(document?.dependencies) ? document.dependencies : [];
  if (!deps.length) {
    dependencyInfo.textContent = 'Sem dependências. Este card pode avançar sem bloqueios externos registrados.';
    return;
  }
  const pending = deps.filter((d) => String(d.status || '') !== 'Concluído');
  if (!pending.length) {
    dependencyInfo.textContent = `Dependências mapeadas: ${deps.length}. Todas já foram concluídas ✅`;
    return;
  }
  dependencyInfo.textContent = `Dependências pendentes (${pending.length}): ${pending.map((d) => d.name).join(', ')}`;
}

// ---------------------------------------------------------------------------
// Carregamento principal do documento na tela de edição
// ---------------------------------------------------------------------------
async function loadDocument() {
  lastActivity = null;
  const d = await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}`));
  const p = d.document;
  doc = p;
  if (Number(p.projectId || 0) !== Number(currentProjectId())) {
    setScopeBlocked(`Escopo inválido: documento pertence ao projeto ${p.projectId}, mas a URL está no projeto ${currentProjectId()}.`);
    return;
  }
  f.name.value = p.name; f.description.value = p.description; f.owner.value = p.owner; f.dueDate.value = p.dueDate;
  f.documentName.value = p.documentName || 'Sem anexo';
  registerLastActivity({
    at: p.updatedAt || p.openedAt,
    author: p.owner || p.createdBy || '-',
    label: p.updatedAt ? `edição do card em ${fmtDateTime(p.updatedAt)}` : `abertura em ${fmtDateTime(p.openedAt)}`,
  });
  f.status.innerHTML = '';
  f.priority.innerHTML = '';
  d.statuses.forEach(s => f.status.append(new Option(s,s))); f.status.value = p.status;
  d.priorities.forEach(x => f.priority.append(new Option(x,x))); f.priority.value = p.priority;
  ownersList.innerHTML = '';
  (d.users || []).forEach(u => ownersList.append(new Option(u, u)));

  const editable = canEditCard();
  [f.name, f.description, f.status, f.priority, f.owner, f.dueDate].forEach((el) => el.disabled = !editable);
  if (dependsOnSelect) {
    Array.from(dependsOnSelect.querySelectorAll('input[type="checkbox"]')).forEach((el) => {
      el.disabled = !editable;
    });
  }
  f.documentFile.disabled = !canUploadDocument();
  deleteBtn.style.display = canDeleteCard() ? 'inline-block' : 'none';

  if (dependsSearch) dependsSearch.value = '';
  await loadDependencyOptions(slug, p.dependsOn || []);
  renderDependencyInfo(p);

  updateReviewNotesAvailability();
  await loadVersions();
  await loadReviewNotes();
  renderDetailMeta(p);
  renderCurrentDocumentPanel(p);
  setDirty(false);
  refreshActionFeedback();
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const out = String(reader.result || '');
      resolve(out.includes(',') ? out.split(',')[1] : out);
    };
    reader.onerror = () => reject(new Error('Falha ao ler arquivo'));
    reader.readAsDataURL(file);
  });
}

[f.name, f.description, f.status, f.priority, f.owner, f.dueDate].forEach((el) => {
  el.addEventListener('input', () => setDirty(true));
  el.addEventListener('change', () => setDirty(true));
});
if (dependsSearch) {
  dependsSearch.addEventListener('input', () => renderDependencyChecklist());
}
f.documentFile.addEventListener('change', () => {
  setDirty(true);
  refreshActionFeedback();
});
f.status.addEventListener('change', () => updateReviewNotesAvailability());

window.addEventListener('beforeunload', (e) => {
  if (!isDirty || isSaving) return;
  e.preventDefault();
  e.returnValue = '';
});

async function navigateBackToBoard() {
  if (isDirty && !isSaving) {
    const leave = await askEditAction({
      eyebrow: 'Alterações pendentes',
      title: 'Sair sem salvar este card?',
      message: 'Existem alterações ainda não salvas neste card. Se você sair agora, elas serão perdidas.',
      confirmLabel: 'Sair sem salvar',
      danger: true,
    });
    if (!leave.confirmed) return;
  }
  location.href = `/kanban.html?project_id=${encodeURIComponent(String(currentProjectId()))}`;
}

backBtn.onclick = navigateBackToBoard;
if (backLinkBtn) backLinkBtn.onclick = navigateBackToBoard;

logoutBtn.onclick = async () => {
  if (isDirty && !isSaving) {
    const leave = await askEditAction({
      eyebrow: 'Alterações pendentes',
      title: 'Encerrar sessão sem salvar?',
      message: 'Existem alterações ainda não salvas neste card. Se você continuar, elas serão perdidas antes do logout.',
      confirmLabel: 'Sair e fazer logout',
      danger: true,
    });
    if (!leave.confirmed) return;
  }
  await api('/api/logout',{method:'POST'});
  location.href='/login.html';
};

addReviewNoteBtn.onclick = async () => {
  try {
    if (!canEditReviewNotes()) {
      feedback.textContent = 'Notas de revisão só ficam habilitadas quando o documento está em "em revisão".';
      return;
    }
    const note = (reviewNoteInput.value || '').trim();
    if (!note) {
      feedback.textContent = 'Digite uma nota antes de adicionar.';
      return;
    }
    await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/review-notes`), {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ note })
    });
    reviewNoteInput.value = '';
    await loadReviewNotes();
    renderDetailMeta(doc);
    renderCurrentDocumentPanel(doc);
    feedback.textContent = 'Nota adicionada ✅ Histórico de revisão atualizado.';
  } catch (e) {
    feedback.textContent = e.message;
  }
};

// ---------------------------------------------------------------------------
// Salvamento principal da edição do documento
// ---------------------------------------------------------------------------
async function handleSave() {
  if (scopeBlocked) {
    feedback.textContent = 'Bloqueado por escopo inválido. Volte ao Kanban e abra o card no projeto correto.';
    return;
  }
  if (!canEditCard()) return;
  if (!isDirty) return;
  isSaving = true;
  savePhase = 'saving';
  saveBtn.textContent = 'Salvando...';
  saveBtn.disabled = true;
  updateNavigationStatus();
  refreshActionFeedback();
  try {
    const owner = (f.owner.value || '').trim();
    const validOwners = Array.from(ownersList.options).map(o => o.value);
    if (owner && !validOwners.includes(owner)) {
      feedback.textContent = 'Responsável inválido. Selecione um usuário existente da lista para manter o card consistente.';
      isSaving = false;
      savePhase = 'idle';
      saveBtn.textContent = 'Salvar alterações';
      saveBtn.disabled = !isDirty;
      updateNavigationStatus();
      refreshActionFeedback();
      return;
    }

    const depends_on = Array.from(dependencySelected);

    await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}`), {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      name:f.name.value, description:f.description.value, status:f.status.value, priority:f.priority.value, owner, dueDate:f.dueDate.value, depends_on,
    })});

    const file = f.documentFile.files?.[0];
    if (file) {
      savePhase = 'uploading';
      saveBtn.textContent = 'Enviando arquivo...';
      updateNavigationStatus();
      refreshActionFeedback();
      const b64 = await fileToBase64(file);
      await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/document`), {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          fileName: file.name,
          mimeType: file.type || 'application/octet-stream',
          contentBase64: b64,
        })
      });
      f.documentName.value = file.name;
      f.documentFile.value = '';
    }

    doc = {
      ...doc,
      name: f.name.value,
      description: f.description.value,
      status: f.status.value,
      priority: f.priority.value,
      owner,
      dueDate: f.dueDate.value,
      documentName: f.documentName.value === 'Sem anexo' ? '' : f.documentName.value,
      documentStatus: mapCardStatusToDocumentState(f.status.value),
      updatedAt: new Date().toISOString(),
    };
    registerLastActivity({
      at: doc.updatedAt,
      author: me?.username || owner || '-',
      label: file ? `edição + upload em ${fmtDateTime(doc.updatedAt)}` : `edição do card em ${fmtDateTime(doc.updatedAt)}`,
    });
    await loadVersions();
    await loadReviewNotes();
    renderDetailMeta(doc);
    renderCurrentDocumentPanel(doc);
    setDirty(false);
    isSaving = false;
    savePhase = 'idle';
    saveBtn.textContent = 'Salvar alterações';
    updateNavigationStatus();
    refreshActionFeedback();
    setStatusChip(saveStateBadge, 'success', file ? 'Card salvo e upload concluído.' : 'Card salvo com sucesso.');
    if (file) setStatusChip(uploadFeedback, 'success', `Upload concluído: ${f.documentName.value}`);
    feedback.textContent = file
      ? 'Salvo com sucesso ✅ Card atualizado e nova versão do documento registrada.'
      : 'Salvo com sucesso ✅ Dados do card atualizados.';
  } catch (e) {
    feedback.textContent = e.message;
    isSaving = false;
    savePhase = 'idle';
    saveBtn.textContent = 'Salvar alterações';
    saveBtn.disabled = !isDirty;
    updateNavigationStatus();
    refreshActionFeedback();
    setStatusChip(saveStateBadge, 'danger', 'Falha ao salvar.');
  }
}

formEl.addEventListener('submit', (e) => {
  e.preventDefault();
});

saveBtn.onclick = handleSave;

deleteBtn.onclick = async () => {
  const answer = await askEditAction({
    eyebrow: 'Exclusão do card',
    title: 'Apagar este documento do dashboard?',
    message: 'Esta ação moverá o item para a área recuperável e pode impactar o fluxo do projeto. Continue apenas se a remoção for intencional.',
    confirmLabel: 'Apagar documento',
    danger: true,
  });
  if (!answer.confirmed) return;
  try {
    await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}`), {method:'DELETE'});
    location.href = `/kanban.html?project_id=${encodeURIComponent(String(currentProjectId()))}`;
  } catch (e) { feedback.textContent = e.message; }
};

(async () => {
  try {
    await initMe();
    await loadDocument();
    updateNavigationStatus();
    refreshActionFeedback();
  } catch (e) {
    if (e?.status === 401) {
      location.href = '/login.html';
      return;
    }
    const msg = `Falha ao abrir edição: ${e.message || 'erro inesperado'}`;
    if (e?.status === 409 || String(e?.message || '').toLowerCase().includes('escopo inválido')) {
      setScopeBlocked(msg);
      return;
    }
    feedback.textContent = msg;
  }
})();
