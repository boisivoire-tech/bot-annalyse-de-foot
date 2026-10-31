"""Pages des matchs : matchs du jour et matchs à venir."""
from interface.components import BasePage


class TodayMatchesPage(BasePage):
    title_text = "Matchs du jour"
    subtitle_text = "Rencontres d'aujourd'hui, en cours et terminées"

    def build(self) -> None:
        self.add_placeholder("Phase 5", [
            "Liste des rencontres du jour et du lendemain",
            "Recherche par équipe, filtres par championnat, date et pays",
            "Statuts : à venir, en cours, terminé",
        ])


class UpcomingMatchesPage(BasePage):
    title_text = "Matchs à venir"
    subtitle_text = "Calendrier des prochaines rencontres"

    def build(self) -> None:
        self.add_placeholder("Phase 5", [
            "Calendrier des matchs à venir par championnat",
            "Compétitions prioritaires : Premier League, Ligue 1, Bundesliga, Serie A, La Liga, C1, C3, Conference League, CAN",
        ])
