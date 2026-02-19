const params = new URLSearchParams(window.location.search);
const slug = params.get('slug');

const form = document.getElementById('editForm');
const backBtn = document.getElementById('backBtn');
const logoutBtn = document.getElementById('logoutBtn');
const feedback = document.getElementById('feedback');

const fields = {
  name: document.getElementById('name'),
  description: document.getElementById('description'),
  status: document.getElementById('status'),
  priority: document.getElementById('priority'),
  owner: document.getElementById('owner'),
  dueDate: document.getElementById('dueDate'),
  path: document.getElementById('path'),
};

async function requireAuth() {
  const res = await fetch('/api/me');
  if (!res.ok) window.location.href = '/login.html';
}

function fillSelect(select, values, current) {
  select.innerHTML = '';
  values.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v;
    if (v === current) opt.selected = true;
    select.appendChild(opt);
  });
}

async function loadProject() {
  if (!slug) {
    feedback.textContent = 'Projeto inválido.';
    return;
  }

  const res = await fetch(`/api/projects/${encodeURIComponent(slug)}`);
  const data = await res.json();
  if (!res.ok || !data.ok) {
    feedback.textContent = data.error || 'Erro ao carregar projeto';
    return;
  }

  const p = data.project;
  fields.name.value = p.name || '';
  fields.description.value = p.description || '';
  fillSelect(fields.status, data.statuses, p.status);
  fillSelect(fields.priority, data.priorities, p.priority);
  fields.owner.value = p.owner || '';
  fields.dueDate.value = p.dueDate || '';
  fields.path.value = p.path || '';
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  feedback.textContent = '';

  const payload = {
    name: fields.name.value,
    description: fields.description.value,
    status: fields.status.value,
    priority: fields.priority.value,
    owner: fields.owner.value,
    dueDate: fields.dueDate.value,
  };

  const res = await fetch(`/api/projects/${encodeURIComponent(slug)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (!res.ok || !data.ok) {
    feedback.textContent = data.error || 'Erro ao salvar';
    return;
  }

  feedback.textContent = 'Alterações salvas com sucesso ✅';
});

backBtn.addEventListener('click', () => window.location.href = '/');
logoutBtn.addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST' });
  window.location.href = '/login.html';
});

(async function init() {
  await requireAuth();
  await loadProject();
})();
