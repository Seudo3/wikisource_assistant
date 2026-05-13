# -*- coding: utf-8 -*-

"""
Correction assistant for Wikisource / MediaWiki ProofreadPage pages.

Workflow:
1. Fetch a Wikisource page, ideally a `Page:...` URL.
2. Read the current wikitext through the Action API.
3. Try to fetch the scan image displayed on the page.
4. Call OpenAI to produce a strict correction proposal aligned with the scan.
5. Display a unified diff.
6. Optionally save the correction through the MediaWiki Action API after confirmation.

Requirements:
    pip install requests beautifulsoup4 openai

Expected environment variables:
    OPENAI_WSASSISTANT_API_KEY or OPENAI_API_KEY
    MW_USERNAME            (interactive prompt fallback when available)
    MW_PASSWORD            (interactive prompt fallback when available)

Examples:
    python wikisource_assistant.py "https://fr.wikisource.org/wiki/Page:MonLivre.djvu/12" --dry-run
    python wikisource_assistant.py "https://fr.wikisource.org/wiki/Page:MonLivre.djvu/12" --apply
    python wikisource_assistant.py "https://fr.wikisource.org/wiki/Page:MonLivre.djvu/12" --count 5 --apply
"""

from __future__ import annotations

import argparse
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
import difflib
import getpass
import json
import logging
from openai import OpenAI
import os
from pathlib import Path
import re
import requests
import sys
import textwrap
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse

# Sometimes required for SSL access.
# Use it when installed, but keep it optional.
try:
    import truststore
except ImportError:
    truststore = None

if truststore is not None:
    try:
        truststore.inject_into_ssl()
    except Exception:
        pass

# #####################################
# CONFIGURATION

DEFAULT_MODEL = "gpt-5.4-mini"
REQUEST_TIMEOUT = 45
MAX_RETRIES_429 = 4
INITIAL_RETRY_DELAY_SECONDS = 2.0
STATUS_CANCELLED_BY_USER = 10
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "fr")
DEFAULT_EDIT_SUMMARY_BY_LANG = {
    "en": "AI-assisted transcription with [[Utilisateur:Seudo/WikisourceAI_v1|Wikisource AI Assistant]]",
    "fr": "Transcription assistée avec [[Utilisateur:Seudo/WikisourceAI|Wikisource AI Assistant]]",
}
DEFAULT_EDIT_SUMMARY = DEFAULT_EDIT_SUMMARY_BY_LANG[DEFAULT_LANGUAGE]
GUI_CONFIG_PATH = Path.home() / ".wikisource_assistant_gui.json"

# Prompt sent with every request. It should contain generic instructions
# suited to most Wikisource correction tasks. Use --instructions to add
# more page-specific guidance.
SYSTEM_PROMPTS = {
    "en": """
You are transcribing a Wikisource page from a scan.

Mandatory rules:
- Produce the full text to enter from the image, not from the current wikitext.
- Preserve meaning, historical spelling, and punctuation exactly. Do not modernize anything.
- Unless the user says otherwise, apply French typography as follows:
  use a space before a semicolon, exclamation mark, or question mark, and no space before a comma or period.
- Use the current wikitext only as a secondary reference to preserve wiki markup, templates, tags,
  categories, noinclude/includeonly sections, meaningful spacing, and line breaks that are not readable in the image.
- Do not paraphrase.
- If text in the image is uncertain, do not guess. Write [illisible] instead.
- Reproduce paragraph breaks faithfully. In particular, pay attention when sentence-ending punctuation
  appears at the end of a line and the next line starts with an indent, which often indicates a new paragraph.
- If a word is split across two lines in the scan because of a trailing hyphen, join it back without the hyphen.
- If a few words are in English or another language, wrap them with the {{lang}} template,
  for example: {{lang|en|a few words in English}}.
- Wrap small caps with the {{sc}} template, for example: {{sc|Words in small caps}}.
- If a line is centered, use {{c|LINE TEXT}}. If it is printed in a larger font, use
  {{c|LINE TEXT|fs=XXX%}} where XXX is the percentage size.
- If the visible text in the image contradicts the current wikitext, follow the image.
- If a passage remains ambiguous in the image, you may use the current wikitext as a clue, but do not invent text. If you are uncertain, write [unreadable].
- Reply STRICTLY with the complete final wikitext to put in the edit box, with no comments,
  no Markdown fences, and no explanation.
- The page is probably in French, although some passages may be in other languages.
""",
    "fr": """
Vous transcrivez une page Wikisource à partir d'un fac-similé.

Règles impératives :
- Produire l'intégralité du texte à saisir à partir de l'image, pas à partir du wikitexte actuel.
- Respecter strictement le sens, l'orthographe historique et la ponctuation. Ne modernisez rien.
- Toutefois, sauf instruction différente de l'utilisateur, respectez les règles suivantes :
  espace avant un point-virgule, un point d'exclamation ou un point d'interrogation ; pas d'espace avant une virgule ou un point.
- Utiliser le wikitexte actuel uniquement comme référence secondaire pour préserver un éventuel balisage wiki,
  des modèles, des balises, des catégories, des éléments noinclude/includeonly, des espaces significatifs
  et des sauts de ligne qui ne sont pas lisibles sur l'image.
- Ne pas reformuler.
- Reproduire fidèlement les changements de paragraphes : faire attention notamment
    lorsqu'une ponctuation de fin de phrase apparaît en fin de ligne et qu'il y a un 
    retrait au début de la ligne suivante, ce qui indique souvent un nouveau paragraphe.
- Si un mot est coupé entre deux lignes sur le fac-similé (c'est-à-dire si une ligne
    se termine par un trait d'union), vous devez le recoller sans trait d'union.
- S'il y a quelques mots en anglais ou dans une langue autre que le français, entourez ces mots
    avec le modèle {{{{lang}}}}, par exemple : {{{{lang|en|a few words in english}}}}.
- Entourez les mots en petites capitales avec le modèle {{{{sc}}}}. Exemple : 
    {{{{sc|Ici des mots en small-caps}}}}.
- Si une ligne est centrée, insérer {{{{c|TEXTE DE LA LIGNE}}}} ; si elle est écrit en caractère plus grand
    que la normale, insérer {{{{c|TEXTE DE LA LIGNE|fs=XXX%}}}} où XXX est la taille en pourcentage.
- Si le texte visible sur l'image contredit le wikitexte actuel, suivre l'image.
- Si un passage reste ambigu sur l'image, vous pouvez vous aider du wikitexte actuel comme indice, mais sans inventer. Si vous êtes incertain, indiquez [illisible].
- Répondre STRICTEMENT par l'intégralité du wikitexte final à mettre dans le champ de saisie,
  sans commentaire, sans balises Markdown, sans explication.
- La langue probable de la page est le français. Il est possible, toutefois, que certains passages de la page soient dans d'autres langues.
""",
}
SYSTEM_PROMPT = SYSTEM_PROMPTS[DEFAULT_LANGUAGE]

