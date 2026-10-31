"""Couleurs, polices et dimensions de FOOTBALL INTELLIGENCE PRO.

Tout le style visuel est centralisé ici : pour changer une couleur, un seul fichier à modifier.
"""
import customtkinter as ctk

# Fond et surfaces (noir bleuté, bleu foncé)
BG = "#0A1020"            # fond général
SIDEBAR = "#0D1729"       # menu latéral
CARD = "#142039"          # cartes
CARD_BORDER = "#1F2F4D"   # bordure discrète des cartes
ACCENT = "#1E4D8C"        # bleu foncé (boutons, sélection)
ACCENT_HOVER = "#2A62AD"

# Texte
TEXT = "#E6EDF7"
TEXT_MUTED = "#8FA3BF"

# Indicateurs
POSITIVE = "#22C55E"      # vert : indicateurs positifs
NEGATIVE = "#EF4444"      # rouge : indicateurs négatifs
WARNING = "#F59E0B"       # orange : avertissements (données limitées, hors ligne)

# Dimensions
CORNER_RADIUS = 14
SIDEBAR_WIDTH = 230
FONT_FAMILY = "Segoe UI"  # police Windows native ; Tkinter utilise une police de remplacement si absente


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    """Crée une police CustomTkinter avec la famille du thème."""
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)
