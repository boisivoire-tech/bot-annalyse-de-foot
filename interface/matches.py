"""Pages des matchs : matchs du jour (aujourd'hui / demain) et matchs à venir."""
from datetime import datetime, time, timedelta, timezone

import customtkinter as ctk

from database import queries
from interface import theme
from interface.components import BasePage, Card, Table

STATUS_LABELS = {"scheduled": "À venir", "live": "En cours", "finished": "Terminé",
                 "postponed": "Reporté", "cancelled": "Annulé", "other": "Autre"}
STATUS_COLORS = {"live": theme.WARNING, "finished": theme.TEXT_MUTED, "scheduled": theme.TEXT,
                 "postponed": theme.WARNING, "cancelled": theme.NEGATIVE, "other": theme.TEXT_MUTED}
ALL = "Tous"


class MatchListPage(BasePage):
    """Liste de matchs avec recherche et filtres. Les heures sont en UTC (Abidjan = UTC)."""

    upcoming_mode = False

    def build(self) -> None:
        filters = Card(self.content)
        filters.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        row = ctk.CTkFrame(filters.body, fg_color="transparent")
        row.pack(fill="x")

        if not self.upcoming_mode:
            self.day = ctk.CTkSegmentedButton(row, values=["Aujourd'hui", "Demain"],
                                              command=lambda _v: self.refresh())
            self.day.set("Aujourd'hui")
            self.day.pack(side="left", padx=(0, 10), pady=4)

        self.search = ctk.CTkEntry(row, placeholder_text="Rechercher une équipe", width=200)
        self.search.pack(side="left", padx=4, pady=4)
        self.search.bind("<Return>", lambda _e: self.refresh())

        self.competition = ctk.CTkOptionMenu(row, values=[ALL], width=200, command=lambda _v: self.refresh())
        self.competition.pack(side="left", padx=4, pady=4)
        self.country = ctk.CTkOptionMenu(row, values=[ALL], width=160, command=lambda _v: self.refresh())
        self.country.pack(side="left", padx=4, pady=4)
        self.status = ctk.CTkOptionMenu(row, values=[ALL, "À venir", "En cours", "Terminé"], width=140,
                                        command=lambda _v: self.refresh())
        self.status.pack(side="left", padx=4, pady=4)
        ctk.CTkButton(row, text="Filtrer", width=90, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      command=self.refresh).pack(side="left", padx=4, pady=4)

        headers = ["Heure (UTC)", "Championnat", "Domicile", "Extérieur", "Statut", "Score",
                   "Prédiction 1X2 (V/N/D)", ""]
        self.table = Table(self.content, headers, empty_text=(
            "Aucun match. Cliquez sur ACTUALISER (connexion Internet nécessaire) pour charger les matchs."))
        self.table.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        self._competitions: dict[str, int | None] = {ALL: None}
        self._countries: list[str] = [ALL]

    def _range(self) -> tuple[str, str]:
        now = datetime.now(timezone.utc)
        if self.upcoming_mode:
            start = now.replace(microsecond=0)
            return start.isoformat(), (start + timedelta(days=14)).isoformat()
        day = now.date() + timedelta(days=1 if self.day.get() == "Demain" else 0)
        start = datetime.combine(day, time(0), tzinfo=timezone.utc)
        return start.isoformat(), (start + timedelta(days=1)).isoformat()

    def _load_filters(self) -> None:
        comps = queries.list_competitions(self.app.conn)
        self._competitions = {ALL: None}
        for c in comps:
            label = f"{c['name']} ({c['country'] or 'n.d.'})"
            self._competitions[label] = c["id"]
        current = self.competition.get()
        self.competition.configure(values=list(self._competitions))
        self.competition.set(current if current in self._competitions else ALL)
        countries = [ALL] + queries.list_countries(self.app.conn)
        self.country.configure(values=countries)
        if self.country.get() not in countries:
            self.country.set(ALL)

    def refresh(self) -> None:
        if not hasattr(self, "table"):
            return
        self._load_filters()
        start, end = self._range()
        status_map = {"À venir": "scheduled", "En cours": "live", "Terminé": "finished"}
        status = status_map.get(self.status.get())
        if self.upcoming_mode:
            status = status or "scheduled"
        matches = queries.list_matches(
            self.app.conn, start, end,
            team=self.search.get().strip(),
            competition_id=self._competitions.get(self.competition.get()),
            country="" if self.country.get() == ALL else self.country.get(),
            status=status,
        )
        predictions = self._latest_predictions([m["id"] for m in matches])
        rows = []
        for m in matches:
            kick = datetime.fromisoformat(m["kickoff_utc"])
            when = kick.strftime("%d/%m %H:%M") if self.upcoming_mode else kick.strftime("%H:%M")
            score = "—" if m["home_goals"] is None else f"{m['home_goals']} - {m['away_goals']}"
            p = predictions.get(m["id"])
            pred = "—" if p is None else " / ".join(f"{round(x * 100)}" for x in p) + " %"
            rows.append([
                when,
                m["competition"],
                m["home"],
                m["away"],
                (STATUS_LABELS.get(m["status"], "Autre"), STATUS_COLORS.get(m["status"], theme.TEXT)),
                score,
                pred,
                {"button": "Analyser", "command": lambda mid=m["id"]: self.app.open_analysis(mid)},
            ])
        self.table.set_rows(rows)

    def _latest_predictions(self, match_ids: list[int]) -> dict:
        if not match_ids:
            return {}
        marks = ",".join("?" for _ in match_ids)
        rows = self.app.conn.execute(
            f"""SELECT match_id, p_home, p_draw, p_away FROM analyses
                WHERE match_id IN ({marks}) ORDER BY created_at DESC""", match_ids).fetchall()
        result = {}
        for r in rows:
            result.setdefault(r["match_id"], (r["p_home"], r["p_draw"], r["p_away"]))
        return result


class TodayMatchesPage(MatchListPage):
    title_text = "Matchs du jour"
    subtitle_text = "Rencontres d'aujourd'hui et de demain, en cours et terminées"


class UpcomingMatchesPage(MatchListPage):
    title_text = "Matchs à venir"
    subtitle_text = "Calendrier des 14 prochains jours"
    upcoming_mode = True
