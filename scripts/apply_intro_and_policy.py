from __future__ import annotations
import argparse, glob
from pathlib import Path
from scripts._util import load_json, save_json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]
    raw_dir = out_dir / "event_table_raw"

    files = sorted(glob.glob(str(raw_dir / "batch_*.json")))
    if not files:
        raise FileNotFoundError("No out/event_table_raw/batch_*.json")

    # goal fallback: prefer event_candidates goal > config fallback
    goal = None
    cand = load_json(out_dir / "event_candidates.json")
    if cand.get("goal"):
        goal = cand["goal"]
    if not goal:
        fb = cfg["fallbacks"]["goal_text"]  # "目的：進行確認"
        goal = fb.replace("目的：","").strip()

    # ---- 1) collect LLM events but keep only normal/stall ----
    merged = []
    for f in files:
        obj = load_json(Path(f))
        events = obj.get("events") or []
        for ev in events:
            t = float(ev.get("t", 0.0) or 0.0)
            typ = (ev.get("type") or "").strip()
            txt = (ev.get("text") or "").strip()
            src = (ev.get("source") or "system").strip()

            if typ not in ("normal", "stall"):
                continue
            if not txt:
                continue
            # hard normalize source
            if src not in ("whisper","system"):
                src = "system"
            merged.append({"t": t, "type": typ, "text": txt, "source": src})

    merged.sort(key=lambda x: float(x["t"]))

    # ---- 2) intro insert (voiced) ----
    if cfg["intro"]["enabled"]:
        part = int(cfg["intro"]["part"])
        lines = cfg["intro"]["part1_lines"] if part == 1 else cfg["intro"]["part2_lines"]
        t0 = float(cfg["audio"]["silence_head_sec"])

        intro_events = []
        t = t0
        for line in lines:
            text = line.replace("{goal}", goal).strip()
            if not text:
                continue
            # introは音声化対象
            intro_events.append({"t": t, "type":"intro", "text": text, "source":"system"})
            t += 1.0  # 仮。最終はmixでno-overlap適用

        merged = intro_events + merged

    # ---- 3) save voiced-only event table ----
    save_json(out_dir / "event_table.json", {"version":"1.0", "events": merged, "goal": goal})
    print("✅ out/event_table.json written (voiced events only)")

if __name__ == "__main__":
    main()
