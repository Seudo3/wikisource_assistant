This is a program for editing Wikisource using AI.

__This program is highly experimental and may not work as expected. IT MAY EDIT WIKISOURCE (or maybe Wikipedia) pages on your behalf: remember that everything it does is under YOUR responsibility.__

I intend to translate everything to English soon (or later), but in the meantime feel free to use your favorite translation software.

## Installation de l'application
- installer Python
- installer les packages nécessaires dans un environnement local situé dans un dossier `.pythonenv` :
```powershell
python -m venv .pythonenv
.pythonenv\Scripts\pip install -r requirements.txt
```

## Configuration
Obligatoire : entrer une clé d'API OpenAI dans la variable d'environnement `OPENAI_WSASSISTANT_API_KEY` ou `OPENAI_API_KEY`.

Facultatif : vous pouvez définir votre nom d'utilisateur et votre mot de passe Wikisource dans les variables d'environnement `MW_USERNAME` et `MW_PASSWORD`. Sinon, le système vous les demandera à l'exécution si vous passez l'option `--apply` afin d'envoyer le résultat sur Wikisource.

## Lancement en ligne de commande
`.\WikisourceAssistant.bat https://fr.wikisource.org/wiki/Page:xxxxxxx.djvu/nn`

Pour connaître les options disponibles :
`.\WikisourceAssistant.bat --help`

Exemples :
- pour corriger une page sans la publier :
`.\wikisource_assistant.bat https://fr.wikisource.org/wiki/Page:xxxxxxx.djvu/nn`
- pour corriger une page et publier le résultat (après confirmation) :
`.\wikisource_assistant.bat https://fr.wikisource.org/wiki/Page:xxxxxxx.djvu/nn --apply`
- pour corriger 5 pages consécutives :
`.\wikisource_assistant.bat https://fr.wikisource.org/wiki/Page:xxxxxxx.djvu/nn --count 5 --apply`
- pour corriger 5 pages en sautant une page sur deux :
`.\wikisource_assistant.bat https://fr.wikisource.org/wiki/Page:xxxxxxx.djvu/nn --count 5 --step 2 --apply`
- pour utiliser un modèle OpenAI autre que le modèle par défaut :
`.\wikisource_assistant.bat https://fr.wikisource.org/wiki/Page:xxxxxxx.djvu/nn --apply --model gpt-5.4`

## Interface graphique
Vous pouvez lancer l'interface graphique locale sous Windows avec :
`.\wikisource_assistant_gui.bat`

L'interface permet :
- de saisir l'URL Wikisource, `count`, `step`, le modèle, les instructions supplémentaires, la clé API OpenAI et les identifiants Wikisource ;
- d'analyser sans publier, ou d'analyser puis publier avec confirmation ;
- de consulter le texte actuel, la proposition, le diff et le journal d'exécution ;
- de modifier le prompt système global envoyé à OpenAI pour toutes les pages.

Les dernières valeurs saisies pour l'URL, `count`, `step`, le modèle, les instructions supplémentaires et le prompt système sont conservées dans un fichier de configuration local au profil utilisateur.

## Construire un exécutable Windows
Le dépôt contient un script de build pour produire une version distribuable de l'interface graphique sans demander à l'utilisateur final d'installer Python.

Préparation :
```powershell
python -m venv .pythonenv
.pythonenv\Scripts\pip install -r requirements.txt
.pythonenv\Scripts\pip install pyinstaller
```

Construction :
```powershell
.\build_windows_exe.ps1
```

Fichiers générés :
- `dist\WikisourceAssistant\WikisourceAssistant.exe` : exécutable Windows prêt à lancer ;
- `dist\WikisourceAssistant-windows.zip` : archive à distribuer.

La personne qui reçoit l'application doit simplement extraire l'archive puis lancer `WikisourceAssistant.exe`. La clé API OpenAI reste nécessaire via l'interface ou les variables d'environnement habituelles.

## FAQ
* Quel modèle OpenAI utiliser ?
Dans mon expérience, `gpt-5.4` est significativement meilleur que `gpt-5.4-mini` si le coût vous convient.
