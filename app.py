#!/usr/bin/env python3
import json
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path("/home/panosso/.openclaw/workspace/projects")
WEB_DIR = Path(__file__).parent / "web"
HOST = "0.0.0.0"
PORT = 8765
STATUSES = ["Backlog", "Em andamento", "Bloqueado", "Concluído"]
PRIORITIES = ["Baixa", "Média", "Alta", "Urgente"]
SKIP_DIRS = {"ProjectDashboard", "__pycache__"}


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "projeto"


def read_text_if_exists(path: Path) -> str:
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def infer_description(project_dir: Path) -> str:
    readme = read_text_if_exists(project_dir / "README.md").strip().splitlines()
    for line in readme:
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:180]
    return "Sem descrição"


def project_meta_path(project_dir: Path) -> Path:
    return project_dir / "project.json"


def load_project(project_dir: Path) -> dict:
    meta_path = project_meta_path(project_dir)
    data = {}
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    status = data.get("status") if data.get("status") in STATUSES else "Backlog"
    priority = data.get("priority") if data.get("priority") in PRIORITIES else "Média"

    return {
        "name": data.get("name") or project_dir.name,
        "status": status,
        "description": data.get("description") or infer_description(project_dir),
        "owner": data.get("owner") or "",
        "dueDate": data.get("dueDate") or "",
        "priority": priority,
        "path": str(project_dir),
        "updatedAt": data.get("updatedAt") or "",
    }


def save_project(project_dir: Path, data: dict):
    data["updatedAt"] = now_iso()
    project_meta_path(project_dir).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def list_projects() -> list[dict]:
    projects = []
    if not BASE_DIR.exists():
        return projects

    for p in sorted(BASE_DIR.iterdir()):
        if not p.is_dir() or p.name in SKIP_DIRS:
            continue
        projects.append(load_project(p))
    return projects


def find_project_dir_by_name(project_name: str) -> Path | None:
    for p in BASE_DIR.iterdir():
        if not p.is_dir() or p.name in SKIP_DIRS:
            continue
        loaded = load_project(p)
        if loaded["name"] == project_name or p.name == project_name:
            return p
    return None


def write_project_status(project_name: str, new_status: str) -> tuple[bool, str]:
    if new_status not in STATUSES:
        return False, "Status inválido"

    project_dir = find_project_dir_by_name(project_name)
    if not project_dir:
        return False, "Projeto não encontrado"

    current = load_project(project_dir)
    current["status"] = new_status
    save_project(project_dir, current)
    return True, "ok"


def create_project(payload: dict) -> tuple[bool, str]:
    name = (payload.get("name") or "").strip()
    if not name:
        return False, "Nome é obrigatório"

    folder_name = slugify(name)
    project_dir = BASE_DIR / folder_name
    if project_dir.exists():
        return False, "Já existe um projeto com esse nome de pasta"

    status = payload.get("status") if payload.get("status") in STATUSES else "Backlog"
    priority = payload.get("priority") if payload.get("priority") in PRIORITIES else "Média"

    project_dir.mkdir(parents=True, exist_ok=False)
    (project_dir / "README.md").write_text(
        f"# Projeto: {name}\n\n{(payload.get('description') or 'Sem descrição').strip()}\n",
        encoding="utf-8",
    )
    (project_dir / "TASKS.md").write_text(
        "# TASKS\n\n## Done\n\n- [ ] Inicializar projeto\n\n## Next\n\n- [ ] Definir roadmap\n",
        encoding="utf-8",
    )

    meta = {
        "name": name,
        "status": status,
        "description": (payload.get("description") or "Sem descrição").strip(),
        "owner": (payload.get("owner") or "").strip(),
        "dueDate": (payload.get("dueDate") or "").strip(),
        "priority": priority,
    }
    save_project(project_dir, meta)
    return True, "ok"


def patch_project(project_name: str, payload: dict) -> tuple[bool, str]:
    project_dir = find_project_dir_by_name(project_name)
    if not project_dir:
        return False, "Projeto não encontrado"

    current = load_project(project_dir)

    if "status" in payload and payload["status"] in STATUSES:
        current["status"] = payload["status"]
    if "description" in payload:
        current["description"] = str(payload["description"]).strip() or "Sem descrição"
    if "owner" in payload:
        current["owner"] = str(payload["owner"]).strip()
    if "dueDate" in payload:
        current["dueDate"] = str(payload["dueDate"]).strip()
    if "priority" in payload and payload["priority"] in PRIORITIES:
        current["priority"] = payload["priority"]

    save_project(project_dir, current)
    return True, "ok"


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_error(404)
            return
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            return True, json.loads(raw)
        except Exception:
            return False, {"error": "JSON inválido"}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if parsed.path == "/app.js":
            return self._serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        if parsed.path == "/styles.css":
            return self._serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
        if parsed.path == "/api/projects":
            return self._json(
                200,
                {
                    "projects": list_projects(),
                    "statuses": STATUSES,
                    "priorities": PRIORITIES,
                },
            )
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/projects":
            ok, payload = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": payload["error"]})
            done, msg = create_project(payload)
            if not done:
                return self._json(400, {"ok": False, "error": msg})
            return self._json(200, {"ok": True})

        if parsed.path.startswith("/api/projects/") and parsed.path.endswith("/status"):
            parts = parsed.path.split("/")
            if len(parts) < 5:
                return self._json(400, {"ok": False, "error": "Rota inválida"})
            project_name = parts[3]

            ok, payload = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": payload["error"]})

            done, msg = write_project_status(project_name, payload.get("status", ""))
            if not done:
                return self._json(400, {"ok": False, "error": msg})
            return self._json(200, {"ok": True})

        self.send_error(404)

    def do_PATCH(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/projects/"):
            parts = parsed.path.split("/")
            if len(parts) < 4:
                return self._json(400, {"ok": False, "error": "Rota inválida"})
            project_name = parts[3]

            ok, payload = self._read_json()
            if not ok:
                return self._json(400, {"ok": False, "error": payload["error"]})

            done, msg = patch_project(project_name, payload)
            if not done:
                return self._json(400, {"ok": False, "error": msg})
            return self._json(200, {"ok": True})

        self.send_error(404)


def main():
    server = HTTPServer((HOST, PORT), Handler)
    print(f"ProjectDashboard online em http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
