const params = new URLSearchParams(location.search);
const token = params.get('token') || '';
const msg = document.getElementById('msg');

async function api(url, opts={}) {
  const r = await fetch(url, opts);
  const d = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(d.error || 'Erro');
  return d;
}

document.getElementById('signupForm').onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api('/api/signup', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
      token,
      username: document.getElementById('username').value,
      password: document.getElementById('password').value,
    })});
    msg.textContent = 'Conta criada com sucesso! Faça login.';
  } catch (e) { msg.textContent = e.message; }
};
