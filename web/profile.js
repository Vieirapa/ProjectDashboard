const usersLink = document.getElementById('usersLink');
const settingsLink = document.getElementById('settingsLink');
const whoami = document.getElementById('whoami');
const logoutBtn = document.getElementById('logoutBtn');
const form = document.getElementById('profileForm');
const saveBtn = document.getElementById('saveBtn');
const changePasswordBtn = document.getElementById('changePasswordBtn');
const feedback = document.getElementById('feedback');

const fields = {
  email: document.getElementById('email'),
  phone: document.getElementById('phone'),
  extension: document.getElementById('extension'),
  work_area: document.getElementById('work_area'),
  notes: document.getElementById('notes'),
  currentPassword: document.getElementById('currentPassword'),
  newPassword: document.getElementById('newPassword'),
  confirmPassword: document.getElementById('confirmPassword'),
};

let me = null;

async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || 'Erro');
    err.status = res.status;
    throw err;
  }
  return data;
}

async function loadMe() {
  const d = await api('/api/me');
  me = d.user;
  whoami.textContent = `${me.username} (${me.role})`;
  usersLink.style.display = me.role === 'admin' ? 'block' : 'none';
  settingsLink.style.display = me.role === 'admin' ? 'block' : 'none';
}

async function loadProfile() {
  const d = await api('/api/me/profile');
  ['email', 'phone', 'extension', 'work_area', 'notes'].forEach((k) => {
    fields[k].value = d.profile?.[k] || '';
  });
  fields.currentPassword.value = '';
  fields.newPassword.value = '';
  fields.confirmPassword.value = '';
}

form.onsubmit = async (e) => {
  e.preventDefault();
  saveBtn.disabled = true;
  feedback.textContent = '';
  try {
    await api('/api/me/profile', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: fields.email.value,
        phone: fields.phone.value,
        extension: fields.extension.value,
        work_area: fields.work_area.value,
        notes: fields.notes.value,
      }),
    });
    feedback.textContent = 'Perfil atualizado com sucesso ✅';
  } catch (err) {
    feedback.textContent = err.message;
  } finally {
    saveBtn.disabled = false;
  }
};

changePasswordBtn.onclick = async () => {
  feedback.textContent = '';
  try {
    const currentPassword = fields.currentPassword.value || '';
    const newPassword = fields.newPassword.value || '';
    const confirmPassword = fields.confirmPassword.value || '';

    if (!currentPassword || !newPassword || !confirmPassword) {
      feedback.textContent = 'Preencha senha atual, nova senha e confirmação.';
      return;
    }
    if (newPassword !== confirmPassword) {
      feedback.textContent = 'Nova senha e confirmação não conferem.';
      return;
    }

    changePasswordBtn.disabled = true;
    await api('/api/me/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ currentPassword, newPassword }),
    });
    fields.currentPassword.value = '';
    fields.newPassword.value = '';
    fields.confirmPassword.value = '';
    feedback.textContent = 'Senha alterada com sucesso ✅';
  } catch (err) {
    feedback.textContent = err.message;
  } finally {
    changePasswordBtn.disabled = false;
  }
};

logoutBtn.onclick = async () => {
  await api('/api/logout', { method: 'POST' });
  location.href = '/login.html';
};

(async () => {
  try {
    await loadMe();
    await loadProfile();
  } catch (err) {
    if (err?.status === 401) {
      location.href = '/login.html';
      return;
    }
    feedback.textContent = err.message || 'Erro ao carregar perfil';
  }
})();
