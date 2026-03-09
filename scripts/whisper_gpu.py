from __future__ import annotations
import argparse, os
from pathlib import Path
from scripts._util import load_json, save_json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]
    audio = out_dir / "mic.wav"
    out_json = out_dir / "whisper.json"

    from faster_whisper import WhisperModel

    # GPU優先→失敗時CPU
    try:
        model = WhisperModel("medium", device="cuda", compute_type="float16")
        device = "cuda"
    except Exception:
        model = WhisperModel("medium", device="cpu", compute_type="int8")
        device = "cpu"

    print(f"▶ faster-whisper device={device}")

    # ★VADを切る（混在音声でもゼロになりにくい）
    segments, info = model.transcribe(
        str(audio),
        language="ja",
        vad_filter=False
    )

    segs = []
    for s in segments:
        text = (s.text or "").strip()
        if not text:
            continue
        segs.append({"start": float(s.start), "end": float(s.end), "text": text})

    save_json(out_json, {"language": info.language, "duration": float(info.duration), "segments": segs})
    print(f"✅ whisper -> {out_json}  segments={len(segs)}")

    # ★Windows+CUDAで終了時に落ちることがあるので、保存後に強制終了（回避策）
    os._exit(0)

if __name__ == "__main__":
    main()
