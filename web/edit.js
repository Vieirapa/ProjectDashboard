const params = new URLSearchParams(location.search);
const slug = params.get('slug');

function currentProjectId() {
  const pid = Number(new URLSearchParams(location.search).get('project_id'));
  return Number.isFinite(pid) && pid > 0 ? pid : 1;
}

function withProjectId(url) {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}project_id=${encodeURIComponent(String(currentProjectId()))}`;
}
const backBtn = document.getElementById('backBtn');
const logoutBtn = document.getElementById('logoutBtn');
const deleteBtn = document.getElementById('deleteBtn');
const feedback = document.getElementById('feedback');
const formEl = document.getElementById('editForm');
const saveBtn = document.getElementById('saveBtn');
const reviewNoteInput = document.getElementById('reviewNoteInput');
const addReviewNoteBtn = document.getElementById('addReviewNoteBtn');
const reviewNotesHistory = document.getElementById('reviewNotesHistory');
const ownersList = document.getElementById('ownersList');
const dependsOnSelect = document.getElementById('dependsOn');
const dependsSearch = document.getElementById('dependsSearch');
const dependencyInfo = document.getElementById('dependencyInfo');

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
let doc = null;
let isDirty = false;
let isSaving = false;
let scopeBlocked = false;
let dependencyDocs = [];
let dependencySelected = new Set();
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
  return ['admin', 'lider_projeto', 'member', 'desenhista', 'colaborador'].includes(me?.role || '');
}

function canUploadDocument() {
  return ['admin', 'lider_projeto', 'member', 'desenhista', 'colaborador'].includes(me?.role || '');
}

function canAddReviewNotes() {
  return ['admin', 'lider_projeto', 'member', 'desenhista', 'colaborador', 'revisor'].includes(me?.role || '');
}

function getMultiSelectedValues(containerEl) {
  if (!containerEl) return [];
  return Array.from(containerEl.querySelectorAll('input[type="checkbox"][data-dep-slug]:checked'))
    .map((el) => String(el.getAttribute('data-dep-slug') || '').trim())
    .filter(Boolean);
}

function canDeleteCard() {
  if (!doc || !me) return false;
  if (['admin', 'lider_projeto'].includes(me.role)) return true;
  if (me.role === 'member') return (doc.createdBy || '').toLowerCase() === (me.username || '').toLowerCase();
  return false;
}

function setDirty(v) {
  isDirty = !!v;
  saveBtn.disabled = scopeBlocked || !isDirty || isSaving || !canEditCard();
}

function setScopeBlocked(message) {
  scopeBlocked = true;
  isSaving = false;
  isDirty = false;
  [f.name, f.description, f.status, f.priority, f.owner, f.dueDate, f.documentFile, reviewNoteInput, addReviewNoteBtn, deleteBtn, saveBtn].forEach((el) => {
    if (!el) return;
    el.disabled = true;
  });
  feedback.textContent = message || 'Escopo inválido para este documento.';
}

async function initMe() {
  const d = await api('/api/me');
  me = d.user;
  deleteBtn.style.display = 'none';
}

function canEditReviewNotes() {
  return canAddReviewNotes() && (f.status.value || '').trim().toLowerCase() === 'em revisão';
}

function canResolveReviewNotes() {
  return ['desenhista', 'colaborador', 'admin', 'lider_projeto'].includes(me?.role || '') && (f.status.value || '').trim().toLowerCase() === 'em revisão';
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
  const d = await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/review-notes`));
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
          <input type="checkbox" class="review-note-resolve" data-note-id="${n.id}" ${resolved ? 'checked' : ''} ${!canResolve ? 'disabled' : ''} />
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
      const nextResolved = !!input.checked;
      try {
        await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/review-notes/${encodeURIComponent(input.dataset.noteId)}`), {
          method: 'PATCH',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ resolved: nextResolved })
        });
        feedback.textContent = nextResolved
          ? 'Item de revisão marcado como resolvido ✅'
          : 'Item de revisão retornou para pendente ↩️';
        await loadReviewNotes();
      } catch (err) {
        input.checked = !nextResolved;
        feedback.textContent = err.message;
      }
    });
  });
}

async function loadVersions() {
  try {
    const d = await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/document/versions`));
    if (!d.versions?.length) {
      f.documentVersions.textContent = 'Sem revisões ainda.';
      return;
    }
    const items = d.versions.map(v => `<li><a href="/api/documents/${encodeURIComponent(slug)}/document?version=${v.version}&project_id=${encodeURIComponent(String(currentProjectId()))}" target="_blank">r${v.version}</a> · ${v.document_status} · ${v.document_name} · usuário: ${v.created_by || '-'} · ${new Date(v.created_at).toLocaleString('pt-BR')}</li>`).join('');
    f.documentVersions.innerHTML = `<ul>${items}</ul>`;
  } catch (e) {
    if (e?.status === 404) {
      f.documentVersions.textContent = 'Histórico indisponível (reinicie o backend para ativar controle de revisões).';
      return;
    }
    throw e;
  }
}

