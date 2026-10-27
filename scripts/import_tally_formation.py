#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import des candidatures collectées via le formulaire Tally "Candidature —
Formation DEJEPS" dans le module training_frmjc (Odoo).

Ne dépend d'aucune bibliothèque tierce (seulement la lib standard Python) :
aucun "pip install" n'est nécessaire, le script parle à Odoo en XML-RPC.

────────────────────────────────────────────────────────────────────────
USAGE
────────────────────────────────────────────────────────────────────────

    python3 scripts/import_tally_formation.py export.csv

    # Pour voir ce qui serait fait SANS rien écrire en base :
    python3 scripts/import_tally_formation.py export.csv --dry-run

Connexion à Odoo (variables d'environnement recommandées pour ne pas
laisser le mot de passe dans l'historique du shell ; à défaut, le script
les demande de façon interactive) :

    ODOO_URL        (défaut : http://localhost:8070)
    ODOO_DB         (défaut : frmjc_v20_test)
    ODOO_USER       (demandé si absent)
    ODOO_PASSWORD   (demandé de façon masquée si absent)

Options utiles :

    --dry-run                 N'écrit rien, affiche ce qui serait créé/ignoré
    --session-id ID            Force la session cible (prioritaire sur
                                --formation-intitule/--formation-mention)
    --formation-intitule TEXT  Défaut : "DEJEPS ASEC 25-30"
    --formation-mention TEXT   Défaut : "Coordination de projets"
    --no-files                 N'essaie pas de télécharger les pièces jointes
                                (utile si les liens Tally ont expiré)

────────────────────────────────────────────────────────────────────────
IDEMPOTENCE (ré-exécution sans doublons)
────────────────────────────────────────────────────────────────────────

Tally ré-exporte TOUTES les soumissions à chaque export (pas seulement
les nouvelles). Ce script est donc fait pour être relancé régulièrement
sur le fichier le plus récent :

  - Le candidat est retrouvé par email (res.partner). S'il n'existe pas,
    il est créé.
  - Le dossier (training.inscription) n'est créé QUE s'il n'existe pas
    déjà pour le couple (candidat, session cible). S'il existe déjà,
    la ligne est ignorée (aucune écriture, aucune modification) : le
    script ne touche jamais un dossier qu'un membre du secrétariat a pu
    modifier depuis dans Odoo.
  - Les champs d'un candidat déjà présent en base (même email, nouveau
    dossier pour une AUTRE session) ne sont complétés que s'ils sont
    vides — un champ déjà renseigné n'est jamais écrasé.

