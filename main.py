"""Jean-Kulki — assistant vocal IA pour stream Pestovich."""
import sys
import threading

import config
from agent.listener import Listener
from agent.brain    import Brain
from agent.voice    import Voice


def main() -> None:
    if not config.ANTHROPIC_API_KEY:
        print("ERREUR : ANTHROPIC_API_KEY manquant.")
        print("Copie .env.example en .env et remplis ta clé API Anthropic.")
        sys.exit(1)

    listener = Listener()
    brain    = Brain()
    voice    = Voice()

    _lock = threading.Lock()

    def handle_query(query: str) -> None:
        if not _lock.acquire(blocking=False):
            print("[Skip] Jean-Kulki répond déjà, requête ignorée.")
            return

        try:
            listener.set_speaking(True)

            print(f"[User]  {query}")
            reply = brain.respond(query)
            print(f"[Jean-Kulki] {reply}")

            voice.speak(reply)

        except Exception as exc:
            print(f"[Erreur] {exc}")
        finally:
            listener.set_speaking(False)
            _lock.release()

    def on_query(query: str) -> None:
        threading.Thread(target=handle_query, args=(query,), daemon=True).start()

    print("=" * 50)
    print("  Jean-Kulki — Assistant vocal de Pestovich")
    print("=" * 50)
    print("Commandes clavier : Ctrl+C pour quitter")
    print()

    try:
        listener.listen_loop(on_query)
    except KeyboardInterrupt:
        print("\n[Jean-Kulki] Bonne session, boss. À plus.")


if __name__ == "__main__":
    main()
