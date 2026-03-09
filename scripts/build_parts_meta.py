from __future__ import annotations
import argparse, wave
from pathlib import Path
from scripts._util import load_json, save_json

def wav_duration_sec(p: Path) -> float:
    with wave.open(str(p), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]
    parts_dir = out_dir / "commentary_parts"
    table = load_json(out_dir / "event_table.json")
    events = table["events"]

    if not parts_dir.exists():
        raise FileNotFoundError(f"commentary_parts not found: {parts_dir}")

    items = []
    missing = []

    for idx, ev in enumerate(events, start=1):
        wav = parts_dir / f"{idx:04d}.wav"
        if not wav.exists():
            missing.append(str(wav))
            continue

        dur = wav_duration_sec(wav)
        items.append({
            "index": idx,
            "event_id": ev.get("id") or f"evt_idx_{idx:04d}",
            "wav": str(wav).replace("\\","/"),
            "dur_sec": dur
        })

    # 欠番があるなら止める（=欠番を仕様として許さない）
    if missing:
        sample = "\n".join(missing[:10])
        raise RuntimeError(
            f"Missing wav files: {len(missing)}\n"
            f"Example:\n{sample}\n"
            f"Fix: regenerate VOICEVOX parts so every index has a wav."
        )

    meta = {"version":"1.0","items":items, "count": len(items)}
    save_json(out_dir / "parts_meta.json", meta)
    print("✅ out/parts_meta.json written")

if __name__ == "__main__":
    main()
