"""Page de performance du modèle (Brier score, log loss, accuracy)."""
from interface.components import BasePage


class PerformancePage(BasePage):
    title_text = "Performance du modèle"
    subtitle_text = "Évaluation honnête des prédictions passées"

    def build(self) -> None:
        self.add_placeholder("Phase 9", [
            "Nombre de matchs analysés et de prédictions évaluées",
            "Accuracy, Brier Score, Log Loss",
            "Performance par championnat et par catégorie de prédiction",
        ])