USER_PROMPT_TEMPLATES = {
    "en": """
    Page title: {page_title}
    URL: {url}

    Current wikitext, provided only as a secondary reference:
    ----- BEGIN WIKITEXT -----
    {current_wikitext}
    ----- END WIKITEXT -----

    Transcribe the content visible in the image and produce the final wikitext to place in the edit field.
    """,
    "fr": """
    Titre de la page : {page_title}
    URL : {url}

    Wikitexte actuel, fourni seulement comme référence secondaire :
    ----- DEBUT WIKITEXTE -----
    {current_wikitext}
    ----- FIN WIKITEXTE -----

    Transcrivez le contenu visible sur l'image et produisez le wikitexte final à placer dans le champ de saisie.
    """,
}

I18N = {
    "en": {
        "openai_quota": "OpenAI rejected the request with HTTP 429: API quota or credit is insufficient. Check billing and account limits.",
        "openai_rate_limit": "OpenAI returned HTTP 429: too many requests or a temporary limit was reached. The program already retried automatically.",
        "server_rate_limit": "{service_name} returned HTTP 429: temporary server-side throttling. The program already retried automatically.",
        "mw_retry": "MediaWiki returned 429, retrying in {delay:.1f} s ({attempt}/{max_retries}).",
        "openai_retry": "OpenAI returned 429, retrying in {delay:.1f} s ({attempt}/{max_retries}).",
        "persistent_mw_429": "Persistent MediaWiki 429 error.",
        "url_scheme_required": "The URL must include http:// or https://",
        "cannot_extract_title": "Could not extract the title from the URL. Use a URL like https://fr.wikisource.org/wiki/Page:... or https://fr.wikisource.org/w/index.php?title=Page:...",
        "no_pages_found": "No page found through the MediaWiki API.",
        "no_revision_found": "The page exists but no revision was found.",
        "mw_login_failed": "MediaWiki login failed: {details}",
        "user_prompt_extra": "Additional user instructions:\n{instructions}",
        "openai_empty_response": "The model response is empty.",
        "diff_current": "{title} (current)",
        "diff_proposed": "{title} (proposed)",
        "yes_no_suffix_default_no": "[y/N]",
        "yes_no_suffix_default_yes": "[Y/n]",
        "mediawiki_username_prompt": "MediaWiki username: ",
        "mediawiki_password_prompt": "MediaWiki password: ",
        "invalid_page_number": "The resulting page number is invalid.",
        "multi_page_url_required": "The URL must end with a page number to process multiple consecutive pages.",
        "missing_openai_key": "The OPENAI_API_KEY environment variable is not set.",
        "invalid_count": "--count must be greater than or equal to 1.",
        "invalid_step": "--step must be greater than or equal to 1.",
        "page_fetch_error": "Error while fetching the page: {error}",
        "page_progress": "[Page {page_index}/{total_pages}] {url}",
        "mw_title": "MediaWiki title   : {value}",
        "current_revision": "Current revision  : {value}",
        "probable_language": "Probable language : {value}",
        "detected_image": "Detected image    : {value}",
        "no_scan_error": "Error: no scan image was detected for this page. Transcription from the image cannot be performed.",
        "analyzing_scan": "Calling {model} to analyze the scan of {page_title}...",
        "openai_duration": "OpenAI call duration: {seconds:.2f} s",
        "openai_call_error": "Error during OpenAI call: {error}",
        "proposal_saved": "Proposal saved to: {path}",
        "no_difference": "No difference detected between the current text and the proposal.",
        "proposed_diff": "PROPOSED DIFF",
        "empty_but_different_diff": "(empty diff but different text)",
        "finish_use_apply": "Done: use --apply to allow saving to the wiki.",
        "publish_missing_credentials": "Error: to publish, set MW_USERNAME and MW_PASSWORD",
        "publish_missing_password": "Error: MediaWiki password not found. Set MW_PASSWORD or run the program interactively to enter it.",
        "publish_question": "Publish this correction to the wiki ({page_title})?",
        "publish_cancelled": "Publishing cancelled.",
        "publish_error": "Error while publishing: {error}",
        "publish_success": "Edit saved successfully.",
        "unexpected_edit_response": "Unexpected response from the edit API:",
        "argparse_description": "Transcribe a Wikisource page from its scan with OpenAI, then optionally save it through the MediaWiki API.",
        "argparse_url": "Full URL of the Wikisource page to transcribe",
        "argparse_count": "Number of pages to process by incrementing the final page number in the URL (default: 1)",
        "argparse_step": "Step between processed pages (default: 1 = consecutive pages)",
        "argparse_model": "OpenAI model to use (default: {model})",
        "argparse_summary": "MediaWiki edit summary",
        "argparse_instructions": "Additional instructions to pass to the model",
        "argparse_dry_run": "Only display the proposed transcription and diff, without allowing automatic editing",
        "argparse_apply": "After showing the diff, offer to save the modification to the wiki",
        "argparse_minor": "Mark the edit as minor",
        "argparse_bot": "Add the bot flag if the account is allowed to use it",
        "argparse_no_image": "Do not send the scan image to the model even if it is detected",
        "argparse_save_output": "File path where the proposed wikitext should be saved",
        "argparse_verbose": "Show debug messages (timings, API details, ...)",
        "argparse_lang": "Interface and prompt language (`en` or `fr`)",
        "main_missing_key": "Error: the OPENAI_API_KEY environment variable is not set.",
        "main_invalid_count": "Error: --count must be greater than or equal to 1.",
        "main_invalid_step": "Error: --step must be greater than or equal to 1.",
        "generic_error": "Error: {error}",
        "user_cancelled_processing": "Processing stopped at the user's request.",
    },
    "fr": {
        "openai_quota": "OpenAI a refusé la requête avec une erreur 429 : quota ou crédit API insuffisant. Vérifiez la facturation et les limites du compte utilisé.",
        "openai_rate_limit": "OpenAI a renvoyé une erreur 429 : trop de requêtes ou limite temporaire atteinte. Le programme a déjà réessayé automatiquement.",
        "server_rate_limit": "{service_name} a renvoyé une erreur 429 : limitation temporaire côté serveur. Le programme a déjà réessayé automatiquement.",
        "mw_retry": "MediaWiki a répondu 429, nouvelle tentative dans {delay:.1f} s ({attempt}/{max_retries}).",
        "openai_retry": "OpenAI a répondu 429, nouvelle tentative dans {delay:.1f} s ({attempt}/{max_retries}).",
        "persistent_mw_429": "Erreur 429 MediaWiki persistante.",
        "url_scheme_required": "L'URL doit inclure http:// ou https://",
        "cannot_extract_title": "Impossible d'extraire le titre depuis l'URL. Utilisez une URL de type https://fr.wikisource.org/wiki/Page:... ou https://fr.wikisource.org/w/index.php?title=Page:...",
        "no_pages_found": "Aucune page trouvée via l'API MediaWiki.",
        "no_revision_found": "La page existe mais aucune révision n'a été trouvée.",
        "mw_login_failed": "Échec de connexion MediaWiki : {details}",
        "user_prompt_extra": "Instructions supplémentaires de l'utilisateur :\n{instructions}",
        "openai_empty_response": "La réponse du modèle est vide.",
        "diff_current": "{title} (actuel)",
        "diff_proposed": "{title} (proposé)",
        "yes_no_suffix_default_no": "[o/N]",
        "yes_no_suffix_default_yes": "[O/n]",
        "mediawiki_username_prompt": "Nom d'utilisateur MediaWiki : ",
        "mediawiki_password_prompt": "Mot de passe MediaWiki : ",
        "invalid_page_number": "Le numéro de page résultant est invalide.",
        "multi_page_url_required": "L'URL doit se terminer par un numéro de page pour utiliser plusieurs pages consécutives.",
        "missing_openai_key": "La variable d'environnement OPENAI_API_KEY n'est pas définie.",
        "invalid_count": "--count doit être supérieur ou égal à 1.",
        "invalid_step": "--step doit être supérieur ou égal à 1.",
        "page_fetch_error": "Erreur lors de la récupération de la page : {error}",
        "page_progress": "[Page {page_index}/{total_pages}] {url}",
        "mw_title": "Titre MediaWiki   : {value}",
        "current_revision": "Révision courante : {value}",
        "probable_language": "Langue probable   : {value}",
        "detected_image": "Image détectée    : {value}",
        "no_scan_error": "Erreur : aucune image de fac-similé n'a été détectée pour cette page. La transcription depuis l'image ne peut pas être effectuée.",
        "analyzing_scan": "Appel de {model} pour analyser le fac-similé de {page_title}...",
        "openai_duration": "Durée appel OpenAI : {seconds:.2f} s",
        "openai_call_error": "Erreur pendant l'appel OpenAI : {error}",
        "proposal_saved": "Proposition enregistrée dans : {path}",
        "no_difference": "Aucune différence détectée entre le texte actuel et la proposition.",
        "proposed_diff": "DIFF PROPOSÉ",
        "empty_but_different_diff": "(diff vide mais texte différent)",
        "finish_use_apply": "Fin : utilisez --apply pour permettre l'enregistrement sur le wiki.",
        "publish_missing_credentials": "Erreur : pour publier, définissez MW_USERNAME et MW_PASSWORD",
        "publish_missing_password": "Erreur : mot de passe MediaWiki introuvable. Définissez MW_PASSWORD ou lancez le programme en mode interactif pour le saisir.",
        "publish_question": "Publier cette correction sur le wiki ({page_title}) ?",
        "publish_cancelled": "Publication annulée.",
        "publish_error": "Erreur lors de la publication : {error}",
        "publish_success": "Modification enregistrée avec succès.",
        "unexpected_edit_response": "Réponse inattendue de l'API d'édition :",
        "argparse_description": "Transcrire une page Wikisource depuis son fac-similé avec OpenAI puis, si souhaité, l'enregistrer via l'API MediaWiki.",
        "argparse_url": "URL complète de la page Wikisource à transcrire",
        "argparse_count": "Nombre de pages à traiter en incrémentant le numéro final de l'URL (défaut : 1)",
        "argparse_step": "Pas entre chaque page traitée (défaut : 1 = pages consécutives)",
        "argparse_model": "Modèle OpenAI à utiliser (défaut : {model})",
        "argparse_summary": "Résumé de modification MediaWiki",
        "argparse_instructions": "Instructions supplémentaires à transmettre au modèle",
        "argparse_dry_run": "Ne fait qu'afficher la transcription proposée et le diff, sans possibilité d'édition automatique",
        "argparse_apply": "Après affichage du diff, propose d'enregistrer la modification sur le wiki",
        "argparse_minor": "Marquer l'édition comme mineure",
        "argparse_bot": "Ajouter le drapeau bot si le compte y est autorisé",
        "argparse_no_image": "Ne pas envoyer l'image du fac-similé au modèle, même si elle est détectée",
        "argparse_save_output": "Chemin de fichier où enregistrer la proposition de wikitexte",
        "argparse_verbose": "Afficher les messages de débogage (durées, détails API...)",
        "argparse_lang": "Langue de l'interface et des prompts (`en` ou `fr`)",
        "main_missing_key": "Erreur : la variable d'environnement OPENAI_API_KEY n'est pas définie.",
        "main_invalid_count": "Erreur : --count doit être supérieur ou égal à 1.",
        "main_invalid_step": "Erreur : --step doit être supérieur ou égal à 1.",
        "generic_error": "Erreur : {error}",
        "user_cancelled_processing": "Traitement arrêté à la demande de l'utilisateur.",
    },
}


