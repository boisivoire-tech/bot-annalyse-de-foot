"""Composants réutilisables : cartes, tableaux, et structure commune des pages."""
import customtkinter as ctk

from interface import theme


class Card(ctk.CTkFrame):
    """Carte arrondie avec un titre optionnel."""

    def __init__(self, master, title: str | None = None, **kwargs):
        super().__init__(master, fg_color=theme.CARD, border_color=theme.CARD_BORDER,
                         border_width=1, corner_radius=theme.CORNER_RADIUS, **kwargs)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=18, pady=16)
        if title:
            ctk.CTkLabel(self.body, text=title, font=theme.font(15, "bold"),
                         text_color=theme.TEXT, anchor="w").pack(fill="x", pady=(0, 10))


class StatCard(Card):
    """Indicateur : libellé, valeur et couleur."""

    def __init__(self, master, label: str, value: str = "—", color: str = theme.TEXT, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self.body, text=label, font=theme.font(12),
                     text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x")
        self.value_label = ctk.CTkLabel(self.body, text=value, font=theme.font(24, "bold"),
                                        text_color=color, anchor="w")
        self.value_label.pack(fill="x", pady=(6, 0))

    def set_value(self, value: str, color: str | None = None) -> None:
        self.value_label.configure(text=value)
        if color:
            self.value_label.configure(text_color=color)


class Table(ctk.CTkFrame):
    """Tableau simple et défilable par la page parente.

    Une cellule peut être :
    - un texte ;
    - un tuple (texte, couleur) ;
    - un dictionnaire {"button": texte, "command": fonction} pour un bouton d'action.
    """

    def __init__(self, master, headers: list[str], empty_text: str = "Aucune donnée à afficher.", **kwargs):
        super().__init__(master, fg_color=theme.CARD, border_color=theme.CARD_BORDER, border_width=1,
                         corner_radius=theme.CORNER_RADIUS, **kwargs)
        self.headers = headers
        self.empty_text = empty_text
        self._widgets: list = []
        for i in range(len(headers)):
            self.grid_columnconfigure(i, weight=1)
        for i, header in enumerate(headers):
            label = ctk.CTkLabel(self, text=header, font=theme.font(12, "bold"),
                                 text_color=theme.TEXT_MUTED, anchor="w")
            label.grid(row=0, column=i, sticky="ew", padx=10, pady=(10, 4))
            self._widgets.append(label)

    def set_rows(self, rows: list[list]) -> None:
        for widget in self._widgets[len(self.headers):]:
            widget.destroy()
        self._widgets = self._widgets[:len(self.headers)]
        if not rows:
            label = ctk.CTkLabel(self, text=self.empty_text, text_color=theme.TEXT_MUTED, anchor="w")
            label.grid(row=1, column=0, columnspan=len(self.headers), sticky="ew", padx=10, pady=10)
            self._widgets.append(label)
            return
        for r, row in enumerate(rows, start=1):
            for c, cell in enumerate(row):
                widget = self._make_cell(cell)
                widget.grid(row=r, column=c, sticky="ew", padx=10, pady=4)
                self._widgets.append(widget)

    def _make_cell(self, cell):
        if isinstance(cell, dict):
            return ctk.CTkButton(self, text=cell["button"], command=cell["command"], height=28,
                                 corner_radius=8, font=theme.font(12), fg_color=theme.ACCENT,
                                 hover_color=theme.ACCENT_HOVER)
        text, color = cell if isinstance(cell, tuple) else (cell, theme.TEXT)
        return ctk.CTkLabel(self, text=str(text), font=theme.font(12), text_color=color,
                            anchor="w", justify="left", wraplength=260)


class BasePage(ctk.CTkFrame):
    """Structure commune : titre, sous-titre et zone de contenu défilable."""

    title_text = "Page"
    subtitle_text = ""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text=self.title_text, font=theme.font(24, "bold"),
                     text_color=theme.TEXT, anchor="w").pack(fill="x")
        if self.subtitle_text:
            ctk.CTkLabel(header, text=self.subtitle_text, font=theme.font(13),
                         text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x", pady=(2, 0))

        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.content.grid_columnconfigure(0, weight=1)
        self.build()
        self.refresh()

    def build(self) -> None:
        """À surcharger : création des widgets."""

    def refresh(self) -> None:
        """À surcharger : relecture des données depuis la base."""
