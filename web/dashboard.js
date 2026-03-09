const kpiProjects = document.getElementById('kpiProjects');
const kpiOwned = document.getElementById('kpiOwned');
const kpiDone = document.getElementById('kpiDone');
const kpiAvgResolution = document.getElementById('kpiAvgResolution');
const projectsSummaryTable = document.getElementById('projectsSummaryTable');
const refreshHomeBtn = document.getElementById('refreshHomeBtn');
const goKanbanBtn = document.getElementById('goKanbanBtn');

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

function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}

function avg(values) {
  if (!values.length) return null;
  const total = values.reduce((acc, n) => acc + (Number(n) || 0), 0);
  return total / values.length;
}

function fmtDays(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-';
  return `${Number(v).toFixed(1)} dias`;
}

async function loadDashboard() {
  const [{ user }, { projects }] = await Promise.all([
    api('/api/me'),
    api('/api/projects-registry'),
  ]);

  const projectList = projects || [];
  const perProject = await Promise.all(
    projectList.map(async (p) => {
      const d = await api(`/api/documents?project_id=${encodeURIComponent(String(p.project_id))}`);
      const docs = d.documents || [];
      const doneDocs = docs.filter((x) => x.status === 'Concluído');
      return {
        project_id: p.project_id,
        project_name: p.project_name,
        total: docs.length,
        owned: docs.filter((x) => String(x.owner || '').toLowerCase() === String(user.username || '').toLowerCase()).length,
        done: doneDocs.length,
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
    projectsSummaryTable.textContent = 'Você ainda não tem projetos com acesso.';
    return;
  }

  projectsSummaryTable.innerHTML = `<table>
    <tr><th>ID</th><th>Projeto</th><th>Total de cards</th><th>Seus cards</th><th>Concluídos</th><th>Média resolução</th><th>Ação</th></tr>
    ${perProject.map((p) => `
      <tr>
        <td>${esc(p.project_id)}</td>
        <td>${esc(p.project_name)}</td>
        <td>${esc(p.total)}</td>
        <td>${esc(p.owned)}</td>
        <td>${esc(p.done)}</td>
        <td>${esc(fmtDays(p.avgDoneDays))}</td>
        <td><a href="/kanban.html?project_id=${encodeURIComponent(String(p.project_id))}">Abrir</a></td>
      </tr>
    `).join('')}
  </table>`;
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
    projectsSummaryTable.textContent = e?.message || 'Falha ao carregar painel de resumo.';
  }
})();
