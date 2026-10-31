"""Fenêtre principale : menu latéral, barre supérieure, actualisation en arrière-plan."""
import os
import queue
import threading
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from config import APP_NAME, APP_VERSION
from database import db
from interface import theme
from interface.analysis import AnalysisPage
from interface.dashboard import DashboardPage
from interface.history import HistoryPage
from interface.matches import TodayMatchesPage, UpcomingMatchesPage
from interface.performance import PerformancePage
from interface.predictions import PredictionsPage
from interface.settings import SettingsPage
from interface.statistics import TeamStatisticsPage
from services.data_manager import RefreshReport, refresh_all
from services.football_api import FootballApiClient

# (libellé du menu, classe de la page)
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

        self.conn = db.connect()                 # connexion de l'interface (thread principal)
        self.pending_match_id: int | None = None
        self.last_refresh: datetime | None = None
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._current: str | None = None
        self._refreshing = False
        self._queue: queue.Queue = queue.Queue()

        self._build_sidebar()
        self._build_topbar()
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=1, column=1, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show_page(NAVIGATION[0][0])

    # ----- Mise en page -----------------------------------------------------
    def _set_initial_geometry(self) -> None:
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = min(1280, int(screen_w * 0.9))
        height = min(800, int(screen_h * 0.85))
        x = max((screen_w - width) // 2, 0)
        y = max((screen_h - height) // 2 - 20, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(960, width), min(600, height))

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=theme.SIDEBAR_WIDTH, fg_color=theme.SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(len(NAVIGATION) + 2, weight=1)
        ctk.CTkLabel(sidebar, text="FOOTBALL", font=theme.font(20, "bold"),
                     text_color=theme.TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(24, 0))
        ctk.CTkLabel(sidebar, text="INTELLIGENCE PRO", font=theme.font(12, "bold"),
                     text_color=theme.TEXT_MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 18))
        for index, (label, _) in enumerate(NAVIGATION, start=2):
            button = ctk.CTkButton(
                sidebar, text=label, anchor="w", height=38, corner_radius=10, font=theme.font(13),
                fg_color="transparent", text_color=theme.TEXT_MUTED, hover_color=theme.CARD,
                command=lambda name=label: self.show_page(name))
            button.grid(row=index, column=0, sticky="ew", padx=12, pady=3)
            self._nav_buttons[label] = button
        ctk.CTkLabel(sidebar, text=f"Version {APP_VERSION}", font=theme.font(11),
                     text_color=theme.TEXT_MUTED).grid(row=len(NAVIGATION) + 3, column=0, sticky="sw",
                                                       padx=20, pady=12)

    def _build_topbar(self) -> None:
        topbar = ctk.CTkFrame(self, fg_color="transparent")
        topbar.grid(row=0, column=1, sticky="ne", padx=20, pady=(14, 0))
        self.status_label = ctk.CTkLabel(topbar, text="Données locales", font=theme.font(12),
                                         text_color=theme.TEXT_MUTED)
        self.status_label.pack(side="left", padx=(0, 16))
        self.refresh_button = ctk.CTkButton(
            topbar, text="ACTUALISER", width=140, height=36, corner_radius=10, font=theme.font(13, "bold"),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self.on_refresh)
        self.refresh_button.pack(side="left")

    # ----- Navigation ---------------------------------------------------------
    def show_page(self, label: str) -> None:
        if label == self._current:
            self._pages[label].refresh()
            return
        page_class = dict(NAVIGATION)[label]
        if label not in self._pages:
            self._pages[label] = page_class(self.container, self)
        if self._current is not None:
            self._pages[self._current].grid_forget()
            self._nav_buttons[self._current].configure(fg_color="transparent", text_color=theme.TEXT_MUTED)
        self._pages[label].grid(row=0, column=0, sticky="nsew")
        self._pages[label].refresh()
        self._nav_buttons[label].configure(fg_color=theme.ACCENT, text_color=theme.TEXT)
        self._current = label

    def open_analysis(self, match_id: int) -> None:
        """Ouvre la page d'analyse pour un match choisi depuis une liste."""
        self.pending_match_id = match_id
        self.show_page("Analyse des matchs")

    def last_refresh_text(self) -> str:
        if self.last_refresh is None:
            return ("Aucune actualisation depuis le démarrage. Les données affichées sont celles enregistrées "
                    "localement. ACTUALISER nécessite une connexion Internet.")
        return f"Dernière actualisation : {self.last_refresh.strftime('%d/%m/%Y %H:%M')}."

    # ----- Actualisation (arrière-plan, l'interface reste active) ------------
    def on_refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        self.refresh_button.configure(state="disabled", text="Actualisation…")
        self.status_label.configure(text="Actualisation en cours…", text_color=theme.TEXT_MUTED)
        threading.Thread(target=self._refresh_worker, daemon=True).start()
        self.after(200, self._poll_refresh)

    def _refresh_worker(self) -> None:
        conn = None
        try:
            conn = db.connect()
            client = FootballApiClient(api_key=os.getenv("API_FOOTBALL_KEY", ""))
            report = refresh_all(conn, client)
            self._queue.put(("ok", report))
        except Exception as exc:  # erreur inattendue : affichée à l'utilisateur, l'app continue
            self._queue.put(("error", str(exc)))
        finally:
            if conn is not None:
                conn.close()

    def _poll_refresh(self) -> None:
        try:
            kind, payload = self._queue.get_nowait()
        except queue.Empty:
            self.after(200, self._poll_refresh)
            return
        self._refreshing = False
        self.refresh_button.configure(state="normal", text="ACTUALISER")
        if kind == "error":
            self.status_label.configure(text="Erreur d'actualisation", text_color=theme.NEGATIVE)
            messagebox.showerror("Actualisation", f"Une erreur est survenue :\n{payload}")
        else:
            self._show_report(payload)
        for page in self._pages.values():
            page.refresh()

    def _show_report(self, report: RefreshReport) -> None:
        self.last_refresh = datetime.now()
        if report.offline:
            self.status_label.configure(text="Hors ligne : données locales", text_color=theme.WARNING)
        else:
            self.status_label.configure(text=f"Mis à jour à {self.last_refresh:%H:%M}", text_color=theme.POSITIVE)
        lines = []
        if report.offline:
            lines.append("Connexion impossible. Les nouvelles statistiques nécessitent une connexion Internet. "
                         "Les données précédentes restent consultables.")
        lines += [
            f"Requêtes API utilisées : {report.requests_used} (limite par actualisation : 40).",
            f"Matchs mis à jour : {report.matches_stored}.",
            f"Analyses verrouillées (match commencé) : {report.analyses_locked}.",
            f"Résultats évalués : {report.analyses_evaluated}.",
        ]
        lines += report.messages
        if report.errors:
            lines.append("Erreurs signalées : " + " ; ".join(sorted(set(report.errors))[:3]))
        (messagebox.showwarning if report.offline or report.errors else messagebox.showinfo)(
            "Actualisation", "\n".join(lines))

    def _on_close(self) -> None:
        try:
            self.conn.close()
        finally:
            self.destroy()
