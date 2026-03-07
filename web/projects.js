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

const newBtn = document.getElementById('newBtn');
const saveBtn = document.getElementById('saveBtn');
const deleteBtn = document.getElementById('deleteBtn');

let me = null;
let projects = [];
let selectedProjectId = null;

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

function setAllowedRolesChecks(csvValue) {
  const set = new Set(String(csvValue || '').split(',').map(x => x.trim().toLowerCase()).filter(Boolean));
  const checks = allowedRolesBox?.querySelectorAll('.allowed-role') || [];
  checks.forEach((c) => {
    c.checked = set.size ? set.has(String(c.value || '').toLowerCase()) : true;
  });
}

function getAllowedRolesFromChecks() {
  const checks = allowedRolesBox?.querySelectorAll('.allowed-role:checked') || [];
  const vals = Array.from(checks).map((c) => String(c.value || '').trim().toLowerCase()).filter(Boolean);
  return vals.join(',') || 'member,desenhista,revisor,cliente';
}

async function loadMe() {
  const d = await api('/api/me');
  me = d.user;
  if (me.role !== 'admin') {
    alert('Acesso restrito a administradores.');
    window.location.href = '/';
  }
}

function setForm(p = null) {
  selectedProjectId = p?.project_id ? Number(p.project_id) : null;
  projectId.value = p?.project_id || '';
  projectName.value = p?.project_name || '';
  startDate.value = p?.start_date?.slice(0, 10) || '';
  isTemplate.checked = Boolean(p?.is_template);
  notes.value = p?.notes || '';
  setAllowedRolesChecks(p?.allowed_roles || 'member,desenhista,revisor,cliente');
  deleteBtn.disabled = !p;

  if (selectedProjectId) {
    const u = new URL(window.location.href);
    u.searchParams.set('project_id', String(selectedProjectId));
    window.history.replaceState({}, '', `${u.pathname}?${u.searchParams.toString()}`);
  }

  loadCardsForSelectedProject();
}

function renderList() {
  if (!projects.length) {
    projectsList.textContent = 'Nenhum projeto cadastrado.';
    return;
  }
  projectsList.innerHTML = `<table>
    <tr><th>ID</th><th>Nome</th><th>Início</th><th>Roles</th></tr>
    ${projects.map(p => `<tr data-id="${p.project_id}"><td>${p.project_id}</td><td>${esc(p.project_name)}${p.is_template ? ' <span class="template-chip">Template</span>' : ''}</td><td>${esc((p.start_date || '').slice(0,10))}</td><td>${esc(p.allowed_roles || '')}</td></tr>`).join('')}
  </table>`;
  projectsList.querySelectorAll('tr[data-id]').forEach(tr => {
    tr.style.cursor = 'pointer';
    tr.onclick = () => {
      const id = Number(tr.dataset.id);
      const found = projects.find(x => Number(x.project_id) === id);
      setForm(found || null);
    };
  });
}

async function loadCardsForSelectedProject() {
  if (!selectedProjectId) {
    projectCardsList.textContent = 'Selecione um projeto para listar os cards.';
    return;
  }
  try {
    const d = await api(`/api/documents?project_id=${encodeURIComponent(String(selectedProjectId))}`);
    const docs = d.documents || [];
    if (!docs.length) {
      projectCardsList.textContent = 'Nenhum card neste projeto.';
      return;
    }

    projectCardsList.innerHTML = `<table>
      <tr><th>Nome</th><th>Slug</th><th>Criado em</th><th>Status</th><th>Responsável</th><th>Ações</th></tr>
      ${docs.map(doc => `
        <tr data-slug="${esc(doc.slug)}">
          <td>${esc(doc.name)}</td>
          <td>${esc(doc.slug)}</td>
          <td>${esc(fmtDate(doc.openedAt || doc.updatedAt))}</td>
          <td>${esc(doc.status || '-')}</td>
          <td>${esc(doc.owner || '-')}</td>
          <td><button type="button" class="danger card-delete-btn" data-slug="${esc(doc.slug)}">Excluir</button></td>
        </tr>
      `).join('')}
    </table>`;

    projectCardsList.querySelectorAll('.card-delete-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const slug = btn.dataset.slug;
        if (!slug) return;
        if (!confirm(`Apagar o card "${slug}" deste projeto?`)) return;
        try {
          await api(`/api/documents/${encodeURIComponent(slug)}?project_id=${encodeURIComponent(String(selectedProjectId))}`, { method: 'DELETE' });
          feedback.textContent = `Card ${slug} apagado ✅`;
          await loadCardsForSelectedProject();
        } catch (e) {
          feedback.textContent = e.message;
        }
      });
    });
  } catch (e) {
    projectCardsList.textContent = `Falha ao carregar cards: ${e.message || e}`;
  }
}

async function refresh(preferredId = null) {
  const d = await api('/api/admin/projects');
  projects = d.projects || [];
  renderList();

  const qsId = Number(new URLSearchParams(window.location.search).get('project_id'));
  const targetId = Number(preferredId || selectedProjectId || (Number.isFinite(qsId) && qsId > 0 ? qsId : 0));
  const found = projects.find((p) => Number(p.project_id) === Number(targetId));
  if (found) {
    setForm(found);
  } else {
    setForm(null);
  }
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
      feedback.textContent = 'Projeto atualizado ✅';
    } else {
      await api('/api/admin/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      feedback.textContent = 'Projeto criado ✅';
    }
    await refresh(preserveId);
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
  } catch {
    window.location.href = '/login.html';
  }
})();
