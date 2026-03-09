from __future__ import annotations
import json, re
from pathlib import Path

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def parse_mmss(s: str) -> float:
    # "MM:SS" or "HH:MM:SS" to seconds
    parts = s.strip().split(":")
    if len(parts) == 2:
        mm, ss = parts
        return int(mm) * 60 + float(ss)
    if len(parts) == 3:
        hh, mm, ss = parts
        return int(hh) * 3600 + int(mm) * 60 + float(ss)
    raise ValueError(f"Bad time format: {s}")

def norm_goal(label: str) -> str:
    # "今回の目的：xxx" -> "目的：xxx"
    label = label.strip()
    label = re.sub(r"^今回の目的[:：]\s*", "目的：", label)
    if label.startswith("目的："):
        return label
    return "目的：" + label
