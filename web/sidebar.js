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

    const projectItems = projects || [];
    const projectId = currentProjectId(projectItems);

    const canAdminTools = ['admin', 'lider_projeto'].includes(user.role);
    // `projects.html` is an admin page; hide the link for non-admin users.
    const canAccessProjectArea = canAdminTools && projectItems.length > 0;

    root.innerHTML = `
      <h2>ProjectDashbord</h2>

      <div class="side-group">Área de trabalho</div>
      <a class="side-link ${active === 'home' ? 'active' : ''}" href="/">Início</a>
      ${canAccessProjectArea ? `<a class="side-link ${active === 'projects' ? 'active' : ''}" href="/projects.html?project_id=${projectId}">Projetos</a>` : ''}
      <a class="side-link ${active === 'kanban' ? 'active' : ''}" href="/kanban.html?project_id=${projectId}">Kanban</a>

      ${canAdminTools ? `
      <div class="side-group">Administração</div>
      <a id="usersLink" class="side-link ${active === 'users' ? 'active' : ''}" href="/admin-users.html?project_id=${projectId}">Usuários & Convites</a>
      <a id="settingsLink" class="side-link ${active === 'settings' ? 'active' : ''}" href="/settings.html?project_id=${projectId}">Configurações</a>
      ` : ''}

      <div class="side-group" id="whoamiTitle"></div>
      <a class="side-link ${active === 'profile' ? 'active' : ''}" href="/profile.html?project_id=${projectId}">Meu perfil</a>
      <a id="logoutLink" class="side-link" href="#">Logout</a>
    `;

    const whoamiTitle = document.getElementById('whoamiTitle');
    if (whoamiTitle) whoamiTitle.textContent = `${user.username} (${user.role})`;


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
