"""jev-music: librosa で測定し、Jev で判定する音楽解析 CLI。"""

import argparse
import json
import sys
import time
from pathlib import Path

from . import features, jev


def top(probs: dict, n: int = 3) -> str:
    items = sorted(probs.items(), key=lambda kv: -kv[1])[:n]
    return " / ".join(f"{k} {v:.0%}" for k, v in items if v > 0)


def render(path: str, f: features.Features, result: dict | None, elapsed: dict) -> str:
    lines = [f"🎵 {Path(path).name}", ""]
    lines.append("[librosa] 測定")
    lines.append(f"  テンポ     {f.bpm} BPM（ビート {f.beat_count} 個 / 拍の明確さ {f.pulse_clarity} / {'3拍子系' if f.meter == 'triple' else '2・4拍子系'}）")
    lines.append(f"  キー       {f.key}（確からしさ {f.key_confidence}）")
    lines.append(f"  長さ       {f.duration_sec} 秒 / 音圧 {f.loudness_db} dBFS / 抑揚 {f.dynamic_range_db} dB")
    lines.append(f"  音色       重心 {f.brightness_hz:.0f} Hz / 低音比 {f.bass_ratio} / 高音比 {f.treble_ratio} / ノイズ感 {f.noisiness}")
    lines.append(f"  リズム     打楽器比 {f.percussive_ratio} / 毎秒 {f.onset_rate} 音")
    if result:
        a = result["answers"]
        lines += ["", "[Jev] 判定"]
        lines.append(f"  ジャンル   {a['genre']['choice']}（{top(a['genre']['probabilities'])}）")
        lines.append(f"  ムード     {a['mood']['choice']}（{top(a['mood']['probabilities'])}）")
        lines.append(f"  明るさ     {a['valence']['score']:.2f} / 4")
        lines.append(f"  激しさ     {a['energy']['score']:.2f} / 4")
        lines.append(f"  踊れる     {a['danceable']['noul']:.0%}")
        lines.append(f"  作業BGM    {a['focus_bgm']['noul']:.0%}")
        lines.append(f"  電子音中心 {a['electronic']['noul']:.0%}")
    lines += ["", f"  ⏱ 解析 {elapsed['analyze']:.2f}s" + (f" / Jev {elapsed['jev']:.2f}s" if "jev" in elapsed else "")]
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(prog="jev-music", description="音楽ファイルのテンポ・キーを librosa で測定し、ジャンル・ムードを Jev で判定する")
    p.add_argument("files", nargs="+", help="mp3 / wav などの音声ファイル")
    p.add_argument("--json", action="store_true", help="JSON で出力する")
    p.add_argument("--no-jev", action="store_true", help="librosa の測定だけ行う")
    p.add_argument("--hint", help="曲名・アーティスト・タグなど判定のヒントにするテキスト")
    p.add_argument("--duration", type=float, default=120.0, help="解析する最大秒数（既定 120）")
    args = p.parse_args()

    outputs, failed = [], False
    for path in args.files:
        try:
            t0 = time.perf_counter()
            f = features.extract(path, max_duration=args.duration)
            elapsed = {"analyze": time.perf_counter() - t0}
            result = None
            if not args.no_jev:
                t1 = time.perf_counter()
                result = jev.classify(f, hint=args.hint)
                elapsed["jev"] = time.perf_counter() - t1
        except Exception as e:  # 1ファイルの失敗で全体を止めない
            print(f"❌ {path}: {e}", file=sys.stderr)
            failed = True
            continue

        if args.json:
            outputs.append({"file": path, "features": f.to_dict(), "jev": result, "elapsed_sec": elapsed})
        else:
            print(render(path, f, result, elapsed), end="\n\n")

    if args.json:
        print(json.dumps(outputs, ensure_ascii=False, indent=2))
    sys.exit(1 if failed else 0)
