from __future__ import annotations

import argparse
import time
import wave
from pathlib import Path

import requests
from scripts._util import load_json


def write_silence_wav(path: Path, duration_sec: float = 0.05, sample_rate: int = 48000) -> None:
    frames = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16bit
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * frames)


def post_with_retry(
    url: str,
    *,
    params: dict,
    json_body: dict | None = None,
    timeout: int = 30,
    retries: int = 3,
    backoff_sec: float = 1.0,
) -> requests.Response:
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, params=params, json=json_body, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_err = e
            if attempt == retries:
                break
            time.sleep(backoff_sec * attempt)

    raise RuntimeError(f"POST failed after {retries} retries: {url} / {last_err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]
    table = load_json(out_dir / "event_table.json")

    base = cfg["voicevox"]["base_url"].rstrip("/")
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
    silent = 0

    for i, ev in enumerate(events, start=1):
        out_wav = parts_dir / f"{i:04d}.wav"

        text = (ev.get("text") or "").strip()
        ev_type = (ev.get("type") or "").strip()
        src = (ev.get("source") or "").strip()

        # 空テキストは欠番を作らず無音wav
        if not text:
            write_silence_wav(out_wav)
            silent += 1
            continue

        # chapter は基本読まない。ただし今後混ざっても欠番防止で無音wavを置く
        if ev_type == "chapter" and src != "system":
            write_silence_wav(out_wav)
            silent += 1
            continue

        try:
            q_resp = post_with_retry(
                f"{base}/audio_query",
                params={"text": text, "speaker": speaker},
                timeout=30,
                retries=3,
                backoff_sec=1.0,
            )
            q = q_resp.json()

            for k, v in params_override.items():
                q[k] = v

            syn_resp = post_with_retry(
                f"{base}/synthesis",
                params={"speaker": speaker},
                json_body=q,
                timeout=60,
                retries=3,
                backoff_sec=1.0,
            )
            out_wav.write_bytes(syn_resp.content)
            generated += 1

        except Exception as e:
            raise RuntimeError(
                f"VOICEVOX generation failed at index={i}, "
                f"type={ev_type}, source={src}, text={text!r}: {e}"
            ) from e

    print(
        f"✅ VOICEVOX parts generated: {parts_dir} "
        f"(generated={generated}, silent={silent}, total={len(events)})"
    )


if __name__ == "__main__":
    main()