"""Page de performance du modèle : Brier, log loss, précision, par championnat et par marché."""
import customtkinter as ctk

from engine import evaluation
from engine.report import fmt, pct
from interface import theme
from interface.components import BasePage, Card, StatCard, Table


class PerformancePage(BasePage):
    title_text = "Performance du modèle"
    subtitle_text = "Évaluation honnête des prédictions passées, sur les résultats réels"

    def build(self) -> None:
        self.content.grid_columnconfigure((0, 1, 2), weight=1)
        self.stats = {
            "analyses": StatCard(self.content, "Analyses enregistrées"),
            "matches": StatCard(self.content, "Matchs analysés"),
            "evaluated": StatCard(self.content, "Prédictions évaluées"),
            "accuracy": StatCard(self.content, "Précision (1X2)"),
            "brier": StatCard(self.content, "Brier 1X2 (0 = parfait)"),
            "logloss": StatCard(self.content, "Log loss (plus bas = mieux)"),
        }
        for i, card in enumerate(self.stats.values()):
            card.grid(row=i // 3, column=i % 3, sticky="ew", padx=8, pady=8)

        self.explain = ctk.CTkLabel(self.content, text="", text_color=theme.TEXT_MUTED, justify="left",
                                    anchor="w", wraplength=900)
        self.explain.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=4)

        self.chart_card = Card(self.content, title="Précision par championnat")
        self.chart_card.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=8)
        self._canvas = None

        ctk.CTkLabel(self.content, text="Par championnat", font=theme.font(15, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(row=4, column=0, sticky="w", padx=12, pady=(10, 4))
        self.by_comp = Table(self.content, ["Championnat", "Prédictions", "Précision", "Brier", "Log loss"],
                             empty_text="Pas encore de matchs évalués.")
        self.by_comp.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

        ctk.CTkLabel(self.content, text="Par catégorie de prédiction", font=theme.font(15, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(row=6, column=0, sticky="w", padx=12, pady=(10, 4))
        self.by_market = Table(self.content, ["Catégorie", "Prédictions", "Précision", "Brier", "Log loss"],
                               empty_text="Pas encore de marchés évalués.")
        self.by_market.grid(row=7, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

    def refresh(self) -> None:
        if not hasattr(self, "stats"):
            return
        s = evaluation.performance_summary(self.app.conn)
        o = s["overall"]
        self.stats["analyses"].set_value(str(s["analyses"]))
        self.stats["matches"].set_value(str(s["matches_analyzed"]))
        self.stats["evaluated"].set_value(str(s["evaluated"]))
        if o["accuracy"] is None:
            for key in ("accuracy", "brier", "logloss"):
                self.stats[key].set_value("—", theme.TEXT_MUTED)
        else:
            self.stats["accuracy"].set_value(pct(o["accuracy"]), theme.POSITIVE)
            self.stats["brier"].set_value(fmt(o["brier"], 3))
            self.stats["logloss"].set_value(fmt(o["log_loss"], 3))
        self.explain.configure(text=(
            "Brier 1X2 : 0 = parfait ; une prédiction au hasard (1/3 chacun) donne environ 0,67. "
            "Log loss : pénalise fortement les probabilités élevées données à une issue qui n'arrive pas. "
            "Ces chiffres se stabilisent avec le temps : un petit nombre de matchs reste peu fiable."))
        self.by_comp.set_rows([[name, str(v["count"]), pct(v["accuracy"]), fmt(v["brier"], 3),
                                fmt(v["log_loss"], 3)] for name, v in s["by_competition"].items()])
        self.by_market.set_rows([[name, str(v["count"]), pct(v["accuracy"]), fmt(v["brier"], 3),
                                  fmt(v["log_loss"], 3)] for name, v in s["by_market"].items()])
        self._draw_chart(s["by_competition"])

    def _draw_chart(self, by_comp: dict) -> None:
        if self._canvas is not None:
            self._canvas.get_tk_widget().destroy()
            self._canvas = None
        if not by_comp:
            return
        # Import tardif : matplotlib n'est chargé que si un graphique est nécessaire (économie de RAM)
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        fig = Figure(figsize=(8, 2.6), dpi=100, facecolor=theme.CARD)
        ax = fig.add_subplot(111)
        ax.set_facecolor(theme.CARD)
        names = list(by_comp)
        values = [(by_comp[n]["accuracy"] or 0) * 100 for n in names]
        ax.bar(names, values, color=theme.ACCENT)
        ax.set_ylabel("Précision (%)", color=theme.TEXT_MUTED)
        ax.set_ylim(0, 100)
        ax.tick_params(colors=theme.TEXT_MUTED, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(theme.CARD_BORDER)
        fig.tight_layout()
        self._canvas = FigureCanvasTkAgg(fig, master=self.chart_card.body)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)
        self._canvas.draw()
