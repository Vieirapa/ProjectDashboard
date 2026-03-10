const board = document.getElementById('board');
const refreshBtn = document.getElementById('refreshBtn');
const newBtn = document.getElementById('newBtn');

const searchInput = document.getElementById('searchInput');
const statusFilter = document.getElementById('statusFilter');
const priorityFilter = document.getElementById('priorityFilter');
const ownerFilter = document.getElementById('ownerFilter');
const sortOrderFilter = document.getElementById('sortOrderFilter');
const projectSelect = document.getElementById('sidebarProjectSelect');
const projectStartDateEl = document.getElementById('projectStartDate');
const projectCollaboratorsEl = document.getElementById('projectCollaborators');
const sumBacklogEl = document.getElementById('sumBacklog');
const sumProgressEl = document.getElementById('sumProgress');
const sumReviewEl = document.getElementById('sumReview');
const sumDoneEl = document.getElementById('sumDone');

const dialog = document.getElementById('documentDialog');
const form = document.getElementById('documentForm');
const cancelDialogBtn = document.getElementById('cancelDialogBtn');

const pName = document.getElementById('pName');
const pDescription = document.getElementById('pDescription');
const pStatus = document.getElementById('pStatus');
const pPriority = document.getElementById('pPriority');
const pOwner = document.getElementById('pOwner');
const pDueDate = document.getElementById('pDueDate');
const pDocumentFile = document.getElementById('pDocumentFile');
const pDependsOn = document.getElementById('pDependsOn');
const pDependsSearch = document.getElementById('pDependsSearch');
const ownersList = document.getElementById('ownersList');

let me = null;
let state = { documents: [], statuses: [], priorities: [], projects: [], selectedProjectId: 1 };
let createDependencyDocs = [];
let createDependencySelected = new Set();
let behavior = {
  priorityColorEnabled: false,
  priorityColors: {
    'Baixa': '#dbeafe',
    'Média': '#fef3c7',
    'Alta': '#fed7aa',
    'Urgente': '#fecaca',
  },
};

function projectIdFromUrlOrNull() {
  const rawPid = new URLSearchParams(window.location.search).get('project_id');
  const pid = Number(rawPid);
  return Number.isFinite(pid) && pid > 0 ? pid : null;
}

function currentProjectIdFromUrl() {
  return projectIdFromUrlOrNull() || Number(state.selectedProjectId || 1) || 1;
}

