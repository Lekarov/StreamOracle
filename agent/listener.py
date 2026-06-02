"""Capture micro, VAD, transcription Whisper, wake word — version avec callbacks."""
from __future__ import annotations

import queue
import threading
from collections import deque
from typing import Callable

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

import config


class Listener:
    def __init__(
        self,
        on_level:  Callable[[float], None]  | None = None,
        on_query:  Callable[[str],   None]  | None = None,
        on_status: Callable[[str],   None]  | None = None,
        device: int | None = None,
    ) -> None:
        self.on_level  = on_level
        self.on_query  = on_query
        self.on_status = on_status
        self.device    = device

        self.threshold = config.SILENCE_RMS_THRESHOLD
        self.silence_after_speech = config.SILENCE_AFTER_SPEECH

        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._speaking             = threading.Event()
        self._stop_event           = threading.Event()
        self._transcription_ready  = threading.Event()  # activé après chargement modèle
        self._model: WhisperModel | None = None
        self._thread: threading.Thread | None = None

    # ── Chargement modèle ────────────────────────────────────────────────────

    def load_model(self, on_ready: Callable[[], None] | None = None) -> None:
        def _load() -> None:
            self._emit_status("loading")
            self._model = WhisperModel(
                config.WHISPER_MODEL_SIZE,
                device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE,
            )
            if on_ready:
                on_ready()

        threading.Thread(target=_load, daemon=True).start()

    # ── Contrôle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Démarre la capture audio immédiatement (VU-mètre actif).
        La transcription ne commence qu'après enable_transcription()."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._transcription_ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def enable_transcription(self) -> None:
        """Active la transcription — à appeler une fois le modèle chargé."""
        self._transcription_ready.set()
        self._emit_status("idle")

    def stop(self) -> None:
        self._stop_event.set()
        self._transcription_ready.clear()

    def set_speaking(self, speaking: bool) -> None:
        if speaking:
            self._speaking.set()
            self._emit_status("speaking")
        else:
            self._speaking.clear()
            self._emit_status("idle")
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break

    # ── Boucle interne ───────────────────────────────────────────────────────

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            self._emit_status(f"error:PortAudio : {status}")
        if not self._speaking.is_set():
            self._audio_queue.put(indata.copy())

    def _run(self) -> None:
        CHUNK            = int(config.SAMPLE_RATE * 0.1)
        pre_buf: deque   = deque(maxlen=int(config.PRE_SPEECH_BUFFER / 0.1))
        recording: list  = []
        is_recording     = False
        silence_count    = 0
        speech_count     = 0
        peak_rms         = 0.0

        self._emit_status("loading")

        # Détecter les canaux réels du device
        ch = config.CHANNELS
        dev_name = f"device={self.device}"
        try:
            dev_info = (
                sd.query_devices(self.device, "input")
                if self.device is not None
                else sd.query_devices(kind="input")
            )
            ch = min(config.CHANNELS, int(dev_info["max_input_channels"]))
            dev_name = dev_info["name"]
            if ch == 0:
                self._emit_status("error:Ce périphérique n'a aucune entrée audio — choisis un autre micro")
                return
        except Exception as exc:
            self._emit_status(f"error:query_devices échoué : {exc}")

        self._emit_status(f"error:Micro : {dev_name} | {ch}ch | {config.SAMPLE_RATE}Hz")

        try:
            stream_ctx = sd.InputStream(
                samplerate=config.SAMPLE_RATE,
                channels=ch,
                dtype="float32",
                blocksize=CHUNK,
                callback=self._audio_callback,
                device=self.device,
            )
        except Exception as exc:
            self._emit_status(f"error:Impossible d'ouvrir le stream : {exc}")
            return

        with stream_ctx:
            while not self._stop_event.is_set():
                try:
                    chunk = self._audio_queue.get(timeout=0.3)
                except queue.Empty:
                    continue

                rms       = float(np.sqrt(np.mean(chunk ** 2)))
                is_speech = rms > self.threshold

                if self.on_level:
                    self.on_level(rms)

                # Sans modèle prêt : VU-mètre seulement, pas de transcription
                if not self._transcription_ready.is_set():
                    continue

                SILENCE_NEEDED = int(self.silence_after_speech / 0.1)
                MIN_SPEECH     = int(config.MIN_SPEECH_DURATION / 0.1)
                MAX_SPEECH     = int(config.MAX_SPEECH_DURATION / 0.1)

                if not is_recording:
                    pre_buf.append(chunk)
                    if is_speech:
                        is_recording  = True
                        recording     = list(pre_buf)
                        speech_count  = 1
                        silence_count = 0
                        peak_rms      = rms
                else:
                    recording.append(chunk)
                    if is_speech:
                        speech_count  += 1
                        silence_count  = 0
                        if rms > peak_rms:
                            peak_rms = rms
                    else:
                        silence_count += 1

                    done     = silence_count >= SILENCE_NEEDED and speech_count >= MIN_SPEECH
                    too_long = len(recording) >= MAX_SPEECH

                    if done or too_long:
                        audio = np.concatenate(recording).flatten()
                        self._emit_status(f"segment:{peak_rms:.4f}:{len(recording) * 0.1:.1f}s")
                        self._emit_status("processing")
                        text  = self._transcribe(audio)
                        if text:
                            query = self._extract_query(text)
                            if query is not None and self.on_query:
                                self._emit_status("wake")
                                self.on_query(query)
                            else:
                                self._emit_status("idle")
                        else:
                            self._emit_status("idle")

                        recording     = []
                        is_recording  = False
                        silence_count = 0
                        speech_count  = 0
                        pre_buf.clear()

        self._emit_status("stopped")

    def _transcribe(self, audio: np.ndarray) -> str:
        if self._model is None:
            return ""

        def _run(model: WhisperModel) -> str:
            segments, _ = model.transcribe(
                audio,
                language=config.WHISPER_LANGUAGE,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
            )
            return " ".join(seg.text.strip() for seg in segments).strip()

        try:
            return _run(self._model)
        except RuntimeError as exc:
            msg = str(exc)
            if any(k in msg for k in ("cublas", "cudnn", "CUDA", "cuda")):
                # DLLs CUDA manquantes — fallback CPU automatique
                self._emit_status("error:CUDA manquant — bascule CPU (installe nvidia-cublas-cu12 nvidia-cudnn-cu12 pour le GPU)")
                try:
                    self._model = WhisperModel(
                        config.WHISPER_MODEL_SIZE,
                        device="cpu",
                        compute_type="int8",
                    )
                    return _run(self._model)
                except Exception:
                    return ""
            return ""

    def _extract_query(self, transcript: str) -> str | None:
        lower = transcript.lower().strip()
        for wake in config.WAKE_WORDS:
            idx = lower.find(wake)
            if idx != -1:
                after = transcript[idx + len(wake):].strip().lstrip(",.!?; ")
                return after if after else "(appelé sans question)"
        return None

    def _emit_status(self, status: str) -> None:
        if self.on_status:
            self.on_status(status)
