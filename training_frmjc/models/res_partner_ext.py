from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── État civil (stagiaire) ─────────────────────────────────────
    date_naissance = fields.Date(string='Date de naissance')
    lieu_naissance = fields.Char(string='Lieu de naissance')
    pays_naissance_id = fields.Many2one('res.country', string='Pays de naissance')
    nationalite_id = fields.Many2one('res.country', string='Nationalité')
    sexe = fields.Selection([
        ('m', 'Homme'),
        ('f', 'Femme'),
        ('autre', 'Non précisé'),
    ], string='Sexe')
    situation_familiale = fields.Selection([
        ('celibataire', 'Célibataire'),
        ('marie', 'Marié(e) / Pacsé(e)'),
        ('divorce', 'Divorcé(e)'),
        ('veuf', 'Veuf / Veuve'),
    ], string='Situation familiale')
    nombre_enfants = fields.Integer(string="Enfants à charge")

    # ── Identifiants réglementaires ────────────────────────────────
    numero_secu = fields.Char(string='N° de sécurité sociale')
    photo_identite = fields.Binary(string="Photo d'identité", attachment=True)

    # ── Flags FRMJC ───────────────────────────────────────────────
    is_stagiaire_frmjc = fields.Boolean(
        string='Stagiaire FRMJC', default=False, index=True
    )
    is_formateur = fields.Boolean(
        string='Intervenant / Formateur FRMJC', default=False, index=True,
    )
    inscription_ids = fields.One2many(
        'training.inscription', 'partner_id', string="Dossiers d'inscription"
    )
    nb_inscriptions = fields.Integer(
        compute='_compute_nb_inscriptions', string='Nb dossiers', store=True
    )

    @api.depends('inscription_ids')
    def _compute_nb_inscriptions(self):
        for rec in self:
            rec.nb_inscriptions = len(rec.inscription_ids)

    # ── Structure d'accueil (employeur alternance) ─────────────────
    is_structure_accueil = fields.Boolean(
        string="Structure d'accueil FRMJC", default=False, index=True,
    )
    siret = fields.Char(string='SIRET', size=14)
    code_naf = fields.Char(string='Code NAF / APE', size=6)
    forme_juridique = fields.Char(
        string='Forme juridique',
        help='Ex : Association loi 1901, SARL, EPIC…',
    )
    convention_collective = fields.Char(string='Convention collective applicable')
    code_idcc = fields.Char(
        string='Code IDCC',
        help='Identifiant de la convention collective',
    )
    convention_accueil_ids = fields.One2many(
        'training.convention', 'structure_accueil_id',
        string='Conventions d\'accueil',
    )

    # ── Tuteur / Maître d'apprentissage ────────────────────────────
    diplome = fields.Char(
        string='Diplôme obtenu',
        help='Diplôme du tuteur / maître d\'apprentissage',
    )
    annee_diplome = fields.Integer(
        string='Année d\'obtention du diplôme',
    )
    experience_domaine_annees = fields.Integer(
        string='Années d\'expérience dans le domaine',
    )
    numero_carte_pro = fields.Char(
        string='N° carte professionnelle',
        help='Optionnel',
    )
