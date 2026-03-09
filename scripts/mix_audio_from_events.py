from __future__ import annotations
import argparse, subprocess, wave
from pathlib import Path
from pydub import AudioSegment
from scripts._util import load_json

def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)

def wav_duration_sec(p: Path) -> float:
    with wave.open(str(p), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]

    table = load_json(out_dir / "event_table.json")
    meta = load_json(out_dir / "parts_meta.json")
    events = table["events"]
    items = {it["index"]: it for it in meta["items"]}

    gap = float(cfg["policy"]["no_overlap"]["gap_sec"])
    drop_late = float(cfg["policy"]["no_overlap"]["drop_if_late_sec"])

    # ✅ 動画(=mic.wav)の実長でクランプ
    mic_wav = out_dir / "mic.wav"
    if mic_wav.exists():
        max_sec = wav_duration_sec(mic_wav)
    else:
        # 保険：無ければ「最後のイベントまで」
        max_sec = None

    scheduled = []
    current_end = 0.0

    for idx, ev in enumerate(events, start=1):
        if idx not in items:
            continue

        t_req = float(ev.get("t", 0.0))
        dur = float(items[idx]["dur_sec"])

        start = max(t_req, current_end + gap)

        # 遅れすぎたら捨てる
        if start - t_req > drop_late:
            continue

        # ✅ クランプ：動画長を超える発話は捨てる
        if max_sec is not None and start >= max_sec:
            continue
        if max_sec is not None and start + dur > max_sec:
            # 途中で切るより「捨てる」方が安全（設計思想的にも）
            continue

        scheduled.append((idx, start, dur))
        current_end = start + dur

    if not scheduled:
        raise RuntimeError("No scheduled audio events. Check VOICEVOX outputs or LLM output.")

    total_sec = (max_sec if max_sec is not None else (scheduled[-1][1] + scheduled[-1][2] + 1.0))
    timeline = AudioSegment.silent(duration=int(total_sec * 1000), frame_rate=48000)

    parts_dir = out_dir / "commentary_parts"
    for idx, start, _dur in scheduled:
        wav = parts_dir / f"{idx:04d}.wav"
        seg = AudioSegment.from_wav(wav)
        timeline = timeline.overlay(seg, position=int(start * 1000))

    raw = out_dir / "commentary_mix_raw.wav"
    timeline.export(raw, format="wav")

    final = out_dir / "commentary_mix.wav"
    ln = cfg["audio"]["loudnorm"]
    run([
        "ffmpeg", "-y",
        "-i", str(raw),
        "-af", f"loudnorm=I={ln['i']}:TP={ln['tp']}:LRA={ln['lra']}",
        "-ar", "48000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(final)
    ])

    print(f"✅ commentary_mix.wav -> {final}")

if __name__ == "__main__":
    main()
