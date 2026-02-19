const board = document.getElementById('board');
const refreshBtn = document.getElementById('refreshBtn');
const newBtn = document.getElementById('newBtn');
const logoutBtn = document.getElementById('logoutBtn');

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

let state = { projects: [], statuses: [], priorities: [] };

async function requireAuth() {
  const res = await fetch('/api/me');
  if (!res.ok) {
    window.location.href = '/login.html';
    return false;
  }
  return true;
}

async function fetchData() {
  const res = await fetch('/api/projects');
  if (!res.ok) throw new Error('Falha ao carregar projetos');
  return res.json();
}

async function createProject(payload) {
  const res = await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || 'Erro ao criar projeto');
}

async function patchProject(slug, payload) {
  const res = await fetch(`/api/projects/${encodeURIComponent(slug)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || 'Erro ao editar projeto');
}

function makeColumn(status) {
  const col = document.createElement('div');
  col.className = 'column';
  col.dataset.status = status;

  const title = document.createElement('h2');
  title.textContent = status;
  col.appendChild(title);

  const info = document.createElement('div');
  info.className = 'small';
  info.textContent = '0 projetos';
  col.appendChild(info);

  return col;
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

function makeMeta(project) {
  const wrap = document.createElement('div');
  wrap.className = 'meta';
  wrap.innerHTML = `Prioridade: <b>${project.priority || 'Média'}</b><br/>Responsável: <b>${project.owner || '-'}</b><br/>Prazo: <b>${project.dueDate || '-'}</b>`;
  return wrap;
}

function makeCard(project, statuses, priorities) {
  const card = document.createElement('div');
  card.className = 'card';

  const title = document.createElement('h3');
  title.textContent = project.name;
  card.appendChild(title);

  const desc = document.createElement('p');
  desc.textContent = project.description || 'Sem descrição';
  card.appendChild(desc);

  card.appendChild(makeMeta(project));

  const statusSelect = document.createElement('select');
  for (const st of statuses) {
    const opt = document.createElement('option');
    opt.value = st;
    opt.textContent = st;
    if (st === project.status) opt.selected = true;
    statusSelect.appendChild(opt);
  }

  statusSelect.addEventListener('change', async () => {
    const oldValue = project.status;
    try {
      await patchProject(project.slug, { status: statusSelect.value });
      project.status = statusSelect.value;
      await render();
    } catch (err) {
      alert(err.message);
      statusSelect.value = oldValue;
    }
  });

  const prioritySelect = document.createElement('select');
  for (const p of priorities) {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = `Prioridade: ${p}`;
    if (p === project.priority) opt.selected = true;
    prioritySelect.appendChild(opt);
  }

  prioritySelect.addEventListener('change', async () => {
    const oldValue = project.priority;
    try {
      await patchProject(project.slug, { priority: prioritySelect.value });
      project.priority = prioritySelect.value;
      await render();
    } catch (err) {
      alert(err.message);
      prioritySelect.value = oldValue;
    }
  });

  const actions = document.createElement('div');
  actions.className = 'card-actions';

  const editBtn = document.createElement('button');
  editBtn.className = 'secondary';
  editBtn.textContent = 'Editar';
  editBtn.addEventListener('click', () => {
    window.location.href = `/edit.html?slug=${encodeURIComponent(project.slug)}`;
  });

  const openBtn = document.createElement('button');
  openBtn.textContent = 'Copiar pasta';
  openBtn.addEventListener('click', () => {
    navigator.clipboard?.writeText(project.path);
    alert(`Caminho copiado:\n${project.path}`);
  });

  actions.appendChild(editBtn);
  actions.appendChild(openBtn);

  card.appendChild(statusSelect);
  card.appendChild(prioritySelect);
  card.appendChild(actions);
  return card;
}

function fillFilters(statuses, priorities) {
  if (statusFilter.options.length <= 1) {
    statuses.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = s;
      statusFilter.appendChild(opt);
    });
  }
  if (priorityFilter.options.length <= 1) {
    priorities.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = p;
      priorityFilter.appendChild(opt);
    });
  }
}

function fillDialogOptions(statuses, priorities) {
  pStatus.innerHTML = '';
  pPriority.innerHTML = '';
  statuses.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    pStatus.appendChild(opt);
  });
  priorities.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = p;
    pPriority.appendChild(opt);
  });
  pStatus.value = 'Backlog';
  pPriority.value = 'Média';
}

async function render() {
  state = await fetchData();
  fillFilters(state.statuses, state.priorities);
  fillDialogOptions(state.statuses, state.priorities);

  const filters = currentFilters();
  const visible = state.projects.filter(p => passesFilters(p, filters));

  board.innerHTML = '';
  const columns = new Map();
  for (const status of state.statuses) {
    const col = makeColumn(status);
    columns.set(status, col);
    board.appendChild(col);
  }

  visible
    .slice()
    .sort((a, b) => {
      const rank = { 'Urgente': 0, 'Alta': 1, 'Média': 2, 'Baixa': 3 };
      return (rank[a.priority] ?? 99) - (rank[b.priority] ?? 99);
    })
    .forEach(project => {
      const col = columns.get(project.status) || columns.get('Backlog');
      col.appendChild(makeCard(project, state.statuses, state.priorities));
    });

  for (const [, col] of columns) {
    const count = col.querySelectorAll('.card').length;
    col.querySelector('.small').textContent = `${count} projeto(s)`;
  }
}

[newBtn, refreshBtn, searchInput, statusFilter, priorityFilter, ownerFilter].forEach(el => {
  const eventName = el.tagName === 'INPUT' ? 'input' : 'change';
  el.addEventListener(eventName, () => render());
});

newBtn.addEventListener('click', () => {
  pName.value = '';
  pDescription.value = '';
  pOwner.value = '';
  pDueDate.value = '';
  dialog.showModal();
});

cancelDialogBtn.addEventListener('click', () => dialog.close());

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await createProject({
      name: pName.value,
      description: pDescription.value,
      status: pStatus.value,
      priority: pPriority.value,
      owner: pOwner.value,
      dueDate: pDueDate.value,
    });
    dialog.close();
    await render();
  } catch (err) {
    alert(err.message);
  }
});

logoutBtn.addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST' });
  window.location.href = '/login.html';
});

(async function init() {
  const ok = await requireAuth();
  if (!ok) return;
  render().catch((e) => {
    board.innerHTML = `<p style="color:red">Erro: ${e.message}</p>`;
  });
})();
