#!/usr/bin/env python3
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path("/home/panosso/.openclaw/workspace/projects")
WEB_DIR = Path(__file__).parent / "web"
PORT = 8765
STATUSES = ["Backlog", "Em andamento", "Bloqueado", "Concluído"]
SKIP_DIRS = {"ProjectDashboard", "__pycache__"}


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


def load_project(project_dir: Path) -> dict:
    meta_path = project_dir / "project.json"
    data = {}
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    name = data.get("name") or project_dir.name
    status = data.get("status") or "Backlog"
    if status not in STATUSES:
        status = "Backlog"

    description = data.get("description") or infer_description(project_dir)

    return {
        "name": name,
        "status": status,
        "description": description,
        "path": str(project_dir),
    }


def list_projects() -> list[dict]:
    projects = []
    if not BASE_DIR.exists():
        return projects

    for p in sorted(BASE_DIR.iterdir()):
        if not p.is_dir() or p.name in SKIP_DIRS:
            continue
        projects.append(load_project(p))
    return projects


def write_project_status(project_name: str, new_status: str) -> tuple[bool, str]:
    if new_status not in STATUSES:
        return False, "Status inválido"

    project_dir = BASE_DIR / project_name
    if not project_dir.exists() or not project_dir.is_dir():
        return False, "Projeto não encontrado"

    meta_path = project_dir / "project.json"
    data = {}
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["name"] = data.get("name") or project_name
    data["status"] = new_status
    data["description"] = data.get("description") or infer_description(project_dir)
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if parsed.path == "/app.js":
            return self._serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        if parsed.path == "/styles.css":
            return self._serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
        if parsed.path == "/api/projects":
            return self._json(200, {"projects": list_projects(), "statuses": STATUSES})
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/projects/") and parsed.path.endswith("/status"):
            parts = parsed.path.split("/")
            if len(parts) < 5:
                return self._json(400, {"ok": False, "error": "Rota inválida"})
            project_name = parts[3]

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                payload = json.loads(raw)
            except Exception:
                return self._json(400, {"ok": False, "error": "JSON inválido"})

            ok, msg = write_project_status(project_name, payload.get("status", ""))
            if not ok:
                return self._json(400, {"ok": False, "error": msg})
            return self._json(200, {"ok": True})

        self.send_error(404)


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"ProjectDashboard online em http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
