"""librosa 付属の楽曲でジャンル判定の当たり具合を確認する。

    uv run python scripts/eval_examples.py
"""

import warnings

import librosa

from jev_music import features, jev

warnings.filterwarnings("ignore")

# 正解として許容するジャンル（jev.GENRES のキー）
EXPECTED = {
    "brahms": {"classical"},
    "choice": {"drum_and_bass", "edm"},
    "fishin": {"country_bluegrass", "folk_acoustic"},
    "nutcracker": {"classical"},
    "pistachio": {"jazz", "classical"},  # ラグタイムのピアノ
    "sweetwaltz": {"classical", "folk_acoustic"},
    "vibeace": {"jazz", "lofi"},
}


def main() -> None:
    hits = 0
    for name, ok in EXPECTED.items():
        f = features.extract(librosa.ex(name))
        a = jev.classify(f)["answers"]
        genre, mood = a["genre"], a["mood"]
        hit = genre["choice"] in ok
        hits += hit
        p = genre["probabilities"][genre["choice"]]
        print(f"{'✅' if hit else '❌'} {name:11s} → {genre['choice']:18s} {p:4.0%}  mood={mood['choice']:10s} (正解: {', '.join(sorted(ok))})")
    print(f"\n{hits}/{len(EXPECTED)} 正解")


if __name__ == "__main__":
    main()
