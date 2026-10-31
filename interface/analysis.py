"""Page d'analyse détaillée d'un match."""
from interface.components import BasePage


class AnalysisPage(BasePage):
    title_text = "Analyse des matchs"
    subtitle_text = "Analyse complète d'une rencontre sélectionnée"

    def build(self) -> None:
        self.add_placeholder("Phase 8", [
            "Présentation du match et analyse des deux équipes",
            "Forme sur 5 et 10 matchs, performances domicile/extérieur",
            "Confrontations directes, analyse offensive et défensive",
            "Probabilités, scores exacts et conclusion argumentée",
        ])
