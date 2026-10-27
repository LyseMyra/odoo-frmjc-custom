#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import des fiches de renseignement de volontaires collectées via le
formulaire Tally "Fiche de renseignement — Volontariat" dans le module
mobility_frmjc (Odoo).

Ne dépend d'aucune bibliothèque tierce (seulement la lib standard Python) :
aucun "pip install" n'est nécessaire, le script parle à Odoo en XML-RPC.

────────────────────────────────────────────────────────────────────────
PRINCIPE
────────────────────────────────────────────────────────────────────────

Ce script réutilise exactement la même logique que le formulaire public
(portal_fiche_renseignement) et l'assistant d'import Excel
(mobility.import.fiche.wizard) : la méthode serveur
`mobility.mobility._build_fiche_vals(post)`, appelée ici via XML-RPC à
travers le wrapper public `build_fiche_vals_rpc` (Odoo refuse les appels
XML-RPC sur les méthodes commençant par un underscore). Le find-or-create
du participant et des deux structures (envoi/accueil) est donc fait par
Odoo lui-même, pas réimplémenté ici — un seul endroit où cette logique
existe, comme pour les deux autres canaux de saisie.

Chaque ligne du CSV est rattachée à une mobilité retrouvée par PRN
(Participation Reference Number) :
  - Si une mobilité existe déjà avec ce PRN : sa fiche de renseignement
    est mise à jour (sauf si déjà validée — même garde-fou que
    l'assistant Excel, il faut la dévalider dans Odoo pour réimporter).
  - Sinon, une mobilité mobility.mobility est créée ENTIÈREMENT À PARTIR
    DE ZÉRO. Le formulaire Tally ne demande ni le programme (SC/CES/VSI)
    ni la direction (accueil/envoi) : ces deux champs obligatoires sont
    fixés en dur ci-dessous (PROGRAMME_DEFAUT / DIRECTION_DEFAUT), car ce
    formulaire Tally précis ne sert qu'à ce cas de figure (vocabulaire
    PRN/OID = Corps Européen de Solidarité, et FRMJC agit ici comme
    organisme de coordination recevant des volontaires). Si un jour ce
    formulaire sert aussi à d'autres programmes/directions, il faudra
    ajouter une question Tally dédiée plutôt que de changer cette
    constante.

────────────────────────────────────────────────────────────────────────
USAGE
────────────────────────────────────────────────────────────────────────

    python3 scripts/import_tally_mobilite.py export.csv

    # Pour voir ce qui serait fait SANS rien écrire en base :
    python3 scripts/import_tally_mobilite.py export.csv --dry-run

