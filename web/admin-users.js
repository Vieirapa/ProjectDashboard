const usersList = document.getElementById('usersList');
const auditList = document.getElementById('auditList');
const logoutBtn = document.getElementById('logoutBtn');
const inviteOut = document.getElementById('inviteOut');
const adminUsersFeedback = document.getElementById('adminUsersFeedback');
const adminUsersCount = document.getElementById('adminUsersCount');
const adminAdminsCount = document.getElementById('adminAdminsCount');
const adminAuditCount = document.getElementById('adminAuditCount');
const usersSearchInput = document.getElementById('usersSearchInput');
const usersFilteredCount = document.getElementById('usersFilteredCount');
const auditSearchInput = document.getElementById('auditSearchInput');
const auditFilteredCount = document.getElementById('auditFilteredCount');

function escHtml(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function copyText(text) {
  const raw = String(text || '').trim();
  if (!raw) return false;
  try {
    await navigator.clipboard.writeText(raw);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = raw;
    ta.setAttribute('readonly', 'readonly');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    ta.style.pointerEvents = 'none';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    ta.remove();
    return ok;
  }
}


function setAdminFeedback(message, tone = 'neutral') {
  if (!adminUsersFeedback) return;
  const safeTone = ['neutral', 'success', 'warning', 'danger'].includes(tone) ? tone : 'neutral';
  adminUsersFeedback.className = `settings-inline-feedback status-${safeTone} admin-users-feedback`;
  adminUsersFeedback.innerHTML = `<strong>Status</strong><span>${escHtml(message || 'Sem atualizações no momento.')}</span>`;
}

const adminUsersDialog = document.getElementById('adminUsersDialog');
const adminUsersDialogTitle = document.getElementById('adminUsersDialogTitle');
const adminUsersDialogMessage = document.getElementById('adminUsersDialogMessage');
const adminUsersDialogEyebrow = document.getElementById('adminUsersDialogEyebrow');
const adminUsersDialogInputWrap = document.getElementById('adminUsersDialogInputWrap');
const adminUsersDialogInputLabel = document.getElementById('adminUsersDialogInputLabel');
const adminUsersDialogInput = document.getElementById('adminUsersDialogInput');
const adminUsersDialogCancel = document.getElementById('adminUsersDialogCancel');
const adminUsersDialogConfirm = document.getElementById('adminUsersDialogConfirm');

function wrapTable(html) {
  return `<div class="table-shell">${html}</div>`;
}

function setCountLabel(el, count, singular, plural) {
  if (el) el.textContent = `${count} ${count === 1 ? singular : plural}`;
}

function askAdminAction({ title, message, confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', eyebrow = 'Ação administrativa', inputLabel = '', inputValue = '', inputType = 'text', danger = false }) {
  if (!adminUsersDialog) return Promise.resolve({ confirmed: true, value: String(inputValue || '') });
  adminUsersDialogTitle.textContent = title || 'Confirmar ação';
  adminUsersDialogMessage.innerHTML = message || 'Revise a ação antes de continuar.';
  adminUsersDialogEyebrow.textContent = eyebrow || 'Ação administrativa';
  adminUsersDialogCancel.textContent = cancelLabel;
  adminUsersDialogConfirm.textContent = confirmLabel;
  adminUsersDialogConfirm.className = danger ? 'danger' : '';
  const needsInput = !!String(inputLabel || '').trim();
  adminUsersDialogInputWrap.classList.toggle('hidden', !needsInput);
  adminUsersDialogInputLabel.textContent = inputLabel || 'Valor';
  adminUsersDialogInput.type = inputType || 'text';
  adminUsersDialogInput.value = String(inputValue || '');
  return new Promise((resolve) => {
    const cleanup = (payload) => {
      adminUsersDialogConfirm.onclick = null;
      adminUsersDialogCancel.onclick = null;
      adminUsersDialog.oncancel = null;
      if (adminUsersDialog.open) adminUsersDialog.close();
      resolve(payload);
    };
    adminUsersDialogConfirm.onclick = () => cleanup({ confirmed: true, value: adminUsersDialogInput.value });
    adminUsersDialogCancel.onclick = () => cleanup({ confirmed: false, value: adminUsersDialogInput.value });
    adminUsersDialog.oncancel = () => cleanup({ confirmed: false, value: adminUsersDialogInput.value });
    adminUsersDialog.showModal();
    if (needsInput) adminUsersDialogInput.focus();
    else adminUsersDialogConfirm.focus();
  });
}

function renderUsersTable() {
  const term = String(usersSearchInput?.value || '').trim().toLowerCase();
  const filtered = usersCache.filter((u) => {
    if (!term) return true;
    const hay = `${u.username || ''} ${u.role || ''}`.toLowerCase();
    return hay.includes(term);
  });
  setCountLabel(usersFilteredCount, filtered.length, 'usuário', 'usuários');
  if (!filtered.length) {
    usersList.innerHTML = '<div class="empty-state">Nenhum usuário encontrado para o filtro informado.</div>';
    return;
  }
  usersList.innerHTML = wrapTable(`
    <table>
      <thead><tr><th>Usuário</th><th>Role</th><th>Tarefas associadas</th><th>Criado em</th><th>Ações</th></tr></thead>
      <tbody>${filtered.map(u => `
        <tr>
          <td>${u.username}</td>
          <td><select data-role-user="${u.username}" ${u.username === 'admin' || !hasModule('admin_users.create') ? 'disabled' : ''}>${roleOptions(u.role)}</select></td>
          <td>${u.associated_tasks ?? 0}</td>
          <td>${u.created_at}</td>
          <td>
            <button class="secondary" data-pass-user="${u.username}" ${!hasModule('admin_users.create') ? 'disabled' : ''}>Trocar senha</button>
            <button class="danger" data-del-user="${u.username}" data-task-count="${u.associated_tasks ?? 0}" ${u.username === me.username || u.role === 'admin' || !hasModule('admin_users.create') ? 'disabled' : ''}>Excluir</button>
          </td>
        </tr>`).join('')}</tbody>
    </table>`);

  usersList.querySelectorAll('[data-role-user]').forEach(sel => {
    sel.addEventListener('change', async () => {
      try { await updateRole(sel.dataset.roleUser, sel.value); setAdminFeedback(`Role de ${sel.dataset.roleUser} atualizada para ${sel.value}.`, 'success'); await loadUsers(); await loadAudit(); }
      catch (e) { setAdminFeedback(e.message, 'danger'); }
    });
  });

  usersList.querySelectorAll('[data-pass-user]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try { await changePassword(btn.dataset.passUser); await loadAudit(); }
      catch (e) { setAdminFeedback(e.message, 'danger'); }
    });
  });

  usersList.querySelectorAll('[data-del-user]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try { await deleteUser(btn.dataset.delUser, Number(btn.dataset.taskCount || 0)); await loadUsers(); await loadAudit(); }
      catch (e) { setAdminFeedback(e.message, 'danger'); }
    });
  });
}

