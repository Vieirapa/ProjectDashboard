const usersList = document.getElementById('usersList');
const auditList = document.getElementById('auditList');
const logoutBtn = document.getElementById('logoutBtn');
const inviteOut = document.getElementById('inviteOut');

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
  const pwd = prompt(`Nova senha para ${username}:`);
  if (!pwd) return;
  await api(`/api/admin/users/${encodeURIComponent(username)}`, {
    method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ password: pwd })
  });
  alert('Senha alterada com sucesso');
}

async function deleteUser(username, associatedTasks) {
  const taskInfo = associatedTasks > 0
    ? `\n\n⚠️ Este usuário possui ${associatedTasks} tarefa(s) associada(s).`
    : '';

  if (!confirm(`Confirma exclusão do usuário ${username}?${taskInfo}`)) return;

  const typed = prompt(`Para confirmar, digite EXCLUIR (${username}):`);
  if (typed !== 'EXCLUIR') {
    alert('Exclusão cancelada.');
    return;
  }

  await api(`/api/admin/users/${encodeURIComponent(username)}`, { method: 'DELETE' });
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

  usersList.innerHTML = `
    <table>
      <tr><th>Usuário</th><th>Role</th><th>Tarefas associadas</th><th>Criado em</th><th>Ações</th></tr>
      ${d.users.map(u => `
        <tr>
          <td>${u.username}</td>
          <td>
            <select data-role-user="${u.username}" ${u.username === 'admin' || !hasModule('admin_users.create') ? 'disabled' : ''}>
              ${roleOptions(u.role)}
            </select>
          </td>
          <td>${u.associated_tasks ?? 0}</td>
          <td>${u.created_at}</td>
          <td>
            <button class="secondary" data-pass-user="${u.username}" ${!hasModule('admin_users.create') ? 'disabled' : ''}>Trocar senha</button>
            <button class="danger" data-del-user="${u.username}" data-task-count="${u.associated_tasks ?? 0}" ${u.username === me.username || u.role === 'admin' || !hasModule('admin_users.create') ? 'disabled' : ''}>Excluir</button>
          </td>
        </tr>
      `).join('')}
    </table>
  `;

  usersList.querySelectorAll('[data-role-user]').forEach(sel => {
    sel.addEventListener('change', async () => {
      try { await updateRole(sel.dataset.roleUser, sel.value); await loadUsers(); await loadAudit(); }
      catch (e) { alert(e.message); }
    });
  });

  usersList.querySelectorAll('[data-pass-user]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try { await changePassword(btn.dataset.passUser); await loadAudit(); }
      catch (e) { alert(e.message); }
    });
  });

  usersList.querySelectorAll('[data-del-user]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        await deleteUser(btn.dataset.delUser, Number(btn.dataset.taskCount || 0));
        await loadUsers();
        await loadAudit();
      } catch (e) { alert(e.message); }
    });
  });
}

async function loadAudit() {
  const d = await api('/api/admin/audit');
  auditList.innerHTML = `
    <table>
      <tr><th>Quando</th><th>Quem</th><th>Ação</th><th>Alvo</th><th>Detalhes</th></tr>
      ${d.logs.map(l => `
        <tr>
          <td>${l.created_at}</td>
          <td>${l.actor}</td>
          <td>${l.action}</td>
          <td>${l.target}</td>
          <td>${l.details || '-'}</td>
        </tr>
      `).join('')}
    </table>
  `;
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
    alert('Usuário criado');
    e.target.reset();
    if (hasModule('admin_users.list')) await loadUsers();
    if (hasModule('admin_users.audit_log')) await loadAudit();
  } catch (e) { alert(e.message); }
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
    if (hasModule('admin_users.audit_log')) await loadAudit();
  } catch (e) { alert(e.message); }
};

logoutBtn.onclick = async () => { await api('/api/logout',{method:'POST'}); location.href='/login.html'; };

renderInviteOutput('Nenhum convite gerado ainda.');

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