Connexion à Odoo (variables d'environnement recommandées pour ne pas
laisser le mot de passe dans l'historique du shell ; à défaut, le script
les demande de façon interactive) :

    ODOO_URL        (défaut : http://localhost:8070)
    ODOO_DB         (défaut : frmjc_v20_test)
    ODOO_USER       (demandé si absent)
    ODOO_PASSWORD   (demandé de façon masquée si absent)

────────────────────────────────────────────────────────────────────────
RÉ-EXÉCUTION (sans doublons)
────────────────────────────────────────────────────────────────────────

Tally ré-exporte TOUTES les soumissions à chaque export. Ce script est
donc fait pour être relancé régulièrement sur le fichier le plus récent :
une mobilité dont la fiche de renseignement est déjà validée
(`fiche_renseignement_validee = True`) est ignorée (il faut la
dévalider dans Odoo avant de pouvoir réimporter dessus) ; sinon, la
fiche est simplement réécrite avec les dernières valeurs du CSV, comme
le ferait une nouvelle soumission du formulaire public.
"""

import argparse
import getpass
import os
import xmlrpc.client
from datetime import datetime


# ──────────────────────────────────────────────────────────────────────
# Mapping colonne CSV (libellé exact Tally) → clé de champ attendue par
# mobility.mobility._build_fiche_vals(). Tenu à jour avec le formulaire
# Tally — si une question y est renommée, ce dictionnaire doit suivre.
# ──────────────────────────────────────────────────────────────────────

FIELD_MAP = {
    'Prénom': 'participant_prenom',
    'Nom': 'participant_nom',
    'Email': 'email',
    'Téléphone': 'telephone',
    "N° pièce d'identité / passeport": 'id_document_numero',
    'Besoins particuliers': 'besoins_particuliers',
    'Ville de résidence': 'ville_residence',

    # Contact d'urgence
    'Nom (2)': 'contact_urgence_nom',
    'Lien avec le volontaire': 'contact_urgence_lien',
    'Adresse': 'contact_urgence_adresse',
    'Téléphone (2)': 'contact_urgence_telephone',
    'Email (2)': 'contact_urgence_email',

    # Mission
    'Ville de mission': 'city',

    # Offre
    "ID de l'offre": 'offer_code',
    "Intitulé de l'offre": 'titre_offre',
    "Source de l'offre": 'source_offre',

    # Structure d'envoi
    'Nom (3)': 'sending_org_nom',
    'OID (si connu)': 'sending_org_oid_saisi',
    'Nom légal complet': 'sending_org_nom_legal',
    'Adresse légale complète': 'sending_org_adresse',
    "Type d'organisme": 'sending_org_type_organisme',
    'Email de la structure': 'sending_org_email',
    'Téléphone de la structure': 'sending_org_telephone',
    'Nom du coordinateur': 'sending_contact_nom',
    'Email du coordinateur': 'sending_contact_email',
    'Téléphone du coordinateur': 'sending_contact_telephone',

    # Structure d'accueil
    'Nom (4)': 'hosting_org_nom',
    'OID (si connu) (2)': 'hosting_org_oid_saisi',
    'Nom légal complet (2)': 'hosting_org_nom_legal',
    'Adresse légale complète (2)': 'hosting_org_adresse',
    "Type d'organisme (2)": 'hosting_org_type_organisme',
    'Email de la structure (2)': 'hosting_org_email',
    'Téléphone de la structure (2)': 'hosting_org_telephone',
    'Nom du référent': 'hosting_contact_nom',
    'Email du référent': 'hosting_contact_email',
    'Téléphone du référent': 'hosting_contact_telephone',

    # Déclaration
    'Lieu': 'lieu_declaration',
    'Nom complet': 'signature_nom',
}

DATE_COLUMNS = {
    'Date de naissance': 'date_naissance',
    'Validité de la pièce d\'identité': 'id_document_validite',
    'Date de début proposée': 'date_debut_proposee',
    'Date de fin proposée': 'date_fin_proposee',
    'Date de publication': 'date_publication_offre',
    'Date de sélection': 'date_selection_offre',
}

COUNTRY_COLUMNS = {
    'Nationalité': 'nationalite_id',
    'Pays de résidence': 'pays_residence_id',
    'Pays de mission': 'country_id',
}

PRN_COLUMN = 'PRN'

# Valeurs fixées en dur pour les mobilités créées à partir de ce
# formulaire Tally précis — voir l'explication dans le docstring du module.
PROGRAMME_DEFAUT = 'ces'
DIRECTION_DEFAUT = 'accueil'

CONSENT_COLUMN = (
    "Je certifie l'exactitude des informations fournies ci-dessus. "
    "(Je certifie l'exactitude des informations fournies ci-dessus.)"
)

EXPECTED_COLUMNS = [
    'Submission ID', 'Submitted at', PRN_COLUMN, 'Prénom', 'Nom', 'Email',
    CONSENT_COLUMN,
]

# Démonymes français courants → nom du pays dans res.country (même logique
# que scripts/import_tally_formation.py).
NATIONALITE_TO_COUNTRY = {
    'française': 'France', 'francaise': 'France', 'français': 'France', 'francais': 'France',
    'allemande': 'Allemagne', 'allemand': 'Allemagne',
    'belge': 'Belgique',
    'suisse': 'Suisse',
    'italienne': 'Italie', 'italien': 'Italie',
    'espagnole': 'Espagne', 'espagnol': 'Espagne',
    'portugaise': 'Portugal', 'portugais': 'Portugal',
    'britannique': 'Royaume-Uni',
    'néerlandaise': 'Pays-Bas', 'neerlandaise': 'Pays-Bas', 'néerlandais': 'Pays-Bas',
    'polonaise': 'Pologne', 'polonais': 'Pologne',
    'roumaine': 'Roumanie', 'roumain': 'Roumanie',
    'marocaine': 'Maroc', 'marocain': 'Maroc',
    'algérienne': 'Algérie', 'algerienne': 'Algérie', 'algérien': 'Algérie',
    'tunisienne': 'Tunisie', 'tunisien': 'Tunisie',
}

# Tally envoie le libellé affiché par le formulaire ("ONG (EPLUS-NGO)"), pas
# la clé technique attendue par res.partner.type_organisme ("eplus-ngo") —
# voir mobility_frmjc/models/res_partner_ext.py pour la liste fermée.
TYPE_ORGANISME_MAP = {
    'ong (eplus-ngo)': 'eplus-ngo',
    'autre organisme (eplus-oth-type)': 'eplus-oth-type',
}
TYPE_ORGANISME_FIELDS = ('sending_org_type_organisme', 'hosting_org_type_organisme')


# ──────────────────────────────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────────────────────────────

def norm(s):
    return (s or '').strip().lower()


def parse_date(value):
    """'YYYY-MM-DD' ou 'YYYY-MM-DD HH:MM:SS' (format export Tally)."""
    value = (value or '').strip()
    if not value:
        return False
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return False


def parse_bool(value):
    return (value or '').strip().lower() == 'true'


def check_expected_columns(fieldnames):
    missing = [c for c in EXPECTED_COLUMNS if c not in fieldnames]
    if missing:
        raise SystemExit(
            "Le fichier CSV ne contient pas les colonnes attendues suivantes "
            "(le formulaire Tally a probablement été modifié) :\n"
            + '\n'.join(f'  - {c!r}' for c in missing)
            + "\n\nMets à jour FIELD_MAP / EXPECTED_COLUMNS en haut de "
              "import_tally_mobilite.py avec les nouveaux intitulés, puis relance."
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

    def search_read(self, model, domain, fields, **kwargs):
        return self.execute(model, 'search_read', domain, fields, **kwargs)

    def create(self, model, vals):
        return self.execute(model, 'create', vals)

    def write(self, model, ids, vals):
        return self.execute(model, 'write', ids, vals)

    def build_fiche_vals(self, post):
        """Appelle mobility.mobility._build_fiche_vals(post) côté serveur
        (via le wrapper public build_fiche_vals_rpc — Odoo refuse les appels
        XML-RPC sur les méthodes commençant par un underscore) — réutilise
        le find-or-create participant/structures déjà en place pour le
        formulaire public et l'assistant Excel."""
        return self.execute('mobility.mobility', 'build_fiche_vals_rpc', post)


class CountryResolver:
    def __init__(self, odoo):
        self.odoo = odoo
        self._by_name = {}
        # Sans context lang, Odoo renvoie le nom de base (anglais) du pays
        # ("Germany"), pas sa traduction française ("Allemagne") — on force
        # donc le lang ici pour matcher les noms français saisis dans Tally.
        countries = odoo.search_read(
            'res.country', [], ['id', 'name'], context={'lang': 'fr_FR'},
        )
        for c in countries:
            self._by_name[norm(c['name'])] = c['id']

    def resolve(self, value, warnings, row_ref, label):
        value = (value or '').strip()
        if not value:
            return False
        key = norm(value)
        if key in self._by_name:
            return self._by_name[key]
        demonym = NATIONALITE_TO_COUNTRY.get(key)
        if demonym and norm(demonym) in self._by_name:
            return self._by_name[norm(demonym)]
        warnings.append(
            f"[{row_ref}] {label} « {value} » non reconnu(e) — champ laissé vide."
        )
        return False


# ──────────────────────────────────────────────────────────────────────
# Construction du dict "post" attendu par _build_fiche_vals
# ──────────────────────────────────────────────────────────────────────

def build_post(row, country_resolver, warnings, row_ref):
    post = {}
    for column, field_key in FIELD_MAP.items():
        post[field_key] = (row.get(column) or '').strip()

    for column, field_key in DATE_COLUMNS.items():
        post[field_key] = parse_date(row.get(column))

    for column, field_key in COUNTRY_COLUMNS.items():
        post[field_key] = country_resolver.resolve(
            row.get(column), warnings, row_ref, column,
        )

    for field_key in TYPE_ORGANISME_FIELDS:
        label = post.get(field_key) or ''
        key = TYPE_ORGANISME_MAP.get(norm(label))
        if label and not key:
            warnings.append(
                f"[{row_ref}] Type d'organisme « {label} » non reconnu(e) "
                f"— champ laissé vide."
            )
        post[field_key] = key or False

    post['declaration_acceptee'] = parse_bool(row.get(CONSENT_COLUMN))
    return post


# ──────────────────────────────────────────────────────────────────────
# Boucle principale
# ──────────────────────────────────────────────────────────────────────

def process_row(odoo, country_resolver, row, args, warnings, stats):
    submission_id = row.get('Submission ID', '?')
    prn = (row.get(PRN_COLUMN) or '').strip()
    email = (row.get('Email') or '').strip().lower()
    row_ref = f"{submission_id} / PRN {prn or '(absent)'} / {email or '(sans email)'}"

    if not prn:
        warnings.append(f"[{row_ref}] Pas de PRN — ligne ignorée.")
        stats['errors'] += 1
        return

    mobilities = odoo.search_read(
        'mobility.mobility', [('prn', '=', prn)],
        ['id', 'name', 'fiche_renseignement_validee'],
    )
    if len(mobilities) > 1:
        warnings.append(
            f"[{row_ref}] Plusieurs mobilités partagent ce PRN "
            f"({[m['name'] for m in mobilities]}) — ligne ignorée, à corriger manuellement."
        )
        stats['errors'] += 1
        return

    mobility = mobilities[0] if mobilities else None
    creation = mobility is None

    if mobility and mobility['fiche_renseignement_validee']:
        print(f"  = déjà validée, ignoré  [{row_ref}] -> {mobility['name']}")
        stats['skipped'] += 1
        return

    post = build_post(row, country_resolver, warnings, row_ref)

    manquants = [
        label for label, key in [
            ('Prénom', 'participant_prenom'), ('Nom', 'participant_nom'),
            ('Email', 'email'), ('Date de naissance', 'date_naissance'),
            ("Nom (4) / structure d'accueil", 'hosting_org_nom'),
        ] if not post.get(key)
    ]
    if manquants:
        warnings.append(
            f"[{row_ref}] Champs obligatoires manquants ({', '.join(manquants)}) "
            f"— ligne ignorée."
        )
        stats['errors'] += 1
        return

    if creation:
        if args.dry_run:
            print(f"  + serait créé  [{row_ref}]")
            stats['created'] += 1
            return

        vals = odoo.build_fiche_vals(post)
        vals['prn'] = prn
        vals['programme'] = PROGRAMME_DEFAUT
        vals['mobility_direction'] = DIRECTION_DEFAUT
        mobility_id = odoo.create('mobility.mobility', vals)
        odoo.create('mobility.document', {
            'mobility_id': mobility_id,
            'participant_id': vals.get('participant_id'),
            'document_type': 'fiche_renseignement',
            'statut': 'valide',
            'upload_date': datetime.today().strftime('%Y-%m-%d'),
            'emis_par': 'Import Tally (automatique)',
            'notes': (
                f"Fiche de renseignement importée automatiquement depuis Tally "
                f"(Submission ID: {submission_id})."
            ),
        })
        print(f"  + créé  [{row_ref}] -> mobility.mobility id {mobility_id}")
        stats['created'] += 1
        return

    if args.dry_run:
        print(f"  + serait mis à jour  [{row_ref}] -> {mobility['name']}")
        stats['updated'] += 1
        return

    vals = odoo.build_fiche_vals(post)
    odoo.write('mobility.mobility', [mobility['id']], vals)
    odoo.create('mobility.document', {
        'mobility_id': mobility['id'],
        'participant_id': vals.get('participant_id'),
        'document_type': 'fiche_renseignement',
        'statut': 'valide',
        'upload_date': datetime.today().strftime('%Y-%m-%d'),
        'emis_par': 'Import Tally (automatique)',
        'notes': (
            f"Fiche de renseignement importée automatiquement depuis Tally "
            f"(Submission ID: {submission_id})."
        ),
    })
    print(f"  + mis à jour  [{row_ref}] -> {mobility['name']}")
    stats['updated'] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('csv_path', help="Fichier CSV exporté depuis Tally")
    parser.add_argument('--dry-run', action='store_true', help="N'écrit rien, affiche le résultat prévu")
    args = parser.parse_args()

    url = os.environ.get('ODOO_URL', 'http://localhost:8070')
    db = os.environ.get('ODOO_DB', 'frmjc_v20_test')
    user = os.environ.get('ODOO_USER') or input('Utilisateur Odoo : ').strip()
    password = os.environ.get('ODOO_PASSWORD') or getpass.getpass('Mot de passe Odoo : ')

    odoo = OdooClient(url, db, user, password)
    country_resolver = CountryResolver(odoo)

    warnings = []
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

    import csv
    with open(args.csv_path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        check_expected_columns(reader.fieldnames or [])
        rows = list(reader)

    print(f"{len(rows)} soumission(s) dans le fichier."
          f"{' (DRY-RUN — rien ne sera écrit)' if args.dry_run else ''}")

    for row in rows:
        process_row(odoo, country_resolver, row, args, warnings, stats)

    print()
    print('── Résumé ' + '─' * 50)
    print(f"  Créés (ou le seraient) : {stats['created']}")
    print(f"  Mis à jour (ou le seraient) : {stats['updated']}")
    print(f"  Ignorés (déjà validés) : {stats['skipped']}")
    print(f"  Erreurs (champs manquants, PRN ambigu...) : {stats['errors']}")
    if warnings:
        print()
        print(f"── Avertissements ({len(warnings)}) " + '─' * 30)
        for w in warnings:
            print(f"  ! {w}")


if __name__ == '__main__':
    main()
