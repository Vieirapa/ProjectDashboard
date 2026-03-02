const slug = new URLSearchParams(location.search).get('slug');
const usersLink = document.getElementById('usersLink');
const whoami = document.getElementById('whoami');
const backBtn = document.getElementById('backBtn');
const logoutBtn = document.getElementById('logoutBtn');
const deleteBtn = document.getElementById('deleteBtn');
const feedback = document.getElementById('feedback');
const saveBtn = document.getElementById('saveBtn');

const f = {
  name: document.getElementById('name'),
  description: document.getElementById('description'),
  status: document.getElementById('status'),
  priority: document.getElementById('priority'),
  owner: document.getElementById('owner'),
  dueDate: document.getElementById('dueDate'),
  path: document.getElementById('path'),
  documentStatus: document.getElementById('documentStatus'),
  documentFile: document.getElementById('documentFile'),
  documentName: document.getElementById('documentName'),
  documentVersions: document.getElementById('documentVersions'),
};

let me = null;
let isDirty = false;
let isSaving = false;
saveBtn.disabled = true;

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

function setDirty(v) {
  isDirty = !!v;
  saveBtn.disabled = !isDirty || isSaving;
}

async function initMe() {
  const d = await api('/api/me');
  me = d.user;
  whoami.textContent = `${me.username} (${me.role})`;
  usersLink.style.display = me.role === 'admin' ? 'block' : 'none';
  deleteBtn.style.display = me.role === 'admin' ? 'inline-block' : 'none';
}

async function loadVersions() {
  try {
    const d = await api(`/api/projects/${encodeURIComponent(slug)}/document/versions`);
    if (!d.versions?.length) {
      f.documentVersions.textContent = 'Sem versões ainda.';
      return;
    }
    const items = d.versions.map(v => `<li><a href="/api/projects/${encodeURIComponent(slug)}/document?version=${v.version}" target="_blank">v${v.version}</a> · ${v.document_status} · ${v.document_name} · ${new Date(v.created_at).toLocaleString('pt-BR')}</li>`).join('');
    f.documentVersions.innerHTML = `<ul>${items}</ul>`;
  } catch (e) {
    if (e?.status === 404) {
      f.documentVersions.textContent = 'Histórico indisponível (reinicie o backend para ativar versionamento híbrido).';
      return;
    }
    throw e;
  }
}

async function loadProject() {
  const d = await api(`/api/projects/${encodeURIComponent(slug)}`);
  const p = d.project;
  f.name.value = p.name; f.description.value = p.description; f.owner.value = p.owner; f.dueDate.value = p.dueDate; f.path.value = p.path;
  f.documentName.value = p.documentName || 'Sem anexo';
  d.statuses.forEach(s => f.status.append(new Option(s,s))); f.status.value = p.status;
  d.priorities.forEach(x => f.priority.append(new Option(x,x))); f.priority.value = p.priority;
  const documentStatuses = d.documentStatuses || ['aguardando edição', 'editando', 'em revisão', 'release'];
  documentStatuses.forEach(x => f.documentStatus.append(new Option(x,x)));
  f.documentStatus.value = p.documentStatus || 'aguardando edição';
  await loadVersions();
  setDirty(false);
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

[f.name, f.description, f.status, f.priority, f.owner, f.dueDate, f.documentStatus].forEach((el) => {
  el.addEventListener('input', () => setDirty(true));
  el.addEventListener('change', () => setDirty(true));
});
f.documentFile.addEventListener('change', () => setDirty(true));

window.addEventListener('beforeunload', (e) => {
  if (!isDirty || isSaving) return;
  e.preventDefault();
  e.returnValue = '';
});

backBtn.onclick = () => {
  if (isDirty && !isSaving) {
    const leave = confirm('Você fez alterações que ainda não foram salvas. Se sair agora, elas serão perdidas. Deseja continuar?');
    if (!leave) return;
  }
  location.href = '/';
};

logoutBtn.onclick = async () => {
  if (isDirty && !isSaving) {
    const leave = confirm('Você fez alterações que ainda não foram salvas. Se sair agora, elas serão perdidas. Deseja continuar?');
    if (!leave) return;
  }
  await api('/api/logout',{method:'POST'});
  location.href='/login.html';
};

document.getElementById('editForm').onsubmit = async (e) => {
  e.preventDefault();
  if (!isDirty) return;
  isSaving = true;
  saveBtn.disabled = true;
  try {
    await api(`/api/projects/${encodeURIComponent(slug)}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      name:f.name.value, description:f.description.value, status:f.status.value, priority:f.priority.value, owner:f.owner.value, dueDate:f.dueDate.value,
      documentStatus: f.documentStatus.value,
    })});

    const file = f.documentFile.files?.[0];
    if (file) {
      const b64 = await fileToBase64(file);
      await api(`/api/projects/${encodeURIComponent(slug)}/document`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          fileName: file.name,
          mimeType: file.type || 'application/octet-stream',
          contentBase64: b64,
          documentStatus: f.documentStatus.value,
        })
      });
      f.documentName.value = file.name;
      f.documentFile.value = '';
    }

    await loadVersions();
    setDirty(false);
    feedback.textContent = 'Salvo com sucesso ✅';
    location.href = '/';
  } catch (e) {
    feedback.textContent = e.message;
    isSaving = false;
    saveBtn.disabled = !isDirty;
  }
};

deleteBtn.onclick = async () => {
  if (!confirm('Apagar este projeto do dashboard? (somente admin)')) return;
  try {
    await api(`/api/projects/${encodeURIComponent(slug)}`, {method:'DELETE'});
    location.href = '/';
  } catch (e) { feedback.textContent = e.message; }
};

(async () => {
  try {
    await initMe();
    await loadProject();
  } catch (e) {
    if (e?.status === 401) {
      location.href = '/login.html';
      return;
    }
    feedback.textContent = `Falha ao abrir edição: ${e.message || 'erro inesperado'}`;
  }
})();
