"""Affiche l'adresse à ouvrir depuis les autres machines (ordinateur, smartphone) pour la démo.

    python backend/scripts/show_lan_url.py            # port 8000
    python backend/scripts/show_lan_url.py --port 80  # avec Docker
"""
import argparse
import socket


def lan_ip():
    """IP de la carte réseau utilisée pour sortir (aucun paquet n'est réellement envoyé)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    ip = lan_ip()
    suffix = "" if a.port == 80 else f":{a.port}"
    print(f"Depuis les autres machines du même réseau : http://{ip}{suffix}")
    print(f"Page du graphe de Jaccard                  : http://{ip}{suffix}/graphe")
    print(f"Test de charge depuis une autre machine    : python backend/scripts/load_test.py --url http://{ip}{suffix}")
    if ip.startswith("127."):
        print("Aucune connexion réseau détectée : branchez-vous à un réseau (Wi-Fi, partage de connexion).")