function renderAuditTable() {
  const term = String(auditSearchInput?.value || '').trim().toLowerCase();
  const filtered = auditCache.filter((l) => {
    if (!term) return true;
    const hay = `${l.created_at || ''} ${l.actor || ''} ${l.action || ''} ${l.target || ''} ${l.details || ''}`.toLowerCase();
    return hay.includes(term);
  });
  setCountLabel(auditFilteredCount, filtered.length, 'evento', 'eventos');
  if (!filtered.length) {
    auditList.innerHTML = '<div class="empty-state">Nenhum evento de auditoria encontrado para o filtro informado.</div>';
    return;
  }
  auditList.innerHTML = wrapTable(`
    <table>
      <thead><tr><th>Quando</th><th>Quem</th><th>Ação</th><th>Alvo</th><th>Detalhes</th></tr></thead>
      <tbody>${filtered.map(l => `
        <tr><td>${l.created_at}</td><td>${l.actor}</td><td>${l.action}</td><td>${l.target}</td><td>${l.details || '-'}</td></tr>`).join('')}</tbody>
    </table>`);
}

function renderInviteOutput(message, link = '', copied = false) {
  if (!inviteOut) return;
  const safeMessage = escHtml(message || 'Nenhum convite gerado ainda.');
  const safeLink = String(link || '').trim();
  if (!safeLink) {
    inviteOut.innerHTML = safeMessage;
    return;
  }
  inviteOut.innerHTML = `
    <div class="invite-output-row">
      <div class="invite-output-text">${safeMessage}</div>
      <button type="button" id="copyInviteBtn" class="secondary invite-copy-btn" title="Copiar link do convite">📋 Copiar link</button>
    </div>
    <div class="invite-output-link-wrap">
      <a class="invite-output-link" href="${escHtml(safeLink)}" target="_blank" rel="noopener noreferrer">${escHtml(safeLink)}</a>
    </div>
    <div id="inviteCopyFeedback" class="small invite-copy-feedback">${copied ? 'Link copiado ✅' : ''}</div>
  `;
  const btn = document.getElementById('copyInviteBtn');
  const feedback = document.getElementById('inviteCopyFeedback');
  btn?.addEventListener('click', async () => {
    const ok = await copyText(safeLink);
    if (feedback) feedback.textContent = ok ? 'Link copiado ✅' : 'Não foi possível copiar automaticamente.';
  });
}

