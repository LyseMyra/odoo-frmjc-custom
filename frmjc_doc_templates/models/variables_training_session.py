"""Variables pour les documents liés à training.session (planning)."""

from .variable_registry import register_variable, register_list_variable

MODULE = "training_frmjc"
MODEL = "training.session"

CIVILITE_PAR_SEXE = {"m": "M.", "f": "Mme"}


def register(code, description, getter):
    register_variable(MODEL, code, description, getter, module=MODULE)


def register_list(code, description, getter):
    register_list_variable(MODEL, code, description, getter, module=MODULE)


def _date_fr(d):
    return d.strftime("%d/%m/%Y") if d else ""


register("session_nom", "Nom de la session", lambda r: r.name or "")
register(
    "formation_type",
    "Type de formation (ex. DEJEPS), en majuscules",
    lambda r: (r.formation_id.type_formation or "").upper(),
)
register(
    "formation_specialite",
    "Spécialité de la formation",
    lambda r: r.formation_id.specialite or "",
)
register(
    "formation_mention",
    "Mention de la formation",
    lambda r: r.formation_id.mention or "",
)
register(
    "session_date_debut",
    "Date de début de la session (JJ/MM/AAAA)",
    lambda r: _date_fr(r.date_debut),
)
register(
    "session_date_fin",
    "Date de fin de la session (JJ/MM/AAAA)",
    lambda r: _date_fr(r.date_fin),
)
register("session_lieu", "Lieu de la formation", lambda r: r.lieu_formation or "")
register(
    "session_nature_action",
    "Nature de l'action de formation",
    lambda r: r.nature_action or "",
)
register("numero_drajes", "Numéro DRAJES", lambda r: r.numero_drajes or "")
register(
    "habilitation_numero",
    "Numéro d'habilitation DRAJES",
    lambda r: r.habilitation_id.numero or "",
)
register(
    "responsable_nom",
    "Nom du ou de la responsable pédagogique",
    lambda r: r.responsable_id.name or "",
)
register(
    "responsable_email",
    "Email du ou de la responsable pédagogique",
    lambda r: r.responsable_id.email or "",
)
register(
    "responsable_telephone",
    "Téléphone du ou de la responsable pédagogique",
    lambda r: r.responsable_id.phone or "",
)
register(
    "signataire_nom",
    "Nom de la personne signataire des documents",
    lambda r: r.signataire_nom or r.responsable_id.name or "",
)
register(
    "signataire_titre",
    "Titre/fonction de la personne signataire",
    lambda r: r.signataire_titre or "Directrice / Directeur",
)


def _candidats_rows(session):
    """Candidats de la session pour un tableau nominatif (ex. attestation
    de complétude de la promotion) — un seul statut ('accepté') pour ne
    lister que la promotion réellement inscrite ; ajuste le filtre si un
    document a besoin d'un autre périmètre (ex. tous statuts confondus)."""
    rows = []
    for insc in session.inscription_ids.filtered(lambda i: i.statut == "accepte"):
        partner = insc.partner_id
        rows.append(
            {
                "civilite": CIVILITE_PAR_SEXE.get(partner.sexe, ""),
                # Nom et prénom ne sont pas stockés séparément dans res.partner
                # (name = nom complet) : nom_complet couvre les deux colonnes
                # "NOM (majuscule), Prénom (minuscule)" en une seule balise.
                "nom_complet": partner.name or "",
                "date_naissance": _date_fr(partner.date_naissance),
                "ville_naissance": partner.lieu_naissance or "",
            }
        )
    return rows


register_list(
    "candidats",
    "Liste des candidats de la session (statut accepté) — colonnes : "
    "civilite, nom_complet, date_naissance, ville_naissance",
    _candidats_rows,
)
