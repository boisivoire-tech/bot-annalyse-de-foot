# bot-annalyse-de-foot

## Lancer l'application (Windows)

```powershell
cd C:\chemin\vers\bot-annalyse-de-foot
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Votre clé API se place dans un fichier `.env` (copie de `.env.example`). Ne publiez jamais ce fichier.


## Utilisation rapide

1. Copiez `.env.example` en `.env` et collez votre clé API-Football (voir Paramètres dans l'application).
2. Cliquez sur **ACTUALISER** : les matchs, historiques, classements et résultats sont chargés (connexion Internet requise).
3. Choisissez un match dans **Matchs du jour**, **Matchs à venir** ou **Analyse des matchs**.
4. Les analyses sont enregistrées avant le coup d'envoi et verrouillées ensuite. Les résultats sont évalués dans **Performance du modèle**.

Les heures sont affichées en UTC (Abidjan et Reykjavik sont à UTC+0).
Les probabilités sont des estimations statistiques, jamais des certitudes.

## Tests

```powershell
python -m unittest discover -s tests -t . -v
```

## Créer l'exécutable Windows

Dans PowerShell, à la racine du projet :

```powershell
.\build_exe.bat
```

Le fichier produit est `dist\FootballIntelligencePro\FootballIntelligencePro.exe`. Copiez `.env` dans le même dossier.
