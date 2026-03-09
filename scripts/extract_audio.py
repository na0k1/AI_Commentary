from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
from scripts._util import load_json

def ffprobe_audio_streams(video: Path) -> list[dict]:
    cmd = [
        "ffprobe","-v","error","-select_streams","a",
        "-show_entries","stream=index,codec_type,tags:stream_tags",
        "-of","json", str(video)
    ]
    out = subprocess.check_output(cmd, text=True, encoding="utf-8")
    return json.loads(out).get("streams", [])

def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    video = root / cfg["paths"]["video"]
    out_dir = root / cfg["paths"]["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    mic = out_dir / "mic.wav"

    streams = ffprobe_audio_streams(video)
    if not streams:
        raise RuntimeError("No audio streams found in video")

    # ルール：
    # 1) タグに mic/microphone/マイク があればそれ
    # 2) なければ「最後の音声ストリーム」を優先（OBSの2トラックでマイクが後ろに来がち）
    prefer_idx = None
    for st in streams:
        tags = (st.get("tags") or {})
        title = (tags.get("title") or "") + " " + (tags.get("handler_name") or "")
        if any(k in title.lower() for k in ["mic", "microphone", "マイク"]):
            prefer_idx = st["index"]
            break

    if prefer_idx is None:
        prefer_idx = streams[-1]["index"]  # ★ここが変更点

    # まず prefer を試す
    try:
        run(["ffmpeg","-y","-i",str(video),"-map",f"0:{prefer_idx}","-ac","1","-ar","16000",str(mic)])
        print(f"✅ Extracted audio stream index={prefer_idx} -> {mic}")
        return
    except subprocess.CalledProcessError:
        print("⚠ preferred stream extraction failed. Fallback to mixed audio.")

    # フォールバック：全音声mix
    run(["ffmpeg","-y","-i",str(video),"-vn","-ac","1","-ar","16000",str(mic)])
    print(f"✅ Extracted mixed audio -> {mic}")

if __name__ == "__main__":
    main()
