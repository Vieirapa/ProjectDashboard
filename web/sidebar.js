/*
 * sidebar.js
 * ==========
 *
 * Responsável por montar dinamicamente a sidebar principal da aplicação.
 *
 * Papel deste arquivo
 * -------------------
 * - Descobrir o usuário autenticado.
 * - Descobrir o catálogo de projetos acessíveis.
 * - Descobrir páginas permitidas pela política de permissões.
 * - Renderizar a navegação lateral coerente com o contexto atual.
 *
 * Como deve ser tratado no restante da aplicação
 * ----------------------------------------------
 * - Deve permanecer focado em shell/navegação.
 * - Não deve concentrar lógica de domínio de negócio.
 * - Alterações nele impactam praticamente todas as telas, então mudanças devem
 *   ser pequenas, consistentes e bem validadas visualmente.
 */

(async () => {
  const root = document.getElementById('sidebar-root');
  if (!root) return;

  const active = root.dataset.active || '';

  // -------------------------------------------------------------------------
  // Helper HTTP JSON da sidebar
  // -------------------------------------------------------------------------
  async function api(url, opts = {}) {
    const res = await fetch(url, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Erro na API');
    return data;
  }

  // -------------------------------------------------------------------------
  // Resolve o projeto atual a partir da URL ou do primeiro projeto visível
  // -------------------------------------------------------------------------
  function currentProjectId(projects) {
    const raw = new URLSearchParams(window.location.search).get('project_id');
    const id = Number(raw);
    if (Number.isFinite(id) && id > 0) return id;
    return projects?.[0]?.project_id || 1;
  }

  try {
    const [{ user }, { projects }, permsResp] = await Promise.all([
      api('/api/me'),
      api('/api/projects-registry'),
      api('/api/me/permissions'),
    ]);

    const projectItems = projects || [];
    const projectId = currentProjectId(projectItems);
    const allowedPages = new Set(permsResp?.permissions?.allowedPages || []);

    const canAccessProjectsPage = allowedPages.has('projects.html') && projectItems.length > 0;
    const canAccessAdminUsersPage = allowedPages.has('admin-users.html');
    const canAccessSettingsPage = allowedPages.has('settings.html');
    const hasAdminGroup = canAccessAdminUsersPage || canAccessSettingsPage;

    root.innerHTML = `
      <div class="sidebar-brand">
        <p class="eyebrow sidebar-eyebrow">Workspace</p>
        <h2>ProjectDashbord</h2>
        <p class="sidebar-subtitle">Gestão operacional de projetos, documentos e revisão.</p>
      </div>

      <div class="side-group">Área de trabalho</div>
      <a class="side-link ${active === 'home' ? 'active' : ''}" href="/">Início</a>
      ${canAccessProjectsPage ? `<a class="side-link ${active === 'projects' ? 'active' : ''}" href="/projects.html?project_id=${projectId}">Projetos</a>` : ''}
      <a class="side-link ${active === 'kanban' ? 'active' : ''}" href="/kanban.html?project_id=${projectId}">Kanban</a>

      ${hasAdminGroup ? `<div class="side-group">Administração</div>` : ''}
      ${canAccessAdminUsersPage ? `<a id="usersLink" class="side-link ${active === 'users' ? 'active' : ''}" href="/admin-users.html?project_id=${projectId}">Usuários & Convites</a>` : ''}
      ${canAccessSettingsPage ? `<a id="settingsLink" class="side-link ${active === 'settings' ? 'active' : ''}" href="/settings.html?project_id=${projectId}">Configurações</a>` : ''}

      <div class="side-group">Conta</div>
      <a class="side-link ${active === 'profile' ? 'active' : ''}" href="/profile.html?project_id=${projectId}">Meu perfil</a>
      <a id="logoutLink" class="side-link side-link-logout" href="#">Logout</a>

      <div class="side-foot">${user.username} · ${user.role}</div>
    `;

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
