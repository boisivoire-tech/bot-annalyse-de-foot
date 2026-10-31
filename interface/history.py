"""Page de l'historique des analyses enregistrées."""
from datetime import datetime

from database import queries
from interface import theme
from interface.components import BasePage, Table


class HistoryPage(BasePage):
    title_text = "Historique"
    subtitle_text = "Toutes les analyses enregistrées, avec le résultat réel quand le match est terminé"

    def build(self) -> None:
        self.table = Table(self.content, [
            "Analysée le (UTC)", "Match", "1X2 (V/N/D)", "Score probable", "Qualité",
            "Verrouillée", "Résultat réel", "Prédiction"], empty_text="Aucune analyse enregistrée pour l'instant.")
        self.table.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

    def refresh(self) -> None:
        if not hasattr(self, "table"):
            return
        rows = []
        for a in queries.list_saved_analyses(self.app.conn):
            created = datetime.fromisoformat(a["created_at"]).strftime("%d/%m/%Y %H:%M")
            probs = " / ".join(f"{round(x * 100)}" for x in (a["p_home"], a["p_draw"], a["p_away"])) + " %"
            if a["home_goals"] is None:
                result, verdict = "—", ("en attente", theme.TEXT_MUTED)
            else:
                result = f"{a['home_goals']} - {a['away_goals']}"
                if a["correct_1x2"] is None:
                    verdict = ("à évaluer", theme.TEXT_MUTED)
                elif a["correct_1x2"] == 1:
                    verdict = ("✓ correcte", theme.POSITIVE)
                else:
                    verdict = ("✗ incorrecte", theme.NEGATIVE)
            rows.append([created, f"{a['home']} - {a['away']}", probs, a["most_likely_score"],
                         a["data_quality"], "Oui" if a["is_locked"] else "Non", result, verdict])
        self.table.set_rows(rows)
