"""작업 데이터를 로컬 JSON 파일로 저장한다 (data/ 폴더, git에 올라가지 않음)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("BLOGWRITER_DATA", Path(__file__).resolve().parent.parent / "data"))


def _path(name: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"{name}.json"


def load(name: str, default=None):
    p = _path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(name: str, value) -> None:
    p = _path(name)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def slug(text: str) -> str:
    return re.sub(r"[^\w가-힣-]+", "_", text).strip("_")[:40] or "untitled"


def save_project(keyword: str, project: dict) -> str:
    """키워드별 작업(준비 자료·초안·검수)을 저장하고 파일 이름을 돌려준다."""
    project = {**project, "keyword": keyword, "updated": datetime.now().isoformat(timespec="seconds")}
    name = f"project_{slug(keyword)}"
    save(name, project)
    return name


def list_projects() -> list[dict]:
    if not DATA_DIR.exists():
        return []
    items = []
    for p in DATA_DIR.glob("project_*.json"):
        data = load(p.stem, {})
        if data:
            items.append(data)
    return sorted(items, key=lambda d: d.get("updated", ""), reverse=True)
