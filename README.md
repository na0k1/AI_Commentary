# (freeze) AI Commentary Pipeline for Shinelll
※もう使わないので凍結します。

人間プレイ × AI後付け実況 用のローカルパイプラインです。  
ゲーム録画ファイルから、以下を自動生成します。

- `out/commentary_mix.wav` … AI実況音声
- `out/chapters.txt` … YouTube用チャプター
- `out/event_table.json` … 中間イベント表

## 前提

- Windows 11
- Python 3.12
- ffmpeg / ffprobe が PATH に通っていること
- VOICEVOX エンジンが起動していること
- Gemini API キーを利用できること

## ディレクトリ構成

```text
project_root/
  video.mp4
  manual_events.jsonl
  llm_config.json
  .env
  prompts/
    input_template.txt
    system_prompt_observer_ja.txt
    system_prompt_style_guide_01.txt
  scripts/
    run_all.py
    extract_audio.py
    whisper_gpu.py
    detect_events.py
    split_for_llm.py
    generate_event_table.py
    apply_intro_and_policy.py
    voicevox_batch_generate.py
    build_parts_meta.py
    mix_audio_from_events.py
    make_chapters.py
````

## セットアップ

### 1. 仮想環境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
```

### 2. 依存パッケージ

```powershell
pip install -U python-dotenv faster-whisper pydub requests google-genai
```

必要に応じて GPU 用:

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

### 3. `.env`

```env
GEMINI_API_KEY_1=your_key_here
GEMINI_API_KEY_2=your_key_here
GEMINI_API_KEY_3=your_key_here
```

### 4. VOICEVOX

VOICEVOX エンジンを起動し、既定では以下を利用します。

```text
http://127.0.0.1:50021
```

## 実行

```powershell
python .\scripts\run_all.py
```

## 出力

* `out/commentary_mix.wav`
* `out/chapters.txt`
* `out/event_table.json`

## よく使う個別実行

## 途中再開

### 利用できるステップ名を表示
```powershell
python .\scripts\run_all.py --list-steps
````

### 途中から再開

例：VOICEVOX以降だけ再開する

```powershell
python .\scripts\run_all.py --from voicevox_batch_generate
```

### 1ステップだけ実行

例：chapters だけ作り直す

```powershell
python .\scripts\run_all.py --only make_chapters
```

### LLM生成を強制作り直し

既存の `out/event_table_raw/` を上書きして再生成したい場合

```powershell
python .\scripts\run_all.py --from generate_event_table --force-llm
```

### LLM生成だけやり直す

```powershell
python -m scripts.generate_event_table --config .\llm_config.json --force
```

### VOICEVOX以降だけやり直す

```powershell
python -m scripts.voicevox_batch_generate --config .\llm_config.json
python -m scripts.build_parts_meta --config .\llm_config.json
python -m scripts.mix_audio_from_events --config .\llm_config.json
```

## manual_events.jsonl

1行1イベントの JSONL です。

例:

```jsonl
{"t":"00:00","tag":"start","label":"開始"}
{"t":"00:08","tag":"goal","label":"今回の目的：初回の流れ確認"}
{"t":"46:10","tag":"end","label":"区切り：パート終了"}
```

### tag の用途

* `start` … 章の開始基点
* `goal` … 今回の目的
* `chapter` … 節目
* `end` … パート終了

## プロンプト切替

`llm_config.json` の `paths.system_prompt_file` で切替します。

例:

```json
"paths": {
  "video": "video.mp4",
  "manual_events": "manual_events.jsonl",
  "out_dir": "out",
  "prompts_dir": "prompts",
  "system_prompt_file": "system_prompt_style_guide_01.txt"
}
```

## 注意

* `out/` は生成物なのでコミットしない
* `.env` は絶対にコミットしない
* `video.mp4` など大きいローカル素材もコミットしない
* Notion は設計・運用メモ、GitHub はコードの正本として扱う

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