def normalize_language(language: Optional[str]) -> str:
    if language in SUPPORTED_LANGUAGES:
        return language
    return DEFAULT_LANGUAGE


def tr(key: str, language: Optional[str] = None, **kwargs: Any) -> str:
    lang = normalize_language(language)
    return I18N[lang][key].format(**kwargs)

# END CONFIGURATION
# ################################### 

_CACHED_MEDIAWIKI_USERNAME: Optional[str] = None
_CACHED_MEDIAWIKI_PASSWORD: Optional[str] = None

logger = logging.getLogger(__name__)


@dataclass
class PageData:
    page_title: str
    canonical_url: str
    api_endpoint: str
    html_url: str
    html_title: str
    current_wikitext: str
    basetimestamp: Optional[str]
    starttimestamp: Optional[str]
    revision_id: Optional[int]
    image_url: Optional[str]
    language_hint: Optional[str]


@dataclass
class ProcessingOptions:
    model: str = DEFAULT_MODEL
    summary: str = DEFAULT_EDIT_SUMMARY
    extra_instructions: str = ""
    system_prompt: str = SYSTEM_PROMPT
    dry_run: bool = False
    apply: bool = False
    minor: bool = False
    bot: bool = False
    no_image: bool = False
    save_output: str = ""
    username: Optional[str] = None
    password: Optional[str] = None
    prompt_for_credentials: bool = True
    confirm_publish: Optional[Callable[[PageData], bool]] = None
    language: str = DEFAULT_LANGUAGE


