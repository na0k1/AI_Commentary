from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from scripts._util import load_json, save_json

# New Google GenAI SDK
from google import genai


# -----------------------------
# Helpers
# -----------------------------
def fill_template(template: str, mapping: dict) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def build_whisper_block(candidates: list[dict]) -> str:
    # candidates already have "context", and they are "no-vision"
    lines = []
    for c in candidates:
        t = float(c.get("t_request", 0.0))
        ctx = (c.get("context") or "").strip()
        if not ctx:
            continue
        lines.append(f"[{t:.1f}s] {ctx}")
    return "\n".join(lines)


def list_batches(out_dir: Path) -> list[Path]:
    idx_path = out_dir / "llm_inputs_index.json"
    index = load_json(idx_path)
    return [Path(p) for p in index["batches"]]


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def is_quota_or_rate_error(e: Exception) -> bool:
    """
    Gemini SDK例外はバージョンで型が揺れるので、文字列ベースで雑に判定。
    """
    s = str(e).lower()
    keywords = [
        "429",
        "rate limit",
        "quota",
        "resource_exhausted",
        "too many requests",
        "exceeded",
        "limit",
    ]
    return any(k in s for k in keywords)


def try_extract_json(text: str) -> dict:
    """
    Geminiが前後に余計な文字を付けた場合に備えて、最初の{...}を雑に抜く。
    それでもダメなら例外を投げる（=リトライ/キー切替対象）。
    """
    text = text.strip()

    # まずは素直に
    try:
        return json.loads(text)
    except Exception:
        pass

    # ```json ... ``` の可能性
    if "```" in text:
        # 最初の ``` 〜 最後の ``` の中身を取る
        parts = text.split("```")
        for i in range(len(parts) - 1):
            cand = parts[i + 1].strip()
            # 先頭に json が付くことがある
            if cand.lower().startswith("json"):
                cand = cand[4:].strip()
            try:
                return json.loads(cand)
            except Exception:
                continue

    # 最初の { から最後の } までを抜く（雑だが実務で効く）
    l = text.find("{")
    r = text.rfind("}")
    if 0 <= l < r:
        chunk = text[l : r + 1]
        return json.loads(chunk)

    raise ValueError("LLM output is not valid JSON.")


def get_api_keys(cfg: dict) -> list[str]:
    env_names = cfg.get("llm", {}).get("gemini_keys_env") or []
    keys = []
    for name in env_names:
        v = os.getenv(name)
        if v:
            keys.append(v)
    # 互換：もし1本だけ環境変数 GEMINI_API_KEY があるなら拾う
    if not keys:
        v = os.getenv("GEMINI_API_KEY")
        if v:
            keys.append(v)
    return keys


def call_gemini_json(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_retries: int,
) -> dict:
    """
    1つのAPIキーで、最大max_retries回リトライしてJSONを返す。
    失敗したら例外を投げる。
    """
    client = genai.Client(api_key=api_key)

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            # できるだけ「JSONのみ」を守らせる
            # ※SDKのconfig項目はバージョンで揺れる可能性があるので最小限で。
            resp = client.models.generate_content(
                model=model,
                contents=[
                    system_prompt,
                    user_prompt,
                ],
            )

            text = (resp.text or "").strip()
            obj = try_extract_json(text)

            # 最低限の形式チェック
            if not isinstance(obj, dict):
                raise ValueError("JSON root is not an object.")
            if obj.get("version") != "1.0":
                raise ValueError(f"Unexpected version: {obj.get('version')}")
            if "events" not in obj or not isinstance(obj["events"], list):
                raise ValueError("Missing or invalid 'events' list.")

            return obj

        except Exception as e:
            last_err = e
            # リトライは指数バックオフ気味に
            time.sleep(1.2 * attempt)

    raise RuntimeError(f"Gemini failed after retries. last_err={last_err}")


# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--force", action="store_true", help="Overwrite existing batch outputs")
    args = ap.parse_args()

    load_dotenv()

    cfg = load_json(Path(args.config))
    root = Path(args.config).resolve().parents[0]
    out_dir = root / cfg["paths"]["out_dir"]
    prompts_dir = root / cfg["paths"]["prompts_dir"]

    model = cfg["llm"]["model"]
    temperature = float(cfg["llm"].get("temperature", 0.4))
    max_retries = int(cfg["llm"].get("max_retries", 3))

    # keys
    keys = get_api_keys(cfg)
    if not keys:
        raise RuntimeError(
            "No Gemini API key found. Set env GEMINI_API_KEY_1.. or GEMINI_API_KEY."
        )

    sp_name = cfg.get("paths", {}).get("system_prompt_file") or "system_prompt_observer_ja.txt"
    system_prompt = (prompts_dir / sp_name).read_text(encoding="utf-8")
    print(f"ℹ system_prompt: {sp_name}")
    input_template = (prompts_dir / "input_template.txt").read_text(encoding="utf-8")

    # load batches
    batches = list_batches(out_dir)

    raw_dir = out_dir / "event_table_raw"
    ensure_dir(raw_dir)

    for bp in batches:
        b = load_json(bp)
        batch_id = int(b["batch_id"])
        mode = str(b.get("mode", "1"))
        goal = (b.get("goal") or "").strip()
        candidates = b.get("candidates") or []

        whisper_block = build_whisper_block(candidates)
        mapping = {
            "MODE": mode,
            "GOAL": goal,
            "RANGE_START": str(b.get("range_start_sec", 0)),
            "RANGE_END": str(b.get("range_end_sec", 0)),
            "WHISPER_BLOCK": whisper_block,
        }
        user_prompt = fill_template(input_template, mapping)

        out_path = raw_dir / f"batch_{batch_id:04d}.json"
        if out_path.exists() and not args.force:
            print(f"↪ skip (exists) batch {batch_id:04d} -> {out_path}")
            continue

        last_err: Exception | None = None
        ok = False

        # key rotation
        for key_idx, api_key in enumerate(keys, start=1):
            try:
                obj = call_gemini_json(
                    api_key=api_key,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_retries=max_retries,
                )

                # ここで source の正規化（念のため）
                # Geminiが "system" など勝手に混ぜたらここで抑止してもいいが、
                # 今は input_template と system_prompt で縛っている前提。
                save_json(out_path, obj)
                print(f"✅ Gemini batch {batch_id:04d} -> {out_path} (key#{key_idx})")
                ok = True
                last_err = None
                break

            except Exception as e:
                last_err = e
                # クォータ/レート系なら次のキーに切り替え
                if is_quota_or_rate_error(e):
                    print(f"⚠ batch {batch_id:04d} key#{key_idx} quota/rate error -> switch key: {e}")
                    continue

                # それ以外は「キーを変えても直らない」可能性が高いので即エラー
                print(f"❌ batch {batch_id:04d} non-quota error: {e}")
                break

        if not ok:
            raise RuntimeError(f"LLM failed for batch {batch_id:04d}: {last_err}")


if __name__ == "__main__":
    main()
