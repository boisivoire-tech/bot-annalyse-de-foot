"""Composants réutilisables : cartes arrondies et pages de base."""
import customtkinter as ctk

from interface import theme


class Card(ctk.CTkFrame):
    """Carte arrondie avec un titre optionnel."""

    def __init__(self, master, title: str | None = None, **kwargs):
        super().__init__(
            master,
            fg_color=theme.CARD,
            border_color=theme.CARD_BORDER,
            border_width=1,
            corner_radius=theme.CORNER_RADIUS,
            **kwargs,
        )
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=18, pady=16)
        if title:
            ctk.CTkLabel(
                self.body, text=title, font=theme.font(15, "bold"),
                text_color=theme.TEXT, anchor="w",
            ).pack(fill="x", pady=(0, 10))


class StatCard(Card):
    """Carte d'indicateur : un libellé, une valeur, et une couleur optionnelle."""

    def __init__(self, master, label: str, value: str = "—", color: str = theme.TEXT, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self.body, text=label, font=theme.font(12),
                     text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x")
        self.value_label = ctk.CTkLabel(self.body, text=value, font=theme.font(26, "bold"),
                                        text_color=color, anchor="w")
        self.value_label.pack(fill="x", pady=(6, 0))


class BasePage(ctk.CTkFrame):
    """Structure commune à toutes les pages : titre, sous-titre et zone de contenu défilable."""

    title_text = "Page"
    subtitle_text = ""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text=self.title_text, font=theme.font(24, "bold"),
                     text_color=theme.TEXT, anchor="w").pack(fill="x")
        if self.subtitle_text:
            ctk.CTkLabel(header, text=self.subtitle_text, font=theme.font(13),
                         text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x", pady=(2, 0))

        # Zone de contenu : défilable pour s'adapter aux petites résolutions
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.content.grid_columnconfigure((0, 1), weight=1)

        self.build()

    def build(self) -> None:
        """À surcharger dans chaque page."""

    def add_placeholder(self, phase: str, features: list[str]) -> None:
        """Affiche une carte 'module en construction' listant les fonctions prévues."""
        card = Card(self.content, title=f"Module en préparation — {phase}")
        card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        for feature in features:
            ctk.CTkLabel(card.body, text=f"•  {feature}", font=theme.font(13),
                         text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x", pady=2)
