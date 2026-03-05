(async () => {
  const root = document.getElementById('sidebar-root');
  if (!root) return;

  const active = root.dataset.active || '';

  async function api(url, opts = {}) {
    const res = await fetch(url, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Erro na API');
    return data;
  }

  function currentProjectId(projects) {
    const raw = new URLSearchParams(window.location.search).get('project_id');
    const id = Number(raw);
    if (Number.isFinite(id) && id > 0) return id;
    return projects?.[0]?.project_id || 1;
  }

  try {
    const [{ user }, { projects }] = await Promise.all([
      api('/api/me'),
      api('/api/projects-registry'),
    ]);

    const projectId = currentProjectId(projects || []);

    root.innerHTML = `
      <h2>DocumentDashboard</h2>
      <select id="sidebarProjectSelect" class="header-project-select"></select>

      <div class="side-group">Área de trabalho</div>
      <a class="side-link ${active === 'projects' ? 'active' : ''}" href="/projects.html?project_id=${projectId}">Projetos</a>
      <a class="side-link ${active === 'kanban' ? 'active' : ''}" href="/?project_id=${projectId}">Kanban</a>

      <div class="side-group">Administração</div>
      <a id="usersLink" class="side-link ${active === 'users' ? 'active' : ''}" href="/admin-users.html?project_id=${projectId}">Usuários & Convites</a>
      <a id="settingsLink" class="side-link ${active === 'settings' ? 'active' : ''}" href="/settings.html?project_id=${projectId}">Configurações</a>

      <div class="side-group" id="whoamiTitle"></div>
      <a class="side-link ${active === 'profile' ? 'active' : ''}" href="/profile.html?project_id=${projectId}">Meu perfil</a>
      <a id="logoutLink" class="side-link" href="#">Logout</a>
    `;

    const whoamiTitle = document.getElementById('whoamiTitle');
    if (whoamiTitle) whoamiTitle.textContent = `${user.username} (${user.role})`;

    const usersLink = document.getElementById('usersLink');
    const settingsLink = document.getElementById('settingsLink');
    if (usersLink) usersLink.style.display = user.role === 'admin' ? 'block' : 'none';
    if (settingsLink) settingsLink.style.display = user.role === 'admin' ? 'block' : 'none';

    const select = document.getElementById('sidebarProjectSelect');
    if (select) {
      select.innerHTML = '';
      for (const p of (projects || [])) {
        const opt = new Option(`${p.project_id} · ${p.project_name}`, String(p.project_id));
        if (Number(p.project_id) === Number(projectId)) opt.selected = true;
        select.append(opt);
      }
      select.onchange = () => {
        const pid = select.value;
        if (!pid) return;
        const url = new URL(window.location.href);
        url.searchParams.set('project_id', pid);
        if (window.location.pathname === '/edit.html') {
          window.location.href = `/?project_id=${encodeURIComponent(pid)}`;
          return;
        }
        window.location.href = `${url.pathname}?${url.searchParams.toString()}`;
      };
    }

    const logoutLink = document.getElementById('logoutLink');
    if (logoutLink) {
      logoutLink.onclick = async (e) => {
        e.preventDefault();
        await api('/api/logout', { method: 'POST' });
        window.location.href = '/login.html';
      };
    }
  } catch {
    window.location.href = '/login.html';
  }
})();