@dataclass
class PageProcessResult:
    status: int
    page: Optional[PageData] = None
    corrected_text: str = ""
    diff: str = ""
    saved_output_path: str = ""
    published: bool = False
    messages: List[str] = field(default_factory=list)


@dataclass
class GuiConfig:
    recent_url: str = ""
    recent_count: int = 1
    recent_step: int = 1
    recent_model: str = DEFAULT_MODEL
    recent_instructions: str = ""
    system_prompt: str = SYSTEM_PROMPT
    language: str = DEFAULT_LANGUAGE

    @classmethod
    def load(cls, path: Path = GUI_CONFIG_PATH) -> "GuiConfig":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except Exception:
            return cls()

        return cls(
            recent_url=str(raw.get("recent_url", "")),
            recent_count=max(1, int(raw.get("recent_count", 1))),
            recent_step=max(1, int(raw.get("recent_step", 1))),
            recent_model=str(raw.get("recent_model", DEFAULT_MODEL)),
            recent_instructions=str(raw.get("recent_instructions", "")),
            system_prompt=str(raw.get("system_prompt", SYSTEM_PROMPT)),
            language=normalize_language(raw.get("language")),
        )

    def save(self, path: Path = GUI_CONFIG_PATH) -> None:
        payload = {
            "recent_url": self.recent_url,
            "recent_count": self.recent_count,
            "recent_step": self.recent_step,
            "recent_model": self.recent_model,
            "recent_instructions": self.recent_instructions,
            "system_prompt": self.system_prompt,
            "language": normalize_language(self.language),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class MediaWikiAPIError(RuntimeError):
    pass


def _retry_delay_from_headers(headers: Any, attempt: int) -> float:
    retry_after = None
    if headers is not None:
        try:
            retry_after = headers.get("retry-after")
        except Exception:
            retry_after = None

    if retry_after:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass

    return INITIAL_RETRY_DELAY_SECONDS * (2 ** max(attempt - 1, 0))


def _is_openai_rate_limit_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True
    return "429" in str(exc)


def _friendly_rate_limit_message(service_name: str, exc: Exception, language: str = DEFAULT_LANGUAGE) -> str:
    text = str(exc)
    lower = text.lower()
    if service_name == "OpenAI":
        if "insufficient_quota" in lower:
            return tr("openai_quota", language)
        return tr("openai_rate_limit", language)
    return tr("server_rate_limit", language, service_name=service_name)


class WikisourceAssistant:
    def __init__(self, user_agent: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Language": "fr,en;q=0.9",
            }
        )

    def _session_get_with_retry(self, url: str) -> requests.Response:
        last_response: requests.Response | None = None
        for attempt in range(1, MAX_RETRIES_429 + 1):
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 429:
                response.raise_for_status()
                return response

            last_response = response
            delay = _retry_delay_from_headers(response.headers, attempt)
            logger.warning(
                tr("mw_retry", DEFAULT_LANGUAGE, delay=delay, attempt=attempt, max_retries=MAX_RETRIES_429)
            )
            time.sleep(delay)

        if last_response is not None:
            raise MediaWikiAPIError(_friendly_rate_limit_message("MediaWiki", Exception("429")))
        raise MediaWikiAPIError(tr("persistent_mw_429"))

    @staticmethod
    def _normalize_page_url(url: str) -> str:
        url = url.strip()
        parsed = urlparse(url)
        if not parsed.scheme:
            raise ValueError(tr("url_scheme_required"))
        return url

    @staticmethod
    def _api_from_page_url(page_url: str) -> str:
        parsed = urlparse(page_url)
        return f"{parsed.scheme}://{parsed.netloc}/w/api.php"

    @staticmethod
    def _language_from_host(host: str) -> Optional[str]:
        m = re.match(r"^([a-z\-]+)\.wikisource\.org$", host)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _title_from_url_path(page_url: str) -> Optional[str]:
        parsed = urlparse(page_url)
        path = unquote(parsed.path)
        m = re.match(r"^/wiki/(.+)$", path)
        if m:
            return m.group(1)
        # Edit URL: /w/index.php?title=Title...
        qs = parse_qs(parsed.query, keep_blank_values=True)
        title = qs.get("title", [None])[0]
        if title:
            return unquote(title)
        return None

    def _action_api_get(self, api_url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES_429 + 1):
            r = self.session.get(api_url, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code != 429:
                r.raise_for_status()
                data = r.json()
                if "error" in data:
                    raise MediaWikiAPIError(json.dumps(data["error"], ensure_ascii=False))
                return data

            delay = _retry_delay_from_headers(r.headers, attempt)
            last_error = requests.HTTPError(_friendly_rate_limit_message("MediaWiki", Exception("429")))
            logger.warning(
                tr("mw_retry", DEFAULT_LANGUAGE, delay=delay, attempt=attempt, max_retries=MAX_RETRIES_429)
            )
            time.sleep(delay)

        raise MediaWikiAPIError(str(last_error) if last_error else tr("persistent_mw_429"))

    def _action_api_post(self, api_url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES_429 + 1):
            r = self.session.post(api_url, data=data, timeout=REQUEST_TIMEOUT)
            if r.status_code != 429:
                r.raise_for_status()
                out = r.json()
                if "error" in out:
                    raise MediaWikiAPIError(json.dumps(out["error"], ensure_ascii=False))
                return out

            delay = _retry_delay_from_headers(r.headers, attempt)
            last_error = requests.HTTPError(_friendly_rate_limit_message("MediaWiki", Exception("429")))
            logger.warning(
                tr("mw_retry", DEFAULT_LANGUAGE, delay=delay, attempt=attempt, max_retries=MAX_RETRIES_429)
            )
            time.sleep(delay)

        raise MediaWikiAPIError(str(last_error) if last_error else tr("persistent_mw_429"))

    def get_page_data(self, page_url: str) -> PageData:
        page_url = self._normalize_page_url(page_url)
        api_url = self._api_from_page_url(page_url)
        parsed = urlparse(page_url)
        lang = self._language_from_host(parsed.netloc)

        title = self._title_from_url_path(page_url)
        if not title:
            raise ValueError(tr("cannot_extract_title"))

        query_params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "revisions|info",
            "titles": title,
            "rvprop": "ids|timestamp|content",
            "rvslots": "main",
            "curtimestamp": 1,
        }
        query = self._action_api_get(api_url, query_params)

        pages = query.get("query", {}).get("pages", [])
        if not pages:
            raise MediaWikiAPIError(tr("no_pages_found"))
        page = pages[0]
        if page.get("missing"):
            parsed_url = urlparse(page_url)
            edit_url = (
                f"{parsed_url.scheme}://{parsed_url.netloc}/w/index.php"
                f"?title={quote(title, safe='')}&action=edit&redlink=1"
            )
            edit_resp = self._session_get_with_retry(edit_url)
            edit_soup = BeautifulSoup(edit_resp.text, "html.parser")
            textarea = edit_soup.find("textarea", {"id": "wpTextbox1"})
            current_text = textarea.get_text() if textarea else ""
            image_url = self._extract_scan_image_from_html(edit_resp.text, edit_url)
            return PageData(
                page_title=page.get("title", title),
                canonical_url=page_url,
                api_endpoint=api_url,
                html_url=page_url,
                html_title=title,
                current_wikitext=current_text,
                basetimestamp=None,
                starttimestamp=query.get("curtimestamp"),
                revision_id=None,
                image_url=image_url,
                language_hint=lang,
            )

        revisions = page.get("revisions") or []
        if not revisions:
            raise MediaWikiAPIError(tr("no_revision_found"))

        rev = revisions[0]
        slots = rev.get("slots", {})
        main_slot = slots.get("main", {})
        current_text = main_slot.get("content", "")

        html = self._session_get_with_retry(page_url)
        image_url = self._extract_scan_image_from_html(html.text, page_url)

        return PageData(
            page_title=page["title"],
            canonical_url=page_url,
            api_endpoint=api_url,
            html_url=page_url,
            html_title=title,
            current_wikitext=current_text,
            basetimestamp=rev.get("timestamp"),
            starttimestamp=query.get("curtimestamp"),
            revision_id=rev.get("revid"),
            image_url=image_url,
            language_hint=lang,
        )

    def _extract_scan_image_from_html(self, html: str, base_url: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")

        selectors = [
            "img.prp-page-image",
            ".prp-page-image img",
            "#prp-page-image img",
            ".proofreadpage-image img",
            ".mw-proofreadpage-image img",
            ".prp-page-container img",
            ".quality-page img",
            "img[data-file-width]",
        ]

        for sel in selectors:
            node = soup.select_one(sel)
            if node and node.get("src"):
                return urljoin(base_url, node["src"])

        candidates = []
        for img in soup.select("#mw-content-text img, .mw-body-content img, img"):
            src = img.get("src")
            if not src:
                continue
            width = 0
            try:
                width = int(img.get("width") or 0)
            except Exception:
                width = 0
            candidates.append((width, src))

        if candidates:
            candidates.sort(reverse=True)
            return urljoin(base_url, candidates[0][1])

        return None

    def login(self, api_url: str, username: str, password: str) -> None:
        login_token = self._action_api_get(
            api_url,
            {
                "action": "query",
                "meta": "tokens",
                "type": "login",
                "format": "json",
            },
        )["query"]["tokens"]["logintoken"]

        result = self._action_api_post(
            api_url,
            {
                "action": "login",
                "lgname": username,
                "lgpassword": password,
                "lgtoken": login_token,
                "format": "json",
            },
        )
        status = result.get("login", {}).get("result")
        if status != "Success":
            raise MediaWikiAPIError(
                tr("mw_login_failed", details=json.dumps(result, ensure_ascii=False))
            )

    def get_csrf_token(self, api_url: str) -> str:
        result = self._action_api_get(
            api_url,
            {
                "action": "query",
                "meta": "tokens",
                "format": "json",
            },
        )
        return result["query"]["tokens"]["csrftoken"]

    def edit_page(
        self,
        page: PageData,
        new_text: str,
        summary: str,
        csrf_token: str,
        minor: bool = False,
        bot: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "action": "edit",
            "title": page.page_title,
            "text": new_text,
            "summary": summary,
            "token": csrf_token,
            "format": "json",
        }

        if page.basetimestamp:
            payload["basetimestamp"] = page.basetimestamp
        if page.starttimestamp:
            payload["starttimestamp"] = page.starttimestamp

        if minor:
            payload["minor"] = 1
        if bot:
            payload["bot"] = 1

        return self._action_api_post(page.api_endpoint, payload)



def build_prompt(
    page: PageData,
    extra_instructions: Optional[str] = None,
    system_prompt: Optional[str] = None,
    prompt_language: str = DEFAULT_LANGUAGE,
) -> Tuple[str, str]:
    language = normalize_language(prompt_language)
    default_system_prompt = SYSTEM_PROMPTS[language]
    system_instructions = textwrap.dedent(system_prompt or default_system_prompt).strip()

    user_prompt = textwrap.dedent(
        USER_PROMPT_TEMPLATES[language].format(
            page_title=page.page_title,
            url=page.canonical_url,
            current_wikitext=page.current_wikitext,
        )
    ).strip()

    if extra_instructions:
        user_prompt += "\n\n" + tr(
            "user_prompt_extra", language, instructions=extra_instructions.strip()
        )

    return system_instructions, user_prompt


def call_openai_for_correction(
    page: PageData,
    model: str,
    extra_instructions: Optional[str],
    image_url: Optional[str],
    system_prompt: Optional[str] = None,
    prompt_language: str = DEFAULT_LANGUAGE,
) -> str:
    client = OpenAI()

    language = normalize_language(prompt_language)
    system_instructions, user_prompt = build_prompt(
        page,
        extra_instructions,
        system_prompt,
        prompt_language=language,
    )

    content = [{"type": "input_text", "text": user_prompt}]
    if image_url:
        content.append(
            {
                "type": "input_image",
                "image_url": image_url,
                "detail": "high",
            }
        )

    corrected = ""
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES_429 + 1):
        try:
            if hasattr(client, "responses"):
                response = client.responses.create(
                    model=model,
                    instructions=system_instructions,
                    input=[
                        {
                            "role": "user",
                            "content": content,
                        }
                    ],
                )
                corrected = (response.output_text or "").strip()
            else:
                chat_messages = [{"role": "system", "content": system_instructions}]

                user_parts = [{"type": "text", "text": user_prompt}]
                if image_url:
                    user_parts.append({"type": "image_url", "image_url": {"url": image_url}})

                chat_messages.append({"role": "user", "content": user_parts})

                response = client.chat.completions.create(
                    model=model,
                    messages=chat_messages,
                )
                corrected = (response.choices[0].message.content or "").strip()
            break
        except Exception as e:
            last_error = e
            if not _is_openai_rate_limit_error(e):
                raise
            if attempt >= MAX_RETRIES_429:
                raise RuntimeError(_friendly_rate_limit_message("OpenAI", e, language)) from e

            response_headers = getattr(getattr(e, "response", None), "headers", None)
            delay = _retry_delay_from_headers(response_headers, attempt)
            logger.warning(
                tr("openai_retry", language, delay=delay, attempt=attempt, max_retries=MAX_RETRIES_429)
            )
            time.sleep(delay)

    if not corrected:
        if last_error and _is_openai_rate_limit_error(last_error):
            raise RuntimeError(_friendly_rate_limit_message("OpenAI", last_error, language)) from last_error
        raise RuntimeError(tr("openai_empty_response", language))
    return corrected


