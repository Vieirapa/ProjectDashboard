(async () => {
  const sel = document.getElementById('sidebarProjectSelect');
  if (!sel) return;

  async function api(url) {
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Erro na API');
    return data;
  }

  function currentProjectId() {
    const raw = new URLSearchParams(window.location.search).get('project_id');
    const id = Number(raw);
    return Number.isFinite(id) && id > 0 ? id : null;
  }

  try {
    const d = await api('/api/projects-registry');
    const items = d.projects || [];
    sel.innerHTML = '';
    if (!items.length) {
      sel.disabled = true;
      sel.append(new Option('Sem projetos', ''));
      return;
    }

    const selected = currentProjectId() || items[0].project_id;
    items.forEach((p) => {
      const opt = new Option(`${p.project_id} · ${p.project_name}`, String(p.project_id));
      if (Number(p.project_id) === Number(selected)) opt.selected = true;
      sel.append(opt);
    });

    sel.onchange = () => {
      const pid = sel.value;
      if (!pid) return;
      const u = new URL(window.location.href);
      u.searchParams.set('project_id', pid);
      if (u.pathname === '/edit.html' || u.pathname === '/profile.html' || u.pathname === '/admin-users.html' || u.pathname === '/settings.html' || u.pathname === '/projects.html') {
        window.location.href = `/?project_id=${encodeURIComponent(pid)}`;
      } else {
        window.location.href = u.pathname + '?' + u.searchParams.toString();
      }
    };
  } catch (_) {
    sel.disabled = true;
    sel.innerHTML = '';
    sel.append(new Option('Falha ao carregar projetos', ''));
  }
})();