function renderDependencyChecklist() {
  if (!dependsOnSelect) return;
  const q = String(dependsSearch?.value || '').trim().toLowerCase();
  const shown = dependencyDocs.filter((d) => {
    if (!q) return true;
    const hay = `${d.name || ''} ${d.status || ''}`.toLowerCase();
    return hay.includes(q);
  });

  if (!shown.length) {
    dependsOnSelect.innerHTML = '<div class="deps-empty">Nenhum card encontrado.</div>';
    return;
  }

  dependsOnSelect.innerHTML = shown
    .map((d) => `
      <label class="small">
        <input type="checkbox" data-dep-slug="${String(d.slug)}" ${dependencySelected.has(String(d.slug)) ? 'checked' : ''} /> ${d.name} [${d.status}]
      </label>
    `)
    .join('');

  Array.from(dependsOnSelect.querySelectorAll('input[type="checkbox"][data-dep-slug]')).forEach((el) => {
    el.addEventListener('change', () => {
      const slug = String(el.getAttribute('data-dep-slug') || '');
      if (!slug) return;
      if (el.checked) dependencySelected.add(slug);
      else dependencySelected.delete(slug);
      setDirty(true);
    });
  });
}

async function loadDependencyOptions(currentSlug, selected = []) {
  if (!dependsOnSelect) return;
  const data = await api(`/api/documents?project_id=${encodeURIComponent(String(currentProjectId()))}`);
  dependencyDocs = (data.documents || [])
    .filter((d) => String(d.slug) !== String(currentSlug))
    .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'pt-BR'));
  dependencySelected = new Set((selected || []).map((s) => String(s || '').trim()).filter(Boolean));
  renderDependencyChecklist();
}

function renderDependencyInfo(document) {
  if (!dependencyInfo) return;
  const deps = Array.isArray(document?.dependencies) ? document.dependencies : [];
  if (!deps.length) {
    dependencyInfo.textContent = 'Sem dependências.';
    return;
  }
  const pending = deps.filter((d) => String(d.status || '') !== 'Concluído');
  if (!pending.length) {
    dependencyInfo.textContent = `Dependências: ${deps.length} (todas concluídas ✅)`;
    return;
  }
  dependencyInfo.textContent = `Dependências pendentes: ${pending.map((d) => d.name).join(', ')}`;
}

async function loadDocument() {
  const d = await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}`));
  const p = d.document;
  doc = p;
  if (Number(p.projectId || 0) !== Number(currentProjectId())) {
    setScopeBlocked(`Escopo inválido: documento pertence ao projeto ${p.projectId}, mas a URL está no projeto ${currentProjectId()}.`);
    return;
  }
  f.name.value = p.name; f.description.value = p.description; f.owner.value = p.owner; f.dueDate.value = p.dueDate;
  f.documentName.value = p.documentName || 'Sem anexo';
  d.statuses.forEach(s => f.status.append(new Option(s,s))); f.status.value = p.status;
  d.priorities.forEach(x => f.priority.append(new Option(x,x))); f.priority.value = p.priority;
  ownersList.innerHTML = '';
  (d.users || []).forEach(u => ownersList.append(new Option(u, u)));

  const editable = canEditCard();
  [f.name, f.description, f.status, f.priority, f.owner, f.dueDate].forEach((el) => el.disabled = !editable);
  if (dependsOnSelect) {
    Array.from(dependsOnSelect.querySelectorAll('input[type="checkbox"]')).forEach((el) => {
      el.disabled = !editable;
    });
  }
  f.documentFile.disabled = !canUploadDocument();
  deleteBtn.style.display = canDeleteCard() ? 'inline-block' : 'none';

  if (dependsSearch) dependsSearch.value = '';
  await loadDependencyOptions(slug, p.dependsOn || []);
  renderDependencyInfo(p);

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
if (dependsSearch) {
  dependsSearch.addEventListener('input', () => renderDependencyChecklist());
}
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
  location.href = `/kanban.html?project_id=${encodeURIComponent(String(currentProjectId()))}`;
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
    await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/review-notes`), {
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
  if (scopeBlocked) {
    feedback.textContent = 'Bloqueado por escopo inválido. Volte ao Kanban e abra o card no projeto correto.';
    return;
  }
  if (!canEditCard()) return;
  if (!isDirty) return;
  isSaving = true;
  saveBtn.disabled = true;
  try {
    const owner = (f.owner.value || '').trim();
    const validOwners = Array.from(ownersList.options).map(o => o.value);
    if (owner && !validOwners.includes(owner)) {
      feedback.textContent = 'Responsável inválido. Selecione um usuário existente.';
      isSaving = false;
      saveBtn.disabled = !isDirty;
      return;
    }

    const depends_on = Array.from(dependencySelected);

    await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}`), {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      name:f.name.value, description:f.description.value, status:f.status.value, priority:f.priority.value, owner, dueDate:f.dueDate.value, depends_on,
    })});

    const file = f.documentFile.files?.[0];
    if (file) {
      const b64 = await fileToBase64(file);
      await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}/document`), {
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
    location.href = `/kanban.html?project_id=${encodeURIComponent(String(currentProjectId()))}`;
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
  if (!confirm('Apagar este documento do dashboard? (somente admin)')) return;
  try {
    await api(withProjectId(`/api/documents/${encodeURIComponent(slug)}`), {method:'DELETE'});
    location.href = `/kanban.html?project_id=${encodeURIComponent(String(currentProjectId()))}`;
  } catch (e) { feedback.textContent = e.message; }
};

(async () => {
  try {
    await initMe();
    await loadDocument();
  } catch (e) {
    if (e?.status === 401) {
      location.href = '/login.html';
      return;
    }
    const msg = `Falha ao abrir edição: ${e.message || 'erro inesperado'}`;
    if (e?.status === 409 || String(e?.message || '').toLowerCase().includes('escopo inválido')) {
      setScopeBlocked(msg);
      return;
    }
    feedback.textContent = msg;
  }
})();
