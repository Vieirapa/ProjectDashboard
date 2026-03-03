const slug = new URLSearchParams(location.search).get('slug');
const usersLink = document.getElementById('usersLink');
const whoami = document.getElementById('whoami');
const backBtn = document.getElementById('backBtn');
const logoutBtn = document.getElementById('logoutBtn');
const deleteBtn = document.getElementById('deleteBtn');
const feedback = document.getElementById('feedback');
const formEl = document.getElementById('editForm');
const saveBtn = document.getElementById('saveBtn');
const reviewNoteInput = document.getElementById('reviewNoteInput');
const addReviewNoteBtn = document.getElementById('addReviewNoteBtn');
const reviewNotesHistory = document.getElementById('reviewNotesHistory');

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
let project = null;
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

function canEditCard() {
  return ['admin', 'member', 'desenhista'].includes(me?.role || '');
}

function canUploadDocument() {
  return ['admin', 'member', 'desenhista'].includes(me?.role || '');
}

function canAddReviewNotes() {
  return ['admin', 'member', 'desenhista', 'revisor'].includes(me?.role || '');
}

function canDeleteCard() {
  if (!project || !me) return false;
  if (me.role === 'admin') return true;
  if (me.role === 'member') return (project.createdBy || '').toLowerCase() === (me.username || '').toLowerCase();
  return false;
}

function setDirty(v) {
  isDirty = !!v;
  saveBtn.disabled = !isDirty || isSaving || !canEditCard();
}

async function initMe() {
  const d = await api('/api/me');
  me = d.user;
  whoami.textContent = `${me.username} (${me.role})`;
  usersLink.style.display = me.role === 'admin' ? 'block' : 'none';
  deleteBtn.style.display = 'none';
}

function canEditReviewNotes() {
  return canAddReviewNotes() && (f.status.value || '').trim().toLowerCase() === 'em revisão';
}

function canResolveReviewNotes() {
  return ['desenhista', 'admin'].includes(me?.role || '') && (f.status.value || '').trim().toLowerCase() === 'em revisão';
}

function updateReviewNotesAvailability() {
  const enabled = canEditReviewNotes();
  reviewNoteInput.disabled = !enabled;
  addReviewNoteBtn.disabled = !enabled;
  reviewNoteInput.placeholder = enabled
    ? 'Descreva o ajuste solicitado na revisão...'
    : 'Notas liberadas apenas quando o documento estiver em "em revisão"';
}

async function loadReviewNotes() {
  const d = await api(`/api/projects/${encodeURIComponent(slug)}/review-notes`);
  if (!d.notes?.length) {
    reviewNotesHistory.textContent = 'Sem notas registradas.';
    return;
  }

  const canResolve = canResolveReviewNotes();
  reviewNotesHistory.innerHTML = d.notes.map((n) => {
    const resolved = Number(n.is_resolved || 0) === 1;
    const createdAt = n.created_at ? new Date(n.created_at).toLocaleString('pt-BR') : '-';
    const resolvedAt = n.resolved_at ? new Date(n.resolved_at).toLocaleString('pt-BR') : '-';
    return `
      <div class="note-item" style="margin-bottom:8px; padding:8px; border:1px solid #ddd; border-radius:8px;">
        <label style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
          <input type="checkbox" class="review-note-resolve" data-note-id="${n.id}" ${resolved ? 'checked' : ''} ${(!canResolve || resolved) ? 'disabled' : ''} />
          <b>${resolved ? 'RESOLVIDO' : 'PENDENTE'}</b>
        </label>
        <div><b>usuário:</b> ${n.created_by} <span style="float:right"><b>criado em:</b> ${createdAt}</span></div>
        <div style="white-space:pre-wrap; margin-top:4px;">${n.note}</div>
        <div style="margin-top:6px;"><b>resolvido por:</b> ${n.resolved_by || '-'} <span style="float:right"><b>resolvido em:</b> ${resolvedAt}</span></div>
      </div>
    `;
  }).join('');

  reviewNotesHistory.querySelectorAll('.review-note-resolve').forEach((checkbox) => {
    checkbox.addEventListener('change', async (e) => {
      const input = e.currentTarget;
      if (!input.checked) {
        input.checked = true;
        return;
      }
      try {
        await api(`/api/projects/${encodeURIComponent(slug)}/review-notes/${encodeURIComponent(input.dataset.noteId)}`, {
          method: 'PATCH',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ resolved: true })
        });
        feedback.textContent = 'Item de revisão marcado como resolvido ✅';
        await loadReviewNotes();
      } catch (err) {
        input.checked = false;
        feedback.textContent = err.message;
      }
    });
  });
}

async function loadVersions() {
  try {
    const d = await api(`/api/projects/${encodeURIComponent(slug)}/document/versions`);
    if (!d.versions?.length) {
      f.documentVersions.textContent = 'Sem revisões ainda.';
      return;
    }
    const items = d.versions.map(v => `<li><a href="/api/projects/${encodeURIComponent(slug)}/document?version=${v.version}" target="_blank">r${v.version}</a> · ${v.document_status} · ${v.document_name} · usuário: ${v.created_by || '-'} · ${new Date(v.created_at).toLocaleString('pt-BR')}</li>`).join('');
    f.documentVersions.innerHTML = `<ul>${items}</ul>`;
  } catch (e) {
    if (e?.status === 404) {
      f.documentVersions.textContent = 'Histórico indisponível (reinicie o backend para ativar controle de revisões).';
      return;
    }
    throw e;
  }
}

async function loadProject() {
  const d = await api(`/api/projects/${encodeURIComponent(slug)}`);
  const p = d.project;
  project = p;
  f.name.value = p.name; f.description.value = p.description; f.owner.value = p.owner; f.dueDate.value = p.dueDate;
  f.documentName.value = p.documentName || 'Sem anexo';
  d.statuses.forEach(s => f.status.append(new Option(s,s))); f.status.value = p.status;
  d.priorities.forEach(x => f.priority.append(new Option(x,x))); f.priority.value = p.priority;

  const editable = canEditCard();
  [f.name, f.description, f.status, f.priority, f.owner, f.dueDate].forEach((el) => el.disabled = !editable);
  f.documentFile.disabled = !canUploadDocument();
  deleteBtn.style.display = canDeleteCard() ? 'inline-block' : 'none';

  updateReviewNotesAvailability();
  await loadVersions();
  await loadReviewNotes();
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

[f.name, f.description, f.status, f.priority, f.owner, f.dueDate].forEach((el) => {
  el.addEventListener('input', () => setDirty(true));
  el.addEventListener('change', () => setDirty(true));
});
f.documentFile.addEventListener('change', () => setDirty(true));
f.status.addEventListener('change', () => updateReviewNotesAvailability());

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
    await api(`/api/projects/${encodeURIComponent(slug)}/review-notes`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ note })
    });
    reviewNoteInput.value = '';
    await loadReviewNotes();
    feedback.textContent = 'Nota adicionada ✅';
  } catch (e) {
    feedback.textContent = e.message;
  }
};

async function handleSave() {
  if (!canEditCard()) return;
  if (!isDirty) return;
  isSaving = true;
  saveBtn.disabled = true;
  try {
    await api(`/api/projects/${encodeURIComponent(slug)}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      name:f.name.value, description:f.description.value, status:f.status.value, priority:f.priority.value, owner:f.owner.value, dueDate:f.dueDate.value,
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
}

formEl.addEventListener('submit', (e) => {
  e.preventDefault();
});

saveBtn.onclick = handleSave;

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
