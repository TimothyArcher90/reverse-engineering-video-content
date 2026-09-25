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
    r = subprocess.run([exe, "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(SR), out_path], capture_output=True)
    return out_path if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1000 else None


def load_wav(path: str) -> np.ndarray:
    import wave

    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
        width = w.getsampwidth()
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
    x = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    return x / float(np.iinfo(dtype).max)


def _onset_strength(x: np.ndarray, n_fft=2048, hop=512, chunk=2048) -> np.ndarray:
    """Half-wave-rectified spectral flux on log magnitude, computed in chunks to bound memory."""
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    frames = np.lib.stride_tricks.sliding_window_view(x, n_fft)[::hop]
    win = np.hanning(n_fft).astype(np.float32)
    flux, prev = [], None
    for i in range(0, len(frames), chunk):
        logm = np.log1p(np.abs(np.fft.rfft(frames[i : i + chunk] * win, axis=1)) * 10).astype(np.float32)
        if prev is not None:
            logm = np.vstack([prev, logm])
        flux.append(np.maximum(0, np.diff(logm, axis=0)).sum(axis=1))
        prev = logm[-1:]
    return np.concatenate([[0.0], *flux])


def _rms(x: np.ndarray, win=2048, hop=512) -> np.ndarray:
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    starts = np.arange(0, max(1, len(x) - win + 1), hop)
    ends = np.minimum(starts + win, len(x))
    return np.sqrt((c[ends] - c[starts]) / np.maximum(1, ends - starts))


# Krumhansl–Kessler key profiles (C major / C minor), rotated for the other 11 tonics
_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _spectrum_frames(x: np.ndarray, n_fft: int = 4096, hop: int = 2048, max_frames: int = 4000) -> np.ndarray:
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    frames = np.lib.stride_tricks.sliding_window_view(x, n_fft)[::hop]
    if len(frames) > max_frames:  # evenly subsample long files: bounded time and memory
        frames = frames[np.linspace(0, len(frames) - 1, max_frames).astype(int)]
    return np.abs(np.fft.rfft(frames * np.hanning(n_fft), axis=1)).astype(np.float32)


def key_estimate(x: np.ndarray, sr: int = SR) -> dict | None:
    """Chroma from the magnitude spectrum, correlated with the 24 major/minor key profiles."""
    mag = _spectrum_frames(x)
    freqs = np.fft.rfftfreq(4096, 1 / sr)
    band = (freqs >= 55) & (freqs <= 2000)
    if not band.any() or mag[:, band].sum() == 0:
        return None
    pcs = np.round(12 * np.log2(freqs[band] / 440.0)).astype(int) % 12  # 0 = A
    energy = mag[:, band].mean(axis=0)
    chroma = np.bincount(pcs, weights=energy, minlength=12)
    chroma = np.roll(chroma, -3)  # re-index so 0 = C
    scores = []
    for tonic in range(12):
        for mode, prof in (("major", _MAJOR), ("minor", _MINOR)):
            scores.append((float(np.corrcoef(chroma, np.roll(prof, tonic))[0, 1]), f"{_NOTES[tonic]} {mode}"))
    scores.sort(reverse=True)
    return {
        "key": scores[0][1],
        "confidence_r": round(scores[0][0], 3),
        "runner_up": scores[1][1],
        "note": "Krumhansl-Kessler estimate; relative major/minor and percussion-heavy tracks are often confused",
    }


def spectral_profile(x: np.ndarray, sr: int = SR) -> dict:
    mag = _spectrum_frames(x)
    freqs = np.fft.rfftfreq(4096, 1 / sr)
    p = mag.mean(axis=0) ** 2
    tot = p.sum() + 1e-12
    bands = {"sub_bass_<60Hz": (0, 60), "bass_60-250Hz": (60, 250), "mids_250-4kHz": (250, 4000), "highs_>4kHz": (4000, sr / 2)}
    share = {k: round(float(p[(freqs >= lo) & (freqs < hi)].sum() / tot * 100), 1) for k, (lo, hi) in bands.items()}
    centroid = float((freqs * p).sum() / tot)
    return {
        "energy_share_pct": share,
        "spectral_centroid_hz": round(centroid, 0),
        "brightness_guess": "dark/bass-heavy" if centroid < 1200 else "bright/airy" if centroid > 3000 else "balanced",
        "crest_factor_db": round(float(20 * np.log10((np.abs(x).max() + 1e-9) / (np.sqrt((x**2).mean()) + 1e-9))), 1),
    }


def analyze(wav_path: str, cut_times: list[float]) -> dict:
    x = load_wav(wav_path)
    hop = 512
    fr = SR / hop
    rms_db = 20 * np.log10(_rms(x, hop=hop) + 1e-9)
    flux = _onset_strength(x, hop=hop)
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)

    # tempo via autocorrelation (FFT, O(n log n)) in 60–200 BPM
    n = len(flux)
    spec = np.fft.rfft(flux, 2 * n)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]
    lags = np.arange(len(ac))
    bpm_of = lambda lag: 60 * fr / lag
    valid = (lags > 0) & (bpm_of(np.maximum(lags, 1)) <= 200) & (bpm_of(np.maximum(lags, 1)) >= 60)
    bpm, beats = None, []
    if valid.any() and ac[valid].max() > 0:
        lag = int(lags[valid][np.argmax(ac[valid])])
        # parabolic interpolation around the peak: sub-frame lag, so BPM is not quantized to the hop size
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[min(lag + 1, len(ac) - 1)]
        den = y0 - 2 * y1 + y2
        bpm = round(float(bpm_of(lag + (0.5 * (y0 - y2) / den if den != 0 else 0.0))), 1)
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
        "key_estimate": key_estimate(x),
        "spectral": spectral_profile(x),
        "note": "BPM is an autocorrelation estimate; half/double-time errors are possible",
    }