def unified_diff(old: str, new: str, title: str) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=tr("diff_current", DEFAULT_LANGUAGE, title=title),
            tofile=tr("diff_proposed", DEFAULT_LANGUAGE, title=title),
            n=3,
        )
    )


def prompt_yes_no(question: str, default_no: bool = True, language: str = DEFAULT_LANGUAGE) -> bool:
    suffix = tr("yes_no_suffix_default_no", language) if default_no else tr("yes_no_suffix_default_yes", language)
    reply = input(f"{question} {suffix} ").strip().lower()
    if not reply:
        return not default_no
    return reply in {"o", "oui", "y", "yes"}


def mediawiki_username_from_env_or_prompt(language: str = DEFAULT_LANGUAGE) -> Optional[str]:
    global _CACHED_MEDIAWIKI_USERNAME

    if _CACHED_MEDIAWIKI_USERNAME:
        return _CACHED_MEDIAWIKI_USERNAME

    username = os.getenv("MW_USERNAME")
    if username:
        _CACHED_MEDIAWIKI_USERNAME = username
        return username
    else:
        if not sys.stdin.isatty():
            return None

        username = input(tr("mediawiki_username_prompt", language)).strip()
        if not username:
            return None

        _CACHED_MEDIAWIKI_USERNAME = username
        return username

