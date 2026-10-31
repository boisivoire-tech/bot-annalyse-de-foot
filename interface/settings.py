"""Page des paramètres (clé API, cache, apparence)."""
from interface.components import BasePage


class SettingsPage(BasePage):
    title_text = "Paramètres"
    subtitle_text = "Configuration de l'application"

    def build(self) -> None:
        self.add_placeholder("Phases 5 et 11", [
            "Saisie de la clé API-Football (stockée dans le fichier .env)",
            "Durée du cache et gestion hors connexion",
        ])
