from __future__ import annotations
import argparse, requests
from pathlib import Path
from scripts._util import load_json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]
    table = load_json(out_dir / "event_table.json")

    base = cfg["voicevox"]["base_url"]
    speaker = int(cfg["voicevox"]["speaker_id"])
    parts_dir = out_dir / "commentary_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    params_override = {
        "speedScale": float(cfg["voicevox"]["speedScale"]),
        "volumeScale": float(cfg["voicevox"]["volumeScale"]),
        "intonationScale": float(cfg["voicevox"]["intonationScale"]),
    }

    events = table["events"]

    generated = 0
    skipped = 0

    for i, ev in enumerate(events, start=1):
        text = (ev.get("text") or "").strip()
        if not text:
            skipped += 1
            continue

        ev_type = (ev.get("type") or "").strip()
        src = (ev.get("source") or "").strip()

        # ✅ 方針：chapterは基本読まない
        # 例外：introとして挿入した system chapter だけ読む
        if ev_type == "chapter" and src != "system":
            skipped += 1
            continue

        q = requests.post(
            f"{base}/audio_query",
            params={"text": text, "speaker": speaker},
            timeout=30,
        ).json()

        for k, v in params_override.items():
            q[k] = v

        wav = requests.post(
            f"{base}/synthesis",
            params={"speaker": speaker},
            json=q,
            timeout=60,
        ).content

        out_wav = parts_dir / f"{i:04d}.wav"
        out_wav.write_bytes(wav)
        generated += 1

    print(f"✅ VOICEVOX parts generated: {parts_dir} (generated={generated}, skipped={skipped})")

if __name__ == "__main__":
    main()
