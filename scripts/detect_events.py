from __future__ import annotations
import argparse
from pathlib import Path
from scripts._util import load_json, save_json, parse_mmss, norm_goal

def load_json_str(s: str) -> dict:
    import json
    return json.loads(s)

def load_manual_events(path: Path) -> list[dict]:
    if not path.exists():
        print(f"⚠ manual_events not found: {path} (continue as empty)")
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(load_json_str(line))
    return items

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]
    whisper = load_json(out_dir / "whisper.json")
    segments = whisper.get("segments", [])

    manual_path = root / cfg["paths"]["manual_events"]
    manual = load_manual_events(manual_path)

    # goal抽出（intro/chapters用）
    goal_text = None
    for m in manual:
        if m.get("tag") == "goal":
            goal_text = norm_goal(m.get("label","")).replace("目的：","").strip() or None

    mode = int(cfg["modes"]["mode"])
    gap_stall_1 = int(cfg["modes"]["gap_stall_sec_mode1"])
    gap_stall_2 = int(cfg["modes"]["gap_stall_sec_mode2"])
    stall_gap = gap_stall_1 if mode == 1 else gap_stall_2 if mode == 2 else None

    cand = []
    idx = 0

    # (1) whisper-based normal candidates, thinned by 15 sec
    last_t = -1e9
    min_gap = 15.0
    for seg in segments:
        t = float(seg["start"])
        if t - last_t < min_gap:
            continue
        last_t = t
        idx += 1
        cand.append({
            "id": f"evt_{idx:06d}",
            "t_request": t,
            "type": "normal",
            "source": "whisper",
            "context": seg.get("text",""),
            "hint_only": True
        })

    # (2) stall candidates based on gaps
    if stall_gap is not None:
        last_end = 0.0
        for seg in segments:
            gap = float(seg["start"]) - float(last_end)
            if gap >= stall_gap:
                idx += 1
                cand.append({
                    "id": f"evt_{idx:06d}",
                    "t_request": float(last_end) + 1.0,
                    "type": "stall",
                    "source": "system",
                    "context": f"（無発話が約{int(gap)}秒続いている）",
                    "hint_only": True
                })
            last_end = float(seg["end"])

    cand.sort(key=lambda x: (x["t_request"], x["type"]))

    save_json(out_dir / "event_candidates.json", {
        "version":"1.0",
        "candidates": cand,
        "goal": goal_text
    })
    print(f"✅ candidates={len(cand)} -> out/event_candidates.json")

if __name__ == "__main__":
    main()
