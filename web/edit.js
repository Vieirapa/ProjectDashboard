const slug = new URLSearchParams(location.search).get('slug');
const usersLink = document.getElementById('usersLink');
const whoami = document.getElementById('whoami');
const backBtn = document.getElementById('backBtn');
const logoutBtn = document.getElementById('logoutBtn');
const deleteBtn = document.getElementById('deleteBtn');
const feedback = document.getElementById('feedback');

const f = {
  name: document.getElementById('name'),
  description: document.getElementById('description'),
  status: document.getElementById('status'),
  priority: document.getElementById('priority'),
  owner: document.getElementById('owner'),
  dueDate: document.getElementById('dueDate'),
  path: document.getElementById('path'),
};

let me = null;

async function api(url, opts={}) {
  const r = await fetch(url, opts);
  const d = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(d.error || 'Erro');
  return d;
}

async function initMe() {
  const d = await api('/api/me');
  me = d.user;
  whoami.textContent = `${me.username} (${me.role})`;
  usersLink.style.display = me.role === 'admin' ? 'block' : 'none';
  deleteBtn.style.display = me.role === 'admin' ? 'inline-block' : 'none';
}

async function loadProject() {
  const d = await api(`/api/projects/${encodeURIComponent(slug)}`);
  const p = d.project;
  f.name.value = p.name; f.description.value = p.description; f.owner.value = p.owner; f.dueDate.value = p.dueDate; f.path.value = p.path;
  d.statuses.forEach(s => f.status.append(new Option(s,s))); f.status.value = p.status;
  d.priorities.forEach(x => f.priority.append(new Option(x,x))); f.priority.value = p.priority;
}

document.getElementById('editForm').onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api(`/api/projects/${encodeURIComponent(slug)}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      name:f.name.value, description:f.description.value, status:f.status.value, priority:f.priority.value, owner:f.owner.value, dueDate:f.dueDate.value
    })});
    feedback.textContent = 'Salvo com sucesso ✅';
  } catch (e) { feedback.textContent = e.message; }
};

deleteBtn.onclick = async () => {
  if (!confirm('Apagar este projeto do dashboard? (somente admin)')) return;
  try {
    await api(`/api/projects/${encodeURIComponent(slug)}`, {method:'DELETE'});
    location.href = '/';
  } catch (e) { feedback.textContent = e.message; }
};

backBtn.onclick = () => location.href = '/';
logoutBtn.onclick = async () => { await api('/api/logout',{method:'POST'}); location.href='/login.html'; };

(async () => {
  try { await initMe(); await loadProject(); } catch { location.href='/login.html'; }
})();
