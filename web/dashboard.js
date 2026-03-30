/*
 * dashboard.js
 * ============
 *
 * Responsável pela tela inicial (home/dashboard) do ProjectDashboard.
 *
 * Papel deste arquivo
 * -------------------
 * - Carregar métricas resumidas dos projetos visíveis ao usuário.
 * - Construir a tabela de resumo operacional por projeto.
 * - Fornecer uma leitura rápida da situação atual da operação.
 *
 * Como este arquivo deve ser tratado no restante da aplicação
 * ----------------------------------------------------------
 * - Deve continuar focado em leitura e composição visual do dashboard.
 * - Não deve concentrar regras complexas de domínio; para isso, deve consumir
 *   endpoints já preparados pelo backend.
 * - Pode ser evoluído para componentes reutilizáveis no futuro, mas hoje seu
 *   papel é orquestrar a home de forma clara e simples.
 */

const kpiProjects = document.getElementById('kpiProjects');
const kpiOwned = document.getElementById('kpiOwned');
const kpiDone = document.getElementById('kpiDone');
const kpiAvgResolution = document.getElementById('kpiAvgResolution');
const projectsSummaryTable = document.getElementById('projectsSummaryTable');
const refreshHomeBtn = document.getElementById('refreshHomeBtn');
const goKanbanBtn = document.getElementById('goKanbanBtn');


// ---------------------------------------------------------------------------
// Helper HTTP JSON do dashboard
// ---------------------------------------------------------------------------
async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || 'Erro na API');
    err.status = res.status;
    throw err;
  }
  return data;
}


// ---------------------------------------------------------------------------
// Escape HTML defensivo para composição de tabela
// ---------------------------------------------------------------------------
function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}


// ---------------------------------------------------------------------------
// Média aritmética simples
// ---------------------------------------------------------------------------
function avg(values) {
  if (!values.length) return null;
  const total = values.reduce((acc, n) => acc + (Number(n) || 0), 0);
  return total / values.length;
}


// ---------------------------------------------------------------------------
// Formatação amigável de dias
// ---------------------------------------------------------------------------
function fmtDays(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-';
  return `${Number(v).toFixed(1)} dias`;
}


// ---------------------------------------------------------------------------
// Classe visual de badge por valor numérico
// ---------------------------------------------------------------------------
function badgeClass(value) {
  const num = Number(value) || 0;
  if (num >= 12) return 'status-badge status-danger';
  if (num >= 5) return 'status-badge status-warning';
  return 'status-badge status-success';
}


// ---------------------------------------------------------------------------
// Carregamento principal do dashboard
// ---------------------------------------------------------------------------
async function loadDashboard() {
  projectsSummaryTable.innerHTML = '<div class="loading-state">Carregando métricas e resumo dos projetos...</div>';

  const [{ user }, { projects }] = await Promise.all([
    api('/api/me'),
    api('/api/projects-registry'),
  ]);

  const projectList = (projects || []).filter((p) => !p.is_template);
  const perProject = await Promise.all(
    projectList.map(async (p) => {
      const d = await api(`/api/documents?project_id=${encodeURIComponent(String(p.project_id))}`);
      const docs = d.documents || [];
      const doneDocs = docs.filter((x) => x.status === 'Concluído');
      const reviewDocs = docs.filter((x) => x.status === 'Em revisão');
      const activeDocs = docs.filter((x) => x.status === 'Em andamento');
      return {
        project_id: p.project_id,
        project_name: p.project_name,
        is_template: !!p.is_template,
        total: docs.length,
        owned: docs.filter((x) => String(x.owner || '').toLowerCase() === String(user.username || '').toLowerCase()).length,
        done: doneDocs.length,
        review: reviewDocs.length,
        active: activeDocs.length,
        avgDoneDays: avg(doneDocs.map((x) => Number(x.ageDays) || 0)),
      };
    })
  );

  const totalProjects = perProject.length;
  const totalOwned = perProject.reduce((acc, p) => acc + p.owned, 0);
  const totalDone = perProject.reduce((acc, p) => acc + p.done, 0);
  const allDoneDays = perProject.flatMap((p) => (p.done ? [p.avgDoneDays * p.done] : []));
  const weightedAvgDone = totalDone ? allDoneDays.reduce((a, b) => a + b, 0) / totalDone : null;

  kpiProjects.textContent = String(totalProjects);
  kpiOwned.textContent = String(totalOwned);
  kpiDone.textContent = String(totalDone);
  kpiAvgResolution.textContent = fmtDays(weightedAvgDone);

  if (!perProject.length) {
    projectsSummaryTable.innerHTML = '<div class="empty-state">Você ainda não tem projetos com acesso. Assim que houver projetos disponíveis, eles aparecerão aqui.</div>';
    return;
  }

  const sortedProjects = [...perProject].sort((a, b) => (b.total - a.total) || a.project_name.localeCompare(b.project_name));

  projectsSummaryTable.innerHTML = `
    <table>
      <tr>
        <th>ID</th>
        <th>Projeto</th>
        <th>Total</th>
        <th>Seus cards</th>
        <th>Em andamento</th>
        <th>Em revisão</th>
        <th>Concluídos</th>
        <th>Média</th>
        <th>Ação</th>
      </tr>
      ${sortedProjects.map((p) => `
        <tr>
          <td>${esc(p.project_id)}</td>
          <td>
            <div class="table-title-cell">
              <strong>${esc(p.project_name)}</strong>
              ${p.is_template ? '<span class="status-badge status-neutral">Template</span>' : ''}
            </div>
          </td>
          <td><span class="status-badge status-neutral">${esc(p.total)}</span></td>
          <td><span class="status-badge status-primary">${esc(p.owned)}</span></td>
          <td>${esc(p.active)}</td>
          <td>${esc(p.review)}</td>
          <td>${esc(p.done)}</td>
          <td><span class="${badgeClass(p.avgDoneDays)}">${esc(fmtDays(p.avgDoneDays))}</span></td>
          <td><a class="table-link" href="/kanban.html?project_id=${encodeURIComponent(String(p.project_id))}">Abrir Kanban</a></td>
        </tr>
      `).join('')}
    </table>
  `;
}

refreshHomeBtn?.addEventListener('click', () => loadDashboard());
goKanbanBtn?.addEventListener('click', async () => {
  try {
    const d = await api('/api/projects-registry');
    const first = (d.projects || [])[0];
    window.location.href = first ? `/kanban.html?project_id=${encodeURIComponent(String(first.project_id))}` : '/kanban.html';
  } catch {
    window.location.href = '/kanban.html';
  }
});

(async () => {
  try {
    await loadDashboard();
  } catch (e) {
    if (e?.status === 401) {
      window.location.href = '/login.html';
      return;
    }
    projectsSummaryTable.innerHTML = `<div class="error-state">${esc(e?.message || 'Falha ao carregar painel de resumo.')}</div>`;
  }
})();
