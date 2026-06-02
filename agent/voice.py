"""Synthèse vocale via edge-tts + lecture sounddevice (sélection device)."""
from __future__ import annotations

import asyncio
from typing import Callable

import edge_tts
import miniaudio
import numpy as np
import sounddevice as sd

import config


def _device_samplerate(device: int | None) -> int:
    """Retourne le sample rate natif du device de sortie."""
    try:
        info = (
            sd.query_devices(device, "output")
            if device is not None
            else sd.query_devices(kind="output")
        )
        return int(info["default_samplerate"])
    except Exception:
        return 48000


def _decode(audio_bytes: bytes, sr: int) -> np.ndarray:
    """Décode MP3 → float32 mono au sample rate demandé."""
    decoded = miniaudio.decode(
        audio_bytes,
        output_format=miniaudio.SampleFormat.SIGNED16,
        nchannels=1,
        sample_rate=sr,
    )
    return np.frombuffer(bytes(decoded.samples), dtype=np.int16).astype(np.float32) / 32768.0


class Voice:
    def __init__(
        self,
        output_device: int | None = None,
        on_error: Callable[[str], None] | None = None,
        on_info:  Callable[[str], None] | None = None,
    ) -> None:
        self.output_device = output_device
        self.on_error = on_error
        self.on_info  = on_info

    async def _generate_audio(self, text: str) -> bytes:
        communicate = edge_tts.Communicate(text, voice=config.TTS_VOICE)
        audio = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        return audio

    def speak(self, text: str) -> None:
        # 1. Génération TTS
        try:
            audio_bytes = asyncio.run(self._generate_audio(text))
        except Exception as exc:
            if self.on_error:
                self.on_error(f"edge-tts : {exc}")
            return

        if not audio_bytes:
            if self.on_error:
                self.on_error("edge-tts : 0 octets — vérifie ta connexion internet")
            return

        if self.on_info:
            self.on_info(f"TTS prêt ({len(audio_bytes) // 1024} ko) — lecture…")

        # 2. Essaie le device choisi, puis fallback défaut
        for device in ([self.output_device, None] if self.output_device is not None else [None]):
            sr = _device_samplerate(device)
            try:
                samples = _decode(audio_bytes, sr)
            except Exception as exc:
                if self.on_error:
                    self.on_error(f"décodage MP3 : {exc}")
                return

            try:
                sd.play(samples, samplerate=sr, device=device, blocksize=2048)
                sd.wait()
                if self.on_info:
                    self.on_info("Lecture terminée")
                return
            except Exception as exc:
                if device is not None:
                    if self.on_error:
                        self.on_error(f"Device [{device}] ({sr}Hz) échoué — fallback défaut…")
                else:
                    if self.on_error:
                        self.on_error(f"Lecture impossible : {exc}")

    def stop(self) -> None:
        try:
            sd.stop()
        except Exception:
            pass
