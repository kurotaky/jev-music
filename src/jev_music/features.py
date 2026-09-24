"""librosa で音声から測定できる特徴（テンポ・ビート・キー・音色など）を抽出する。"""

from dataclasses import asdict, dataclass

import librosa
import numpy as np

PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler のキープロファイル
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


@dataclass
class Features:
    duration_sec: float
    bpm: float
    beat_count: int
    beat_regularity: float  # 0-1。ビート間隔が一定なほど 1
    key: str
    key_confidence: float
    loudness_db: float
    dynamic_range_db: float
    brightness_hz: float  # スペクトル重心
    onset_rate: float  # 1秒あたりの発音数
    percussive_ratio: float  # 打楽器成分の割合 0-1
    zero_crossing_rate: float

    def to_dict(self) -> dict:
        return asdict(self)


def estimate_key(chroma: np.ndarray) -> tuple[str, float]:
    profile = chroma.mean(axis=1)
    scores = []
    for i in range(12):
        for mode, template in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            r = np.corrcoef(profile, np.roll(template, i))[0, 1]
            scores.append((r, f"{PITCHES[i]} {mode}"))
    scores.sort(reverse=True)
    (best, key), (second, _) = scores[0], scores[1]
    return key, round(float(best - second), 3)


def extract(path: str, max_duration: float | None = 120.0) -> Features:
    y, sr = librosa.load(path, sr=22050, mono=True, duration=max_duration)
    if y.size == 0:
        raise ValueError(f"音声が読み込めませんでした: {path}")

    y_harm, y_perc = librosa.effects.hpss(y)
    onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    intervals = np.diff(beat_times)
    regularity = 1.0 - min(1.0, float(np.std(intervals) / np.mean(intervals))) if intervals.size > 1 else 0.0

    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr)
    key, key_conf = estimate_key(chroma)

    rms_db = librosa.amplitude_to_db(librosa.feature.rms(y=y)[0], ref=1.0)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    duration = librosa.get_duration(y=y, sr=sr)
    harm_e, perc_e = float(np.sum(y_harm**2)), float(np.sum(y_perc**2))

    return Features(
        duration_sec=round(duration, 1),
        bpm=round(float(np.atleast_1d(tempo)[0]), 1),
        beat_count=int(len(beats)),
        beat_regularity=round(regularity, 3),
        key=key,
        key_confidence=key_conf,
        loudness_db=round(float(np.mean(rms_db)), 1),
        dynamic_range_db=round(float(np.percentile(rms_db, 95) - np.percentile(rms_db, 5)), 1),
        brightness_hz=round(float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))), 0),
        onset_rate=round(len(onsets) / duration, 2),
        percussive_ratio=round(perc_e / (harm_e + perc_e), 3),
        zero_crossing_rate=round(float(np.mean(librosa.feature.zero_crossing_rate(y))), 4),
    )
