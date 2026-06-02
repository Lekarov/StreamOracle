"""LLM brain — Claude + system prompt + conversation history."""
from __future__ import annotations

import anthropic
import config

# ── Personnalité de l'assistant ───────────────────────────────────────────────
# Personnalise ce bloc pour définir qui est ton assistant.
# Plus c'est précis et concret, meilleur sera le résultat.

SYSTEM_PROMPT = """Tu es Oracle, un assistant IA vocal pour stream Twitch.

Personnalité :
- Ton naturel : décontracté, direct, avec une pointe d'humour sec — tu dis ce que tu penses sans chercher à plaire
- Tu es curieux et engagé : quand un sujet t'intéresse, ça se sent, tu pousses la réflexion
- Tu gardes une cohérence : tu te souviens de ce qui a été dit et tu peux y faire référence
- Tu n'es jamais condescendant, jamais faux-poli — juste honnête et utile

Ton rôle sur le stream :
- Répondre aux questions du streamer quand il t'appelle
- Donner ton avis sans langue de bois si on te le demande
- Rester dans le contexte du stream sans partir dans des monologues

Règles strictes :
- TOUJOURS en français, langage oral naturel
- Maximum 2 phrases courtes — tu parles à la radio, pas dans un roman
- Zéro markdown, zéro liste, zéro astérisque — texte oral uniquement
- Contenu PG-13, stream public
- Si tu ne sais pas quelque chose, dis-le brièvement et passe à autre chose

──────────────────────────────────────────────────────────────────────
 PERSONNALISATION : remplace ce bloc par ta propre définition.
 Exemples de paramètres utiles :
   - Nom de l'assistant et éventuelle origine fictive
   - Sujets de passion / d'aversion
   - Expressions et tics verbaux signature
   - Ton par rapport au streamer (pote, subordonné, rival affectueux...)
   - Contexte du stream (jeux joués, running gags, noms de viewers réguliers)
──────────────────────────────────────────────────────────────────────"""


class Brain:
    def __init__(self) -> None:
        self._client  = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self._history: list[dict] = []

    def respond(self, query: str) -> str:
        self._history.append({"role": "user", "content": query})

        max_msgs = config.MAX_HISTORY_TURNS * 2
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]

        message = self._client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=180,
            system=SYSTEM_PROMPT,
            messages=self._history,
        )

        reply = message.content[0].text.strip()
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def clear_history(self) -> None:
        self._history.clear()
