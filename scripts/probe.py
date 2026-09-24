"""Jev の性質を調べる実験。

実験1: state を「数値＋言葉」「数値だけ」「言葉だけ」で渡したときに、ジャンル判定がどう変わるか
実験2: 1曲を基準に特徴を1つずつ動かしたとき、ジャンルの確率がどう動くか（数値だけ / 数値＋言葉）

    uv run python scripts/probe.py            # docs/probe-data.{json,md} を出力
"""

import dataclasses
import json
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import librosa

from eval_examples import EXPECTED
from jev_music import features, jev

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "features.json"
OUT_JSON = ROOT / "docs" / "probe-data.json"
OUT_MD = ROOT / "docs" / "probe-data.md"

MODES = ["both", "numbers", "labels"]
MODE_JA = {"both": "数値＋言葉", "numbers": "数値だけ", "labels": "言葉だけ"}

BASE_SONG = "nutcracker"  # 低音・打楽器とも少ないクラシック。ここから特徴を動かす
SWEEPS = {
    # field: (値の列, 言葉が切り替わる境界)
    "bass_ratio": ([round(i * 0.1, 1) for i in range(10)], [0.2, 0.5]),
    "percussive_ratio": ([0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6], [0.1, 0.2, 0.4]),
    "bpm": ([60, 75, 90, 105, 120, 135, 150, 165, 180], [90, 130]),
}
SWEEP_MODES = ["numbers", "both"]


def load_features() -> dict[str, features.Features]:
    cached = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    out = {}
    for name in EXPECTED:
        if name not in cached:
            cached[name] = features.extract(librosa.ex(name)).to_dict()
        out[name] = features.Features(**cached[name])
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    return out


def genre_probs(f: features.Features, mode: str) -> dict[str, float]:
    return jev.classify(f, mode=mode)["answers"]["genre"]["probabilities"]


def run_parallel(jobs: list) -> list:
    with ThreadPoolExecutor(max_workers=8) as ex:
        return list(ex.map(lambda job: job(), jobs))


def experiment1(feats: dict) -> list[dict]:
    keys = [(name, mode) for name in EXPECTED for mode in MODES]
    results = run_parallel([lambda n=n, m=m: genre_probs(feats[n], m) for n, m in keys])
    rows = []
    for (name, mode), probs in zip(keys, results):
        choice = max(probs, key=probs.get)
        rows.append({
            "song": name,
            "mode": mode,
            "choice": choice,
            "choice_prob": probs[choice],
            "correct": choice in EXPECTED[name],
            "prob_on_correct": sum(probs.get(g, 0) for g in EXPECTED[name]),
            "probs": probs,
        })
    return rows


def experiment2(feats: dict) -> list[dict]:
    base = feats[BASE_SONG]
    keys = [(field, v, mode) for field, (values, _) in SWEEPS.items() for v in values for mode in SWEEP_MODES]
    results = run_parallel([lambda fl=fl, v=v, m=m: genre_probs(dataclasses.replace(base, **{fl: v}), m) for fl, v, m in keys])
    return [{"field": fl, "value": v, "mode": m, "probs": p} for (fl, v, m), p in zip(keys, results)]


def pct(v: float) -> str:
    return f"{v:.0%}" if v >= 0.005 else "·"


def render_md(feats: dict, exp1: list[dict], exp2: list[dict]) -> str:
    lines = ["# probe データ（自動生成）", "", "`uv run python scripts/probe.py` の出力。考察は [jev-probe.md](jev-probe.md) を参照。", ""]

    lines += ["## 実験1: 数値と言葉のどちらを見ているか", "", "| 曲 | 正解 | " + " | ".join(MODE_JA[m] for m in MODES) + " |", "|---|---|" + "---|" * len(MODES)]
    by = {(r["song"], r["mode"]): r for r in exp1}
    for name, ok in EXPECTED.items():
        cells = []
        for m in MODES:
            r = by[(name, m)]
            cells.append(f"{'✅' if r['correct'] else '❌'} {r['choice']} {pct(r['choice_prob'])}")
        lines.append(f"| {name} | {', '.join(sorted(ok))} | " + " | ".join(cells) + " |")
    lines.append("| **正解数** | | " + " | ".join(f"**{sum(by[(n, m)]['correct'] for n in EXPECTED)}/{len(EXPECTED)}**" for m in MODES) + " |")
    lines.append("| **正解ジャンルへの確率（平均）** | | " + " | ".join(f"**{sum(by[(n, m)]['prob_on_correct'] for n in EXPECTED) / len(EXPECTED):.0%}**" for m in MODES) + " |")

    lines += ["", f"## 実験2: 特徴を1つずつ動かしたときのジャンル確率（基準曲: {BASE_SONG}）", ""]
    base = feats[BASE_SONG]
    lines.append(f"基準値: bass_ratio={base.bass_ratio}, percussive_ratio={base.percussive_ratio}, bpm={base.bpm}。他の特徴は固定。")
    for field, (values, bounds) in SWEEPS.items():
        rows = [r for r in exp2 if r["field"] == field]
        # どこかで 15% 以上になったジャンルだけ列にする
        genres = sorted({g for r in rows for g, p in r["probs"].items() if p >= 0.15}, key=lambda g: -max(r["probs"].get(g, 0) for r in rows))
        for mode in SWEEP_MODES:
            lines += ["", f"### {field}（{MODE_JA[mode]}）", "", f"言葉が切り替わる境界: {', '.join(map(str, bounds))}", ""]
            lines.append(f"| {field} | " + " | ".join(genres) + " |")
            lines.append("|---|" + "---|" * len(genres))
            for r in (r for r in rows if r["mode"] == mode):
                top = max(r["probs"], key=r["probs"].get)
                cells = [f"**{pct(r['probs'].get(g, 0))}**" if g == top else pct(r["probs"].get(g, 0)) for g in genres]
                lines.append(f"| {r['value']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    feats = load_features()
    exp1 = experiment1(feats)
    exp2 = experiment2(feats)
    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps({"experiment1": exp1, "experiment2": exp2}, ensure_ascii=False, indent=1))
    OUT_MD.write_text(render_md(feats, exp1, exp2))
    print(OUT_MD.read_text())


if __name__ == "__main__":
    main()