def mediawiki_password_from_env_or_prompt(language: str = DEFAULT_LANGUAGE) -> Optional[str]:
    global _CACHED_MEDIAWIKI_PASSWORD

    if _CACHED_MEDIAWIKI_PASSWORD:
        return _CACHED_MEDIAWIKI_PASSWORD

    password = os.getenv("MW_PASSWORD")
    if password:
        _CACHED_MEDIAWIKI_PASSWORD = password
        return password

    if not sys.stdin.isatty():
        return None

    password = getpass.getpass(tr("mediawiki_password_prompt", language)).strip()
    if not password:
        return None

    _CACHED_MEDIAWIKI_PASSWORD = password
    return password


def increment_page_url(page_url: str, offset: int) -> str:
    parsed = urlparse(page_url)

    # Standard wiki URL: /wiki/Title/NNN
    match = re.match(r"^(.*?/)(\d+)$", parsed.path)
    if match:
        page_number = int(match.group(2)) + offset
        if page_number < 1:
            raise ValueError(tr("invalid_page_number"))
        new_path = f"{match.group(1)}{page_number}"
        return parsed._replace(path=new_path).geturl()

    # Edit URL: /w/index.php?title=Title/NNN&action=edit...
    qs = parse_qs(parsed.query, keep_blank_values=True)
    title = qs.get("title", [None])[0]
    if title:
        title_match = re.match(r"^(.*?/)(\d+)$", title)
        if title_match:
            page_number = int(title_match.group(2)) + offset
            if page_number < 1:
                raise ValueError(tr("invalid_page_number"))
            qs["title"] = [f"{title_match.group(1)}{page_number}"]
            new_query = urlencode({k: v[0] for k, v in qs.items()})
            return parsed._replace(query=new_query).geturl()

    raise ValueError(tr("multi_page_url_required"))


