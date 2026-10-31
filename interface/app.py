"""Fenêtre principale : menu latéral à 9 entrées, barre supérieure et zone de contenu.

Les pages sont créées à la demande (lazy) pour économiser la mémoire du PC.
"""
import tkinter.messagebox as messagebox

import customtkinter as ctk

from config import APP_NAME, APP_VERSION
from interface import theme
from interface.analysis import AnalysisPage
from interface.dashboard import DashboardPage
from interface.history import HistoryPage
from interface.matches import TodayMatchesPage, UpcomingMatchesPage
from interface.performance import PerformancePage
from interface.predictions import PredictionsPage
from interface.settings import SettingsPage
from interface.statistics import TeamStatisticsPage

# (libellé du menu, classe de la page) — l'ordre correspond au cahier des charges
NAVIGATION = [
    ("Tableau de bord", DashboardPage),
    ("Matchs du jour", TodayMatchesPage),
    ("Matchs à venir", UpcomingMatchesPage),
    ("Analyse des matchs", AnalysisPage),
    ("Prédictions", PredictionsPage),
    ("Statistiques des équipes", TeamStatisticsPage),
    ("Historique", HistoryPage),
    ("Performance du modèle", PerformancePage),
    ("Paramètres", SettingsPage),
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=theme.BG)
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self._set_initial_geometry()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._pages: dict[str, ctk.CTkFrame] = {}
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._current: str | None = None

        self._build_sidebar()
        self._build_main_area()
        self.show_page(NAVIGATION[0][0])

    # ----- Mise en page -------------------------------------------------
    def _set_initial_geometry(self) -> None:
        """Adapte la taille de la fenêtre à la résolution de l'écran."""
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1280, int(screen_w * 0.9))
        height = min(800, int(screen_h * 0.85))
        x = max((screen_w - width) // 2, 0)
        y = max((screen_h - height) // 2 - 20, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(960, width), min(600, height))

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=theme.SIDEBAR_WIDTH, fg_color=theme.SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(len(NAVIGATION) + 1, weight=1)

        ctk.CTkLabel(sidebar, text="FOOTBALL", font=theme.font(20, "bold"),
                     text_color=theme.TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(24, 0))
        ctk.CTkLabel(sidebar, text="INTELLIGENCE PRO", font=theme.font(12, "bold"),
                     text_color=theme.TEXT_MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 18))

        for index, (label, _) in enumerate(NAVIGATION, start=2):
            button = ctk.CTkButton(
                sidebar, text=label, anchor="w", height=38,
                corner_radius=10, font=theme.font(13),
                fg_color="transparent", text_color=theme.TEXT_MUTED,
                hover_color=theme.CARD,
                command=lambda name=label: self.show_page(name),
            )
            button.grid(row=index, column=0, sticky="ew", padx=12, pady=3)
            self._nav_buttons[label] = button

        ctk.CTkLabel(sidebar, text=f"Version {APP_VERSION}", font=theme.font(11),
                     text_color=theme.TEXT_MUTED).grid(row=len(NAVIGATION) + 2, column=0,
                                                       sticky="sw", padx=20, pady=12)

    def _build_main_area(self) -> None:
        topbar = ctk.CTkFrame(self, fg_color="transparent", height=56)
        topbar.grid(row=0, column=1, sticky="ne", padx=20, pady=(14, 0))
        self.status_label = ctk.CTkLabel(topbar, text="Hors ligne : données locales",
                                         font=theme.font(12), text_color=theme.WARNING)
        self.status_label.pack(side="left", padx=(0, 16))
        ctk.CTkButton(
            topbar, text="ACTUALISER", width=140, height=36, corner_radius=10,
            font=theme.font(13, "bold"), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            command=self.on_refresh,
        ).pack(side="left")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

    # ----- Navigation ---------------------------------------------------
    def show_page(self, label: str) -> None:
        """Affiche la page demandée et met en surbrillance son bouton."""
        if label == self._current:
            return
        page_class = dict(NAVIGATION)[label]
        if label not in self._pages:
            self._pages[label] = page_class(self.container)
        if self._current is not None:
            self._pages[self._current].grid_forget()
            self._nav_buttons[self._current].configure(fg_color="transparent",
                                                       text_color=theme.TEXT_MUTED)
        self._pages[label].grid(row=0, column=0, sticky="nsew")
        self._nav_buttons[label].configure(fg_color=theme.ACCENT, text_color=theme.TEXT)
        self._current = label

    def on_refresh(self) -> None:
        """Bouton ACTUALISER : la vraie logique arrive en Phase 11."""
        messagebox.showinfo(
            "Actualiser",
            "La mise à jour des données nécessite une connexion Internet.\n\n"
            "Cette fonction sera branchée à l'API en Phase 5 et Phase 11.",
        )
