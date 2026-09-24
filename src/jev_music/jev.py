"""抽出した特徴を Jev (ロリポップ！AIゲートウェイ /v1/systemone) に渡してジャンル・ムードを判定する。"""

import json
import os
import urllib.error
import urllib.request

from .features import Features

BASE_URL = os.environ.get("AI_GATEWAY_BASE_URL", "https://ai-gateway.lolipop.jp")
MODEL = os.environ.get("JEV_MODEL", "typesafe/jev-latest")

# 各ジャンルの説明は、state に渡す特徴量（低音・打楽器・音圧・抑揚・音色・拍）と同じ言葉で書いて比較しやすくする
GENRES = {
    "pop": "ポップ。歌もの。ドラムとベースあり（打楽器・低音とも中くらい）、音圧高め、抑揚小さめ、明るい音色",
    "rock": "ロック。ドラムとベースあり、歪んだギターで高音成分とノイズ成分が多い、音圧高い、抑揚小さい",
    "metal": "メタル。非常に速く激しい、歪みでノイズ成分・高音成分が非常に多い、音圧が非常に高い",
    "hiphop": "ヒップホップ。打楽器成分が多い（キック・スネアが明確）、低音が非常に多い、BPM 80-100前後",
    "rnb_soul": "R&B/ソウル。歌もの、ドラムとベースあり、グルーヴ重視、中くらいのテンポ",
    "house_techno": "ハウス/テクノ。打ち込みの4つ打ちキックで打楽器成分・低音とも多い、拍が非常に明確・機械的、BPM 120-130前後",
    "edm": "EDM/ダブステップ。派手なシンセでノイズ成分・高音成分が多い、低音が非常に多い、音圧が非常に高い",
    "drum_and_bass": "ドラムンベース/ブレイクビーツ。細かく速いドラム、太いベースで低音が非常に多い、BPM 160-180前後（検出では 80-90 や 130-140 に誤ることも）、短調が多い",
    "lofi": "Lo-fi/チル。ゆったりしたヒップホップ系ビートあり（打楽器成分中くらい）、こもった暗い音色、音圧控えめ",
    "ambient": "アンビエント。拍が弱いか無い、打楽器ほぼ無し、音数が少なく持続的な音",
    "jazz": "ジャズ。ウッドベースが鳴り続けるため低音が多い一方、ドラムはブラシやシンバル中心で打楽器成分は少ない。ピアノ・管楽器、スウィング",
    "classical": "クラシック。オーケストラ・ピアノ・弦楽・室内楽。ドラムもベースラインも無いので低音と打楽器成分が少ない、澄んだ楽音、録音の音圧は控えめで抑揚が大きい、3拍子のワルツも多い",
    "soundtrack": "映画・ゲーム音楽。オーケストラやシンセによる壮大な展開、抑揚が非常に大きい",
    "folk_acoustic": "フォーク/シンガーソングライター。アコースティックギターと歌が中心、ベースは中くらい、音圧と抑揚は中くらい",
    "country_bluegrass": "カントリー/ブルーグラス。バンジョー・フィドル・アコギを速く刻むので音数が多い、明るい長調、打楽器と低音は中くらい、ポップス並みの音圧で抑揚は小さい",
    "latin": "ラテン/ボサノヴァ。シンコペーションの効いたパーカッションで打楽器成分が多い、中くらいのテンポ",
    "reggae": "レゲエ。裏拍を刻むギター、ゆったりしたテンポ（BPM 60-90）、太いベースで低音が多い",
}

MOODS = {
    "happy": "楽しい・陽気",
    "energetic": "エネルギッシュ・高揚",
    "calm": "穏やか・リラックス",
    "sad": "悲しい・切ない",
    "dark": "暗い・重い",
    "romantic": "ロマンチック・甘い",
    "epic": "壮大・ドラマチック",
}