def output_path_for_page(save_output: str, page_index: int, multi_pages: bool) -> str:
    if not save_output or not multi_pages:
        return save_output

    root, ext = os.path.splitext(save_output)
    return f"{root}_{page_index + 1}{ext}"


def ensure_openai_api_key(explicit_key: Optional[str] = None) -> None:
    key = explicit_key or os.getenv("OPENAI_WSASSISTANT_API_KEY")
    if key:
        os.environ["OPENAI_API_KEY"] = key

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(tr("missing_openai_key"))


def validate_paging(count: int, step: int) -> None:
    if count < 1:
        raise ValueError(tr("invalid_count"))
    if step < 1:
        raise ValueError(tr("invalid_step"))


def get_mediawiki_credentials(
    options: ProcessingOptions,
) -> Tuple[Optional[str], Optional[str]]:
    username = options.username
    password = options.password

    if username is None and options.prompt_for_credentials:
        username = mediawiki_username_from_env_or_prompt(options.language)
    if password is None and username and options.prompt_for_credentials:
        password = mediawiki_password_from_env_or_prompt(options.language)

    return username, password


def process_page(
    assistant: WikisourceAssistant,
    args: argparse.Namespace,
    page_url: str,
    page_index: int,
    total_pages: int,
) -> int:
    language = normalize_language(getattr(args, "lang", DEFAULT_LANGUAGE))
    try:
        page = assistant.get_page_data(page_url)
    except Exception as e:
        logger.error(tr("page_fetch_error", language, error=e))
        return 1

    if total_pages > 1:
        logger.info(tr("page_progress", language, page_index=page_index + 1, total_pages=total_pages, url=page.canonical_url))

    logger.info(tr("mw_title", language, value=page.page_title))
    logger.info(tr("current_revision", language, value=page.revision_id))
    logger.info(tr("probable_language", language, value=page.language_hint or ("unknown" if language == "en" else "inconnue")))
    logger.info(tr("detected_image", language, value=page.image_url or ("none" if language == "en" else "aucune")))
    logger.info("")

    if not page.image_url and not args.no_image:
        logger.error(tr("no_scan_error", language))
        return 1

    image_url = page.image_url if (page.image_url and not args.no_image) else None

    try:
        logger.info(tr("analyzing_scan", language, model=args.model, page_title=page.page_title))
        start_time = time.time()
        corrected = call_openai_for_correction(
            page=page,
            model=args.model,
            extra_instructions=args.instructions or None,
            image_url=image_url,
            system_prompt=getattr(args, "system_prompt", SYSTEM_PROMPT),
            prompt_language=language,
        )
        logger.debug(tr("openai_duration", language, seconds=time.time() - start_time))
    except Exception as e:
        logger.error(tr("openai_call_error", language, error=e))
        return 1

    save_output_path = output_path_for_page(args.save_output, page_index, total_pages > 1)
    if save_output_path:
        with open(save_output_path, "w", encoding="utf-8", newline="") as f:
            f.write(corrected)
        logger.info(tr("proposal_saved", language, path=save_output_path))

    diff = unified_diff(page.current_wikitext, corrected, page.page_title)

    if corrected == page.current_wikitext:
        logger.info(tr("no_difference", language))
        return 0

    logger.info("=" * 80)
    logger.info(tr("proposed_diff", language))
    logger.info("=" * 80)
    logger.info(diff if diff.strip() else tr("empty_but_different_diff", language))
    logger.info("=" * 80)

    if args.dry_run and not args.apply:
        return 0

    username = mediawiki_username_from_env_or_prompt(language)
    if not args.apply:
        logger.info(tr("finish_use_apply", language))
        return 0

    password = mediawiki_password_from_env_or_prompt(language) if username else None

    if not username:
        logger.error(tr("publish_missing_credentials", language))
        return 2

    if not password:
        logger.error(tr("publish_missing_password", language))
        return 2

    if not prompt_yes_no(tr("publish_question", language, page_title=page.page_title), default_no=True, language=language):
        logger.info(tr("publish_cancelled", language))
        return STATUS_CANCELLED_BY_USER

    try:
        assistant.login(page.api_endpoint, username, password)
        csrf = assistant.get_csrf_token(page.api_endpoint)
        result = assistant.edit_page(
            page=page,
            new_text=corrected,
            summary=args.summary,
            csrf_token=csrf,
            minor=args.minor,
            bot=args.bot,
        )
    except Exception as e:
        logger.error(tr("publish_error", language, error=e))
        return 1

    edit_info = result.get("edit", {})
    if edit_info.get("result") == "Success":
        logger.info(tr("publish_success", language))
        logger.debug(json.dumps(edit_info, ensure_ascii=False, indent=2))
        return 0

    logger.info(tr("unexpected_edit_response", language))
    logger.info(json.dumps(result, ensure_ascii=False, indent=2))
    return 1


