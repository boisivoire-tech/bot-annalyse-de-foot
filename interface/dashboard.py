"""Tableau de bord : vue d'ensemble."""
from datetime import datetime, timezone

import customtkinter as ctk

from database import queries
from engine import evaluation
from interface import theme
from interface.components import BasePage, Card, StatCard
from engine.report import pct


class DashboardPage(BasePage):
    title_text = "Tableau de bord"
    subtitle_text = "Vue d'ensemble de vos analyses et du modèle"

    def build(self) -> None:
        self.content.grid_columnconfigure((0, 1, 2), weight=1)
        self.cards = {
            "analyses": StatCard(self.content, "Analyses enregistrées"),
            "matches": StatCard(self.content, "Matchs analysés"),
            "upcoming": StatCard(self.content, "Matchs à venir"),
            "accuracy": StatCard(self.content, "Précision (1X2)"),
            "brier": StatCard(self.content, "Brier 1X2 (0 = parfait)"),
            "evaluated": StatCard(self.content, "Prédictions évaluées"),
        }
        for i, card in enumerate(self.cards.values()):
            card.grid(row=i // 3, column=i % 3, sticky="ew", padx=8, pady=8)

        self.info = Card(self.content, title="Dernière actualisation")
        self.info.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=8)
        self.info_label = ctk.CTkLabel(self.info.body, text="", text_color=theme.TEXT_MUTED,
                                       justify="left", anchor="w", wraplength=900)
        self.info_label.pack(fill="x")

    def refresh(self) -> None:
        summary = evaluation.performance_summary(self.app.conn)
        now = datetime.now(timezone.utc).isoformat()
        overall = summary["overall"]
        self.cards["analyses"].set_value(str(summary["analyses"]))
        self.cards["matches"].set_value(str(summary["matches_analyzed"]))
        self.cards["upcoming"].set_value(str(queries.count_upcoming(self.app.conn, now)))
        self.cards["evaluated"].set_value(str(summary["evaluated"]))
        if overall["accuracy"] is not None:
            self.cards["accuracy"].set_value(pct(overall["accuracy"]), theme.POSITIVE)
            self.cards["brier"].set_value(str(overall["brier"]).replace(".", ","))
        else:
            self.cards["accuracy"].set_value("—", theme.TEXT_MUTED)
            self.cards["brier"].set_value("—", theme.TEXT_MUTED)
        self.info_label.configure(text=self.app.last_refresh_text())
