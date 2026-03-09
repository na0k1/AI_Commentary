from __future__ import annotations
import subprocess, sys
from pathlib import Path

STEPS = [
    "extract_audio",
    "whisper_gpu",
    "detect_events",
    "split_for_llm",
    "generate_event_table",
    "apply_intro_and_policy",
    "voicevox_batch_generate",
    "build_parts_meta",
    "mix_audio_from_events",
    "make_chapters",
]

def run(cmd: list[str], cwd: Path) -> None:
    print("▶", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(cwd))

def main():
    # project_root = run_all.py の1つ上の階層
    root = Path(__file__).resolve().parents[1]
    cfg = root / "llm_config.json"
    if not cfg.exists():
        raise FileNotFoundError(f"llm_config.json not found: {cfg}")

    py = sys.executable

    for mod in STEPS:
        # -m で scripts パッケージとして実行
        run([py, "-m", f"scripts.{mod}", "--config", str(cfg)], cwd=root)

    print("\n✅ Done. Outputs:")
    print(" - out/commentary_mix.wav")
    print(" - out/chapters.txt")
    print(" - out/event_table.json")

if __name__ == "__main__":
    main()
