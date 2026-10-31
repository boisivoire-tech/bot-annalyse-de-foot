"""Page des statistiques par équipe : forme, domicile/extérieur, classement."""
import customtkinter as ctk

from database import db, queries
from engine.form_analysis import compute_form
from engine.report import fmt
from engine.team_analysis import quality_label
from interface import theme
from interface.components import BasePage, Card, Table


class TeamStatisticsPage(BasePage):
    title_text = "Statistiques des équipes"
    subtitle_text = "Forme, buts, domicile/extérieur et classement, à partir des matchs enregistrés"

    def build(self) -> None:
        bar = Card(self.content)
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        row = ctk.CTkFrame(bar.body, fg_color="transparent")
        row.pack(fill="x")
        self.search = ctk.CTkEntry(row, placeholder_text="Nom d'équipe", width=260)
        self.search.pack(side="left", padx=4, pady=4)
        self.search.bind("<Return>", lambda _e: self.refresh())
        ctk.CTkButton(row, text="Rechercher", width=120, command=self.refresh).pack(side="left", padx=4)

        self.teams = Table(self.content, ["Équipe", "Pays", ""], empty_text="Aucune équipe enregistrée.")
        self.teams.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        self.profile = Card(self.content, title="Profil de l'équipe")
        self.profile.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        self.profile_label = ctk.CTkLabel(self.profile.body, text="Sélectionnez une équipe dans la liste.",
                                          text_color=theme.TEXT_MUTED, justify="left", anchor="w",
                                          wraplength=900)
        self.profile_label.pack(fill="x")
        self.form_table = Table(self.profile.body, ["Période", "Matchs", "V", "N", "D", "Buts pour",
                                                    "Buts contre", "Pts/match", "Suite"])
        self.form_table.pack(fill="x", pady=(10, 0))
        self._selected: int | None = None

    def refresh(self) -> None:
        if not hasattr(self, "teams"):
            return
        teams = queries.list_teams(self.app.conn, self.search.get().strip(), limit=60)
        self.teams.set_rows([[t["name"], t["country"] or "n.d.",
                              {"button": "Voir", "command": lambda tid=t["id"]: self.show_team(tid)}]
                             for t in teams])
        if self._selected is not None:
            self.show_team(self._selected)

    def show_team(self, team_id: int) -> None:
        self._selected = team_id
        conn = self.app.conn
        name_row = conn.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
        if name_row is None:
            return
        matches = db.get_finished_matches(conn, team_id)
        quality = quality_label(compute_form(matches, team_id).sample)
        standing = conn.execute(
            """SELECT s.rank, s.points, s.played, c.name AS competition FROM standings s
               JOIN competitions c ON c.id = s.competition_id WHERE s.team_id = ?
               ORDER BY s.season DESC, s.rank LIMIT 1""", (team_id,)).fetchone()
        standing_text = ("classement non disponible" if standing is None else
                         f"{standing['rank']}e de {standing['competition']} ({standing['points']} pts, "
                         f"{standing['played']} matchs)")
        self.profile_label.configure(text=(
            f"{name_row['name']} — données : {quality} ({len(matches)} matchs terminés enregistrés) ; "
            f"classement : {standing_text}."))
        rows = []
        for n in (5, 10, 15):
            f = compute_form(matches, team_id, n)
            rows.append(self._form_row(f"{n} derniers", f))
        for label, venue in (("Domicile (15)", "home"), ("Extérieur (15)", "away")):
            rows.append(self._form_row(label, compute_form(matches, team_id, 15, venue)))
        self.form_table.set_rows(rows)

    @staticmethod
    def _form_row(label, f):
        if f.sample == 0:
            return [label, "0", "—", "—", "—", "—", "—", "—", "aucun match"]
        return [label, str(f.sample), str(f.wins), str(f.draws), str(f.losses), str(f.goals_for),
                str(f.goals_against), fmt(f.points_per_game), f.results]