def main() -> int:
    cli_language = DEFAULT_LANGUAGE
    for index, arg in enumerate(sys.argv[1:]):
        if arg.startswith("--lang="):
            cli_language = normalize_language(arg.split("=", 1)[1])
            break
        if arg == "--lang" and index + 2 <= len(sys.argv[1:]):
            cli_language = normalize_language(sys.argv[index + 2])
            break

    parser = argparse.ArgumentParser(
        description=tr("argparse_description", cli_language)
    )
    parser.add_argument("url", help=tr("argparse_url", cli_language))
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help=tr("argparse_count", cli_language),
    )
    parser.add_argument(
        "--step",
        type=int,
        default=1,
        help=tr("argparse_step", cli_language),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=tr("argparse_model", cli_language, model=DEFAULT_MODEL),
    )
    parser.add_argument(
        "--summary",
        default=DEFAULT_EDIT_SUMMARY_BY_LANG[cli_language],
        help=tr("argparse_summary", cli_language),
    )
    parser.add_argument(
        "--instructions",
        default="",
        help=tr("argparse_instructions", cli_language),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=tr("argparse_dry_run", cli_language),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=tr("argparse_apply", cli_language),
    )
    parser.add_argument(
        "--minor",
        action="store_true",
        help=tr("argparse_minor", cli_language),
    )
    parser.add_argument(
        "--bot",
        action="store_true",
        help=tr("argparse_bot", cli_language),
    )
    parser.add_argument(
        "--no-image",
        action="store_true",
        help=tr("argparse_no_image", cli_language),
    )
    parser.add_argument(
        "--save-output",
        default="",
        help=tr("argparse_save_output", cli_language),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help=tr("argparse_verbose", cli_language),
    )
    parser.add_argument(
        "--lang",
        choices=SUPPORTED_LANGUAGES,
        default=cli_language,
        help=tr("argparse_lang", cli_language),
    )

    args = parser.parse_args()
    args.lang = normalize_language(args.lang)

    user_agent = os.getenv(
        "MW_USER_AGENT",
        "WikisourceAssistant/1.0 (personal script; contact via user talk page)",
    )

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    key = os.getenv("OPENAI_WSASSISTANT_API_KEY")
    if key:
        os.environ["OPENAI_API_KEY"] = key

    if not os.getenv("OPENAI_API_KEY"):
        logger.error(tr("main_missing_key", args.lang))
        return 2

    if args.count < 1:
        logger.error(tr("main_invalid_count", args.lang))
        return 2

    if args.step < 1:
        logger.error(tr("main_invalid_step", args.lang))
        return 2

    assistant = WikisourceAssistant(user_agent=user_agent)

    for i, offset in enumerate(range(0, args.count * args.step, args.step)):
        try:
            page_url = increment_page_url(args.url, offset)
        except ValueError as e:
            logger.error(tr("generic_error", args.lang, error=e))
            return 2

        status = process_page(assistant, args, page_url, i, args.count)
        if status == STATUS_CANCELLED_BY_USER:
            logger.info(tr("user_cancelled_processing", args.lang))
            return 0
        if status != 0:
            return status

        if i + 1 < args.count:
            logger.info("")

    return 0



if __name__ == "__main__":
    raise SystemExit(main())
