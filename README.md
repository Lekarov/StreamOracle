# StreamOracle

**StreamOracle** est un assistant IA vocal local pour streamers Twitch. Il écoute le micro en continu, se déclenche sur un mot-clé (*wake word*), transcrit via Whisper, génère une réponse en personnage via Claude, et répond à voix haute avec une voix TTS Microsoft Neural.

Entièrement personnalisable : personnalité, wake words, voix, seuils de détection.

---

## Aperçu

```
[Micro] → VAD RMS → Whisper (STT local) → Wake word détecté
       → Claude Haiku (réponse en personnage)
       → edge-tts (Microsoft Neural TTS) → Lecture audio
```

---

## Stack technique

| Composant | Outil |
|---|---|
| Capture audio | `sounddevice` |
| Speech-to-Text | `faster-whisper` (CUDA ou CPU) |
| Wake word | Détection textuelle post-transcription |
| LLM | Claude Haiku (`claude-haiku-4-5-20251001`) |
| TTS | `edge-tts` — voix Microsoft Neural gratuites |
| Lecture audio | `sounddevice` + `miniaudio` |
| Interface | `customtkinter` — dark mode natif |

---

## Fonctionnalités

- **VU-mètre temps réel** avec peak hold et ligne de seuil visuelle
- **Sélection du micro d'entrée** et du **périphérique de sortie**
- **VAD énergie RMS** — seuil réglable en live via slider
- **Transcription locale** — Faster-Whisper, GPU ou CPU avec fallback automatique
- **Personnalité Claude** — system prompt entièrement personnalisable dans `core/brain.py`
- **TTS multi-voix** — Henri, Denise (FR) — extensible
- **Historique multi-tours** — mémorise les N derniers échanges
- **Journal coloré** — log temps réel des segments, niveaux, réponses
- **Réglages persistants** — sauvegardés automatiquement dans `settings.json`

---

## Structure du projet

```
StreamOracle/
├── core/
│   ├── listener.py     # Capture micro, VAD, Whisper, wake word
│   ├── brain.py        # Claude + system prompt + historique
│   └── voice.py        # edge-tts + lecture sounddevice
├── app.py              # Interface graphique (customtkinter)
├── config.py           # Tous les paramètres centralisés
├── start.bat           # Lancement Windows (double-clic)
├── requirements.txt
└── .gitignore
```

---

## Installation

### Prérequis

- Python 3.10+
- Connexion internet (edge-tts + API Anthropic)
- GPU NVIDIA avec CUDA recommandé (fonctionne aussi en CPU)

### 1. Cloner le dépôt

```bash
git clone https://github.com/Lekarov/StreamOracle.git
cd StreamOracle
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

Pour l'accélération GPU (optionnel, 5× plus rapide) :

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

### 3. Configurer la clé API

Crée un fichier `.env` à la racine du projet :

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

Obtenir une clé : [console.anthropic.com](https://console.anthropic.com)

### 4. Lancer

```bash
python app.py
```

Ou double-cliquer sur `start.bat` sous Windows.

### Dépannage Windows — accès micro refusé

Si le VU-mètre reste à 0 malgré un micro fonctionnel, Windows bloque l'accès au micro pour les applications bureau. Exécute ces deux commandes dans un terminal :

```
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone" /v "Value" /t REG_SZ /d "Allow" /f
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged" /v "Value" /t REG_SZ /d "Allow" /f
```

Ou passe par : **Paramètres → Confidentialité → Microphone → Autoriser les applications bureau**.

---

## Configuration

Tous les paramètres sont dans `config.py` :

| Paramètre | Défaut | Description |
|---|---|---|
| `WAKE_WORDS` | `["jean-kulki", "kulki", ...]` | Mots qui déclenchent l'assistant |
| `SILENCE_RMS_THRESHOLD` | `0.012` | Seuil de détection vocale (réglable dans la GUI) |
| `SILENCE_AFTER_SPEECH` | `1.3s` | Silence nécessaire pour couper l'enregistrement |
| `WHISPER_MODEL_SIZE` | `medium` | `tiny` → `large-v3` selon vitesse/précision |
| `WHISPER_DEVICE` | `cuda` | `cuda` ou `cpu` |
| `TTS_VOICE` | `fr-FR-HenriNeural` | Voix Microsoft Neural |
| `MAX_HISTORY_TURNS` | `8` | Échanges mémorisés par session |
| `CLAUDE_MODEL` | `claude-haiku-4-5-20251001` | Modèle Claude utilisé |

---

## Personnalité

La personnalité est définie dans `core/brain.py` via `SYSTEM_PROMPT`.

Règles efficaces :
- Donner un nom, un ton, une origine fictive à l'assistant
- Ajouter des tics verbaux signature
- Lister des sujets de passion et d'aversion
- Imposer une limite de longueur (`maximum 2 phrases`)
- Interdire le markdown (`zéro astérisque, texte oral uniquement`)
- Ajouter des exemples de bonnes et mauvaises répliques directement dans le prompt

---

## Dépannage

**VU-mètre à 0**
- Vérifie l'accès micro Windows (voir section ci-dessus)
- Vérifie le bon périphérique dans le dropdown "Entrée"

**Erreur CUDA / cublas**
- Installe : `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`
- Ou passe `WHISPER_DEVICE = "cpu"` dans `config.py`

**Pas de son en sortie**
- Sélectionne le bon périphérique dans le dropdown "Sortie voix"
- Teste avec le bouton "🔊 Test voix"

**Trop de faux déclenchements**
- Augmente le slider "Sensibilité micro" dans les réglages

---

## Coût estimé

Claude Haiku est le modèle le moins cher d'Anthropic.

| Usage | Coût estimé |
|---|---|
| 100 interactions / session 3h | ~$0.05 |
| **edge-tts (TTS)** | **Gratuit** |

---

## Licence

MIT — libre d'utilisation, modification et redistribution.
