# StreamOracle

**StreamOracle** est un assistant IA vocal local conçu pour les streamers Twitch. Il écoute le micro en continu, se déclenche sur un mot-clé (*wake word*), transcrit la question via Whisper, génère une réponse en personnage via Claude, et répond à voix haute avec une voix TTS Microsoft Neural.

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
| Lecture audio | `sounddevice` + `miniaudio` (décodage MP3) |
| Interface | `customtkinter` — dark mode natif |

---

## Fonctionnalités

- **VU-mètre temps réel** avec peak hold et ligne de seuil visuelle
- **Sélection du micro d'entrée** et du **périphérique de sortie** (dropdowns)
- **VAD énergie RMS** — seuil réglable en live via slider
- **Transcription locale** — Faster-Whisper, tourne sur GPU ou CPU avec fallback automatique
- **Personnalité Claude** — system prompt entièrement personnalisable
- **TTS multi-voix** — Henri, Denise, Antoine (FR) — extensible
- **Historique multi-tours** — mémorise les N derniers échanges (configurable)
- **Journal coloré** — log en temps réel de chaque segment détecté, niveau audio, réponses
- **Réglages persistants** — sauvegardés dans `settings.json`

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

Pour activer l'accélération GPU (optionnel mais recommandé) :

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

### 3. Configurer la clé API

Crée un fichier `.env` à la racine :

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

Obtenir une clé : [console.anthropic.com](https://console.anthropic.com)

### 4. Lancer

```bash
python gui.py
```

ou double-cliquer sur `lancer.bat`

---

## Configuration

Tous les paramètres sont dans `config.py` :

| Paramètre | Défaut | Description |
|---|---|---|
| `WAKE_WORDS` | `["jean-kulki", "kulki", ...]` | Mots qui déclenchent l'assistant |
| `SILENCE_RMS_THRESHOLD` | `0.012` | Seuil de détection vocale (réglable dans la GUI) |
| `SILENCE_AFTER_SPEECH` | `1.3s` | Pause pour couper l'enregistrement |
| `WHISPER_MODEL_SIZE` | `medium` | `tiny` → `large-v3` selon vitesse/précision voulue |
| `WHISPER_DEVICE` | `cuda` | `cuda` ou `cpu` |
| `TTS_VOICE` | `fr-FR-HenriNeural` | Voix Microsoft Neural |
| `MAX_HISTORY_TURNS` | `8` | Nombre d'échanges mémorisés |
| `CLAUDE_MODEL` | `claude-haiku-4-5-20251001` | Modèle Claude utilisé |

---

## Personnalité

La personnalité de l'assistant est définie dans `agent/brain.py` via `SYSTEM_PROMPT`.

Exemples de règles efficaces :
- Donner un nom et une origine à l'assistant
- Préciser le ton (sarcastique, cash, enthousiaste...)
- Ajouter des tics verbaux signature
- Mentionner des sujets de passion et d'aversion
- Limiter la longueur des réponses (`maximum 2 phrases`)
- Interdire le markdown (`zéro astérisque, texte oral uniquement`)

---

## Structure du projet

```
StreamOracle/
├── gui.py              # Interface graphique principale (customtkinter)
├── config.py           # Tous les paramètres centralisés
├── requirements.txt    # Dépendances Python
├── install.bat         # Installation Windows
├── lancer.bat          # Lancement rapide
├── activer_micro.bat   # Active l'accès micro dans les paramètres Windows
├── .env.example        # Modèle de configuration (sans clé)
└── agent/
    ├── listener.py     # Capture micro, VAD, Whisper, wake word
    ├── brain.py        # Claude + system prompt + historique
    └── voice.py        # edge-tts + lecture sounddevice
```

---

## Dépannage

**Le VU-mètre reste à 0**
- Lance `activer_micro.bat` pour activer l'accès micro Windows
- Va dans Paramètres → Confidentialité → Microphone → autoriser les applications bureau
- Vérifie le bon périphérique dans le dropdown "Entrée"

**Erreur CUDA / cublas**
- Installe les DLLs manquantes : `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`
- Ou passe `WHISPER_DEVICE = "cpu"` dans `config.py` (plus lent)

**Pas de son en sortie**
- Sélectionne le bon périphérique dans le dropdown "Sortie voix"
- Teste avec le bouton "🔊 Test voix"

**Trop de faux déclenchements**
- Augmente le slider "Sensibilité micro" dans les réglages

---

## Coût estimé

Claude Haiku est le modèle le moins cher d'Anthropic. Pour un stream de 3h avec ~100 interactions :

| Usage | Coût estimé |
|---|---|
| 100 questions (∼50 tokens chacune) | ~$0.01 |
| 100 réponses (∼100 tokens chacune) | ~$0.04 |
| **Total session 3h** | **< $0.10** |

edge-tts (Microsoft Neural TTS) est **gratuit**.

---

## Licence

MIT — libre d'utilisation, modification et redistribution.
