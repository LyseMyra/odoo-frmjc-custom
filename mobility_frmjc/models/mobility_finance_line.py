from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

# Postes pour lesquels le bouton « Calculer » est disponible (§11.1 du cahier).
POSTES_CALCULABLES = ('soutien_organisationnel', 'soutien_inclusion', 'argent_poche', 'voyage')


class MobilityFinanceLine(models.Model):
    _name = 'mobility.finance.line'
    _description = 'Ligne du grand livre financier (mobilité)'
    _order = 'date desc'

    mobility_id = fields.Many2one(
        'mobility.mobility', string='Mobilité', required=True,
        ondelete='cascade', index=True,
    )
    date = fields.Date(string='Date', default=fields.Date.today)

    # ── Classification ────────────────────────────────────────────
    poste = fields.Selection(
        selection=[
            ('soutien_organisationnel', 'Soutien organisationnel'),
            ('soutien_inclusion', "Soutien à l'inclusion"),
            ('argent_poche', 'Argent de poche'),
            ('voyage', 'Voyage'),
            ('soutien_linguistique', 'Soutien linguistique'),
            ('visite_preparatoire', 'Visite préparatoire'),
            ('cout_exceptionnel', 'Coût exceptionnel'),
            ('frais_gestion', 'Frais de gestion'),
            ('autre', 'Autre'),
        ],
        string='Poste', required=True,
    )
    nature = fields.Selection(
        selection=[
            ('indemnite', 'Indemnité volontaire'),
            ('depense', 'Dépense'),
            ('recette', 'Recette'),
        ],
        string='Nature', default='indemnite', required=True,
    )

    # ── Période et calcul (postes calculables) ──────────────────────
    periode_du = fields.Date(string='Période du')
    periode_au = fields.Date(string='Période au')
    nb_jours = fields.Integer(
        string='Nb jours', compute='_compute_nb_jours', store=True,
    )
    montant_journalier = fields.Float(string='Montant journalier (€)', digits=(10, 2))
    montant_prevu = fields.Float(
        string='Montant prévu (€)', compute='_compute_montants', store=True, digits=(10, 2),
    )
    montant_realise = fields.Float(string='Montant réalisé (€)', digits=(10, 2))
    ecart = fields.Float(
        string='Écart (€)', compute='_compute_montants', store=True, digits=(10, 2),
    )

    # ── Paiement ──────────────────────────────────────────────────
    statut_paiement = fields.Selection(
        selection=[
            ('a_payer', 'À payer'),
            ('paye', 'Payé'),
            ('recu', 'Reçu'),
            ('refuse', 'Refusé'),
        ],
        string='Statut paiement', default='a_payer', required=True,
    )
    source_financement = fields.Char(string='Source de financement')

    payeur_type = fields.Selection(
        selection=[
            ('erasmus', 'Erasmus+'),
            ('fdmjc22', 'FDMJC 22'),
            ('frmjc', 'FRMJC'),
            ('structure_accueil', "Structure d'accueil"),
            ('agence_civique', 'Agence Civique'),
            ('volontaire', 'Volontaire'),
            ('autre', 'Autre'),
        ],
        string='Payeur',
    )
    payeur_partner_id = fields.Many2one('res.partner', string='Payeur (fiche)')
    beneficiaire_type = fields.Selection(
        selection=[
            ('erasmus', 'Erasmus+'),
            ('fdmjc22', 'FDMJC 22'),
            ('frmjc', 'FRMJC'),
            ('structure_accueil', "Structure d'accueil"),
            ('agence_civique', 'Agence Civique'),
            ('volontaire', 'Volontaire'),
            ('autre', 'Autre'),
        ],
        string='Bénéficiaire',
    )
    beneficiaire_partner_id = fields.Many2one('res.partner', string='Bénéficiaire (fiche)')

    justificatif_id = fields.Many2one(
        'mobility.document', string='Justificatif',
        domain=[('document_type', '=', 'justificatif_finance')],
    )
    export_bm = fields.Boolean(string='À exporter (BM)', default=True)
    notes = fields.Text(string='Notes')

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends('periode_du', 'periode_au')
    def _compute_nb_jours(self):
        for rec in self:
            if rec.periode_du and rec.periode_au:
                rec.nb_jours = (rec.periode_au - rec.periode_du).days + 1
            else:
                rec.nb_jours = 0

    @api.depends('nb_jours', 'montant_journalier', 'montant_realise')
    def _compute_montants(self):
        for rec in self:
            rec.montant_prevu = rec.nb_jours * rec.montant_journalier
            rec.ecart = rec.montant_prevu - (rec.montant_realise or 0.0)

    # ── Contraintes ────────────────────────────────────────────────
    @api.constrains('poste', 'beneficiaire_type')
    def _check_frais_gestion_beneficiaire(self):
        for rec in self:
            if rec.poste == 'frais_gestion' and rec.beneficiaire_type == 'volontaire':
                raise ValidationError(
                    "Les frais de gestion sont perçus par l'organisme "
                    "coordinateur/LEAD, jamais par le volontaire (§11.6 du cahier)."
                )

    @api.constrains('poste', 'justificatif_id')
    def _check_cout_exceptionnel_justificatif(self):
        for rec in self:
            if rec.poste == 'cout_exceptionnel' and not rec.justificatif_id:
                raise ValidationError(
                    'Un justificatif est obligatoire pour un coût exceptionnel '
                    '(§11.5 du cahier).'
                )

    # ── Bouton « Calculer » ─────────────────────────────────────────
    def action_calculer(self):
        for rec in self:
            if rec.poste not in POSTES_CALCULABLES:
                raise UserError(
                    'Le calcul automatique est disponible uniquement pour les '
                    'postes Soutien organisationnel, Soutien à l\'inclusion, '
                    'Argent de poche et Voyage.'
                )
            rec._calculer()

    def _calculer(self):
        self.ensure_one()
        mobility = self.mobility_id
        if self.poste == 'voyage':
            self._calculer_voyage(mobility)
        else:
            self._calculer_indemnite_journaliere(mobility)
        # Pré-remplit le réalisé sur le prévu — reste modifiable manuellement
        # après coup (version light : assistance au calcul, pas de verrouillage).
        self.montant_realise = self.montant_prevu

    def _calculer_indemnite_journaliere(self, mobility):
        if self.poste == 'soutien_inclusion' and not mobility.jeune:
            raise UserError(
                "Le soutien à l'inclusion n'est calculable que si le "
                'participant est marqué « Jeune / moins d\'opportunités ».'
            )
        if not mobility.country_id:
            raise UserError(
                'Le pays de mission doit être renseigné sur la mobilité '
                'pour calculer ce montant.'
            )
        date_ref = self.periode_du or mobility.start_date or fields.Date.today()
        rate = self.env['mobility.rate.country'].search([
            ('country_id', '=', mobility.country_id.id),
            ('date_debut_validite', '<=', date_ref),
            '|',
            ('date_fin_validite', '=', False),
            ('date_fin_validite', '>=', date_ref),
        ], limit=1)
        if not rate:
            # Repli sur le barème générique « Pays tiers voisin de l'UE ».
            rate = self.env['mobility.rate.country'].search([
                ('country_id', '=', False),
                ('date_debut_validite', '<=', date_ref),
                '|',
                ('date_fin_validite', '=', False),
                ('date_fin_validite', '>=', date_ref),
            ], limit=1)
        if not rate:
            raise UserError(
                f'Aucun barème pays trouvé pour {mobility.country_id.name} '
                f'à la date {date_ref}.'
            )
        field_map = {
            'soutien_organisationnel': 'taux_soutien_organisationnel',
            'soutien_inclusion': 'taux_soutien_inclusion',
            'argent_poche': 'taux_argent_poche',
        }
        self.montant_journalier = rate[field_map[self.poste]]
        if not self.periode_du:
            self.periode_du = mobility.start_date
        if not self.periode_au:
            self.periode_au = mobility.end_date

    def _calculer_voyage(self, mobility):
        if not mobility.tranche_kilometrique:
            raise UserError(
                'La tranche kilométrique doit être renseignée sur la '
                'mobilité pour calculer le montant du voyage.'
            )
        rate = self.env['mobility.rate.travel'].search([
            ('tranche_kilometrique', '=', mobility.tranche_kilometrique),
        ], limit=1)
        if not rate:
            raise UserError(
                f'Aucun barème voyage trouvé pour la tranche '
                f'{mobility.tranche_kilometrique}.'
            )
        montant = (
            rate.montant_ecoresponsable if mobility.voyage_vert
            else rate.montant_standard
        )
        ref_date = self.periode_du or mobility.start_date or fields.Date.today()
        # Le voyage est un forfait ponctuel, pas une indemnité journalière :
        # on force une période d'un jour pour que la formule générale
        # (nb_jours × montant_journalier) donne directement le bon total.
        self.periode_du = ref_date
        self.periode_au = ref_date
        self.montant_journalier = montant

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            label = dict(rec._fields['poste'].selection).get(rec.poste, '?')
            rec.display_name = f'{label} — {rec.mobility_id.display_name}'
