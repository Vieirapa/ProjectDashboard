const board = document.getElementById('board');
const refreshBtn = document.getElementById('refreshBtn');
const newBtn = document.getElementById('newBtn');
const logoutBtn = document.getElementById('logoutBtn');
const usersLink = document.getElementById('usersLink');
const whoami = document.getElementById('whoami');

const searchInput = document.getElementById('searchInput');
const statusFilter = document.getElementById('statusFilter');
const priorityFilter = document.getElementById('priorityFilter');
const ownerFilter = document.getElementById('ownerFilter');

const dialog = document.getElementById('projectDialog');
const form = document.getElementById('projectForm');
const cancelDialogBtn = document.getElementById('cancelDialogBtn');

const pName = document.getElementById('pName');
const pDescription = document.getElementById('pDescription');
const pStatus = document.getElementById('pStatus');
const pPriority = document.getElementById('pPriority');
const pOwner = document.getElementById('pOwner');
const pDueDate = document.getElementById('pDueDate');

let me = null;
let state = { projects: [], statuses: [], priorities: [] };

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
}

function currentFilters() {
  return {
    q: (searchInput.value || '').toLowerCase().trim(),
    status: statusFilter.value,
    priority: priorityFilter.value,
    owner: (ownerFilter.value || '').toLowerCase().trim(),
  };
}

function passesFilters(project, f) {
  if (f.status && project.status !== f.status) return false;
  if (f.priority && project.priority !== f.priority) return false;
  if (f.owner && !(project.owner || '').toLowerCase().includes(f.owner)) return false;
  const hay = `${project.name} ${project.description}`.toLowerCase();
  if (f.q && !hay.includes(f.q)) return false;
  return true;
}

function makeColumn(status) {
  const col = document.createElement('div');
  col.className = 'column';
  col.innerHTML = `<h2>${status}</h2><div class="small">0 projetos</div>`;
  col.dataset.status = status;
  return col;
}

function makeCard(p, statuses, priorities) {
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `
    <h3>${p.name}</h3>
    <p>${p.description || 'Sem descrição'}</p>
    <div class="meta">Prioridade: <b>${p.priority}</b><br/>Responsável: <b>${p.owner || '-'}</b><br/>Prazo: <b>${p.dueDate || '-'}</b></div>
  `;

  const st = document.createElement('select');
  statuses.forEach(s => { const o = document.createElement('option'); o.value = s; o.textContent = s; if (s === p.status) o.selected = true; st.appendChild(o); });
  st.onchange = async () => { await api(`/api/projects/${encodeURIComponent(p.slug)}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({status: st.value})}); render(); };

  const pr = document.createElement('select');
  priorities.forEach(x => { const o = document.createElement('option'); o.value = x; o.textContent = `Prioridade: ${x}`; if (x === p.priority) o.selected = true; pr.appendChild(o); });
  pr.onchange = async () => { await api(`/api/projects/${encodeURIComponent(p.slug)}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({priority: pr.value})}); render(); };

  const actions = document.createElement('div');
  actions.className = 'card-actions';
  actions.innerHTML = `<button class="secondary">Editar</button><button>Copiar pasta</button>`;
  actions.children[0].onclick = () => window.location.href = `/edit.html?slug=${encodeURIComponent(p.slug)}`;
  actions.children[1].onclick = async () => { await navigator.clipboard.writeText(p.path); alert('Caminho copiado!'); };

  card.append(st, pr, actions);
  return card;
}

function fillFilters(statuses, priorities) {
  if (statusFilter.options.length <= 1) statuses.forEach(s => statusFilter.append(new Option(s, s)));
  if (priorityFilter.options.length <= 1) priorities.forEach(p => priorityFilter.append(new Option(p, p)));
  pStatus.innerHTML = ''; pPriority.innerHTML = '';
  statuses.forEach(s => pStatus.append(new Option(s, s)));
  priorities.forEach(p => pPriority.append(new Option(p, p)));
  pStatus.value = 'Backlog'; pPriority.value = 'Média';
}

async function render() {
  state = await api('/api/projects');
  fillFilters(state.statuses, state.priorities);
  const filtered = state.projects.filter(p => passesFilters(p, currentFilters()));
  board.innerHTML = '';
  const cols = new Map(state.statuses.map(s => [s, makeColumn(s)]));
  cols.forEach(c => board.appendChild(c));

  filtered.sort((a,b) => ({Urgente:0,Alta:1,'Média':2,Baixa:3}[a.priority] - ({Urgente:0,Alta:1,'Média':2,Baixa:3}[b.priority])));
  filtered.forEach(p => (cols.get(p.status) || cols.get('Backlog')).appendChild(makeCard(p, state.statuses, state.priorities)));
  cols.forEach(c => c.querySelector('.small').textContent = `${c.querySelectorAll('.card').length} projeto(s)`);
}

[newBtn, refreshBtn, searchInput, statusFilter, priorityFilter, ownerFilter].forEach(el => el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', () => render()));

newBtn.onclick = () => { pName.value=''; pDescription.value=''; pOwner.value=''; pDueDate.value=''; dialog.showModal(); };
cancelDialogBtn.onclick = () => dialog.close();

form.onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api('/api/projects', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name:pName.value, description:pDescription.value, status:pStatus.value, priority:pPriority.value, owner:pOwner.value, dueDate:pDueDate.value })});
    dialog.close();
    render();
  } catch (e) { alert(e.message); }
};

logoutBtn.onclick = async () => { await api('/api/logout', {method:'POST'}); window.location.href = '/login.html'; };

(async () => {
  try { await loadMe(); await render(); } catch { window.location.href = '/login.html'; }
})();
