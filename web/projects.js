const usersLink = document.getElementById('usersLink');
const settingsLink = document.getElementById('settingsLink');
const whoami = document.getElementById('whoami');
const logoutBtn = document.getElementById('logoutBtn');

const projectId = document.getElementById('projectId');
const projectName = document.getElementById('projectName');
const startDate = document.getElementById('startDate');
const notes = document.getElementById('notes');
const feedback = document.getElementById('feedback');
const projectsList = document.getElementById('projectsList');

const newBtn = document.getElementById('newBtn');
const saveBtn = document.getElementById('saveBtn');
const deleteBtn = document.getElementById('deleteBtn');

let me = null;
let projects = [];

async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Erro na API');
  return data;
}

async function loadMe() {
  const d = await api('/api/me');
  me = d.user;
  whoami.textContent = `${me.username} (${me.role})`;
  usersLink.style.display = me.role === 'admin' ? 'block' : 'none';
  settingsLink.style.display = me.role === 'admin' ? 'block' : 'none';
  if (me.role !== 'admin') {
    alert('Acesso restrito a administradores.');
    window.location.href = '/';
  }
}

function setForm(p = null) {
  projectId.value = p?.project_id || '';
  projectName.value = p?.project_name || '';
  startDate.value = p?.start_date?.slice(0, 10) || '';
  notes.value = p?.notes || '';
  deleteBtn.disabled = !p;
}

function renderList() {
  if (!projects.length) {
    projectsList.textContent = 'Nenhum projeto cadastrado.';
    return;
  }
  projectsList.innerHTML = `<table>
    <tr><th>ID</th><th>Nome</th><th>Início</th></tr>
    ${projects.map(p => `<tr data-id="${p.project_id}"><td>${p.project_id}</td><td>${p.project_name}</td><td>${(p.start_date || '').slice(0,10)}</td></tr>`).join('')}
  </table>`;
  projectsList.querySelectorAll('tr[data-id]').forEach(tr => {
    tr.style.cursor = 'pointer';
    tr.onclick = () => {
      const id = Number(tr.dataset.id);
      const found = projects.find(x => x.project_id === id);
      setForm(found);
    };
  });
}

async function refresh() {
  const d = await api('/api/admin/projects');
  projects = d.projects || [];
  renderList();
}

newBtn.onclick = () => {
  feedback.textContent = '';
  setForm(null);
};

saveBtn.onclick = async () => {
  feedback.textContent = '';
  try {
    const payload = {
      project_name: projectName.value,
      start_date: startDate.value,
      notes: notes.value,
    };
    if (projectId.value) {
      await api(`/api/admin/projects/${projectId.value}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      feedback.textContent = 'Projeto atualizado ✅';
    } else {
      await api('/api/admin/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      feedback.textContent = 'Projeto criado ✅';
    }
    await refresh();
  } catch (e) {
    feedback.textContent = e.message;
  }
};

deleteBtn.onclick = async () => {
  if (!projectId.value) return;
  if (!confirm('Apagar este projeto?')) return;
  feedback.textContent = '';
  try {
    await api(`/api/admin/projects/${projectId.value}`, { method: 'DELETE' });
    feedback.textContent = 'Projeto apagado ✅';
    setForm(null);
    await refresh();
  } catch (e) {
    feedback.textContent = e.message;
  }
};

logoutBtn.onclick = async () => {
  await api('/api/logout', { method: 'POST' });
  window.location.href = '/login.html';
};

(async () => {
  try {
    await loadMe();
    await refresh();
    setForm(null);
  } catch {
    window.location.href = '/login.html';
  }
})();
