from __future__ import annotations
import argparse, subprocess
from pathlib import Path
from scripts._util import load_json, parse_mmss, norm_goal

def load_manual_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        print(f"⚠ manual_events not found: {p} (continue)")
        return []
    import json
    items = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items

def ffprobe_duration_sec(path: Path) -> float:
    cmd = ["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", str(path)]
    out = subprocess.check_output(cmd, text=True, encoding="utf-8").strip()
    return float(out)

def mmss(sec: float) -> str:
    sec = max(0, int(sec))
    m = sec // 60
    s = sec % 60
    return f"{m:02d}:{s:02d}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]

    manual = load_manual_jsonl(root / cfg["paths"]["manual_events"])
    table = load_json(out_dir / "event_table.json")
    goal = table.get("goal") or "進行確認"

    # end inference (fixed order)
    end_sec = None
    for m in manual:
        if m.get("tag") == "end":
            end_sec = parse_mmss(m["t"])
            break
    if end_sec is None:
        w = load_json(out_dir / "whisper.json")
        segs = w.get("segments") or []
        if segs:
            end_sec = float(segs[-1]["end"])
    if end_sec is None:
        mic = out_dir / "mic.wav"
        if mic.exists():
            end_sec = ffprobe_duration_sec(mic)
    if end_sec is None:
        end_sec = ffprobe_duration_sec(root / cfg["paths"]["video"])

    chapters = []
    # manual chapters/goal first
    for m in manual:
        tag = m.get("tag")
        if tag in ("chapter","goal","start"):
            t = parse_mmss(m["t"])
            label = m.get("label","").strip()
            if tag == "goal":
                label = norm_goal(label)
            chapters.append((t, label))

    # fallback if too few
    if len(chapters) < 3:
        chapters = [(0.0, "開始"),
                    (float(cfg["audio"]["silence_head_sec"]), f"目的：{goal}"),
                    (max(0.0, float(end_sec)-1.0), "区切り：パート終了")]

    chapters.sort(key=lambda x: x[0])

    out = out_dir / "chapters.txt"
    lines = [f"{mmss(t)} {title}" for t, title in chapters]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ chapters -> {out}")

if __name__ == "__main__":
    main()
