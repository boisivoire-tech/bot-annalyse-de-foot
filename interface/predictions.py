"""Page des prédictions (1X2, buts, double chance, scores exacts)."""
from interface.components import BasePage


class PredictionsPage(BasePage):
    title_text = "Prédictions"
    subtitle_text = "Probabilités calculées à partir des données statistiques"

    def build(self) -> None:
        self.add_placeholder("Phase 7", [
            "Probabilités 1X2 (somme égale à 100 %)",
            "Plus/Moins de buts, les deux équipes marquent, double chance",
            "Scores exacts les plus probables et indicateur de fiabilité",
        ])