let me = null;
let roles = ['member', 'admin'];
let allowedModules = new Set();
let usersCache = [];
let auditCache = [];

async function api(url, opts={}) {
  const r = await fetch(url, opts);
  const d = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(d.error || 'Erro');
  return d;
}

function hasModule(moduleId) {
  return allowedModules.has(moduleId);
}

function applyModuleVisibility() {
  document.querySelectorAll('[data-module-id]').forEach((el) => {
    const moduleId = String(el.dataset.moduleId || '').trim();
    if (!moduleId) return;
    el.style.display = hasModule(moduleId) ? '' : 'none';
  });
}

async function loadPermissions() {
  const [meResp, permResp] = await Promise.all([api('/api/me'), api('/api/me/permissions')]);
  me = meResp.user;
  allowedModules = new Set(permResp?.permissions?.allowedModules || []);
  if (!(permResp?.permissions?.allowedPages || []).includes('admin-users.html')) {
    throw new Error('Sem acesso à página de usuários');
  }
  applyModuleVisibility();
}

async function loadSettingsDefaults() {
  if (!hasModule('admin_users.invite')) return;
  try {
    const d = await api('/api/admin/settings');
    const msg = d.settings?.['invite.default_message']?.value || '';
    const inviteMessage = document.getElementById('inviteMessage');
    if (inviteMessage && msg) inviteMessage.value = msg;
  } catch {
    // optional for non-admin users with invite module restrictions
  }
}

async function updateRole(username, role) {
  await api(`/api/admin/users/${encodeURIComponent(username)}`, {
    method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ role })
  });
}

async function changePassword(username) {
  const answer = await askAdminAction({ title: `Trocar senha de ${username}`, message: 'Informe a nova senha temporária para este usuário.', confirmLabel: 'Salvar senha', eyebrow: 'Credenciais', inputLabel: 'Nova senha', inputType: 'password' });
  const pwd = String(answer.value || '');
  if (!answer.confirmed || !pwd) return;
  await api(`/api/admin/users/${encodeURIComponent(username)}`, {
    method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ password: pwd })
  });
  setAdminFeedback(`Senha de ${username} alterada com sucesso.`, 'success');
}

async function deleteUser(username, associatedTasks) {
  const taskInfo = associatedTasks > 0 ? `<br><br><strong>⚠️ Este usuário possui ${associatedTasks} tarefa(s) associada(s).</strong>` : '';
  const answer = await askAdminAction({
    title: `Excluir usuário ${username}`,
    message: `Para confirmar, digite <strong>EXCLUIR</strong>.${taskInfo}`,
    confirmLabel: 'Excluir usuário',
    eyebrow: 'Governança',
    inputLabel: 'Digite EXCLUIR',
    danger: true,
  });
  if (!answer.confirmed) return;
  if (String(answer.value || '').trim().toUpperCase() !== 'EXCLUIR') {
    setAdminFeedback('Exclusão cancelada. Texto de confirmação não corresponde.', 'warning');
    return;
  }

  await api(`/api/admin/users/${encodeURIComponent(username)}`, { method: 'DELETE' });
  setAdminFeedback(`Usuário ${username} removido com sucesso.`, 'success');
}

function roleOptions(currentRole) {
  return roles.map(r => `<option value="${r}" ${currentRole === r ? 'selected' : ''}>${r}</option>`).join('');
}

