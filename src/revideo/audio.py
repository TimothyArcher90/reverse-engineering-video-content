"""Sound forensics with numpy only: loudness, onsets, tempo, beats, and cut-to-beat sync."""

from __future__ import annotations

import os
import subprocess

import numpy as np

from .video import find_ffmpeg

SR = 22050


def extract_wav(video: str, out_path: str) -> str | None:
    exe = find_ffmpeg()
    if not exe:
        return None
    r = subprocess.run([exe, "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(SR), out_path],
                       capture_output=True)
    return out_path if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1000 else None


def load_wav(path: str) -> np.ndarray:
    import wave

    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
        width = w.getsampwidth()
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
    x = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    return x / float(np.iinfo(dtype).max)


def _stft_mag(x: np.ndarray, n_fft=2048, hop=512) -> np.ndarray:
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    frames = np.lib.stride_tricks.sliding_window_view(x, n_fft)[::hop]
    return np.abs(np.fft.rfft(frames * np.hanning(n_fft), axis=1))


def analyze(wav_path: str, cut_times: list[float]) -> dict:
    x = load_wav(wav_path)
    hop = 512
    mag = _stft_mag(x, hop=hop)
    fr = SR / hop
    rms = np.sqrt((np.lib.stride_tricks.sliding_window_view(np.pad(x, (0, 2048)), 2048)[::hop] ** 2).mean(axis=1))
    rms_db = 20 * np.log10(rms + 1e-9)

    # onset strength: half-wave rectified spectral flux on log magnitude
    logm = np.log1p(mag * 10)
    flux = np.maximum(0, np.diff(logm, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)

    # tempo via autocorrelation in 60–200 BPM
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    lags = np.arange(len(ac))
    bpm_of = lambda lag: 60 * fr / lag
    valid = (lags > 0) & (bpm_of(np.maximum(lags, 1)) <= 200) & (bpm_of(np.maximum(lags, 1)) >= 60)
    bpm, beats = None, []
    if valid.any() and ac[valid].max() > 0:
        lag = int(lags[valid][np.argmax(ac[valid])])
        bpm = round(float(bpm_of(lag)), 1)
        # phase: offset maximizing summed onset strength on the grid
        phase = int(np.argmax([flux[p::lag].sum() for p in range(lag)]))
        beats = [round(float(i / fr), 3) for i in range(phase, len(flux), lag)]

    thr = np.percentile(flux, 92)
    peaks = [i for i in range(1, len(flux) - 1) if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]]
    onsets = [round(i / fr, 3) for i in peaks]

    def sync_ratio(ref: list[float], tol=0.08) -> float | None:
        if not ref or not cut_times:
            return None
        r = np.array(ref)
        return round(float(np.mean([np.min(np.abs(r - c)) <= tol for c in cut_times])), 3)

    silence = rms_db < (np.percentile(rms_db, 95) - 35)
    return {
        "duration_sec": round(len(x) / SR, 3),
        "loudness_mean_dbfs": round(float(rms_db.mean()), 2),
        "loudness_peak_dbfs": round(float(rms_db.max()), 2),
        "silence_pct": round(float(silence.mean() * 100), 2),
        "tempo_bpm_estimate": bpm,
        "beat_times": beats[:2000],
        "onset_times": onsets[:2000],
        "cuts_on_beat_ratio": sync_ratio(beats),
        "cuts_on_onset_ratio": sync_ratio(onsets),
        "loudness_curve_1s_db": [round(float(v), 1) for v in rms_db[:: int(fr)]],
        "note": "BPM is an autocorrelation estimate; half/double-time errors are possible",
    }