function withProjectId(url) {
  const pid = currentProjectIdFromUrl();
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}project_id=${encodeURIComponent(String(pid))}`;
}

async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || 'Erro na API');
    err.status = res.status;
    err.payload = data;
    throw err;
  }
  return data;
}

function getMultiSelectedValues(containerEl) {
  if (!containerEl) return [];
  return Array.from(containerEl.querySelectorAll('input[type="checkbox"][data-dep-slug]:checked'))
    .map((el) => String(el.getAttribute('data-dep-slug') || '').trim())
    .filter(Boolean);
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

async function loadMe() {
  const data = await api('/api/me');
  me = data.user;
  newBtn.style.display = canCreateCard() ? 'inline-block' : 'none';

  try {
    const prof = await api('/api/me/profile');
    const p = prof?.profile || {};
    const colors = p.priority_colors || {};
    behavior.priorityColorEnabled = !!p.priority_color_enabled;
    behavior.priorityColors = {
      'Baixa': colors['Baixa'] || '#dbeafe',
      'Média': colors['Média'] || '#fef3c7',
      'Alta': colors['Alta'] || '#fed7aa',
      'Urgente': colors['Urgente'] || '#fecaca',
    };
  } catch {
    // fallback silencioso para defaults
  }
}

function currentFilters() {
  const [sortBy = 'priority', sortDir = 'desc'] = String(sortOrderFilter.value || 'priority_desc').split('_');
  return {
    q: (searchInput.value || '').toLowerCase().trim(),
    status: statusFilter.value,
    priority: priorityFilter.value,
    owner: (ownerFilter.value || '').toLowerCase().trim(),
    sortBy,
    sortDir,
  };
}

function passesFilters(document, f) {
  if (f.status && document.status !== f.status) return false;
  if (f.priority && document.priority !== f.priority) return false;
  if (f.owner && !(document.owner || '').toLowerCase().includes(f.owner)) return false;
  const hay = `${document.name} ${document.description}`.toLowerCase();
  if (f.q && !hay.includes(f.q)) return false;
  return true;
}

function toTimestamp(value) {
  const t = Date.parse(value || '');
  return Number.isFinite(t) ? t : 0;
}

function compareDocuments(a, b, sortBy, sortDir) {
  const dir = sortDir === 'asc' ? 1 : -1;
  const priorityWeight = { Urgente: 4, Alta: 3, 'Média': 2, Baixa: 1 };

  if (sortBy === 'priority') {
    return dir * ((priorityWeight[a.priority] || 0) - (priorityWeight[b.priority] || 0));
  }

  if (sortBy === 'ageDays') {
    return dir * ((Number(a.ageDays) || 0) - (Number(b.ageDays) || 0));
  }

  if (sortBy === 'openedAt' || sortBy === 'updatedAt' || sortBy === 'dueDate') {
    return dir * (toTimestamp(a[sortBy]) - toTimestamp(b[sortBy]));
  }

  const left = String(a[sortBy] || a.name || '').toLowerCase();
  const right = String(b[sortBy] || b.name || '').toLowerCase();
  return dir * left.localeCompare(right, 'pt-BR');
}

function makeColumn(status) {
  const col = document.createElement('div');
  col.className = 'column';
  col.innerHTML = `<h2>${status}</h2><div class="small">0 documentos</div>`;
  col.dataset.status = status;
  return col;
}

function docStatusMeta(cardStatus) {
  const map = {
    'Backlog': { icon: '🕓', cls: 'doc-waiting', label: 'Aguardando edição' },
    'Em andamento': { icon: '✏️', cls: 'doc-editing', label: 'Em andamento' },
    'Em revisão': { icon: '🔎', cls: 'doc-review', label: 'Em revisão' },
    'Concluído': { icon: '🚀', cls: 'doc-release', label: 'Release' },
  };
  return map[cardStatus] || map['Backlog'];
}

function canCreateCard() {
  return ['admin', 'lider_projeto', 'member'].includes(me?.role || '');
}

function canEditCard() {
  return ['admin', 'lider_projeto', 'member', 'desenhista', 'colaborador'].includes(me?.role || '');
}

function makeCard(p, statuses, priorities) {
  const card = document.createElement('div');
  card.className = 'card';
  const docMeta = docStatusMeta(p.status);
  const ageLabel = String(p.ageLabel || 'Dias desde abertura')
    .replace('DIAS PARA SOLUÇÃO', 'Dia até solução')
    .replace('DIAS PARA SOLUCAO', 'Dia até solução')
    .replace('DIAS DESDE ABERTURA', 'Dias desde abertura');

  card.innerHTML = `
    <h3>${p.name}</h3>
    <p>${p.description || 'Sem descrição'}</p>
    <div class="meta">Prioridade: <b>${p.priority}</b><br/>Responsável: <b>${p.owner || '-'}</b><br/>Prazo: <b>${p.dueDate || '-'}</b><br/>${ageLabel}: <b>${p.ageDays ?? '-'}</b><br/>Doc: <b>${docMeta.label}</b></div>
  `;

  if (behavior.priorityColorEnabled) {
    const bg = behavior.priorityColors?.[p.priority];
    if (bg) {
      card.style.background = bg;
      card.style.border = '1px solid rgba(15,23,42,.12)';
    }
  }

  const st = document.createElement('select');
  statuses.forEach(s => { const o = document.createElement('option'); o.value = s; o.textContent = s; if (s === p.status) o.selected = true; st.appendChild(o); });
  st.disabled = !canEditCard();
  st.onchange = async () => {
    const prev = p.status;
    try {
      await api(withProjectId(`/api/documents/${encodeURIComponent(p.slug)}`), { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({status: st.value})});
      render();
    } catch (e) {
      st.value = prev;
      alert(e.message || 'Falha ao alterar status.');
    }
  };

  const pr = document.createElement('select');
  priorities.forEach(x => { const o = document.createElement('option'); o.value = x; o.textContent = `Prioridade: ${x}`; if (x === p.priority) o.selected = true; pr.appendChild(o); });
  pr.disabled = !canEditCard();
  pr.onchange = async () => { await api(withProjectId(`/api/documents/${encodeURIComponent(p.slug)}`), { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({priority: pr.value})}); render(); };

  const controls = document.createElement('div');
  controls.className = 'card-controls';

  const selectsWrap = document.createElement('div');
  selectsWrap.className = 'card-selects';

  const detailsBtn = document.createElement('button');
  detailsBtn.className = 'secondary details-btn';
  detailsBtn.textContent = 'Detalhes';
  detailsBtn.onclick = () => window.location.href = `/edit.html?slug=${encodeURIComponent(p.slug)}&project_id=${encodeURIComponent(String(currentProjectIdFromUrl()))}`;

  selectsWrap.append(st, pr, detailsBtn);

  const docBtn = document.createElement('button');
  docBtn.className = `doc-btn ${docMeta.cls}`;
  docBtn.title = `${docMeta.label}${p.documentName ? ` · ${p.documentName}` : ''}`;
  docBtn.innerHTML = `<span class="doc-main">📄</span><span class="doc-state">${docMeta.icon}</span>`;
  docBtn.onclick = () => {
    if (!p.hasDocument) return alert('Este documento ainda não tem anexo.');
    window.open(withProjectId(`/api/documents/${encodeURIComponent(p.slug)}/document`), '_blank');
  };
  if (!p.hasDocument) {
    docBtn.disabled = true;
    docBtn.title = `${docMeta.label} · sem documento anexado`;
  }

  controls.append(selectsWrap, docBtn);

  card.append(controls);
  return card;
}

function fillFilters(statuses, priorities, users=[]) {
  if (statusFilter.options.length <= 1) statuses.forEach(s => statusFilter.append(new Option(s, s)));
  if (priorityFilter.options.length <= 1) priorities.forEach(p => priorityFilter.append(new Option(p, p)));
  pStatus.innerHTML = ''; pPriority.innerHTML = '';
  statuses.forEach(s => pStatus.append(new Option(s, s)));
  priorities.forEach(p => pPriority.append(new Option(p, p)));
  ownersList.innerHTML = '';
  (users || []).forEach(u => ownersList.append(new Option(u, u)));
  pStatus.value = 'Backlog'; pPriority.value = 'Média';
}

function fillDependenciesOptions() {
  if (!pDependsOn) return;
  const q = String(pDependsSearch?.value || '').trim().toLowerCase();
  const docs = createDependencyDocs.filter((d) => {
    if (!q) return true;
    const hay = `${d.name || ''} ${d.status || ''}`.toLowerCase();
    return hay.includes(q);
  });

  if (!docs.length) {
    pDependsOn.innerHTML = '<div class="deps-empty">Nenhum card encontrado.</div>';
    return;
  }

  pDependsOn.innerHTML = docs.map((d) => `
    <label class="small">
      <input type="checkbox" data-dep-slug="${String(d.slug)}" ${createDependencySelected.has(String(d.slug)) ? 'checked' : ''} /> ${d.name} [${d.status}]
    </label>
  `).join('');

  Array.from(pDependsOn.querySelectorAll('input[type="checkbox"][data-dep-slug]')).forEach((el) => {
    el.addEventListener('change', () => {
      const slug = String(el.getAttribute('data-dep-slug') || '');
      if (!slug) return;
      if (el.checked) createDependencySelected.add(slug);
      else createDependencySelected.delete(slug);
    });
  });
}

function syncProjectSelect() {
  if (!projectSelect) return;
  const selected = Number(state.selectedProjectId || 1);
  projectSelect.innerHTML = '';
  (state.projects || []).forEach((p) => {
    const templateLabel = p.is_template ? ' [Template]' : '';
    const opt = new Option(`${p.project_id} · ${p.project_name}${templateLabel}`, String(p.project_id));
    if (Number(p.project_id) === selected) opt.selected = true;
    projectSelect.append(opt);
  });
}

function formatPtDate(raw) {
  if (!raw) return '-';
  const s = String(raw).trim();

  // Evita bug de fuso em datas sem horário (YYYY-MM-DD),
  // que podem "voltar um dia" ao usar new Date(raw) em UTC-3.
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) {
    const [, y, mo, d] = m;
    return `${d}/${mo}/${y}`;
  }

  const dt = new Date(s);
  if (Number.isNaN(dt.getTime())) return s;
  return dt.toLocaleDateString('pt-BR');
}

function pct(part, total) {
  if (!total) return '0%';
  return `${Math.round((part / total) * 100)}%`;
}

function updateProjectSummary() {
  const selected = Number(state.selectedProjectId || 1);
  const project = (state.projects || []).find((p) => Number(p.project_id) === selected);
  const docs = state.documents || [];
  const total = docs.length;

  const backlog = docs.filter((d) => d.status === 'Backlog').length;
  const progress = docs.filter((d) => d.status === 'Em andamento').length;
  const review = docs.filter((d) => d.status === 'Em revisão').length;
  const done = docs.filter((d) => d.status === 'Concluído').length;

  const collaborators = new Set(
    docs
      .map((d) => String(d.owner || '').trim())
      .filter((x) => !!x)
      .map((x) => x.toLowerCase())
  ).size;

  if (projectStartDateEl) projectStartDateEl.textContent = formatPtDate(project?.start_date || '');
  if (projectCollaboratorsEl) projectCollaboratorsEl.textContent = String(collaborators);
  if (sumBacklogEl) sumBacklogEl.textContent = `${backlog} (${pct(backlog, total)})`;
  if (sumProgressEl) sumProgressEl.textContent = `${progress} (${pct(progress, total)})`;
  if (sumReviewEl) sumReviewEl.textContent = `${review} (${pct(review, total)})`;
  if (sumDoneEl) sumDoneEl.textContent = `${done} (${pct(done, total)})`;
}

async function render() {
  try {
    const pidInUrl = projectIdFromUrlOrNull();
    const query = pidInUrl ? `?project_id=${encodeURIComponent(String(pidInUrl))}` : '';
    state = await api(`/api/documents${query}`);

    if (!pidInUrl && Number(state.selectedProjectId || 0) > 0) {
      const u = new URL(window.location.href);
      u.searchParams.set('project_id', String(state.selectedProjectId));
      window.history.replaceState({}, '', `${u.pathname}?${u.searchParams.toString()}`);
    }

    syncProjectSelect();
    updateProjectSummary();
    fillFilters(state.statuses, state.priorities, state.users || []);
    createDependencyDocs = (state.documents || []).slice().sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'pt-BR'));
    fillDependenciesOptions();
    const filters = currentFilters();
    const filtered = state.documents.filter(p => passesFilters(p, filters));
    board.innerHTML = '';
    const cols = new Map(state.statuses.map(s => [s, makeColumn(s)]));
    cols.forEach(c => board.appendChild(c));

    filtered.sort((a, b) => {
      const cmp = compareDocuments(a, b, filters.sortBy, filters.sortDir);
      if (cmp !== 0) return cmp;
      return String(a.name || '').localeCompare(String(b.name || ''), 'pt-BR');
    });
    filtered.forEach(p => (cols.get(p.status) || cols.get('Backlog')).appendChild(makeCard(p, state.statuses, state.priorities)));
    cols.forEach(c => c.querySelector('.small').textContent = `${c.querySelectorAll('.card').length} documento(s)`);
  } catch (e) {
    if (e?.status === 401) {
      window.location.href = '/login.html';
      return;
    }
    const msg = String(e?.message || 'Falha ao carregar dados do kanban.');
    board.innerHTML = `<div class="panel"><b>Não foi possível carregar este projeto.</b><br/><span class="small">${msg}</span></div>`;
  }
}

[newBtn, refreshBtn, searchInput, statusFilter, priorityFilter, ownerFilter, sortOrderFilter].forEach(el => el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => render()));

if (projectSelect) {
  projectSelect.onchange = () => {
    const pid = projectSelect.value;
    if (!pid) return;
    window.location.href = `/kanban.html?project_id=${encodeURIComponent(pid)}`;
  };
}
if (pDependsSearch) {
  pDependsSearch.addEventListener('input', () => fillDependenciesOptions());
}

newBtn.onclick = () => { pName.value=''; pDescription.value=''; pOwner.value=''; pDueDate.value=''; if (pDocumentFile) pDocumentFile.value=''; createDependencySelected = new Set(); if (pDependsSearch) pDependsSearch.value = ''; fillDependenciesOptions(); dialog.showModal(); };
cancelDialogBtn.onclick = () => dialog.close();

form.onsubmit = async (e) => {
  e.preventDefault();
  try {
    const owner = (pOwner.value || '').trim();
    if (owner && !(state.users || []).includes(owner)) {
      alert('Responsável inválido. Selecione um usuário existente.');
      return;
    }
    const pid = currentProjectIdFromUrl();
    const name = (pName.value || '').trim();
    const depends_on = Array.from(createDependencySelected);
    const created = await api('/api/documents', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name, description:pDescription.value, status:pStatus.value, priority:pPriority.value, owner, dueDate:pDueDate.value, project_id: pid, depends_on })});

    let slug = created?.slug || '';

    // Fallback de robustez: garante persistência de dependências mesmo se algum browser
    // não refletir corretamente selectedOptions no submit.
    if (depends_on.length && slug) {
      await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}`), {
        method: 'PATCH',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ depends_on }),
      });
    }

    const file = pDocumentFile?.files?.[0];
    if (file) {

      // fallback para compatibilidade com backend sem retorno de slug
      if (!slug) {
        const docsData = await api(`/api/documents?project_id=${encodeURIComponent(String(pid))}`);
        const candidates = (docsData.documents || []).filter((d) => String(d.name || '').trim() === name);
        if (candidates.length) {
          candidates.sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')));
          slug = String(candidates[0].slug || '');
        }
      }

      if (!slug) {
        throw new Error('Documento criado, mas não foi possível identificar o slug para anexar o arquivo.');
      }

      const b64 = await fileToBase64(file);
      await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/document`), {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          fileName: file.name,
          mimeType: file.type || 'application/octet-stream',
          contentBase64: b64,
        }),
      });
    }

    dialog.close();
    render();
  } catch (e) { alert(e.message); }
};


(async () => {
  try {
    await loadMe();
    await render();
  } catch (e) {
    if (e?.status === 401) {
      window.location.href = '/login.html';
      return;
    }
    alert(e?.message || 'Falha ao iniciar kanban.');
  }
})();
