"""Page des statistiques par équipe."""
from interface.components import BasePage


class TeamStatisticsPage(BasePage):
    title_text = "Statistiques des équipes"
    subtitle_text = "Forme, buts, classement et statistiques avancées"

    def build(self) -> None:
        self.add_placeholder("Phase 6", [
            "5, 10 et 15 derniers matchs, buts marqués et encaissés",
            "Performances à domicile et à l'extérieur, classement",
            "xG, xGA, tirs, corners, possession, clean sheets (si disponibles)",
        ])
