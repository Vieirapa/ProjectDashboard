const board = document.getElementById('board');
const refreshBtn = document.getElementById('refreshBtn');
const newBtn = document.getElementById('newBtn');
const logoutBtn = document.getElementById('logoutBtn');
const usersLink = document.getElementById('usersLink');
const settingsLink = document.getElementById('settingsLink');
const whoami = document.getElementById('whoami');

const searchInput = document.getElementById('searchInput');
const statusFilter = document.getElementById('statusFilter');
const priorityFilter = document.getElementById('priorityFilter');
const ownerFilter = document.getElementById('ownerFilter');
const sortOrderFilter = document.getElementById('sortOrderFilter');

const dialog = document.getElementById('documentDialog');
const form = document.getElementById('documentForm');
const cancelDialogBtn = document.getElementById('cancelDialogBtn');

const pName = document.getElementById('pName');
const pDescription = document.getElementById('pDescription');
const pStatus = document.getElementById('pStatus');
const pPriority = document.getElementById('pPriority');
const pOwner = document.getElementById('pOwner');
const pDueDate = document.getElementById('pDueDate');
const ownersList = document.getElementById('ownersList');

let me = null;
let state = { documents: [], statuses: [], priorities: [] };

async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Erro na API');
  return data;
}

async function loadMe() {
  const data = await api('/api/me');
  me = data.user;
  whoami.textContent = `${me.username} (${me.role})`;
  usersLink.style.display = me.role === 'admin' ? 'block' : 'none';
  settingsLink.style.display = me.role === 'admin' ? 'block' : 'none';
  newBtn.style.display = canCreateCard() ? 'inline-block' : 'none';
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
  return ['admin', 'member'].includes(me?.role || '');
}

function canEditCard() {
  return ['admin', 'member', 'desenhista'].includes(me?.role || '');
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

  const st = document.createElement('select');
  statuses.forEach(s => { const o = document.createElement('option'); o.value = s; o.textContent = s; if (s === p.status) o.selected = true; st.appendChild(o); });
  st.disabled = !canEditCard();
  st.onchange = async () => { await api(`/api/documents/${encodeURIComponent(p.slug)}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({status: st.value})}); render(); };

  const pr = document.createElement('select');
  priorities.forEach(x => { const o = document.createElement('option'); o.value = x; o.textContent = `Prioridade: ${x}`; if (x === p.priority) o.selected = true; pr.appendChild(o); });
  pr.disabled = !canEditCard();
  pr.onchange = async () => { await api(`/api/documents/${encodeURIComponent(p.slug)}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({priority: pr.value})}); render(); };

  const controls = document.createElement('div');
  controls.className = 'card-controls';

  const selectsWrap = document.createElement('div');
  selectsWrap.className = 'card-selects';

  const detailsBtn = document.createElement('button');
  detailsBtn.className = 'secondary details-btn';
  detailsBtn.textContent = 'Detalhes';
  detailsBtn.onclick = () => window.location.href = `/edit.html?slug=${encodeURIComponent(p.slug)}`;

  selectsWrap.append(st, pr, detailsBtn);

  const docBtn = document.createElement('button');
  docBtn.className = `doc-btn ${docMeta.cls}`;
  docBtn.title = `${docMeta.label}${p.documentName ? ` · ${p.documentName}` : ''}`;
  docBtn.innerHTML = `<span class="doc-main">📄</span><span class="doc-state">${docMeta.icon}</span>`;
  docBtn.onclick = () => {
    if (!p.hasDocument) return alert('Este documento ainda não tem anexo.');
    window.open(`/api/documents/${encodeURIComponent(p.slug)}/document`, '_blank');
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

async function render() {
  state = await api('/api/documents');
  fillFilters(state.statuses, state.priorities, state.users || []);
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
}

[newBtn, refreshBtn, searchInput, statusFilter, priorityFilter, ownerFilter, sortOrderFilter].forEach(el => el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => render()));

newBtn.onclick = () => { pName.value=''; pDescription.value=''; pOwner.value=''; pDueDate.value=''; dialog.showModal(); };
cancelDialogBtn.onclick = () => dialog.close();

form.onsubmit = async (e) => {
  e.preventDefault();
  try {
    const owner = (pOwner.value || '').trim();
    if (owner && !(state.users || []).includes(owner)) {
      alert('Responsável inválido. Selecione um usuário existente.');
      return;
    }
    await api('/api/documents', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name:pName.value, description:pDescription.value, status:pStatus.value, priority:pPriority.value, owner, dueDate:pDueDate.value })});
    dialog.close();
    render();
  } catch (e) { alert(e.message); }
};

logoutBtn.onclick = async () => { await api('/api/logout', {method:'POST'}); window.location.href = '/login.html'; };

(async () => {
  try { await loadMe(); await render(); } catch { window.location.href = '/login.html'; }
})();
