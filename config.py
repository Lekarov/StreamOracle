import os
from dotenv import load_dotenv

load_dotenv(".env.example") or load_dotenv()  # .env.example prioritaire, .env en fallback

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-haiku-4-5-20251001"

# Mots-clés qui réveillent Jean-Kulki (insensible à la casse)
WAKE_WORDS = ["jean-kulki"]

# Capture audio
SAMPLE_RATE = 16000
CHANNELS    = 1

# VAD (Voice Activity Detection)
SILENCE_RMS_THRESHOLD = 0.012   # RMS en dessous = silence (augmente si trop sensible)
MIN_SPEECH_DURATION   = 0.4     # secondes — segment ignoré en dessous
MAX_SPEECH_DURATION   = 15.0    # secondes — coupe la reco si trop long
SILENCE_AFTER_SPEECH  = 1.3     # secondes de silence pour terminer un segment
PRE_SPEECH_BUFFER     = 0.5     # secondes conservées avant la parole

# Whisper
WHISPER_MODEL_SIZE   = "medium"     # tiny/base/small/medium/large-v3
WHISPER_DEVICE       = "cuda"       # "cuda" ou "cpu"
WHISPER_COMPUTE_TYPE = "float16"    # float16 sur GPU, int8 sur CPU
WHISPER_LANGUAGE     = "fr"

# TTS — voix Microsoft (edge-tts, gratuit, requiert internet)
# Voix dispos FR : fr-FR-HenriNeural (homme) | fr-FR-DeniseNeural (femme)
TTS_VOICE = "fr-FR-HenriNeural"

# Historique conversation conservé
MAX_HISTORY_TURNS = 8
