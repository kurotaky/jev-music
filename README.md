# jev-music

音楽ファイル（mp3 / wav / ogg など）を解析して、テンポ・ビート・キーと、ジャンル・ムードを返す CLI。

- **測定**（テンポ・ビート・キー・音圧・音色）… [librosa](https://librosa.org/)
- **判定**（ジャンル・ムード・明るさ・激しさ・踊れるか・作業BGM向きか）… [Jev](https://lolipop.jp/ai/media/what-is-jev/)（ロリポップ！AIゲートウェイ経由）

Jev はテキスト（JSON）で判定材料を受け取る判定特化モデルなので、音声そのものは渡さず、librosa で抽出した特徴を言葉に直して `state` として渡している。

```
mp3/wav ──librosa──▶ 特徴量 (BPM, キー, 音圧, 音色…) ──テキスト化──▶ Jev /v1/systemone ──▶ ジャンル・ムード
```

## セットアップ

```sh
uv sync
export AI_GATEWAY_API_KEY=...   # ロリポップ！AIゲートウェイの API キー
```

## 使い方

```sh
uv run jev-music song.mp3 other.wav
uv run jev-music song.mp3 --json          # JSON 出力
uv run jev-music song.mp3 --no-jev        # librosa の測定だけ
uv run jev-music song.mp3 --hint "曲名: ○○ / タグ: シティポップ"   # 判定のヒントを追加
```

出力例:

```
🎵 brahms.ogg

[librosa] 測定
  テンポ     143.6 BPM（ビート 95 個 / 規則性 0.939）
  キー       G minor（確からしさ 0.099）
  長さ       45.8 秒 / 音圧 -29.5 dBFS / 抑揚 57.5 dB
  音色       重心 2085 Hz / 打楽器比 0.078 / 毎秒 2.14 音

[Jev] 判定
  ジャンル   classical（classical 86% / folk_acoustic 7% / pop 3%）
  ムード     energetic（energetic 66% / sad 16% / dark 9%）
  明るさ     1.09 / 4
  激しさ     2.49 / 4
  踊れる     52%
  作業BGM    45%

  ⏱ 解析 1.20s / Jev 0.43s
```

## Jev に投げている質問

| key | type | 内容 |
|---|---|---|
| genre | choice | ジャンル（12種、`jev.py` の `GENRES`） |
| mood | choice | ムード（7種、`MOODS`） |
| valence | score | 明るさ 0〜4 |
| energy | score | 激しさ 0〜4 |
| danceable | noul | 踊りやすいか |
| focus_bgm | noul | 作業用BGMに向くか |

## 環境変数

| 名前 | 既定値 |
|---|---|
| `AI_GATEWAY_API_KEY` | （必須） |
| `AI_GATEWAY_BASE_URL` | `https://ai-gateway.lolipop.jp` |
| `JEV_MODEL` | `typesafe/jev-latest` |

## メモ

- 初回実行は librosa（numba）の JIT コンパイルで 20 秒ほどかかる。2 曲目以降は 1〜3 秒。
- 解析は先頭 120 秒まで（`--duration` で変更可）。
