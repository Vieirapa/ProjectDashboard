const usersList = document.getElementById('usersList');
const whoami = document.getElementById('whoami');
const logoutBtn = document.getElementById('logoutBtn');
const inviteOut = document.getElementById('inviteOut');

async function api(url, opts={}) {
  const r = await fetch(url, opts);
  const d = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(d.error || 'Erro');
  return d;
}

async function ensureAdmin() {
  const d = await api('/api/me');
  if (!d.user || d.user.role !== 'admin') throw new Error('Acesso restrito a admin');
  whoami.textContent = `${d.user.username} (${d.user.role})`;
}

async function loadUsers() {
  const d = await api('/api/admin/users');
  usersList.innerHTML = `<table><tr><th>Usuário</th><th>Role</th><th>Criado em</th></tr>${d.users.map(u=>`<tr><td>${u.username}</td><td>${u.role}</td><td>${u.created_at}</td></tr>`).join('')}</table>`;
}

document.getElementById('createUserForm').onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api('/api/admin/users', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      username: document.getElementById('newUsername').value,
      password: document.getElementById('newPassword').value,
      role: document.getElementById('newRole').value,
    })});
    alert('Usuário criado');
    e.target.reset();
    loadUsers();
  } catch (e) { alert(e.message); }
};

document.getElementById('inviteForm').onsubmit = async (e) => {
  e.preventDefault();
  try {
    const d = await api('/api/admin/invites', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      role: document.getElementById('inviteRole').value,
    })});
    const full = `${location.origin}${d.inviteUrl}`;
    inviteOut.textContent = `Convite (expira ${d.expiresAt}): ${full}`;
    await navigator.clipboard.writeText(full);
  } catch (e) { alert(e.message); }
};

logoutBtn.onclick = async () => { await api('/api/logout',{method:'POST'}); location.href='/login.html'; };

(async()=>{ try { await ensureAdmin(); await loadUsers(); } catch { location.href='/'; } })();