def describe(f: Features) -> dict:
    """数値だけだと判断しづらいので、目安の言葉を添えて state にする。"""

    def level(v, lo, hi, labels=("低い", "中くらい", "高い")):
        return labels[0] if v < lo else labels[2] if v > hi else labels[1]

    return {
        "duration": f"{f.duration_sec}秒",
        "tempo": f"{f.bpm} BPM（{level(f.bpm, 90, 130, ('遅い', '中くらい', '速い'))}。ビート検出は倍・半分に誤ることがある）",
        "pulse_clarity": f"{f.pulse_clarity}（拍の感じやすさ。{level(f.pulse_clarity, 0.3, 0.7, ('弱い・テンポが揺れる', 'はっきりしている', '非常に明確・機械的'))}）",
        "meter": "3拍子系" if f.meter == "triple" else "2・4拍子系",
        "key": f"{f.key}（{'長調' if 'major' in f.key else '短調'}、推定の確からしさ {f.key_confidence}）",
        "loudness": f"平均 {f.loudness_db} dBFS（音圧{level(f.loudness_db, -30, -18)}）",
        "dynamic_range": f"{f.dynamic_range_db} dB（抑揚{level(f.dynamic_range_db, 15, 30, ('小さい・コンプレッサーで均一', '中くらい', '大きい'))}）",
        "brightness": f"スペクトル重心 {f.brightness_hz:.0f} Hz（音色が{level(f.brightness_hz, 1500, 3000, ('暗い・柔らかい', '標準的', '明るい・きらびやか'))}）",
        "bass": f"150Hz未満のエネルギー比 {f.bass_ratio}（ベース・キックなど低音が{level(f.bass_ratio, 0.2, 0.5, ('少ない', '中くらい', '非常に多い'))}）",
        "treble": f"4kHz超のエネルギー比 {f.treble_ratio}（シンバル・ハイハット・歪みなど高音成分が{level(f.treble_ratio, 0.005, 0.03, ('少ない', '中くらい', '多い'))}）",
        "noisiness": f"スペクトル平坦度 {f.noisiness}（{level(f.noisiness, 0.005, 0.03, ('澄んだ楽音中心', '中くらい', 'ノイズ・歪み・シンセ成分が多い'))}）",
        "onset_rate": f"毎秒 {f.onset_rate} 音（音数{level(f.onset_rate, 2, 5, ('少ない', '中くらい', '多い'))}）",
        "percussive_ratio": f"{f.percussive_ratio}（打楽器成分{'ほぼ無し' if f.percussive_ratio < 0.1 else level(f.percussive_ratio, 0.2, 0.4, ('少ない', '中くらい', '多い'))}）",
    }


def build_questions() -> dict:
    return {
        "genre": {
            "type": "choice",
            "instructions": "この楽曲の音響特徴から、最も当てはまるジャンルはどれか？",
            "criteria": GENRES,
        },
        "mood": {
            "type": "choice",
            "instructions": "この楽曲の雰囲気として最も当てはまるものはどれか？",
            "criteria": MOODS,
        },
        "valence": {
            "type": "score",
            "instructions": "この楽曲の明るさ（ポジティブさ）は？",
            "criteria": ["とても暗い", "やや暗い", "どちらでもない", "やや明るい", "とても明るい"],
        },
        "energy": {
            "type": "score",
            "instructions": "この楽曲のエネルギー（激しさ）は？",
            "criteria": ["とても静か", "やや静か", "中くらい", "やや激しい", "とても激しい"],
        },
        "danceable": {"type": "noul", "instructions": "この楽曲は踊りやすいか？"},
        "focus_bgm": {"type": "noul", "instructions": "この楽曲は作業用BGMに向いているか？"},
        "electronic": {"type": "noul", "instructions": "この楽曲はシンセや打ち込みなど電子音が中心か？（生楽器中心なら No）"},
    }


def classify(f: Features, hint: str | None = None, timeout: float = 30) -> dict:
    key = os.environ.get("AI_GATEWAY_API_KEY")
    if not key:
        raise RuntimeError("AI_GATEWAY_API_KEY が設定されていません")

    state = {"audio_features": describe(f)}
    if hint:
        state["hint"] = hint
    body = json.dumps({"model": MODEL, "state": state, "questions": build_questions()}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/v1/systemone",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Jev API エラー {e.code}: {e.read().decode(errors='replace')}") from e
