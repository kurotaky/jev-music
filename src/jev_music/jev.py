"""抽出した特徴を Jev (ロリポップ！AIゲートウェイ /v1/systemone) に渡してジャンル・ムードを判定する。"""

import json
import os
import urllib.error
import urllib.request

from .features import Features

BASE_URL = os.environ.get("AI_GATEWAY_BASE_URL", "https://ai-gateway.lolipop.jp")
MODEL = os.environ.get("JEV_MODEL", "typesafe/jev-latest")

GENRES = {
    "pop": "ポップ。キャッチーなメロディ、明快な構成",
    "rock": "ロック。バンドサウンド、歪んだギター",
    "hiphop": "ヒップホップ。ビート主体、ラップ、BPM 80-100前後",
    "house_techno": "ハウス/テクノ。4つ打ち、BPM 120-130前後、ビートが非常に一定",
    "edm": "EDM/ダブステップ等。派手な電子音、大きな音圧",
    "jazz": "ジャズ。スウィング、即興、ビートの揺らぎ",
    "classical": "クラシック。オーケストラ・ピアノ、打楽器が少なくダイナミクスが大きい",
    "ambient": "アンビエント。ビートが弱いか無い、静かで持続的",
    "rnb_soul": "R&B/ソウル。グルーヴ、歌もの、中庸なテンポ",
    "metal": "メタル。非常に速く激しい、高音圧",
    "folk_acoustic": "フォーク/アコースティック。生楽器中心、打楽器控えめ",
    "lofi": "Lo-fi/チル。ゆったりしたビート、こもった音色",
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
        "tempo": f"{f.bpm} BPM（{level(f.bpm, 90, 130, ('遅い', '中くらい', '速い'))}）",
        "beat_regularity": f"{f.beat_regularity}（1に近いほど機械的に一定。{level(f.beat_regularity, 0.85, 0.95, ('揺らぎあり', 'やや一定', '非常に一定'))}）",
        "key": f"{f.key}（{'長調' if 'major' in f.key else '短調'}、推定の確からしさ {f.key_confidence}）",
        "loudness": f"平均 {f.loudness_db} dBFS（音圧{level(f.loudness_db, -30, -18)}）",
        "dynamic_range": f"{f.dynamic_range_db} dB（抑揚{level(f.dynamic_range_db, 10, 25, ('小さい', '中くらい', '大きい'))}）",
        "brightness": f"スペクトル重心 {f.brightness_hz:.0f} Hz（音色が{level(f.brightness_hz, 1500, 3000, ('暗い・こもった', '標準的', '明るい・きらびやか'))}）",
        "onset_rate": f"毎秒 {f.onset_rate} 音（音数{level(f.onset_rate, 2, 5, ('少ない', '中くらい', '多い'))}）",
        "percussive_ratio": f"{f.percussive_ratio}（打楽器成分{level(f.percussive_ratio, 0.25, 0.45, ('少ない', '中くらい', '多い'))}）",
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
