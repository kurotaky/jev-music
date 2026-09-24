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
🎵 Kevin_MacLeod_-_Vibe_Ace.ogg

[librosa] 測定
  テンポ     103.4 BPM（ビート 98 個 / 拍の明確さ 0.534 / 2・4拍子系）
  キー       E major（確からしさ 0.139）
  長さ       61.5 秒 / 音圧 -22.7 dBFS / 抑揚 18.4 dB
  音色       重心 887 Hz / 低音比 0.794 / 高音比 0.0011 / ノイズ感 0.0026
  リズム     打楽器比 0.067 / 毎秒 4.75 音

[Jev] 判定
  ジャンル   jazz（jazz 60% / hiphop 17% / rnb_soul 5%）
  ムード     dark（dark 51% / calm 41% / romantic 5%）
  明るさ     1.42 / 4
  激しさ     1.49 / 4
  踊れる     39%
  作業BGM    51%
  電子音中心 37%

  ⏱ 解析 2.58s / Jev 0.50s
```

## 評価

librosa 付属の楽曲 7 曲でジャンル判定を確認できる。

```sh
uv run python scripts/eval_examples.py
```

| 曲 | 判定 | |
|---|---|---|
| brahms（クラシック） | classical 84% | ✅ |
| choice（ドラムンベース） | drum_and_bass 95% | ✅ |
| fishin（カントリーポップ） | pop 79%（country_bluegrass は 3 位） | ❌ |
| nutcracker（クラシック） | classical 82% | ✅ |
| pistachio（ラグタイム） | classical 81% | ✅ |
| sweetwaltz（ワルツ） | classical 99% | ✅ |
| vibeace（ジャズ寄りラウンジ） | jazz 60% | ✅ |

改善の経緯: 2/7 → 6/7

- ビート間隔の規則性はビート検出器が等間隔に揃えるため全曲 0.93〜0.96 になり、電子音楽寄りに判定されていた → オンセット自己相関による「拍の明確さ」と拍子推定に置き換え
- 低音比（150Hz 未満）・高音比（4kHz 超）・スペクトル平坦度を追加
- ジャンルの説明を、state に渡す特徴量と同じ語彙（低音・打楽器・音圧・抑揚）で書き直した

## Jev に投げている質問

| key | type | 内容 |
|---|---|---|
| genre | choice | ジャンル（17種、`jev.py` の `GENRES`） |
| mood | choice | ムード（7種、`MOODS`） |
| valence | score | 明るさ 0〜4 |
| energy | score | 激しさ 0〜4 |
| danceable | noul | 踊りやすいか |
| focus_bgm | noul | 作業用BGMに向くか |
| electronic | noul | 電子音中心か |

## 環境変数

| 名前 | 既定値 |
|---|---|
| `AI_GATEWAY_API_KEY` | （必須） |
| `AI_GATEWAY_BASE_URL` | `https://ai-gateway.lolipop.jp` |
| `JEV_MODEL` | `typesafe/jev-latest` |

## メモ

- 初回実行は librosa（numba）の JIT コンパイルで 20 秒ほどかかる。2 曲目以降は 1〜3 秒。
- 解析は先頭 120 秒まで（`--duration` で変更可）。
