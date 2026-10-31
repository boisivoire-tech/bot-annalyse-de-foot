"""Page des paramètres : clé API (stockée dans .env), cache et informations."""
import os

import customtkinter as ctk

from config import DB_PATH, CACHE_TTL_HOURS, mask_key, write_env_value
from interface import theme
from interface.components import BasePage, Card


class SettingsPage(BasePage):
    title_text = "Paramètres"
    subtitle_text = "Configuration de l'application"

    def build(self) -> None:
        key_card = Card(self.content, title="Clé API-Football")
        key_card.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        self.key_status = ctk.CTkLabel(key_card.body, text="", anchor="w", text_color=theme.TEXT_MUTED)
        self.key_status.pack(fill="x")
        row = ctk.CTkFrame(key_card.body, fg_color="transparent")
        row.pack(fill="x", pady=8)
        self.key_entry = ctk.CTkEntry(row, show="•", width=420, placeholder_text="Collez votre clé ici")
        self.key_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Enregistrer dans .env", width=180, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, command=self.save_key).pack(side="left")
        self.message = ctk.CTkLabel(key_card.body, text="", anchor="w", wraplength=860, justify="left")
        self.message.pack(fill="x")
        ctk.CTkLabel(key_card.body, text=(
            "La clé est stockée localement dans le fichier .env (ignoré par Git). "
            "Elle n'est jamais affichée en entier."), text_color=theme.TEXT_MUTED, anchor="w",
            wraplength=860, justify="left").pack(fill="x", pady=(6, 0))

        cache_card = Card(self.content, title="Cache et données")
        cache_card.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        self.info = ctk.CTkLabel(cache_card.body, text="", anchor="w", justify="left", wraplength=860,
                                 text_color=theme.TEXT_MUTED)
        self.info.pack(fill="x")
        ctk.CTkButton(cache_card.body, text="Vider le cache API", width=180, command=self.clear_cache).pack(
            anchor="w", pady=8)

    def refresh(self) -> None:
        if not hasattr(self, "key_status"):
            return
        key = os.getenv("API_FOOTBALL_KEY", "")
        if key:
            self.key_status.configure(text=f"Clé configurée : {mask_key(key)}", text_color=theme.POSITIVE)
        else:
            self.key_status.configure(text="Aucune clé configurée : les nouvelles données sont indisponibles.",
                                      text_color=theme.WARNING)
        self.info.configure(text=(
            f"Base de données : {DB_PATH}\n"
            f"Durée du cache : {CACHE_TTL_HOURS} heure(s) (modifiable dans .env, CACHE_TTL_HOURS).\n"
            "Les nouvelles statistiques et les résultats nécessitent une connexion Internet.\n"
            "Heures affichées en UTC (Abidjan et Reykjavik sont à UTC+0)."))

    def save_key(self) -> None:
        key = self.key_entry.get().strip()
        if len(key) < 10 or " " in key:
            self.message.configure(text="Clé invalide : elle doit contenir au moins 10 caractères, sans espace.",
                                   text_color=theme.NEGATIVE)
            return
        write_env_value("API_FOOTBALL_KEY", key)
        os.environ["API_FOOTBALL_KEY"] = key
        self.key_entry.delete(0, "end")
        self.message.configure(text="Clé enregistrée dans .env. Lancez ACTUALISER pour charger les données.",
                               text_color=theme.POSITIVE)
        self.refresh()

    def clear_cache(self) -> None:
        with self.app.conn:
            self.app.conn.execute("DELETE FROM api_cache")
        self.message.configure(text="Cache API vidé. Les données enregistrées (matchs, analyses) sont conservées.",
                               text_color=theme.POSITIVE)
