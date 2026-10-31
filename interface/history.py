"""Page de l'historique des analyses enregistrées."""
from interface.components import BasePage


class HistoryPage(BasePage):
    title_text = "Historique"
    subtitle_text = "Toutes les analyses enregistrées, horodatées"

    def build(self) -> None:
        self.add_placeholder("Phase 9", [
            "Liste des analyses sauvegardées dans SQLite",
            "Résultat réel après le match et comparaison avec la prédiction",
        ])
