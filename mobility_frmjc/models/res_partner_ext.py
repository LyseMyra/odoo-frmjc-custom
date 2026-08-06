from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Identifiants réglementaires (Erasmus+ / export BM) ──────────
    oid = fields.Char(string='OID')
    pic = fields.Char(string='PIC')
    erasmus_code = fields.Char(string='Code Erasmus')
    id_national = fields.Char(
        string='ID national',
        help='Identifiant national, le cas échéant',
    )

    # ── Dénomination officielle ──────────────────────────────────────
    nom_legal = fields.Char(
        string='Nom légal complet',
        help='Dénomination officielle, dans la langue nationale',
    )
    nom_commercial = fields.Char(string='Nom commercial')
    acronyme = fields.Char(string='Acronyme')

    # ── Statut de la structure ───────────────────────────────────────
    type_organisme = fields.Selection(
        selection=[
            ('eplus-ngo', 'ONG (EPLUS-NGO)'),
            ('eplus-oth-type', 'Autre organisme (EPLUS-OTH-TYPE)'),
        ],
        string="Type d'organisme",
        help="Liste fermée attendue par l'export BM — à compléter si "
             "de nouvelles valeurs apparaissent dans le référentiel BM.",
    )
    organisme_public = fields.Boolean(string='Organisme public')
    sans_but_lucratif = fields.Boolean(string='Sans but lucratif')
    effectif_moins_250 = fields.Boolean(string='Effectif < 250 salariés')

    # ── Adresse légale (documents officiels / export BM) ─────────────
    adresse_legale = fields.Text(
        string='Adresse légale complète',
        help="Rue, code postal, ville, CEDEX, boîte postale, région, pays — "
             "telle qu'elle doit apparaître sur les documents officiels et "
             "l'export BM. Distincte de l'adresse Odoo standard (rue/CP/ville) "
             "utilisée pour le courrier courant.",
    )

    # ── Coordonnées complémentaires ───────────────────────────────────
    # email, site web et TVA réutilisent les champs standard res.partner
    # (email, website, vat) — pas de duplication.
    telephone_2 = fields.Char(string='Téléphone secondaire')
    fax = fields.Char(string='Fax')

    # ── Rôle(s) dans le dispositif volontariat (multi-valeurs) ────────
    structure_role_ids = fields.Many2many(
        'mobility.structure.role',
        string='Rôle(s) structure (volontariat)',
        help="Ex : Structure d'accueil ET Hébergement pour un même partenaire.",
    )
