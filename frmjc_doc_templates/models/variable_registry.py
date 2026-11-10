"""Registre Python des variables disponibles pour la génération de
documents.

Ce fichier ne contient aucune règle métier : il expose juste le
mécanisme d'enregistrement. Chaque module applicatif (voir
``variables_training.py``) déclare ses propres variables, pour ses
propres modèles, à l'import de son fichier.

Le catalogue visible dans Odoo (modèle ``template.variable``) est
synchronisé depuis ce registre à l'installation/mise à jour du module
(voir ``TemplateVariable._sync_variables``) : il n'y a donc qu'un seul
endroit où une variable est définie, jamais de liste à maintenir à la
main en double.
"""

import datetime
import logging

_logger = logging.getLogger(__name__)

# { model_name: { code: {'description': str, 'getter': callable, 'module': str} } }
_REGISTRY = {}

# Variables globales, disponibles quel que soit le modèle du document
# (ex. la date du jour). { code: {'description': str, 'getter': callable, 'module': str} }
_GLOBAL_REGISTRY = {}

# Variables "liste" : pour remplir une ligne de tableau Word qui se répète
# (ex. la liste des candidats d'une session). Le getter renvoie une liste de
# dicts — un dict par ligne, avec des clés simples (pas d'imbrication).
# { model_name: { code: {'description': str, 'getter': callable, 'module': str} } }
_LIST_REGISTRY = {}

_MOIS_FR = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}


def register_variable(model, code, description, getter, module=""):
    """Déclare une variable {{ code }} disponible pour les documents liés
    au modèle Odoo ``model`` (ex. 'training.inscription').

    :param getter: fonction prenant l'enregistrement et renvoyant la
        valeur texte à insérer dans le document.
    """
    _REGISTRY.setdefault(model, {})[code] = {
        "description": description,
        "getter": getter,
        "module": module,
    }


def register_global_variable(code, description, getter, module=""):
    """Déclare une variable globale, disponible pour tous les documents
    quel que soit leur modèle (ex. {{ date_jour }})."""
    _GLOBAL_REGISTRY[code] = {
        "description": description,
        "getter": getter,
        "module": module,
    }


def register_list_variable(model, code, description, getter, module=""):
    """Déclare une variable {{ code }} qui, pour un document lié au modèle
    Odoo ``model``, remplit une ligne de tableau Word qui se répète (liste
    de candidats, d'apprenants...).

    :param getter: fonction prenant l'enregistrement et renvoyant une
        liste de dicts — un dict par ligne, avec des clés simples
        utilisables dans Word via ``{{ nom_de_boucle.cle }}``.

    Usage dans le document Word (syntaxe docxtpl, dans un tableau) :
        - 1ère cellule de la ligne à répéter : ``{%tr for x in code %}``
        - cellules suivantes : ``{{ x.cle }}`` pour chaque colonne
        - dernière cellule de la même ligne : ``{%tr endfor %}``
    """
    _LIST_REGISTRY.setdefault(model, {})[code] = {
        "description": description,
        "getter": getter,
        "module": module,
    }


def get_variables(model):
    return _REGISTRY.get(model, {})


def get_global_variables():
    return _GLOBAL_REGISTRY


def get_list_variables(model):
    return _LIST_REGISTRY.get(model, {})


def all_models():
    return list(set(_REGISTRY.keys()) | set(_LIST_REGISTRY.keys()))


def build_context(record):
    """Construit le dictionnaire de fusion docxtpl pour UN enregistrement."""
    context = {}
    for code, meta in _GLOBAL_REGISTRY.items():
        try:
            value = meta["getter"](record)
        except Exception:
            _logger.exception("Échec du calcul de la variable globale %r", code)
            value = ""
        context[code] = value if value not in (None, False) else ""
    for code, meta in get_variables(record._name).items():
        try:
            value = meta["getter"](record)
        except Exception:
            _logger.exception("Échec du calcul de la variable %r pour %s", code, record)
            value = ""
        context[code] = value if value not in (None, False) else ""
    for code, meta in get_list_variables(record._name).items():
        try:
            value = meta["getter"](record) or []
        except Exception:
            _logger.exception(
                "Échec du calcul de la variable liste %r pour %s", code, record
            )
            value = []
        context[code] = value
    return context


def format_date_fr(d):
    if not d:
        return ""
    return f"{d.day} {_MOIS_FR.get(d.month, '')} {d.year}"


register_global_variable(
    "date_jour",
    "Date du jour (date de génération du document)",
    lambda record: format_date_fr(datetime.date.today()),
    module="frmjc_doc_templates",
)
register_global_variable(
    "frmjc_nom",
    "Nom de l'organisme de formation (société Odoo)",
    lambda record: record.env.company.name or "",
    module="frmjc_doc_templates",
)
register_global_variable(
    "frmjc_adresse",
    "Adresse complète de l'organisme de formation",
    lambda record: " ".join(
        filter(
            None,
            [
                record.env.company.street or "",
                (
                    (record.env.company.zip or "")
                    + " "
                    + (record.env.company.city or "")
                ).strip(),
            ],
        )
    ).strip(),
    module="frmjc_doc_templates",
)
register_global_variable(
    "frmjc_telephone",
    "Téléphone de l'organisme de formation",
    lambda record: record.env.company.phone or "",
    module="frmjc_doc_templates",
)
register_global_variable(
    "frmjc_email",
    "Email de l'organisme de formation",
    lambda record: record.env.company.email or "",
    module="frmjc_doc_templates",
)
