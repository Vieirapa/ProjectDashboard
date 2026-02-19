const board = document.getElementById('board');
const refreshBtn = document.getElementById('refreshBtn');

async function fetchData() {
  const res = await fetch('/api/projects');
  if (!res.ok) throw new Error('Falha ao carregar projetos');
  return res.json();
}

function makeColumn(status) {
  const col = document.createElement('div');
  col.className = 'column';
  col.dataset.status = status;

  const title = document.createElement('h2');
  title.textContent = status;
  col.appendChild(title);

  const info = document.createElement('div');
  info.className = 'small';
  info.textContent = '0 projetos';
  col.appendChild(info);

  return col;
}

async function updateStatus(projectName, status) {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectName)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(data.error || 'Falha ao atualizar status');
  }
}

function makeCard(project, statuses) {
  const card = document.createElement('div');
  card.className = 'card';

  const title = document.createElement('h3');
  title.textContent = project.name;
  card.appendChild(title);

  const desc = document.createElement('p');
  desc.textContent = project.description || 'Sem descrição';
  card.appendChild(desc);

  const select = document.createElement('select');
  for (const st of statuses) {
    const opt = document.createElement('option');
    opt.value = st;
    opt.textContent = st;
    if (st === project.status) opt.selected = true;
    select.appendChild(opt);
  }

  select.addEventListener('change', async () => {
    const oldValue = project.status;
    try {
      await updateStatus(project.name, select.value);
      project.status = select.value;
      await render();
    } catch (err) {
      alert(err.message);
      select.value = oldValue;
    }
  });

  card.appendChild(select);
  return card;
}

async function render() {
  const data = await fetchData();
  board.innerHTML = '';

  const columns = new Map();
  for (const status of data.statuses) {
    const col = makeColumn(status);
    columns.set(status, col);
    board.appendChild(col);
  }

  for (const project of data.projects) {
    const col = columns.get(project.status) || columns.get('Backlog');
    col.appendChild(makeCard(project, data.statuses));
  }

  for (const [, col] of columns) {
    const count = col.querySelectorAll('.card').length;
    col.querySelector('.small').textContent = `${count} projeto(s)`;
  }
}

refreshBtn.addEventListener('click', () => render());
render().catch((e) => {
  board.innerHTML = `<p style="color:red">Erro: ${e.message}</p>`;
});
