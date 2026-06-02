"""StreamOracle — Interface graphique."""
from __future__ import annotations

import json
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
import tkinter as tk
import sounddevice as sd

import config
from core.listener import Listener
from core.brain    import Brain
from core.voice    import Voice

# ── Palette ──────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG      = "#050507"
SURF    = "#0d0d12"
SURF2   = "#13131a"
SURF3   = "#1a1a24"
BORDER  = "#1f1f2e"
BORDER2 = "#2d2d42"
ACCENT  = "#6366f1"
ACCHOV  = "#4f52d9"
TEXT    = "#f1f1f3"
TEXT2   = "#a1a1b5"
MUTED   = "#5c5c78"
SUCCESS = "#10b981"
WARN    = "#f59e0b"
DANGER  = "#f43f5e"
INFO    = "#38bdf8"

STATUS_META: dict[str, tuple[str, str]] = {
    "idle":       ("● EN ÉCOUTE",    SUCCESS),
    "wake":       ("● WAKE WORD",    WARN),
    "processing": ("● TRAITEMENT",   ACCENT),
    "speaking":   ("● PAROLE",       DANGER),
    "loading":    ("● CHARGEMENT…",  INFO),
    "stopped":    ("● ARRÊTÉ",       MUTED),
    "error":      ("● ERREUR",       DANGER),
}

SETTINGS_FILE = Path(__file__).parent / "settings.json"

