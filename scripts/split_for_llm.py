from __future__ import annotations
import argparse
from pathlib import Path
from scripts._util import load_json, save_json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]
    data = load_json(out_dir / "event_candidates.json")
    candidates = data["candidates"]

    batch_size = int(cfg["llm"]["batch_size_candidates"])
    goal = data.get("goal")  # may be None

    llm_inputs = out_dir / "llm_inputs"
    llm_inputs.mkdir(parents=True, exist_ok=True)

    batches = []
    for i in range(0, len(candidates), batch_size):
        b = candidates[i:i+batch_size]
        batch_id = (i // batch_size) + 1
        out = {
            "batch_id": batch_id,
            "mode": int(cfg["modes"]["mode"]),
            "goal": goal,  # may be None (fallback handled later)
            "candidates": b
        }
        p = llm_inputs / f"batch_{batch_id:04d}.json"
        save_json(p, out)
        batches.append(str(p))

    save_json(out_dir / "llm_inputs_index.json", {"version":"1.0","batches":batches})
    print(f"✅ batches={len(batches)} -> out/llm_inputs/")

if __name__ == "__main__":
    main()
