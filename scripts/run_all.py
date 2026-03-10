from __future__ import annotations

import argparse
import subprocess
import sys
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


def validate_step(step_name: str) -> None:
    if step_name not in STEPS:
        raise ValueError(
            f"Unknown step: {step_name}\n"
            f"Available steps: {', '.join(STEPS)}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        help="Path to llm_config.json (default: project_root/llm_config.json)",
    )
    ap.add_argument(
        "--from",
        dest="from_step",
        help="Start running from this step (inclusive)",
    )
    ap.add_argument(
        "--only",
        dest="only_step",
        help="Run only this step",
    )
    ap.add_argument(
        "--list-steps",
        action="store_true",
        help="Print available step names and exit",
    )
    ap.add_argument(
        "--force-llm",
        action="store_true",
        help="Pass --force to generate_event_table",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    cfg = Path(args.config).resolve() if args.config else (root / "llm_config.json")

    if not cfg.exists():
        raise FileNotFoundError(f"llm_config.json not found: {cfg}")

    if args.list_steps:
        print("Available steps:")
        for s in STEPS:
            print(f" - {s}")
        return

    if args.from_step and args.only_step:
        raise ValueError("--from and --only cannot be used together.")

    if args.from_step:
        validate_step(args.from_step)

    if args.only_step:
        validate_step(args.only_step)

    py = sys.executable

    # 実行対象の絞り込み
    if args.only_step:
        steps_to_run = [args.only_step]
    elif args.from_step:
        idx = STEPS.index(args.from_step)
        steps_to_run = STEPS[idx:]
    else:
        steps_to_run = STEPS[:]

    for mod in steps_to_run:
        cmd = [py, "-m", f"scripts.{mod}", "--config", str(cfg)]

        if mod == "generate_event_table" and args.force_llm:
            cmd.append("--force")

        run(cmd, cwd=root)

    print("\n✅ Done. Outputs:")
    print(" - out/commentary_mix.wav")
    print(" - out/chapters.txt")
    print(" - out/event_table.json")


if __name__ == "__main__":
    main()