TTS_VOICES = {
    "Henri (homme FR)":   "fr-FR-HenriNeural",
    "Denise (femme FR)":  "fr-FR-DeniseNeural",
    "Antoine (homme FR)": "fr-FR-AntoineNeural",
}
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_settings(data: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── App principale ────────────────────────────────────────────────────────────

class App(ctk.CTk):

    def __init__(self) -> None:
        super().__init__()

        self.title("Jean-Kulki — Pestovich")
        self.geometry("960x680")
        self.minsize(800, 580)
        self.configure(fg_color=BG)

        # État
        self._running      = False
        self._busy_lock    = threading.Lock()
        self._rms_queue: queue.Queue[float] = queue.Queue(maxsize=20)
        self._event_queue: queue.Queue[tuple] = queue.Queue()
        self._current_rms  = 0.0
        self._peak_rms     = 0.0
        self._peak_decay   = 0.0

        # Objets agent
        self._listener: Listener | None = None
        self._brain    = Brain()

        # Paramètres
        s = _load_settings()
        self._threshold     = tk.DoubleVar(value=s.get("threshold",           config.SILENCE_RMS_THRESHOLD))
        self._silence_dur   = tk.DoubleVar(value=s.get("silence_dur",         config.SILENCE_AFTER_SPEECH))
        self._whisper_model = tk.StringVar(value=s.get("whisper_model",       config.WHISPER_MODEL_SIZE))
        self._tts_voice_lbl = tk.StringVar(value=s.get("tts_voice_lbl",       "Henri (homme FR)"))
        self._max_history   = tk.IntVar(   value=s.get("max_history",         config.MAX_HISTORY_TURNS))

        # Périphériques d'entrée audio
        self._mic_devices: dict[str, int | None] = self._list_input_devices()
        saved_mic = s.get("mic_device_label", "Défaut")
        if saved_mic not in self._mic_devices:
            saved_mic = "Défaut"
        self._mic_device_lbl = tk.StringVar(value=saved_mic)

        # Périphériques de sortie audio
        self._out_devices: dict[str, int | None] = self._list_output_devices()
        saved_out = s.get("out_device_label", "Défaut")
        if saved_out not in self._out_devices:
            saved_out = "Défaut"
        self._out_device_lbl = tk.StringVar(value=saved_out)

        # Voix — initialisée après les devices
        self._voice = self._make_voice()

        self._build_ui()
        self._poll_queues()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _make_voice(self) -> "Voice":
        out_device = self._out_devices.get(self._out_device_lbl.get())
        return Voice(
            output_device=out_device,
            on_error=lambda e: self._emit_log(f"Voix erreur : {e}", "err"),
            on_info =lambda i: self._emit_log(f"Voix : {i}", "sys"),
        )

    # ── Helpers audio ─────────────────────────────────────────────────────────

    @staticmethod
    def _list_input_devices() -> dict[str, int | None]:
        devices: dict[str, int | None] = {"Défaut": None}
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0:
                    name = dev["name"][:40].strip()
                    devices[f"{name} [{i}]"] = i
        except Exception:
            pass
        return devices

    @staticmethod
    def _list_output_devices() -> dict[str, int | None]:
        devices: dict[str, int | None] = {"Défaut": None}
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_output_channels"] > 0:
                    name = dev["name"][:40].strip()
                    devices[f"{name} [{i}]"] = i
        except Exception:
            pass
        return devices

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # --- Header ---
        hdr = ctk.CTkFrame(self, fg_color=SURF, corner_radius=0, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr, text="JEAN-KULKI", font=ctk.CTkFont("Segoe UI", 18, "bold"),
            text_color=TEXT,
        ).pack(side="left", padx=20)
        ctk.CTkLabel(
            hdr, text="Assistant vocal · Pestovich",
            font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT2,
        ).pack(side="left", padx=(0, 20))

        self._status_lbl = ctk.CTkLabel(
            hdr, text="● ARRÊTÉ",
            font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=MUTED,
        )
        self._status_lbl.pack(side="right", padx=20)

        # Séparateur
        ctk.CTkFrame(self, height=1, fg_color=BORDER, corner_radius=0).pack(fill="x")

        # --- Corps ---
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=12)
        body.columnconfigure(0, weight=0)   # panel gauche fixe
        body.columnconfigure(1, weight=1)   # panel droite flex
        body.rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_right(body)

        # --- Journal ---
        log_frame = ctk.CTkFrame(self, fg_color=SURF, corner_radius=10,
                                  border_color=BORDER, border_width=1)
        log_frame.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            log_frame, text="JOURNAL", font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color=MUTED,
        ).pack(anchor="w", padx=12, pady=(8, 2))

        self._log = ctk.CTkTextbox(
            log_frame, height=150, fg_color=SURF2, text_color=TEXT2,
            font=ctk.CTkFont("Consolas", 10), wrap="word",
            border_width=0, corner_radius=8,
        )
        self._log.pack(fill="x", padx=8, pady=(0, 8))
        self._log.configure(state="disabled")

        # Tags couleur
        self._log._textbox.tag_configure("mic",   foreground=INFO)
        self._log._textbox.tag_configure("bot",   foreground=SUCCESS)
        self._log._textbox.tag_configure("sys",   foreground=MUTED)
        self._log._textbox.tag_configure("err",   foreground=DANGER)
        self._log._textbox.tag_configure("ts",    foreground=MUTED)

    def _build_left(self, parent: ctk.CTkFrame) -> None:
        left = ctk.CTkFrame(parent, fg_color=SURF, corner_radius=12,
                             border_color=BORDER, border_width=1, width=280)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left.pack_propagate(False)
        left.grid_propagate(False)

        # Titre section
        ctk.CTkLabel(
            left, text="MICROPHONE",
            font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color=MUTED,
        ).pack(anchor="w", padx=16, pady=(14, 4))

        # Entrée micro
        ctk.CTkLabel(
            left, text="Entrée", font=ctk.CTkFont("Segoe UI", 8), text_color=MUTED,
        ).pack(anchor="w", padx=16, pady=(2, 0))
        ctk.CTkOptionMenu(
            left,
            values=list(self._mic_devices.keys()),
            variable=self._mic_device_lbl,
            fg_color=SURF3, button_color=SURF3, button_hover_color=BORDER2,
            dropdown_fg_color=SURF2, text_color=TEXT2,
            font=ctk.CTkFont("Segoe UI", 9),
            width=256,
        ).pack(padx=12, pady=(0, 4))

        # Sortie voix
        ctk.CTkLabel(
            left, text="Sortie voix", font=ctk.CTkFont("Segoe UI", 8), text_color=MUTED,
        ).pack(anchor="w", padx=16, pady=(2, 0))
        ctk.CTkOptionMenu(
            left,
            values=list(self._out_devices.keys()),
            variable=self._out_device_lbl,
            fg_color=SURF3, button_color=SURF3, button_hover_color=BORDER2,
            dropdown_fg_color=SURF2, text_color=TEXT2,
            font=ctk.CTkFont("Segoe UI", 9),
            width=256,
        ).pack(padx=12, pady=(0, 6))

        # VU-mètre
        vu_frame = ctk.CTkFrame(left, fg_color=SURF2, corner_radius=8, height=36)
        vu_frame.pack(fill="x", padx=12, pady=(0, 4))
        vu_frame.pack_propagate(False)

        self._vu_canvas = tk.Canvas(
            vu_frame, bg=SURF2, highlightthickness=0, height=36,
        )
        self._vu_canvas.pack(fill="both", expand=True, padx=4, pady=4)

        # Infos niveau
        info_row = ctk.CTkFrame(left, fg_color="transparent")
        info_row.pack(fill="x", padx=12, pady=(0, 10))

        self._rms_lbl = ctk.CTkLabel(
            info_row, text="Niveau : 0.000",
            font=ctk.CTkFont("Consolas", 9), text_color=TEXT2,
        )
        self._rms_lbl.pack(side="left")

        self._thr_lbl = ctk.CTkLabel(
            info_row, text=f"Seuil : {self._threshold.get():.3f}",
            font=ctk.CTkFont("Consolas", 9), text_color=MUTED,
        )
        self._thr_lbl.pack(side="right")

        # Séparateur
        ctk.CTkFrame(left, height=1, fg_color=BORDER, corner_radius=0).pack(
            fill="x", padx=8, pady=6)

        # Bouton Démarrer / Arrêter
        self._start_btn = ctk.CTkButton(
            left, text="▶  DÉMARRER",
            fg_color=ACCENT, hover_color=ACCHOV, text_color=TEXT,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            corner_radius=10, height=42,
            command=self._toggle,
        )
        self._start_btn.pack(fill="x", padx=12, pady=(6, 4))

        # Bouton test voix
        ctk.CTkButton(
            left, text="🔊  Test voix",
            fg_color=SURF3, hover_color="#20202e", text_color=TEXT2,
            font=ctk.CTkFont("Segoe UI", 10), corner_radius=8, height=32,
            border_color=BORDER, border_width=1,
            command=self._test_voice,
        ).pack(fill="x", padx=12, pady=2)

        # Bouton vider historique
        ctk.CTkButton(
            left, text="🗑  Vider l'historique",
            fg_color=SURF3, hover_color="#20202e", text_color=TEXT2,
            font=ctk.CTkFont("Segoe UI", 10), corner_radius=8, height=32,
            border_color=BORDER, border_width=1,
            command=self._clear_history,
        ).pack(fill="x", padx=12, pady=(2, 4))

        # Bouton diagnostic micros
        ctk.CTkButton(
            left, text="🔍  Lister les micros",
            fg_color=SURF3, hover_color="#20202e", text_color=TEXT2,
            font=ctk.CTkFont("Segoe UI", 10), corner_radius=8, height=32,
            border_color=BORDER, border_width=1,
            command=self._list_mics_to_log,
        ).pack(fill="x", padx=12, pady=(0, 12))

    def _build_right(self, parent: ctk.CTkFrame) -> None:
        right = ctk.CTkScrollableFrame(
            parent, fg_color=SURF, corner_radius=12,
            border_color=BORDER, border_width=1,
            scrollbar_button_color=SURF3,
        )
        right.grid(row=0, column=1, sticky="nsew")

        def section(label: str) -> None:
            ctk.CTkLabel(
                right, text=label,
                font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color=MUTED,
            ).pack(anchor="w", padx=16, pady=(16, 6))
            ctk.CTkFrame(right, height=1, fg_color=BORDER, corner_radius=0).pack(
                fill="x", padx=12, pady=(0, 10))

        def slider_row(parent_frame, label: str, var: tk.Variable,
                       from_: float, to: float, fmt: str = "{:.3f}",
                       steps: int = 100) -> None:
            row = ctk.CTkFrame(parent_frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(0, 10))

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(top, text=label,
                         font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT,
                         ).pack(side="left")
            val_lbl = ctk.CTkLabel(top, text=fmt.format(var.get()),
                                   font=ctk.CTkFont("Consolas", 10), text_color=ACCENT)
            val_lbl.pack(side="right")

            def on_change(v, lbl=val_lbl, f=fmt):
                lbl.configure(text=f.format(float(v)))

            ctk.CTkSlider(
                row, from_=from_, to=to, number_of_steps=steps,
                variable=var, command=on_change,
                button_color=ACCENT, button_hover_color=ACCHOV,
                progress_color=ACCENT, fg_color=SURF3,
            ).pack(fill="x", pady=(4, 0))

        # ── Section Détection ─────────────────────────────────────────────
        section("DÉTECTION")

        slider_row(right, "Sensibilité micro (seuil RMS)",
                   self._threshold, 0.002, 0.08, "{:.3f}", 78)
        ctk.CTkLabel(right, text="↑ Augmente si trop de faux déclenchements",
                     font=ctk.CTkFont("Segoe UI", 9), text_color=MUTED,
                     ).pack(anchor="w", padx=16, pady=(0, 8))

        slider_row(right, "Durée silence pour couper (s)",
                   self._silence_dur, 0.5, 3.0, "{:.1f}s", 25)

        # ── Section Modèle ────────────────────────────────────────────────
        section("MODÈLE WHISPER")

        model_row = ctk.CTkFrame(right, fg_color="transparent")
        model_row.pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(model_row, text="Modèle",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT,
                     ).pack(side="left")
        ctk.CTkOptionMenu(
            model_row, values=WHISPER_MODELS, variable=self._whisper_model,
            fg_color=SURF3, button_color=SURF3, button_hover_color=BORDER2,
            dropdown_fg_color=SURF2, text_color=TEXT,
            font=ctk.CTkFont("Segoe UI", 10),
            width=140,
        ).pack(side="right")

        ctk.CTkLabel(right,
                     text="tiny=rapide/imprécis  ·  medium=bon équilibre  ·  large-v3=meilleur",
                     font=ctk.CTkFont("Segoe UI", 9), text_color=MUTED,
                     ).pack(anchor="w", padx=16, pady=(0, 8))

        # ── Section Voix ──────────────────────────────────────────────────
        section("VOIX TTS")

        voice_row = ctk.CTkFrame(right, fg_color="transparent")
        voice_row.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(voice_row, text="Voix",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT,
                     ).pack(side="left")
        ctk.CTkOptionMenu(
            voice_row, values=list(TTS_VOICES.keys()),
            variable=self._tts_voice_lbl,
            fg_color=SURF3, button_color=SURF3, button_hover_color=BORDER2,
            dropdown_fg_color=SURF2, text_color=TEXT,
            font=ctk.CTkFont("Segoe UI", 10),
            width=200,
        ).pack(side="right")

        # ── Section Historique ────────────────────────────────────────────
        section("HISTORIQUE")

        slider_row(right, "Tours conservés en mémoire",
                   self._max_history, 1, 20, "{:.0f}", 19)

        # ── Bouton Sauvegarder ────────────────────────────────────────────
        ctk.CTkFrame(right, height=1, fg_color=BORDER, corner_radius=0).pack(
            fill="x", padx=12, pady=(6, 12))

        ctk.CTkButton(
            right, text="💾  Sauvegarder les réglages",
            fg_color=ACCENT, hover_color=ACCHOV, text_color=TEXT,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            corner_radius=10, height=38,
            command=self._save_settings,
        ).pack(fill="x", padx=16, pady=(0, 16))

    # ── VU-mètre ──────────────────────────────────────────────────────────────

    def _update_vu(self) -> None:
        c = self._vu_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2 or h < 2:
            return

        c.delete("all")

        # Fond
        c.create_rectangle(0, 0, w, h, fill=SURF3, outline="")

        # Barre niveau
        rms       = self._current_rms
        thr       = self._threshold.get()
        max_level = max(thr * 4, 0.08)
        ratio     = min(rms / max_level, 1.0)
        bar_w     = int(ratio * w)

        if rms < thr * 0.6:
            color = "#10b981"
        elif rms < thr:
            color = "#84cc16"
        elif rms < thr * 1.4:
            color = "#f59e0b"
        else:
            color = "#f43f5e"

        if bar_w > 0:
            c.create_rectangle(0, 2, bar_w, h - 2, fill=color, outline="")

        # Peak hold
        if rms > self._peak_rms:
            self._peak_rms   = rms
            self._peak_decay = 60
        elif self._peak_decay > 0:
            self._peak_decay -= 1
        else:
            self._peak_rms = max(self._peak_rms - 0.001, 0)

        pk_x = int(min(self._peak_rms / max_level, 1.0) * w)
        if pk_x > 0:
            c.create_line(pk_x, 2, pk_x, h - 2, fill=TEXT, width=2)

        # Ligne seuil
        thr_x = int(min(thr / max_level, 1.0) * w)
        c.create_line(thr_x, 0, thr_x, h, fill=WARN, width=1, dash=(4, 3))

    # ── Polling / Events ──────────────────────────────────────────────────────

    def _poll_queues(self) -> None:
        # Niveau micro
        try:
            while True:
                rms = self._rms_queue.get_nowait()
                self._current_rms = rms
        except queue.Empty:
            pass

        # Mise à jour VU + labels
        self._update_vu()
        self._rms_lbl.configure(text=f"Niveau : {self._current_rms:.4f}")
        self._thr_lbl.configure(text=f"Seuil : {self._threshold.get():.3f}")

        # Log périodique du niveau (toutes les ~5s)
        self._poll_tick = getattr(self, "_poll_tick", 0) + 1
        self._zero_ticks = getattr(self, "_zero_ticks", 0)
        if self._running and self._poll_tick % 125 == 0:
            thr = self._threshold.get()
            rms = self._current_rms
            if rms < 0.001:
                self._zero_ticks += 1
                if self._zero_ticks == 1:
                    self._emit_log("Niveau micro : 0 — aucun signal détecté", "err")
                elif self._zero_ticks == 3:
                    self._emit_log("Toujours 0 — vérifie : Paramètres Windows > Confidentialité > Microphone > autoriser les applis bureau", "err")
                elif self._zero_ticks == 6:
                    self._emit_log("Toujours 0 — clique '🔍 Lister les micros' et sélectionne le bon index dans le dropdown", "err")
            else:
                self._zero_ticks = 0
                if rms < thr * 0.3:
                    self._emit_log(f"Niveau micro : {rms:.4f} (seuil : {thr:.3f}) — signal faible", "sys")
                else:
                    self._emit_log(f"Niveau micro : {rms:.4f} (seuil : {thr:.3f})", "sys")

        # Events status/log
        try:
            while True:
                kind, data = self._event_queue.get_nowait()
                if kind == "status":
                    lbl, color = STATUS_META.get(data, ("●", MUTED))
                    self._status_lbl.configure(text=lbl, text_color=color)
                elif kind == "log":
                    self._append_log(*data)
        except queue.Empty:
            pass

        self.after(40, self._poll_queues)

    def _emit_status(self, status: str) -> None:
        self._event_queue.put(("status", status))

    def _emit_log(self, text: str, tag: str = "sys") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._event_queue.put(("log", (ts, text, tag)))

    def _append_log(self, ts: str, text: str, tag: str) -> None:
        self._log.configure(state="normal")
        self._log._textbox.insert("end", f"[{ts}] ", ("ts",))
        self._log._textbox.insert("end", text + "\n", (tag,))
        self._log._textbox.see("end")
        self._log.configure(state="disabled")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _toggle(self) -> None:
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        if not config.ANTHROPIC_API_KEY:
            self._emit_log("ANTHROPIC_API_KEY manquant dans .env", "err")
            return

        self._running = True
        self._start_btn.configure(text="⏹  ARRÊTER", fg_color="#3d1520",
                                   hover_color="#4d1f2a", text_color=DANGER,
                                   border_color="#5c2535", border_width=1)

        # Mettre à jour config depuis les sliders
        config.SILENCE_RMS_THRESHOLD = self._threshold.get()
        config.SILENCE_AFTER_SPEECH  = self._silence_dur.get()
        config.WHISPER_MODEL_SIZE    = self._whisper_model.get()
        config.MAX_HISTORY_TURNS     = self._max_history.get()
        config.TTS_VOICE = TTS_VOICES.get(self._tts_voice_lbl.get(), config.TTS_VOICE)

        selected_device = self._mic_devices.get(self._mic_device_lbl.get())
        dev_label = self._mic_device_lbl.get()
        self._emit_log(f"Micro : {dev_label}", "sys")
        # Sauvegarde automatique du choix de micro
        self._save_settings(silent=True)

        self._listener = Listener(
            on_level  = lambda rms: self._rms_queue.put(rms) if not self._rms_queue.full() else None,
            on_query  = self._on_query,
            on_status = self._on_listener_status,
            device    = selected_device,
        )
        self._listener.threshold           = self._threshold.get()
        self._listener.silence_after_speech = self._silence_dur.get()

        # Démarre le stream audio immédiatement (VU-mètre actif pendant chargement)
        self._listener.start()

        self._emit_log("Chargement du modèle Whisper… (VU-mètre actif)", "sys")
        self._listener.load_model(on_ready=self._on_model_ready)

    def _on_model_ready(self) -> None:
        self._emit_log(f"Modèle '{config.WHISPER_MODEL_SIZE}' prêt — transcription activée !", "sys")
        if self._listener is not None:
            self._listener.enable_transcription()

    def _on_listener_status(self, status: str) -> None:
        if status.startswith("segment:"):
            # segment:peak_rms:durée
            parts = status.split(":")
            peak  = float(parts[1]) if len(parts) > 1 else 0.0
            dur   = parts[2] if len(parts) > 2 else "?"
            thr   = self._threshold.get()
            ratio = int(min(peak / max(thr, 0.001) * 10, 10))
            bar   = "█" * ratio + "░" * (10 - ratio)
            self._emit_log(f"Segment {dur} | niveau max {peak:.4f} [{bar}]", "sys")
        elif status.startswith("error:"):
            msg = status[6:]
            if msg.startswith("Micro"):
                self._emit_log(msg, "sys")
            elif "bascule CPU" in msg:
                self._emit_log(msg, "err")
                self._emit_status("idle")
            else:
                self._emit_log(msg, "err")
                self._emit_status("error")
        else:
            self._emit_status(status)

    def _stop(self) -> None:
        self._running = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._start_btn.configure(text="▶  DÉMARRER", fg_color=ACCENT,
                                   hover_color=ACCHOV, text_color=TEXT, border_width=0)
        self._emit_status("stopped")
        self._emit_log("Jean-Kulki arrêté.", "sys")

    def _on_query(self, query: str) -> None:
        self._emit_log(f"🎤 {query}", "mic")
        threading.Thread(target=self._handle_query, args=(query,), daemon=True).start()

    def _handle_query(self, query: str) -> None:
        if not self._busy_lock.acquire(blocking=False):
            self._emit_log("(ignoré — déjà en train de répondre)", "sys")
            return
        try:
            if self._listener:
                self._listener.set_speaking(True)

            reply = self._brain.respond(query)
            self._emit_log(f"🤖 {reply}", "bot")
            self._make_voice().speak(reply)

        except Exception as exc:
            self._emit_log(f"Erreur : {exc}", "err")
        finally:
            if self._listener:
                self._listener.set_speaking(False)
            self._busy_lock.release()

    def _test_voice(self) -> None:
        config.TTS_VOICE = TTS_VOICES.get(self._tts_voice_lbl.get(), config.TTS_VOICE)
        self._voice = self._make_voice()
        self._emit_log(f"Test voix → sortie : {self._out_device_lbl.get()}", "sys")
        threading.Thread(
            target=lambda: self._voice.speak("Bonjour, je suis Jean-Kulki. Prêt pour le stream."),
            daemon=True,
        ).start()

    def _clear_history(self) -> None:
        self._brain.clear_history()
        self._emit_log("Historique effacé.", "sys")

    def _list_mics_to_log(self) -> None:
        self._emit_log("── Périphériques d'entrée détectés ──", "sys")
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0:
                    marker = " ◄ SÉLECTIONNÉ" if self._mic_devices.get(self._mic_device_lbl.get()) == i else ""
                    self._emit_log(f"[{i}] {dev['name']} ({int(dev['max_input_channels'])}ch){marker}", "sys")
            defaut_idx = sd.default.device[0]
            self._emit_log(f"Défaut système : [{defaut_idx}] {sd.query_devices(defaut_idx)['name']}", "sys")
        except Exception as exc:
            self._emit_log(f"Erreur listing : {exc}", "err")
        self._emit_log("────────────────────────────────────", "sys")

    def _save_settings(self, silent: bool = False) -> None:
        data = {
            "threshold":        self._threshold.get(),
            "silence_dur":      self._silence_dur.get(),
            "whisper_model":    self._whisper_model.get(),
            "tts_voice_lbl":    self._tts_voice_lbl.get(),
            "max_history":      self._max_history.get(),
            "mic_device_label": self._mic_device_lbl.get(),
            "out_device_label": self._out_device_lbl.get(),
        }
        _save_settings(data)
        if self._listener:
            self._listener.threshold            = self._threshold.get()
            self._listener.silence_after_speech = self._silence_dur.get()
        if not silent:
            self._emit_log("Réglages sauvegardés.", "sys")

    def _on_close(self) -> None:
        if self._listener:
            self._listener.stop()
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not config.ANTHROPIC_API_KEY:
        print("ERREUR : ANTHROPIC_API_KEY manquant dans .env")

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
