"""Tableau de bord : vue d'ensemble de l'application."""
from interface import theme
from interface.components import BasePage, StatCard


class DashboardPage(BasePage):
    title_text = "Tableau de bord"
    subtitle_text = "Vue d'ensemble de vos analyses et du modèle"

    def build(self) -> None:
        self.content.grid_columnconfigure((0, 1, 2), weight=1)
        StatCard(self.content, "Matchs analysés", "0").grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        StatCard(self.content, "Prédictions évaluées", "0").grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        StatCard(self.content, "Précision du modèle", "—", color=theme.TEXT_MUTED).grid(
            row=0, column=2, sticky="ew", padx=8, pady=8)
        self.add_placeholder("Phases 5, 9 et 11", [
            "Matchs du jour et matchs en cours (Phase 5)",
            "Derniers résultats et performances du modèle (Phases 9 et 10)",
            "Indicateur de connexion et date de dernière mise à jour (Phase 11)",
        ])