function refreshRoleSelectors() {
  const newRole = document.getElementById('newRole');
  const inviteRole = document.getElementById('inviteRole');
  newRole.innerHTML = roleOptions('member');
  inviteRole.innerHTML = roleOptions('member');
}

async function loadUsers() {
  const d = await api('/api/admin/users');
  roles = d.roles?.length ? d.roles : roles;
  refreshRoleSelectors();
  usersCache = d.users || [];

  if (adminUsersCount) adminUsersCount.textContent = String(usersCache.length);
  if (adminAdminsCount) adminAdminsCount.textContent = String(usersCache.filter((u) => u.role === 'admin').length);
  if (!usersCache.length) {
    setCountLabel(usersFilteredCount, 0, 'usuário', 'usuários');
    usersList.innerHTML = '<div class="empty-state">Nenhum usuário encontrado. Crie um acesso direto ou gere um convite para iniciar a base de pessoas.</div>';
    return;
  }

  renderUsersTable();
}

async function loadAudit() {
  const d = await api('/api/admin/audit');
  auditCache = d.logs || [];
  if (adminAuditCount) adminAuditCount.textContent = String(auditCache.length);
  if (!auditCache.length) {
    setCountLabel(auditFilteredCount, 0, 'evento', 'eventos');
    auditList.innerHTML = '<div class="empty-state">Nenhum evento de auditoria encontrado ainda para este recorte.</div>';
    return;
  }

  renderAuditTable();
}

document.getElementById('createUserForm').onsubmit = async (e) => {
  e.preventDefault();
  if (!hasModule('admin_users.create')) return;
  try {
    await api('/api/admin/users', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      username: document.getElementById('newUsername').value,
      password: document.getElementById('newPassword').value,
      role: document.getElementById('newRole').value,
    })});
    setAdminFeedback('Usuário criado com sucesso. A lista foi atualizada.', 'success');
    e.target.reset();
    if (hasModule('admin_users.list')) await loadUsers();
    if (hasModule('admin_users.audit_log')) await loadAudit();
  } catch (e) { setAdminFeedback(e.message, 'danger'); }
};

document.getElementById('inviteForm').onsubmit = async (e) => {
  e.preventDefault();
  if (!hasModule('admin_users.invite')) return;
  try {
    const sendEmail = document.getElementById('sendInviteEmail').checked;
    const d = await api('/api/admin/invites', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      role: document.getElementById('inviteRole').value,
      email: document.getElementById('inviteEmail').value,
      sendEmail,
      message: document.getElementById('inviteMessage').value,
    })});
    const full = d.fullInviteUrl || `${location.origin}${d.inviteUrl}`;
    const message = sendEmail
      ? `Convite (expira ${d.expiresAt}) enviado para ${document.getElementById('inviteEmail').value}.`
      : `Convite gerado (expira ${d.expiresAt}).`;
    const copied = await copyText(full);
    renderInviteOutput(message, full, copied);
    setAdminFeedback(sendEmail
      ? `Convite gerado e fluxo de envio acionado para ${document.getElementById('inviteEmail').value || 'o destinatário informado'}.`
      : 'Convite gerado com sucesso e pronto para compartilhamento.', 'success');
    if (hasModule('admin_users.audit_log')) await loadAudit();
  } catch (e) { setAdminFeedback(e.message, 'danger'); }
};

logoutBtn.onclick = async () => { await api('/api/logout',{method:'POST'}); location.href='/login.html'; };

renderInviteOutput('Nenhum convite gerado ainda.');
setAdminFeedback('Tela pronta. Cadastre usuários imediatos ou use convites para onboarding guiado.', 'neutral');

(async()=>{
  try {
    await loadPermissions();
    await loadSettingsDefaults();
    if (hasModule('admin_users.list')) {
      await loadUsers();
    } else if (usersList) {
      usersList.innerHTML = '<p class="small">Sem acesso ao módulo de usuários cadastrados.</p>';
    }
    if (hasModule('admin_users.audit_log')) {
      await loadAudit();
    } else if (auditList) {
      auditList.innerHTML = '<p class="small">Sem acesso ao módulo de auditoria.</p>';
    }
  } catch {
    location.href='/';
  }
})();

if (usersSearchInput) usersSearchInput.addEventListener('input', renderUsersTable);
if (auditSearchInput) auditSearchInput.addEventListener('input', renderAuditTable);
