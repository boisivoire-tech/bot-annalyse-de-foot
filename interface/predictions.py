"""Page des prédictions des matchs à venir (7 jours)."""
import sqlite3
from datetime import datetime, timedelta, timezone

import customtkinter as ctk

from database import queries
from engine import prediction
from engine.report import pct
from interface import theme
from interface.components import BasePage, Table

MAX_MATCHES = 40


class PredictionsPage(BasePage):
    title_text = "Prédictions"
    subtitle_text = "Probabilités calculées à partir des données statistiques (estimations, pas des certitudes)"

    def build(self) -> None:
        self.note = ctk.CTkLabel(self.content, text="", text_color=theme.TEXT_MUTED, anchor="w",
                                 justify="left", wraplength=900)
        self.note.grid(row=0, column=0, sticky="ew", padx=12, pady=(4, 8))
        self.table = Table(self.content, [
            "Heure (UTC)", "Match", "Dom.", "Nul", "Ext.", "+2,5 buts", "Les 2 marquent",
            "Score probable", "Confiance"], empty_text="Aucun match à venir dans les 7 prochains jours.")
        self.table.grid(row=1, column=0, sticky="ew", padx=8, pady=8)

    def refresh(self) -> None:
        if not hasattr(self, "table"):
            return
        now = datetime.now(timezone.utc)
        matches = queries.list_matches(self.app.conn, now.replace(microsecond=0).isoformat(),
                                       (now + timedelta(days=7)).isoformat(), status="scheduled",
                                       limit=MAX_MATCHES)
        rows = []
        for m in matches:
            try:
                _, r = prediction.predict_for_match(self.app.conn, m["id"], save=True)
            except sqlite3.IntegrityError:  # analyse verrouillée : on affiche sans modifier
                _, r = None, prediction.compute_for_match(self.app.conn, m["id"])
            kick = datetime.fromisoformat(m["kickoff_utc"]).strftime("%d/%m %H:%M")
            probs = [r.p_home, r.p_draw, r.p_away]
            best = probs.index(max(probs))
            cells = []
            for i, p in enumerate(probs):
                cells.append((pct(p), theme.POSITIVE if i == best and p >= 0.45 else theme.TEXT))
            rows.append([kick, f"{m['home']} - {m['away']}", *cells, pct(r.over[2.5]),
                         pct(r.btts_yes), r.top_scores[0][0], f"{round(r.model_confidence * 100)} %"])
        self.table.set_rows(rows)
        self.note.configure(text=(
            "Lecture : les probabilités viennent du modèle de Poisson. Le vert indique l'issue la plus probable "
            f"quand elle dépasse 45 %. {len(matches)} match(s) affiché(s) ; la confiance mesure la qualité des "
            "données, pas la probabilité de victoire."))
