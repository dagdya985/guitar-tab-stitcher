import json
import os
import threading
from pathlib import Path

DATA = Path(os.environ.get("GTS_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
DATA.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()


def project_dir(project_id):
    path = DATA / project_id
    if not path.is_dir():
        raise FileNotFoundError("项目不存在。")
    return path


def read(project_id):
    with LOCK:
        return json.loads((project_dir(project_id) / "project.json").read_text(encoding="utf-8"))


def write(project):
    with LOCK:
        path = project_dir(project["id"]) / "project.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

