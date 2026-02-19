const form = document.getElementById('loginForm');
const errorEl = document.getElementById('error');

async function checkAlreadyLogged() {
  const res = await fetch('/api/me');
  if (res.ok) window.location.href = '/';
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  errorEl.textContent = '';
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;

  const res = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();

  if (!res.ok || !data.ok) {
    errorEl.textContent = data.error || 'Falha no login';
    return;
  }
  window.location.href = '/';
});

checkAlreadyLogged();
