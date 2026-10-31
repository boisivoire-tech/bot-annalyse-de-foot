"""Page d'analyse détaillée d'un match : rapport en 13 sections."""
from datetime import datetime, timedelta, timezone

import customtkinter as ctk

from database import queries
from engine.report import build_report
from interface import theme
from interface.components import BasePage, Card

NO_MATCH = "— Choisir un match —"


class AnalysisPage(BasePage):
    title_text = "Analyse des matchs"
    subtitle_text = "Analyse complète d'une rencontre : probabilités calculées, non certitudes"

    def build(self) -> None:
        bar = Card(self.content)
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        row = ctk.CTkFrame(bar.body, fg_color="transparent")
        row.pack(fill="x")
        self.search = ctk.CTkEntry(row, placeholder_text="Filtrer par équipe", width=200)
        self.search.pack(side="left", padx=4, pady=4)
        self.search.bind("<Return>", lambda _e: self._reload_choices())
        ctk.CTkButton(row, text="Filtrer", width=90, command=self._reload_choices).pack(side="left", padx=4)
        self.choice = ctk.CTkOptionMenu(row, values=[NO_MATCH], width=520)
        self.choice.pack(side="left", padx=4, pady=4)
        ctk.CTkButton(row, text="Analyser", width=110, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      command=self.run_analysis).pack(side="left", padx=4, pady=4)

        self.status = ctk.CTkLabel(self.content, text="", text_color=theme.TEXT_MUTED, anchor="w")
        self.status.grid(row=1, column=0, sticky="ew", padx=12)
        self.report_area = ctk.CTkFrame(self.content, fg_color="transparent")
        self.report_area.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
        self.report_area.grid_columnconfigure(0, weight=1)
        self._map: dict[str, int] = {}

    def _reload_choices(self) -> None:
        now = datetime.now(timezone.utc)
        matches = queries.list_matches(
            self.app.conn, (now - timedelta(days=3)).isoformat(), (now + timedelta(days=14)).isoformat(),
            team=self.search.get().strip(), limit=300)
        self._map = {NO_MATCH: None}
        for m in matches:
            kick = datetime.fromisoformat(m["kickoff_utc"]).strftime("%d/%m %H:%M")
            label = f"{kick}  {m['home']} - {m['away']}  ({m['competition']})"
            self._map[label] = m["id"]
        current = self.choice.get()
        self.choice.configure(values=list(self._map))
        self.choice.set(current if current in self._map else NO_MATCH)

    def refresh(self) -> None:
        if not hasattr(self, "choice"):
            return
        self._reload_choices()
        pending = self.app.pending_match_id
        if pending is not None:
            for label, mid in self._map.items():
                if mid == pending:
                    self.choice.set(label)
                    break
            else:
                self.status.configure(text="Ce match n'est plus dans la liste (fenêtre de 3 jours à 14 jours).")
            self.app.pending_match_id = None
            self.run_analysis()

    def run_analysis(self) -> None:
        match_id = self._map.get(self.choice.get())
        for widget in self.report_area.winfo_children():
            widget.destroy()
        if match_id is None:
            self.status.configure(text="Sélectionnez un match puis cliquez sur Analyser.")
            return
        try:
            report = build_report(self.app.conn, match_id)
        except ValueError as exc:
            self.status.configure(text=str(exc), text_color=theme.NEGATIVE)
            return
        if report["saved"]:
            self.status.configure(text="Analyse enregistrée dans l'historique (modifiable jusqu'au coup d'envoi).",
                                  text_color=theme.POSITIVE)
        else:
            self.status.configure(text="Match déjà commencé ou terminé : analyse affichée, non enregistrée.",
                                  text_color=theme.WARNING)
        for i, section in enumerate(report["sections"]):
            card = Card(self.report_area, title=section["title"])
            card.grid(row=i, column=0, sticky="ew", padx=4, pady=6)
            for line in section["lines"]:
                ctk.CTkLabel(card.body, text=line, font=theme.font(13), text_color=theme.TEXT,
                             justify="left", anchor="w", wraplength=760).pack(fill="x", pady=2)