────────────────────────────────────────────────────────────────────────
LIMITES CONNUES DU FORMULAIRE TALLY (non modifié, sur demande du client)
────────────────────────────────────────────────────────────────────────

  - Pas de question "Formation visée" dans le formulaire : la session
    cible est donc FIXÉE par ce script (voir --formation-intitule /
    --formation-mention / --session-id), jamais lue depuis le CSV.
    => Ce script importe uniquement vers UNE session à la fois. Pour une
       autre formation/session, relance-le avec d'autres --formation-*
       (ou prépare un export Tally séparé par formation).
  - Pas de question "Fonction visée" : insc.fonction_visee reste vide.
  - La question "Nom de la structure" (structure d'accueil, section
    Situation professionnelle) est importée dans insc.structure_accueil
    (texte libre), ET sert à chercher/créer la fiche res.partner liée
    (insc.structure_accueil_id) — avec les questions associées (email,
    adresse, téléphone, SIRET).
  - Idem pour le tuteur (insc.tuteur_id) et le représentant de la
    structure (insc.representant_structure_id) : fiches res.partner
    cherchées/créées comme contacts enfants de la structure.
  - PIÈGE TALLY : la question "Nom de la structure" (structure d'accueil)
    a le même libellé que le sous-champ "Nom de la structure" du bloc
    Expériences. Tally numérote les libellés dupliqués dans l'ordre
    d'apparition sur TOUT le formulaire, pas par bloc : en ajoutant la
    question "structure d'accueil" avant le bloc Expériences, celui-ci a
    décalé d'un cran la numérotation de son propre "Nom de la structure"
    (expérience 1 → suffixe " (2)", expérience 2 → " (3)", etc. — voir
    EXPERIENCE_STRUCTURE_SUFFIXES). Les 3 autres sous-champs du bloc
    (Année / Période, Nombre d'heures, Fonction) ne sont pas affectés.
    Si tu ajoutes/renommes une question dans Tally qui a pour effet
    d'insérer un nouveau libellé "Nom de la structure" ailleurs dans le
    formulaire, les suffixes vont encore bouger — vérifie l'export avec
    check_headers avant de relancer en production.
"""

import argparse
import base64
import csv
import getpass
import os
import unicodedata
import urllib.error
import urllib.request
import xmlrpc.client
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────
# Mappings libellé Tally (= libellé du portail candidat) → clé technique
# Odoo. Tenus à jour avec training_frmjc/views/portal_inscription.xml —
# si le portail change ses libellés, mets ces dictionnaires à jour.
# ──────────────────────────────────────────────────────────────────────

CIVILITE_MAP = {
    'monsieur': 'm',
    'madame': 'f',
    'non précisé': 'autre',
    'non precise': 'autre',
}

STATUT_EMPLOI_MAP = {
    'salarié': 'salarie',
    'salarie': 'salarie',
    'indépendant': 'independant',
    'independant': 'independant',
    "demandeur d'emploi": 'demandeur_emploi',
    'étudiant': 'etudiant',
    'etudiant': 'etudiant',
    'bénévole': 'benevole',
    'benevole': 'benevole',
    'autre': 'autre',
}

TYPE_CONTRAT_MAP = {
    'cdi': 'cdi',
    'cdd': 'cdd',
    'intérim': 'interim',
    'interim': 'interim',
    'apprentissage': 'apprentissage',
    'professionnalisation': 'professionnalisation',
    'pas de contrat': 'sanscontract',
}

RQTH_MAP = {
    'oui': 'oui',
    'non': 'non',
}

NIVEAU_ETUDES_MAP = {
    'niveau 3 (cap/bep)': 'v',
    'niveau 4 (bac)': 'iv',
    'niveau 5 (bac+2)': 'iii',
    'niveau 6 (bac+3/4)': 'ii',
    'niveau 7/8 (bac+5 et +)': 'i',
}

TYPE_FINANCEMENT_MAP = {
    'mon employeur finance ma formation': '1',
    'organisme paritaire (opco, cpf, apprentissage…)': '2',
    'organisme paritaire (opco, cpf, apprentissage...)': '2',
    'pouvoir public — agents publics': '3',
    'pouvoir public - agents publics': '3',
    'instance européenne': '4',
    'état': '5',
    'etat': '5',
    'conseil régional': '6',
    'conseil regional': '6',
    'france travail (ex pôle emploi)': '7',
    'france travail (ex pole emploi)': '7',
    'autre ressource publique': '8',
    'contrat individuel — à mes propres frais': '9',
    'contrat individuel - a mes propres frais': '9',
    'autre organisme de formation / cfa': '10',
    'autre': '11',
}

SOUS_TYPE_FINANCEMENT_MAP = {
    "contrat d'apprentissage": 'a',
    'contrat de professionnalisation': 'b',
    'promotion / reconversion par alternance (pro-a)': 'c',
    'projet de transition professionnelle (ptp)': 'd',
    'compte personnel de formation (cpf)': 'e',
    "dispositif pour demandeurs d'emploi": 'f',
    'dispositif pour travailleurs non-salariés': 'g',
    'dispositif pour travailleurs non-salaries': 'g',
    'plan de développement des compétences / autre': 'h',
    'plan de developpement des competences / autre': 'h',
}

# Démonymes français courants → nom du pays dans res.country (fallback
# quand la "Nationalité" saisie en texte libre ne correspond pas
# directement au nom du pays, ex. "Française" ≠ "France").
NATIONALITE_TO_COUNTRY = {
    'française': 'France', 'francaise': 'France', 'français': 'France', 'francais': 'France',
    'marocaine': 'Maroc', 'marocain': 'Maroc',
    'algérienne': 'Algérie', 'algerienne': 'Algérie', 'algérien': 'Algérie',
    'tunisienne': 'Tunisie', 'tunisien': 'Tunisie',
    'sénégalaise': 'Sénégal', 'senegalaise': 'Sénégal', 'sénégalais': 'Sénégal',
    'ivoirienne': "Côte d'Ivoire", 'ivoirien': "Côte d'Ivoire",
    'belge': 'Belgique',
    'suisse': 'Suisse',
    'portugaise': 'Portugal', 'portugais': 'Portugal',
    'espagnole': 'Espagne', 'espagnol': 'Espagne',
    'italienne': 'Italie', 'italien': 'Italie',
    'allemande': 'Allemagne', 'allemand': 'Allemagne',
    'britannique': 'Royaume-Uni',
    'américaine': 'États-Unis', 'americaine': 'États-Unis', 'américain': 'États-Unis',
    'camerounaise': 'Cameroun', 'camerounais': 'Cameroun',
    'malienne': 'Mali', 'malien': 'Mali',
    'congolaise': 'Congo', 'congolais': 'Congo',
    'guinéenne': 'Guinée', 'guineenne': 'Guinée', 'guinéen': 'Guinée',
    'comorienne': 'Comores', 'comorien': 'Comores',
    "haïtienne": 'Haïti', 'haitienne': 'Haïti', 'haïtien': 'Haïti',
    'roumaine': 'Roumanie', 'roumain': 'Roumanie',
    'polonaise': 'Pologne', 'polonais': 'Pologne',
    'chinoise': 'Chine', 'chinois': 'Chine',
    'malgache': 'Madagascar',
    'togolaise': 'Togo', 'togolais': 'Togo',
}

EXPERIENCE_SUFFIXES = ['', ' (2)', ' (3)', ' (4)']
# Le sous-champ "Nom de la structure" du bloc Expériences est décalé d'un
# cran par rapport aux 3 autres sous-champs du même bloc — voir la note
# "PIÈGE TALLY" dans le docstring du module.
EXPERIENCE_STRUCTURE_SUFFIXES = [' (2)', ' (3)', ' (4)', ' (5)']
DOCUMENT_SUFFIXES = ['', ' (2)', ' (3)']

# Champs fichier "fixes" : colonne CSV -> (champ binaire, champ nom de fichier)
FILE_FIELDS = {
    "Photo d'identité": ('photo_identite', 'photo_identite_filename'),
    'CV': ('cv', 'cv_filename'),
    'Lettre de motivation': ('lettre_motivation_doc', 'lettre_motivation_filename'),
    'Diplôme / attestation de niveau': ('diplome_doc', 'diplome_filename'),
    "Justificatif d'identité valide": ('justificatif_identite', 'justificatif_identite_filename'),
    'Attestation RQTH': ('attestation_rqth', 'attestation_rqth_filename'),
}


# ──────────────────────────────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────────────────────────────

def strip_accents(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )


def norm(s):
    """Normalise une valeur texte pour comparaison robuste (casse, accents,
    espaces superflus)."""
    return strip_accents((s or '').strip().lower())


def map_selection(value, mapping, label, warnings, row_ref):
    value = (value or '').strip()
    if not value:
        return False
    key = mapping.get(norm(value))
    if key is None:
        warnings.append(
            f"[{row_ref}] Valeur inconnue pour « {label} » : {value!r} — champ laissé vide."
        )
        return False
    return key


def parse_bool(value):
    return (value or '').strip().lower() == 'true'


def parse_date(value):
    """Accepte 'YYYY-MM-DD' ou 'YYYY-MM-DD HH:MM:SS' (format export Tally)."""
    value = (value or '').strip()
    if not value:
        return False
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return False


def parse_float(value):
    value = (value or '').strip().replace(',', '.')
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_int(value):
    value = (value or '').strip()
    if not value:
        return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def download_base64(url, warnings, row_ref, label):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FRMJC-import/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return base64.b64encode(data).decode('ascii')
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        warnings.append(
            f"[{row_ref}] Échec de téléchargement « {label} » ({exc}) — fichier ignoré. "
            f"Le lien Tally a peut-être expiré, retélécharge-le depuis Tally et dépose-le "
            f"manuellement sur le dossier."
        )
        return None


def filename_from_url(url):
    if not url:
        return False
    path = url.split('?', 1)[0]
    return path.rsplit('/', 1)[-1] or 'document'


CONSENT_RGPD_COLUMN = (
    "J'ai été informé(e) et j'accepte que mes données personnelles soient "
    "collectées et traitées par la FRMJC dans le cadre de la gestion de mon "
    "inscription et du suivi de mon parcours de formation. (J'accepte)"
)
CONSENT_ATTESTATION_COLUMN = (
    "Je certifie sur l'honneur l'exactitude des informations fournies et "
    "m'engage à fournir les originaux sur demande. (Je certifie)"
)
EXPECTED_COLUMNS = [
    'Submission ID', 'Submitted at', 'Prénom', 'Nom de famille', 'Email',
    CONSENT_RGPD_COLUMN, CONSENT_ATTESTATION_COLUMN,
]


def check_expected_columns(fieldnames):
    """Le script repère beaucoup de colonnes par leur intitulé exact (c'est
    le seul moyen offert par un export Tally). Si quelqu'un renomme une
    question dans Tally, on préfère planter ici avec un message clair
    plutôt qu'importer silencieusement des dossiers avec des champs vides
    (ex : consentement RGPD jamais détecté)."""
    missing = [c for c in EXPECTED_COLUMNS if c not in fieldnames]
    if missing:
        raise SystemExit(
            "Le fichier CSV ne contient pas les colonnes attendues suivantes "
            "(le formulaire Tally a probablement été modifié) :\n"
            + '\n'.join(f'  - {c!r}' for c in missing)
            + "\n\nMets à jour les constantes correspondantes en haut de "
              "import_tally_formation.py (EXPECTED_COLUMNS et les dictionnaires "
              "de mapping) avec les nouveaux intitulés, puis relance."
        )


# ──────────────────────────────────────────────────────────────────────
# Client Odoo (XML-RPC)
# ──────────────────────────────────────────────────────────────────────

class OdooClient:
    def __init__(self, url, db, username, password):
        self.db = db
        self.password = password
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        self.uid = common.authenticate(db, username, password, {})
        if not self.uid:
            raise SystemExit(
                "Authentification Odoo refusée — vérifie ODOO_USER / ODOO_PASSWORD / ODOO_DB."
            )
        self.models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

    def execute(self, model, method, *args, **kwargs):
        return self.models.execute_kw(
            self.db, self.uid, self.password, model, method, list(args), kwargs
        )

    def search(self, model, domain, **kwargs):
        return self.execute(model, 'search', domain, **kwargs)

    def search_read(self, model, domain, fields, **kwargs):
        return self.execute(model, 'search_read', domain, fields, **kwargs)

    def read(self, model, ids, fields):
        return self.execute(model, 'read', ids, fields)

    def create(self, model, vals):
        return self.execute(model, 'create', [vals])

    def write(self, model, ids, vals):
        return self.execute(model, 'write', ids, vals)

    def message_post(self, model, res_id, body):
        try:
            self.execute(model, 'message_post', [res_id], body=body)
        except xmlrpc.client.Fault:
            pass  # chatter facultatif, ne doit jamais faire échouer l'import


# ──────────────────────────────────────────────────────────────────────
# Résolution de la session cible
# ──────────────────────────────────────────────────────────────────────

def resolve_session(odoo, args):
    if args.session_id:
        session = odoo.read('training.session', [args.session_id], ['id', 'display_name'])
        if not session:
            raise SystemExit(f"Aucune training.session avec id={args.session_id}.")
        return args.session_id

    formations = odoo.search_read(
        'training.formation',
        [('intitule', '=', args.formation_intitule),
         ('mention', 'ilike', args.formation_mention)],
        ['id', 'display_name'],
    )
    if not formations:
        raise SystemExit(
            f"Aucune training.formation trouvée pour intitule={args.formation_intitule!r} "
            f"/ mention~={args.formation_mention!r}. Utilise --session-id pour forcer "
            f"la session, ou corrige --formation-intitule/--formation-mention."
        )
    if len(formations) > 1:
        noms = ', '.join(f"{f['id']}:{f['display_name']}" for f in formations)
        raise SystemExit(f"Plusieurs formations correspondent ({noms}) — utilise --session-id.")

    formation = formations[0]
    sessions = odoo.search_read(
        'training.session',
        [('formation_id', '=', formation['id']), ('statut', 'in', ('ouvert', 'en_cours'))],
        ['id', 'display_name', 'statut'],
    )
    if not sessions:
        raise SystemExit(
            f"Aucune session ouverte/en cours pour la formation "
            f"« {formation['display_name']} » (id={formation['id']}). Utilise --session-id."
        )
    if len(sessions) > 1:
        noms = ', '.join(f"{s['id']}:{s['display_name']} ({s['statut']})" for s in sessions)
        raise SystemExit(f"Plusieurs sessions ouvertes pour cette formation ({noms}) — utilise --session-id.")

    print(f"→ Session cible : {sessions[0]['display_name']} (id={sessions[0]['id']})")
    return sessions[0]['id']


# ──────────────────────────────────────────────────────────────────────
# Résolution pays (nationalité)
# ──────────────────────────────────────────────────────────────────────

class CountryResolver:
    def __init__(self, odoo):
        self.odoo = odoo
        self._by_name = {}
        countries = odoo.search_read('res.country', [], ['id', 'name'])
        for c in countries:
            self._by_name[norm(c['name'])] = c['id']

    def resolve(self, nationalite, warnings, row_ref):
        nationalite = (nationalite or '').strip()
        if not nationalite:
            return False
        key = norm(nationalite)
        if key in self._by_name:
            return self._by_name[key]
        demonym_country = NATIONALITE_TO_COUNTRY.get(key)
        if demonym_country and norm(demonym_country) in self._by_name:
            return self._by_name[norm(demonym_country)]
        warnings.append(
            f"[{row_ref}] Nationalité « {nationalite} » non reconnue — champ laissé vide. "
            f"Ajoute-la à NATIONALITE_TO_COUNTRY dans le script si elle doit revenir souvent."
        )
        return False


# ──────────────────────────────────────────────────────────────────────
# Construction des valeurs à partir d'une ligne CSV
# ──────────────────────────────────────────────────────────────────────

def build_partner_vals(row, country_resolver, warnings, row_ref):
    prenom = (row.get('Prénom') or '').strip()
    nom = (row.get('Nom de famille') or '').strip()
    vals = {
        'name': f'{prenom} {nom}'.strip() or (row.get('Email') or '').strip(),
        'email': (row.get('Email') or '').strip().lower(),
        'street': (row.get('Adresse') or '').strip(),
        'city': (row.get('Ville') or '').strip(),
        'zip': (row.get('Code postal') or '').strip(),
        'phone': (row.get('Téléphone') or '').strip(),
        'lieu_naissance': (row.get('Lieu de naissance') or '').strip(),
        'numero_secu': (row.get('N° de sécurité sociale') or '').strip(),
        'is_stagiaire_frmjc': True,
    }
    sexe = map_selection(row.get('Civilité'), CIVILITE_MAP, 'Civilité', warnings, row_ref)
    if sexe:
        vals['sexe'] = sexe
    date_naissance = parse_date(row.get('Date de naissance'))
    if date_naissance:
        vals['date_naissance'] = date_naissance
    nationalite_id = country_resolver.resolve(row.get('Nationalité'), warnings, row_ref)
    if nationalite_id:
        vals['nationalite_id'] = nationalite_id
    # On ne garde que les champs réellement renseignés : on ne veut jamais
    # écraser un champ existant par une valeur vide lors d'une mise à jour.
    # (L'email est toujours non vide ici : process_row() l'a déjà vérifié.)
    return {k: v for k, v in vals.items() if v not in ('', None)}


# ──────────────────────────────────────────────────────────────────────
# Structure d'accueil / tuteur / représentant — recherche ou création
# des fiches contact (res.partner) liées, à partir des nouvelles
# questions Tally. Même logique de non-écrasement que build_partner_vals :
# un champ déjà renseigné sur une fiche existante n'est jamais écrasé.
# ──────────────────────────────────────────────────────────────────────

def find_or_create_structure(odoo, row, warnings, row_ref, dry_run):
    """Cherche (par SIRET puis par nom) ou crée la fiche res.partner de la
    structure d'accueil. Retourne son id, ou None si aucun nom fourni."""
    nom = (row.get('Nom de la structure') or '').strip()
    if not nom:
        return None

    siret = (row.get("N° SIRET de la structure d'accueil") or '').strip().replace(' ', '')
    candidate_vals = {k: v for k, v in {
        'siret': siret,
        'email': (row.get("Email de la structure d'accueil") or '').strip().lower(),
        'phone': (row.get("Téléphone de la structure d'accueil") or '').strip(),
        # Question Tally en texte libre unique (pas de rue/CP/ville séparés) :
        # stockée entière dans 'street'.
        'street': (row.get("Adresse de la structure d'accueil") or '').strip(),
    }.items() if v}
    fields_to_read = ['id'] + list(candidate_vals.keys())

    structure = None
    if siret:
        found = odoo.search_read(
            'res.partner', [('siret', '=', siret), ('is_company', '=', True)],
            fields_to_read, limit=1,
        )
        if found:
            structure = found[0]
    if not structure:
        found = odoo.search_read(
            'res.partner', [('name', '=ilike', nom), ('is_company', '=', True)],
            fields_to_read, limit=1,
        )
        if found:
            structure = found[0]

    if structure:
        to_write = {k: v for k, v in candidate_vals.items() if not structure.get(k)}
        if dry_run:
            print(f"    · structure d'accueil trouvée : {nom!r} (id={structure['id']})"
                  + (f" — à compléter : {sorted(to_write)}" if to_write else ""))
            return structure['id']
        if to_write:
            odoo.write('res.partner', [structure['id']], to_write)
        return structure['id']

    if dry_run:
        print(f"    · structure d'accueil à créer : {nom!r}")
        return None
    create_vals = dict(candidate_vals)
    create_vals.update({'name': nom, 'is_company': True, 'is_structure_accueil': True})
    return odoo.create('res.partner', create_vals)[0]


def find_or_create_person(odoo, structure_id, prenom, nom, dry_run, label,
                           email='', phone='', function=''):
    """Cherche (par email puis par nom+structure) ou crée un contact
    (tuteur ou représentant) rattaché à la structure d'accueil. Retourne
    son id, ou None si aucun nom fourni."""
    nom_complet = ' '.join(filter(None, [prenom, nom])).strip()
    if not nom_complet:
        return None

    candidate_vals = {k: v for k, v in {
        'email': email, 'phone': phone, 'function': function,
    }.items() if v}
    fields_to_read = ['id'] + list(candidate_vals.keys())

    person = None
    if email:
        found = odoo.search_read(
            'res.partner', [('email', '=ilike', email), ('is_company', '=', False)],
            fields_to_read, limit=1,
        )
        if found:
            person = found[0]
    if not person:
        domain = [('name', '=ilike', nom_complet), ('is_company', '=', False)]
        if structure_id:
            domain = domain + [('parent_id', '=', structure_id)]
        found = odoo.search_read('res.partner', domain, fields_to_read, limit=1)
        if found:
            person = found[0]

    if person:
        to_write = {k: v for k, v in candidate_vals.items() if not person.get(k)}
        if dry_run:
            print(f"    · {label} trouvé·e : {nom_complet!r} (id={person['id']})"
                  + (f" — à compléter : {sorted(to_write)}" if to_write else ""))
            return person['id']
        if to_write:
            odoo.write('res.partner', [person['id']], to_write)
        return person['id']

    if dry_run:
        print(f"    · {label} à créer : {nom_complet!r}")
        return None
    create_vals = dict(candidate_vals)
    create_vals['name'] = nom_complet
    create_vals['is_company'] = False
    if structure_id:
        create_vals['parent_id'] = structure_id
    return odoo.create('res.partner', create_vals)[0]


def build_experience_commands(row, warnings, row_ref):
    commands = []
    for suffix, structure_suffix in zip(EXPERIENCE_SUFFIXES, EXPERIENCE_STRUCTURE_SUFFIXES):
        annee = (row.get(f'Année / Période{suffix}') or '').strip()
        heures = (row.get(f"Nombre d'heures effectuées{suffix}") or '').strip()
        structure = (row.get(f'Nom de la structure{structure_suffix}') or '').strip()
        fonction = (row.get(f'Fonction{suffix}') or '').strip()
        if not any((annee, heures, structure, fonction)):
            continue
        if not (annee and structure and fonction):
            warnings.append(
                f"[{row_ref}] Expérience{suffix or ' 1'} incomplète (année/structure/fonction "
                f"requis) — ligne ignorée."
            )
            continue
        commands.append((0, 0, {
            'annee_periode': annee,
            'heures': parse_float(heures),
            'structure': structure,
            'fonction': fonction,
        }))
    return commands


def build_document_commands(row, warnings, row_ref, download_files):
    commands = []
    for suffix in DOCUMENT_SUFFIXES:
        nature = (row.get(f'Nature du document{suffix}') or '').strip()
        url = (row.get(f'Untitled file upload field{suffix}') or '').strip()
        if not nature and not url:
            continue
        if not (nature and url):
            warnings.append(
                f"[{row_ref}] Autre document{suffix or ' 1'} incomplet (nature ou fichier "
                f"manquant) — ligne ignorée."
            )
            continue
        fichier_b64 = download_base64(url, warnings, row_ref, f'Autre document{suffix}') if download_files else None
        if not fichier_b64:
            continue
        commands.append((0, 0, {
            'name': nature,
            'fichier': fichier_b64,
            'fichier_filename': filename_from_url(url),
        }))
    return commands


def build_inscription_vals(row, session_id, warnings, row_ref, download_files):
    vals = {
        'session_id': session_id,
        'structure_accueil': (row.get('Nom de la structure') or '').strip(),
        'employeur_nom': (row.get("Nom de l'employeur") or '').strip(),
        'employeur_adresse': (row.get("Adresse de l'employeur") or '').strip(),
        'remuneration_mensuelle': parse_float(row.get('Rémunération brute mensuelle')),
        'volume_horaire_semaine': parse_float(row.get('Volume horaire hebdomadaire')),
        'dernier_diplome': (row.get('Dernier diplôme obtenu') or '').strip(),
        'etablissement_formation': (row.get('Établissement') or '').strip(),
        'annee_obtention': parse_int(row.get("Année d'obtention")),
        'projet_professionnel': (row.get('Projet professionnel') or '').strip(),
        'notes_candidat': (row.get('Informations complémentaires') or '').strip(),
    }

    statut_emploi = map_selection(row.get("Statut d'emploi actuel"), STATUT_EMPLOI_MAP,
                                   "Statut d'emploi actuel", warnings, row_ref)
    if statut_emploi:
        vals['statut_emploi'] = statut_emploi
    type_contrat = map_selection(row.get('Type de contrat'), TYPE_CONTRAT_MAP,
                                  'Type de contrat', warnings, row_ref)
    if type_contrat:
        vals['type_contrat'] = type_contrat
    rqth = map_selection(row.get('RQTH'), RQTH_MAP, 'RQTH', warnings, row_ref)
    if rqth:
        vals['rqth'] = rqth
    niveau = map_selection(row.get("Niveau d'études"), NIVEAU_ETUDES_MAP,
                            "Niveau d'études", warnings, row_ref)
    if niveau:
        vals['niveau_etudes'] = niveau
    financement = map_selection(row.get('Type de financement'), TYPE_FINANCEMENT_MAP,
                                 'Type de financement', warnings, row_ref)
    if financement:
        vals['type_financement'] = financement
    sous_type = map_selection(row.get('Précision du financement'), SOUS_TYPE_FINANCEMENT_MAP,
                               'Précision du financement', warnings, row_ref)
    if sous_type:
        vals['sous_type_financement'] = sous_type

    conditions_acceptees = parse_bool(row.get(CONSENT_RGPD_COLUMN))
    vals['conditions_acceptees'] = conditions_acceptees

    atteste = parse_bool(row.get(CONSENT_ATTESTATION_COLUMN))
    submitted_date = parse_date(row.get('Submitted at')) or datetime.today().strftime('%Y-%m-%d')
    if atteste:
        vals['date_declaration'] = submitted_date
    vals['date_inscription'] = submitted_date
    vals['statut'] = 'soumis' if (conditions_acceptees and atteste) else 'en_cours'

    experience_commands = build_experience_commands(row, warnings, row_ref)
    if experience_commands:
        vals['experience_ids'] = experience_commands

    document_commands = build_document_commands(row, warnings, row_ref, download_files)
    if document_commands:
        vals['document_ids'] = document_commands

    if download_files:
        for column, (bin_field, fname_field) in FILE_FIELDS.items():
            url = (row.get(column) or '').strip()
            if not url:
                continue
            data = download_base64(url, warnings, row_ref, column)
            if data:
                vals[bin_field] = data
                vals[fname_field] = filename_from_url(url)

    return vals


# ──────────────────────────────────────────────────────────────────────
# Boucle principale
# ──────────────────────────────────────────────────────────────────────

def process_row(odoo, country_resolver, session_id, row, args, warnings, stats):
    submission_id = row.get('Submission ID', '?')
    email = (row.get('Email') or '').strip().lower()
    row_ref = f"{submission_id} / {email or '(sans email)'}"

    if not email:
        warnings.append(f"[{row_ref}] Pas d'email — ligne ignorée.")
        stats['errors'] += 1
        return

    partner_vals = build_partner_vals(row, country_resolver, warnings, row_ref)

    existing_partners = odoo.search_read(
        'res.partner', [('email', '=ilike', email)], ['id'] + list(partner_vals.keys()), limit=1,
    )

    if existing_partners:
        partner = existing_partners[0]
        partner_id = partner['id']
        # Ne compléter que les champs actuellement vides (jamais d'écrasement).
        to_write = {
            k: v for k, v in partner_vals.items()
            if k != 'email' and not partner.get(k)
        }
        if to_write and not args.dry_run:
            odoo.write('res.partner', [partner_id], to_write)
    else:
        if args.dry_run:
            partner_id = None
        else:
            partner_id = odoo.create('res.partner', partner_vals)[0]

    if partner_id:
        existing_inscription = odoo.search(
            'training.inscription',
            [('partner_id', '=', partner_id), ('session_id', '=', session_id)],
            limit=1,
        )
    else:
        existing_inscription = []

    if existing_inscription:
        print(f"  = déjà importé, ignoré  [{row_ref}]")
        stats['skipped'] += 1
        return

    inscription_vals = build_inscription_vals(
        row, session_id, warnings, row_ref, download_files=not args.no_files,
    )

    structure_id = find_or_create_structure(odoo, row, warnings, row_ref, args.dry_run)
    if structure_id:
        inscription_vals['structure_accueil_id'] = structure_id

    tuteur_id = find_or_create_person(
        odoo, structure_id,
        (row.get('Prénom du tuteur') or '').strip(),
        (row.get('Nom du tuteur') or '').strip(),
        args.dry_run, 'tuteur',
        email=(row.get('Email du tuteur') or '').strip().lower(),
        phone=(row.get('Téléphone du tuteur') or '').strip(),
        function=(row.get('Fonction du tuteur') or '').strip(),
    )
    if tuteur_id:
        inscription_vals['tuteur_id'] = tuteur_id

    representant_id = find_or_create_person(
        odoo, structure_id,
        (row.get('Prénom du représentant de la structure') or '').strip(),
        (row.get('Nom du représentant de la structure') or '').strip(),
        args.dry_run, 'représentant de la structure',
        function=(row.get('Fonction du représentant de la structure') or '').strip(),
    )
    if representant_id:
        inscription_vals['representant_structure_id'] = representant_id

    if args.dry_run:
        print(f"  + serait créé  [{row_ref}]  statut={inscription_vals.get('statut')}")
        stats['created'] += 1
        return

    inscription_vals['partner_id'] = partner_id
    try:
        new_id = odoo.create('training.inscription', inscription_vals)[0]
        odoo.message_post(
            'training.inscription', new_id,
            f"Dossier importé automatiquement depuis Tally "
            f"(Submission ID: {submission_id}, soumis le {row.get('Submitted at', '?')})."
        )
        print(f"  + créé #{new_id}  [{row_ref}]")
        stats['created'] += 1
    except xmlrpc.client.Fault as exc:
        warnings.append(f"[{row_ref}] Échec de création : {exc.faultString}")
        stats['errors'] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('csv_path', help="Fichier CSV exporté depuis Tally")
    parser.add_argument('--dry-run', action='store_true', help="N'écrit rien, affiche le résultat prévu")
    parser.add_argument('--no-files', action='store_true', help="Ne télécharge pas les pièces jointes")
    parser.add_argument('--session-id', type=int, default=None, help="Force l'id de la session cible")
    parser.add_argument('--formation-intitule', default='DEJEPS ASEC 25-30')
    parser.add_argument('--formation-mention', default='Coordination de projets')
    args = parser.parse_args()

    url = os.environ.get('ODOO_URL', 'http://localhost:8070')
    db = os.environ.get('ODOO_DB', 'frmjc_v20_test')
    user = os.environ.get('ODOO_USER') or input('Utilisateur Odoo : ').strip()
    password = os.environ.get('ODOO_PASSWORD') or getpass.getpass('Mot de passe Odoo : ')

    odoo = OdooClient(url, db, user, password)
    session_id = resolve_session(odoo, args)
    country_resolver = CountryResolver(odoo)

    warnings = []
    stats = {'created': 0, 'skipped': 0, 'errors': 0}

    with open(args.csv_path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        check_expected_columns(reader.fieldnames or [])
        rows = list(reader)

    print(f"{len(rows)} soumission(s) dans le fichier."
          f"{' (DRY-RUN — rien ne sera écrit)' if args.dry_run else ''}")

    for row in rows:
        process_row(odoo, country_resolver, session_id, row, args, warnings, stats)

    print()
    print('── Résumé ' + '─' * 50)
    print(f"  Créés   : {stats['created']}")
    print(f"  Ignorés (déjà importés) : {stats['skipped']}")
    print(f"  Erreurs : {stats['errors']}")
    if warnings:
        print()
        print(f"── Avertissements ({len(warnings)}) " + '─' * 30)
        for w in warnings:
            print(f"  ! {w}")


if __name__ == '__main__':
    main()
