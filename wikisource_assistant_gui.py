# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from wikisource_assistant import (
    DEFAULT_EDIT_SUMMARY_BY_LANG,
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    GuiConfig,
    SUPPORTED_LANGUAGES,
    SYSTEM_PROMPTS,
    WikisourceAssistant,
    call_openai_for_correction,
    ensure_openai_api_key,
    increment_page_url,
    normalize_language,
    output_path_for_page,
    tr,
    unified_diff,
)


GUI_I18N = {
    "en": {
        "window_title": "Wikisource Assistant",
        "ready": "Ready.",
        "language": "Language",
        "language_en": "English",
        "language_fr": "Français",
        "url": "Wikisource URL",
        "model": "OpenAI model",
        "summary": "MediaWiki summary",
        "api_key": "OpenAI API key",
        "username": "Wikisource username",
        "password": "Wikisource password",
        "output_file": "Output file",
        "browse": "Browse",
        "no_image": "Do not send the image",
        "minor": "Mark edit as minor",
        "bot": "Enable bot flag",
        "analyze": "Analyze",
        "analyze_publish": "Analyze and publish",
        "reset_prompt": "Reset system prompt",
        "save_config": "Save configuration",
        "help": "Help",
        "publish_page": "Publish this page",
        "stop_processing": "Stop processing",
        "tab_instructions": "Page instructions",
        "tab_system_prompt": "System prompt",
        "tab_current": "Current text",
        "tab_proposed": "Proposal",
        "tab_diff": "Diff",
        "tab_log": "Log",
        "choose_output": "Choose output file",
        "text_files": "Text files",
        "all_files": "All files",
        "config_saved": "Configuration saved.",
        "help_title": "Help - Wikisource Assistant",
        "close": "Close",
        "publish_prompt": "Review the diff or proposed text for “{page_title}”, then choose.",
        "waiting_publish": "Waiting for publish confirmation...",
        "credentials_required": "Wikisource credentials required",
        "credentials_intro": "Enter your Wikisource credentials to publish. They will be kept for this session only.",
        "missing_credentials_title": "Missing credentials",
        "missing_credentials_message": "Wikisource username and password are required to publish.",
        "cancel": "Cancel",
        "confirm": "Confirm",
        "processing_running_title": "Processing in progress",
        "processing_running_message": "An analysis is already running.",
        "invalid_values_title": "Invalid values",
        "invalid_values_message": "Count and Step must be integers.",
        "processing": "Processing...",
        "url_required": "The Wikisource URL is required.",
        "count_step_min": "Count and Step must be greater than or equal to 1.",
        "page_done": "Page {index}/{count} processed",
        "processing_interrupted": "Processing interrupted",
        "stopped_by_user": "Processing stopped by the user.",
        "processing_complete": "Processing complete.",
        "processing_failed": "Processing failed.",
        "error_title": "Error",
        "page_log": "[Page {page_index}/{total_pages}] {url}",
        "probable_language_unknown": "unknown",
        "no_image_continue": "No scan image was detected for this page. Check 'Do not send the image' if you want to continue without the scan.",
        "publish_cancelled_missing_credentials": "Publishing cancelled: missing Wikisource credentials.",
        "publish_cancelled": "Publishing cancelled.",
        "help_text": """Quick start

1. Enter a Wikisource page URL such as Page:.../number or https://fr.wikisource.org/wiki/Page:....
2. Enter the number of pages to process in Count.
3. Enter the increment between pages in Step. Use 1 for consecutive pages.
4. Enter the OpenAI API key, or define OPENAI_ASSISTANT_API_KEY or OPENAI_API_KEY in the environment.
5. Add page-specific instructions in the Page instructions tab if needed.
6. Click Analyze to generate a proposal without publishing it.
7. Click Analyze and publish to send corrections to Wikisource after page-by-page confirmation.

Main fields

Wikisource URL
Starting page to correct. For multiple pages, the application increments the page number automatically.

Count
Total number of pages to process. Minimum value: 1.

Step
Increment between pages. For example, Step=2 processes every other page.

Language
Primary interface and prompt language. English is the default; French remains available.

OpenAI model
Model used to propose the correction. Keep the default value unless you need something specific.

MediaWiki summary
Edit summary used when publishing.

Output file
Optional. If provided, analysis results can be written to this file.

Options

Do not send the image
Ask the AI to work only from the Wikisource text, without the page image.

Mark edit as minor
Publish changes with the minor-edit marker.

Enable bot flag
Publish with the bot flag if your account is allowed to use it.

Tabs

Page instructions
Additional instructions sent to the AI for this correction.

System prompt
Global prompt used to guide the AI. Reset system prompt restores the default prompt for the selected language.

Current text
Wikisource text retrieved before correction.

Proposal
Corrected text proposed by the AI.

Diff
Comparison between the current text and the proposal.

Log
Execution messages, errors, and progress.

Publishing

To publish, fill in the Wikisource username and password, or define MW_USERNAME and MW_PASSWORD in the environment. In Analyze and publish mode, the application asks for confirmation before each publication.

Configuration

Save configuration stores the latest useful values in the local user profile. The API key and password are not stored by this button.""",
    },
    "fr": {
        "window_title": "Wikisource Assistant",
        "ready": "Prêt.",
        "language": "Langue",
        "language_en": "English",
        "language_fr": "Français",
        "url": "URL Wikisource",
        "model": "Modèle OpenAI",
        "summary": "Résumé MediaWiki",
        "api_key": "Clé API OpenAI",
        "username": "Utilisateur Wikisource",
        "password": "Mot de passe Wikisource",
        "output_file": "Fichier de sortie",
        "browse": "Parcourir",
        "no_image": "Ne pas envoyer l'image",
        "minor": "Marquer l'édition comme mineure",
        "bot": "Activer le drapeau bot",
        "analyze": "Analyser",
        "analyze_publish": "Analyser et publier",
        "reset_prompt": "Réinitialiser le prompt système",
        "save_config": "Enregistrer la configuration",
        "help": "Aide",
        "publish_page": "Publier cette page",
        "stop_processing": "Arrêter le traitement",
        "tab_instructions": "Instructions page",
        "tab_system_prompt": "Prompt système",
        "tab_current": "Texte actuel",
        "tab_proposed": "Proposition",
        "tab_diff": "Diff",
        "tab_log": "Journal",
        "choose_output": "Choisir le fichier de sortie",
        "text_files": "Fichiers texte",
        "all_files": "Tous les fichiers",
        "config_saved": "Configuration enregistrée.",
        "help_title": "Aide - Wikisource Assistant",
        "close": "Fermer",
        "publish_prompt": "Vérifiez le diff ou le texte proposé pour « {page_title} », puis choisissez.",
        "waiting_publish": "En attente de confirmation de publication...",
        "credentials_required": "Identifiants Wikisource requis",
        "credentials_intro": "Renseignez vos identifiants Wikisource pour publier. Ils seront retenus pendant cette session uniquement.",
        "missing_credentials_title": "Identifiants manquants",
        "missing_credentials_message": "Le nom d'utilisateur et le mot de passe Wikisource sont obligatoires pour publier.",
        "cancel": "Annuler",
        "confirm": "Valider",
        "processing_running_title": "Traitement en cours",
        "processing_running_message": "Une analyse est déjà en cours.",
        "invalid_values_title": "Valeurs invalides",
        "invalid_values_message": "Count et Step doivent être des nombres entiers.",
        "processing": "Traitement en cours...",
        "url_required": "L'URL Wikisource est obligatoire.",
        "count_step_min": "Count et Step doivent être supérieurs ou égaux à 1.",
        "page_done": "Page {index}/{count} traitée",
        "processing_interrupted": "Traitement interrompu",
        "stopped_by_user": "Traitement arrêté par l'utilisateur.",
        "processing_complete": "Traitement terminé.",
        "processing_failed": "Échec du traitement.",
        "error_title": "Erreur",
        "page_log": "[Page {page_index}/{total_pages}] {url}",
        "probable_language_unknown": "inconnue",
        "no_image_continue": "Aucune image de fac-similé n'a été détectée pour cette page. Cochez 'Ne pas envoyer l'image' si vous voulez continuer sans scan.",
        "publish_cancelled_missing_credentials": "Publication annulée : identifiants Wikisource non renseignés.",
        "publish_cancelled": "Publication annulée.",
        "help_text": """Utilisation rapide

1. Renseignez l'URL d'une page Wikisource de type Page:.../numéro ou https://fr.wikisource.org/wiki/Page:....
2. Indiquez le nombre de pages à traiter dans Count.
3. Indiquez l'incrément entre deux pages dans Step. Utilisez 1 pour traiter les pages consécutives.
4. Renseignez la clé API OpenAI, ou définissez OPENAI_ASSISTANTA_API_KEY ou OPENAI_API_KEY dans l'environnement.
5. Ajoutez si besoin des instructions spécifiques dans l'onglet Instructions page.
6. Cliquez sur Analyser pour générer une proposition sans la publier.
7. Cliquez sur Analyser et publier pour envoyer les corrections sur Wikisource après confirmation page par page.

Champs principaux

URL Wikisource
Page de départ à corriger. Pour plusieurs pages, l'application incrémente automatiquement le numéro de page.

Count
Nombre total de pages à traiter. La valeur minimale est 1.

Step
Pas d'incrémentation entre deux pages. Par exemple, Step=2 traite une page sur deux.

Langue
Langue principale de l'interface et des prompts. L'anglais est la valeur par défaut, le français reste disponible.

Modèle OpenAI
Modèle utilisé pour proposer la correction. Gardez la valeur par défaut sauf besoin spécifique.

Résumé MediaWiki
Commentaire d'édition utilisé lors de la publication.

Fichier de sortie
Optionnel. Si renseigné, les résultats d'analyse peuvent être écrits dans ce fichier.

Options

Ne pas envoyer l'image
Demande à l'IA de travailler uniquement à partir du texte Wikisource, sans l'image de la page.

Marquer l'édition comme mineure
Publie les modifications avec le marqueur d'édition mineure.

Activer le drapeau bot
Publie avec le drapeau bot si votre compte dispose des droits nécessaires.

Onglets

Instructions page
Instructions supplémentaires envoyées à l'IA pour cette correction.

Prompt système
Prompt global utilisé pour guider l'IA. Le bouton Réinitialiser le prompt système restaure la valeur par défaut pour la langue sélectionnée.

Texte actuel
Texte Wikisource récupéré avant correction.

Proposition
Texte corrigé proposé par l'IA.

Diff
Comparaison entre le texte actuel et la proposition.

Journal
Messages d'exécution, erreurs et progression.

Publication

Pour publier, renseignez l'utilisateur et le mot de passe Wikisource, ou définissez MW_USERNAME et MW_PASSWORD dans l'environnement. En mode Analyser et publier, l'application demande confirmation avant chaque publication.

Configuration

Le bouton Enregistrer la configuration conserve les dernières valeurs utiles dans le profil utilisateur local. La clé API et le mot de passe ne sont pas enregistrés par ce bouton.""",
    },
}


class AssistantGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = GuiConfig.load()
        self.language_var = tk.StringVar(value=normalize_language(self.config.language))
        self.worker: threading.Thread | None = None
        self.publish_decision_event = threading.Event()
        self.publish_decision: str | None = None
        self.credentials_prompt_event = threading.Event()
        self.credentials_prompt_result = False
        self.pending_publish = False

        self.url_var = tk.StringVar(value=self.config.recent_url)
        self.count_var = tk.StringVar(value=str(self.config.recent_count))
        self.step_var = tk.StringVar(value=str(self.config.recent_step))
        self.model_var = tk.StringVar(value=self.config.recent_model or DEFAULT_MODEL)
        self.api_key_var = tk.StringVar(value=os.getenv("OPENAI_WSASSISTANT_API_KEY", os.getenv("OPENAI_API_KEY", "")))
        self.username_var = tk.StringVar(value=os.getenv("MW_USERNAME", ""))
        self.password_var = tk.StringVar(value=os.getenv("MW_PASSWORD", ""))
        self.summary_var = tk.StringVar(value=DEFAULT_EDIT_SUMMARY_BY_LANG[self.lang])
        self.output_var = tk.StringVar(value="")
        self.no_image_var = tk.BooleanVar(value=False)
        self.minor_var = tk.BooleanVar(value=False)
        self.bot_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value=self.gt("ready"))
        self.progress_var = tk.DoubleVar(value=0.0)
        self.publish_prompt_var = tk.StringVar(value="")

        self.label_widgets: dict[str, ttk.Label] = {}
        self.button_widgets: dict[str, ttk.Button] = {}
        self.check_widgets: dict[str, ttk.Checkbutton] = {}
        self.tab_widgets: list[tuple[ScrolledText, str]] = []

        self._build_ui()
        self._set_text(self.instructions_text, self.config.recent_instructions)
        self._set_text(self.system_prompt_text, self.config.system_prompt or SYSTEM_PROMPTS[self.lang])
        self._apply_language(initial=True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    @property
    def lang(self) -> str:
        return normalize_language(self.language_var.get())

    def gt(self, key: str, **kwargs: object) -> str:
        return GUI_I18N[self.lang][key].format(**kwargs)

    def _build_ui(self) -> None:
        self.root.geometry("1320x920")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        controls = ttk.Frame(self.root, padding=12)
        controls.grid(row=0, column=0, sticky="nsew")
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)

        self.label_widgets["language"] = ttk.Label(controls)
        self.label_widgets["language"].grid(row=0, column=0, sticky="w")
        self.language_combo = ttk.Combobox(
            controls,
            textvariable=self.language_var,
            values=list(SUPPORTED_LANGUAGES),
            width=10,
            state="readonly",
        )
        self.language_combo.grid(row=0, column=1, sticky="w", padx=(6, 12))
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        self.label_widgets["url"] = ttk.Label(controls)
        self.label_widgets["url"].grid(row=1, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.url_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=(6, 12))

        ttk.Label(controls, text="Count").grid(row=2, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.count_var, width=8).grid(row=2, column=1, sticky="w", padx=(6, 12))
        ttk.Label(controls, text="Step").grid(row=2, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.step_var, width=8).grid(row=2, column=3, sticky="w", padx=(6, 0))

        self.label_widgets["model"] = ttk.Label(controls)
        self.label_widgets["model"].grid(row=3, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.model_var).grid(row=3, column=1, sticky="ew", padx=(6, 12))
        self.label_widgets["summary"] = ttk.Label(controls)
        self.label_widgets["summary"].grid(row=3, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.summary_var).grid(row=3, column=3, sticky="ew", padx=(6, 0))

        self.label_widgets["api_key"] = ttk.Label(controls)
        self.label_widgets["api_key"].grid(row=4, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.api_key_var, show="*").grid(row=4, column=1, sticky="ew", padx=(6, 12))
        self.label_widgets["username"] = ttk.Label(controls)
        self.label_widgets["username"].grid(row=4, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.username_var).grid(row=4, column=3, sticky="ew", padx=(6, 0))

        self.label_widgets["password"] = ttk.Label(controls)
        self.label_widgets["password"].grid(row=5, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.password_var, show="*").grid(row=5, column=1, sticky="ew", padx=(6, 12))
        self.label_widgets["output_file"] = ttk.Label(controls)
        self.label_widgets["output_file"].grid(row=5, column=2, sticky="w")

        output_frame = ttk.Frame(controls)
        output_frame.grid(row=5, column=3, sticky="ew", padx=(6, 0))
        output_frame.columnconfigure(0, weight=1)
        ttk.Entry(output_frame, textvariable=self.output_var).grid(row=0, column=0, sticky="ew")
        self.button_widgets["browse"] = ttk.Button(output_frame, command=self._choose_output)
        self.button_widgets["browse"].grid(row=0, column=1, padx=(6, 0))

        toggles = ttk.Frame(controls)
        toggles.grid(row=6, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.check_widgets["no_image"] = ttk.Checkbutton(toggles, variable=self.no_image_var)
        self.check_widgets["no_image"].grid(row=0, column=0, sticky="w")
        self.check_widgets["minor"] = ttk.Checkbutton(toggles, variable=self.minor_var)
        self.check_widgets["minor"].grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.check_widgets["bot"] = ttk.Checkbutton(toggles, variable=self.bot_var)
        self.check_widgets["bot"].grid(row=0, column=2, sticky="w", padx=(12, 0))

        actions = ttk.Frame(controls)
        actions.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        self.button_widgets["analyze"] = ttk.Button(actions, command=lambda: self._start_run(False))
        self.button_widgets["analyze"].grid(row=0, column=0, padx=(0, 6))
        self.button_widgets["publish"] = ttk.Button(actions, command=lambda: self._start_run(True))
        self.button_widgets["publish"].grid(row=0, column=1, padx=(0, 6))
        self.button_widgets["reset_prompt"] = ttk.Button(actions, command=self._reset_system_prompt)
        self.button_widgets["reset_prompt"].grid(row=0, column=2, padx=(0, 6))
        self.button_widgets["save_config"] = ttk.Button(actions, command=self._save_gui_config)
        self.button_widgets["save_config"].grid(row=0, column=3, padx=(0, 6))
        self.button_widgets["help"] = ttk.Button(actions, command=self._show_help)
        self.button_widgets["help"].grid(row=0, column=4, padx=(0, 6))
        actions.columnconfigure(5, weight=1)
        ttk.Progressbar(actions, variable=self.progress_var, maximum=100).grid(row=0, column=5, sticky="ew", padx=(8, 8))
        ttk.Label(actions, textvariable=self.status_var).grid(row=0, column=6, sticky="e")

        self.publish_frame = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        self.publish_frame.grid(row=1, column=0, sticky="ew")
        self.publish_frame.columnconfigure(0, weight=1)
        ttk.Label(self.publish_frame, textvariable=self.publish_prompt_var).grid(row=0, column=0, sticky="w")
        self.button_widgets["publish_page"] = ttk.Button(self.publish_frame, command=lambda: self._resolve_publish_decision("publish"))
        self.button_widgets["publish_page"].grid(row=0, column=1, padx=(8, 6))
        self.button_widgets["stop_processing"] = ttk.Button(self.publish_frame, command=lambda: self._resolve_publish_decision("stop"))
        self.button_widgets["stop_processing"].grid(row=0, column=2)
        self._set_publish_controls_visible(False)

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.notebook = notebook

        self.instructions_text = ScrolledText(notebook, wrap="word", undo=True)
        notebook.add(self.instructions_text)
        self.tab_widgets.append((self.instructions_text, "tab_instructions"))

        self.system_prompt_text = ScrolledText(notebook, wrap="word", undo=True)
        notebook.add(self.system_prompt_text)
        self.tab_widgets.append((self.system_prompt_text, "tab_system_prompt"))

        self.current_text = ScrolledText(notebook, wrap="none")
        notebook.add(self.current_text)
        self.tab_widgets.append((self.current_text, "tab_current"))

        self.proposed_text = ScrolledText(notebook, wrap="none")
        notebook.add(self.proposed_text)
        self.tab_widgets.append((self.proposed_text, "tab_proposed"))

        self.diff_text = ScrolledText(notebook, wrap="none")
        notebook.add(self.diff_text)
        self.tab_widgets.append((self.diff_text, "tab_diff"))

        self.log_text = ScrolledText(notebook, wrap="word")
        notebook.add(self.log_text)
        self.tab_widgets.append((self.log_text, "tab_log"))

    def _apply_language(self, initial: bool = False) -> None:
        self.root.title(self.gt("window_title"))
        self.status_var.set(self.gt("ready") if initial else self.status_var.get())
        self.language_combo.configure(values=list(SUPPORTED_LANGUAGES))
        self.language_combo.set(self.lang)

        for key in ("language", "url", "model", "summary", "api_key", "username", "password", "output_file"):
            self.label_widgets[key].configure(text=self.gt(key))
        for key in ("browse", "analyze", "analyze_publish", "reset_prompt", "save_config", "help", "publish_page", "stop_processing"):
            mapped = "publish" if key == "analyze_publish" else key
            widget_key = mapped
            if key == "analyze_publish":
                self.button_widgets[widget_key].configure(text=self.gt(key))
            else:
                self.button_widgets[key].configure(text=self.gt(key))
        for key in ("no_image", "minor", "bot"):
            self.check_widgets[key].configure(text=self.gt(key))
        for widget, tab_key in self.tab_widgets:
            self.notebook.tab(widget, text=self.gt(tab_key))

    def _on_language_changed(self, _event: object = None) -> None:
        new_lang = normalize_language(self.language_combo.get())
        previous_lang = self.config.language or DEFAULT_LANGUAGE
        self.language_var.set(new_lang)
        if self.summary_var.get().strip() in DEFAULT_EDIT_SUMMARY_BY_LANG.values():
            self.summary_var.set(DEFAULT_EDIT_SUMMARY_BY_LANG[new_lang])
        if self._get_text_value(self.system_prompt_text).strip() in {prompt.strip() for prompt in SYSTEM_PROMPTS.values()}:
            self._set_text(self.system_prompt_text, SYSTEM_PROMPTS[new_lang])
        self.config.language = new_lang
        self._apply_language()
        if self.status_var.get() in {GUI_I18N["en"]["ready"], GUI_I18N["fr"]["ready"], GUI_I18N["en"]["config_saved"], GUI_I18N["fr"]["config_saved"]}:
            self.status_var.set(self.gt("ready") if previous_lang != new_lang else self.status_var.get())

    def _choose_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title=self.gt("choose_output"),
            defaultextension=".txt",
            filetypes=[(self.gt("text_files"), "*.txt"), (self.gt("all_files"), "*.*")],
        )
        if path:
            self.output_var.set(path)

    def _set_text(self, widget: ScrolledText, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value)

    def _append_log(self, message: str) -> None:
        self.root.after(0, lambda: (self.log_text.insert("end", message + "\n"), self.log_text.see("end")))

    def _update_text_panels(self, current: str, proposed: str, diff: str) -> None:
        def callback() -> None:
            self._set_text(self.current_text, current)
            self._set_text(self.proposed_text, proposed)
            self._set_text(self.diff_text, diff)

        self.root.after(0, callback)

    def _set_status(self, text: str, progress: float | None = None, running: bool | None = None) -> None:
        def callback() -> None:
            self.status_var.set(text)
            if progress is not None:
                self.progress_var.set(progress)
            if running is not None:
                state = "disabled" if running else "normal"
                self.button_widgets["analyze"].configure(state=state)
                self.button_widgets["publish"].configure(state=state)

        self.root.after(0, callback)

    def _get_text_value(self, widget: ScrolledText) -> str:
        return widget.get("1.0", "end-1c")

    def _save_gui_config(self) -> None:
        self.config.recent_url = self.url_var.get().strip()
        self.config.recent_count = max(1, int(self.count_var.get() or "1"))
        self.config.recent_step = max(1, int(self.step_var.get() or "1"))
        self.config.recent_model = self.model_var.get().strip() or DEFAULT_MODEL
        self.config.recent_instructions = self._get_text_value(self.instructions_text)
        self.config.system_prompt = self._get_text_value(self.system_prompt_text) or SYSTEM_PROMPTS[self.lang]
        self.config.language = self.lang
        self.config.save()
        self.status_var.set(self.gt("config_saved"))

    def _reset_system_prompt(self) -> None:
        self._set_text(self.system_prompt_text, SYSTEM_PROMPTS[self.lang])

    def _show_help(self) -> None:
        help_window = tk.Toplevel(self.root)
        help_window.title(self.gt("help_title"))
        help_window.geometry("820x680")
        help_window.transient(self.root)
        help_window.columnconfigure(0, weight=1)
        help_window.rowconfigure(0, weight=1)

        text = ScrolledText(help_window, wrap="word", padx=12, pady=12)
        text.grid(row=0, column=0, sticky="nsew")
        text.insert("1.0", self.gt("help_text"))
        text.configure(state="disabled")

        buttons = ttk.Frame(help_window, padding=(12, 8, 12, 12))
        buttons.grid(row=1, column=0, sticky="e")
        ttk.Button(buttons, text=self.gt("close"), command=help_window.destroy).grid(row=0, column=0)

    def _show_error(self, title: str, message: str) -> None:
        self.root.after(0, lambda: messagebox.showerror(title, message, parent=self.root))

    def _set_publish_controls_visible(self, visible: bool, prompt: str = "") -> None:
        def callback() -> None:
            self.pending_publish = visible
            self.publish_prompt_var.set(prompt)
            if visible:
                self.button_widgets["publish_page"].configure(state="normal")
                self.button_widgets["stop_processing"].configure(state="normal")
                self.publish_frame.grid()
            else:
                self.publish_frame.grid_remove()

        self.root.after(0, callback)

    def _resolve_publish_decision(self, decision: str) -> None:
        if not self.pending_publish:
            return
        self.publish_decision = decision
        self.publish_decision_event.set()
        self._set_publish_controls_visible(False)

    def _await_publish_decision(self, page_title: str) -> bool:
        self.publish_decision = None
        self.publish_decision_event.clear()
        self._set_publish_controls_visible(True, self.gt("publish_prompt", page_title=page_title))
        self._set_status(self.gt("waiting_publish"))
        self.publish_decision_event.wait()
        return self.publish_decision == "publish"

    def _prompt_for_missing_credentials(self) -> bool:
        self.credentials_prompt_result = False
        self.credentials_prompt_event.clear()

        def callback() -> None:
            dialog = tk.Toplevel(self.root)
            dialog.title(self.gt("credentials_required"))
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.resizable(False, False)

            frame = ttk.Frame(dialog, padding=12)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(1, weight=1)

            ttk.Label(frame, text=self.gt("credentials_intro"), wraplength=380, justify="left").grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
            )

            username_var = tk.StringVar(value=self.username_var.get().strip())
            password_var = tk.StringVar(value=self.password_var.get())
            ttk.Label(frame, text=self.gt("username")).grid(row=1, column=0, sticky="w")
            username_entry = ttk.Entry(frame, textvariable=username_var, width=42)
            username_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))
            ttk.Label(frame, text=self.gt("password")).grid(row=2, column=0, sticky="w")
            password_entry = ttk.Entry(frame, textvariable=password_var, show="*", width=42)
            password_entry.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

            buttons = ttk.Frame(frame)
            buttons.grid(row=3, column=0, columnspan=2, sticky="e")

            def finish(result: bool) -> None:
                if result:
                    username = username_var.get().strip()
                    password = password_var.get()
                    if not username or not password:
                        messagebox.showerror(self.gt("missing_credentials_title"), self.gt("missing_credentials_message"), parent=dialog)
                        return
                    self.username_var.set(username)
                    self.password_var.set(password)
                    self.credentials_prompt_result = True
                dialog.destroy()
                self.credentials_prompt_event.set()

            ttk.Button(buttons, text=self.gt("cancel"), command=lambda: finish(False)).grid(row=0, column=0, padx=(0, 6))
            ttk.Button(buttons, text=self.gt("confirm"), command=lambda: finish(True)).grid(row=0, column=1)

            dialog.protocol("WM_DELETE_WINDOW", lambda: finish(False))
            username_entry.focus_set()

        self.root.after(0, callback)
        self.credentials_prompt_event.wait()
        return self.credentials_prompt_result

    def _start_run(self, apply_changes: bool) -> None:
        if self.worker and self.worker.is_alive():
            self._show_error(self.gt("processing_running_title"), self.gt("processing_running_message"))
            return
        try:
            count = max(1, int(self.count_var.get().strip() or "1"))
            step = max(1, int(self.step_var.get().strip() or "1"))
        except ValueError:
            self._show_error(self.gt("invalid_values_title"), self.gt("invalid_values_message"))
            return

        self._save_gui_config()
        self._set_text(self.log_text, "")
        self._set_publish_controls_visible(False)
        self._set_status(self.gt("processing"), progress=0, running=True)

        args = {
            "url": self.url_var.get().strip(),
            "count": count,
            "step": step,
            "model": self.model_var.get().strip() or DEFAULT_MODEL,
            "api_key": self.api_key_var.get().strip(),
            "username": self.username_var.get().strip(),
            "password": self.password_var.get(),
            "summary": self.summary_var.get().strip() or DEFAULT_EDIT_SUMMARY_BY_LANG[self.lang],
            "save_output": self.output_var.get().strip(),
            "extra_instructions": self._get_text_value(self.instructions_text).strip(),
            "system_prompt": self._get_text_value(self.system_prompt_text).strip() or SYSTEM_PROMPTS[self.lang],
            "no_image": self.no_image_var.get(),
            "minor": self.minor_var.get(),
            "bot": self.bot_var.get(),
            "apply": apply_changes,
            "lang": self.lang,
        }

        self.worker = threading.Thread(target=self._run_worker, args=(args,), daemon=True)
        self.worker.start()

    def _run_worker(self, args: dict[str, object]) -> None:
        lang = normalize_language(str(args["lang"]))
        try:
            if not args["url"]:
                raise ValueError(GUI_I18N[lang]["url_required"])
            ensure_openai_api_key(str(args["api_key"]) or None)
            count = int(args["count"])
            step = int(args["step"])
            if count < 1 or step < 1:
                raise ValueError(GUI_I18N[lang]["count_step_min"])

            assistant = WikisourceAssistant(
                user_agent=os.getenv("MW_USER_AGENT", "WikisourceAssistant/1.0 (personal script; contact via user talk page)")
            )
            cancelled_by_user = False
            for index in range(count):
                page_url = increment_page_url(str(args["url"]), index * step)
                result = self._process_page(assistant, page_url, index, count, args)
                progress = ((index + 1) / count) * 100
                self._set_status(
                    GUI_I18N[lang]["page_done"].format(index=index + 1, count=count) if result else GUI_I18N[lang]["processing_interrupted"],
                    progress=progress,
                )
                if not result:
                    cancelled_by_user = True
                    break

            self._set_publish_controls_visible(False)
            self._set_status(
                GUI_I18N[lang]["stopped_by_user"] if cancelled_by_user else GUI_I18N[lang]["processing_complete"],
                progress=100,
                running=False,
            )
        except Exception as exc:
            self._set_publish_controls_visible(False)
            self._append_log(f"{GUI_I18N[lang]['error_title']}: {exc}")
            self._show_error(GUI_I18N[lang]["error_title"], str(exc))
            self._set_status(GUI_I18N[lang]["processing_failed"], running=False)

    def _process_page(
        self,
        assistant: WikisourceAssistant,
        page_url: str,
        page_index: int,
        total_pages: int,
        args: dict[str, object],
    ) -> bool:
        lang = normalize_language(str(args["lang"]))
        page = assistant.get_page_data(page_url)
        self._append_log(self.gt("page_log", page_index=page_index + 1, total_pages=total_pages, url=page.canonical_url))
        self._append_log(tr("mw_title", lang, value=page.page_title))
        self._append_log(tr("current_revision", lang, value=page.revision_id))
        self._append_log(tr("probable_language", lang, value=page.language_hint or GUI_I18N[lang]["probable_language_unknown"]))
        self._append_log(tr("detected_image", lang, value=page.image_url or ("none" if lang == "en" else "aucune")))
        self._append_log("")

        if not page.image_url and not bool(args["no_image"]):
            raise RuntimeError(GUI_I18N[lang]["no_image_continue"])

        corrected = call_openai_for_correction(
            page=page,
            model=str(args["model"]),
            extra_instructions=str(args["extra_instructions"]) or None,
            image_url=None if bool(args["no_image"]) else page.image_url,
            system_prompt=str(args["system_prompt"]),
            prompt_language=lang,
        )
        diff = unified_diff(page.current_wikitext, corrected, page.page_title)
        self._update_text_panels(page.current_wikitext, corrected, diff)

        save_output = str(args["save_output"])
        if save_output:
            output_path = output_path_for_page(save_output, page_index, total_pages > 1)
            with open(output_path, "w", encoding="utf-8", newline="") as handle:
                handle.write(corrected)
            self._append_log(tr("proposal_saved", lang, path=output_path))

        if corrected == page.current_wikitext:
            self._append_log(tr("no_difference", lang))
            return True

        self._append_log("=" * 80)
        self._append_log(tr("proposed_diff", lang))
        self._append_log("=" * 80)
        self._append_log(diff if diff.strip() else tr("empty_but_different_diff", lang))
        self._append_log("=" * 80)

        if not bool(args["apply"]):
            return True

        username = str(args["username"]).strip()
        password = str(args["password"])
        if not username or not password:
            self._set_status(self.gt("credentials_required"))
            if not self._prompt_for_missing_credentials():
                self._append_log(GUI_I18N[lang]["publish_cancelled_missing_credentials"])
                return False
            username = self.username_var.get().strip()
            password = self.password_var.get()
            args["username"] = username
            args["password"] = password

        if not self._await_publish_decision(page.page_title):
            self._append_log(GUI_I18N[lang]["publish_cancelled"])
            return False

        assistant.login(page.api_endpoint, username, password)
        csrf = assistant.get_csrf_token(page.api_endpoint)
        result = assistant.edit_page(
            page=page,
            new_text=corrected,
            summary=str(args["summary"]),
            csrf_token=csrf,
            minor=bool(args["minor"]),
            bot=bool(args["bot"]),
        )
        edit_info = result.get("edit", {})
        if edit_info.get("result") != "Success":
            raise RuntimeError(json.dumps(result, ensure_ascii=False, indent=2))

        self._append_log(tr("publish_success", lang))
        self._append_log(json.dumps(edit_info, ensure_ascii=False, indent=2))
        return True

    def _on_close(self) -> None:
        try:
            self._save_gui_config()
        except Exception:
            pass
        if self.pending_publish:
            self.publish_decision = "stop"
            self.publish_decision_event.set()
        self.credentials_prompt_result = False
        self.credentials_prompt_event.set()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    AssistantGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
