"""Point d'entrée de FOOTBALL INTELLIGENCE PRO.

Lancement : python main.py
"""
from interface.app import App


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
