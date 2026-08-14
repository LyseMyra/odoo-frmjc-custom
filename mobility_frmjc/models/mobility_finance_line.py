from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


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
    # subcategory_id remplace l'ancien champ `poste` (Selection à plat) :
    # référentiel catégorie/sous-catégorie calqué sur les documents réels
    # de budget prévisionnel/réalisé (Structures/Transport/Hébergement/
    # Indemnités/Divers, avec compte comptable par sous-catégorie).
    subcategory_id = fields.Many2one(
        'mobility.finance.subcategory', string='Sous-catégorie', required=True,
    )
    categorie = fields.Selection(
        related='subcategory_id.categorie', string='Catégorie', store=True, readonly=True,
    )
    subcategory_calculable = fields.Boolean(
        related='subcategory_id.calculable', string='Calculable', readonly=True,
    )
    nature = fields.Selection(
        selection=[
            ('indemnite', 'Indemnité volontaire'),
            ('depense', 'Dépense'),
            ('recette', 'Recette'),
        ],
        string='Nature', default='indemnite', required=True,
    )

    # ── Période et calcul (sous-catégories calculables) ──────────────
    # Champs calculés (store=True, readonly=False) : pour les sous-
    # catégories calculables, la période correspond TOUJOURS aux dates de
    # la mobilité (réelles si connues, sinon proposées) et se
    # resynchronise automatiquement si ces dates changent plus tard — pas
    # seulement au moment de la saisie. Pour les autres, la période reste
    # librement saisissable (aucune valeur imposée). C'est la vue qui se
    # charge de griser le champ quand la sous-catégorie est calculable.
    periode_du = fields.Date(
        string='Période du', compute='_compute_periode', store=True, readonly=False,
    )
    periode_au = fields.Date(
        string='Période au', compute='_compute_periode', store=True, readonly=False,
    )
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

    # ── Validation & génération de documents comptables ──────────────
    # Uniquement pertinent pour nature ∈ {recette, dépense} — les lignes
    # d'indemnité volontaire (subvention Erasmus+) ne génèrent rien ici.
    statut_validation = fields.Selection(
        selection=[
            ('brouillon', 'Brouillon'),
            ('validee', 'Validée'),
            ('document_genere', 'Document généré'),
        ],
        string='Statut validation', default='brouillon', required=True,
    )
    invoice_id = fields.Many2one(
        'account.move', string='Facture', readonly=True, copy=False,
    )
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Bon de commande', readonly=True, copy=False,
    )

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends(
        'subcategory_id', 'mobility_id',
        'mobility_id.start_date', 'mobility_id.end_date',
        'mobility_id.date_debut_proposee', 'mobility_id.date_fin_proposee',
    )
    def _compute_periode(self):
        for rec in self:
            mobility = rec.mobility_id
            if rec.subcategory_id.calculable and mobility:
                if rec.subcategory_id.type_calcul == 'voyage':
                    # Forfait ponctuel, pas une indemnité journalière :
                    # période réduite à un seul jour de référence.
                    ref = (
                        mobility.start_date or mobility.date_debut_proposee
                        or fields.Date.today()
                    )
                    rec.periode_du = ref
                    rec.periode_au = ref
                else:
                    rec.periode_du = mobility.start_date or mobility.date_debut_proposee
                    rec.periode_au = mobility.end_date or mobility.date_fin_proposee
            else:
                # Sous-catégorie non calculable : période libre — on
                # préserve la valeur déjà enregistrée plutôt que
                # d'imposer quoi que ce soit (rien à calculer ici).
                rec.periode_du = rec._origin.periode_du
                rec.periode_au = rec._origin.periode_au

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
    @api.constrains('subcategory_id', 'beneficiaire_type')
    def _check_frais_gestion_beneficiaire(self):
        for rec in self:
            if (rec.subcategory_id.code == 'frais_gestion'
                    and rec.beneficiaire_type == 'volontaire'):
                raise ValidationError(
                    "Les frais de gestion sont perçus par l'organisme "
                    "coordinateur/LEAD, jamais par le volontaire (§11.6 du cahier)."
                )

    @api.constrains('subcategory_id', 'justificatif_id')
    def _check_cout_exceptionnel_justificatif(self):
        for rec in self:
            if rec.subcategory_id.code == 'cout_exceptionnel' and not rec.justificatif_id:
                raise ValidationError(
                    'Un justificatif est obligatoire pour un coût exceptionnel '
                    '(§11.5 du cahier).'
                )

    # ── Calcul automatique + bouton manuel ──────────────────────────
    @api.onchange('subcategory_id')
    def _onchange_subcategory_id(self):
        """Pré-remplit la nature depuis la sous-catégorie, puis calcule
        automatiquement dès que c'est possible — le bouton « Calculer »
        reste disponible pour recalculer après coup (ex. si le pays de
        la mobilité ou la période ont changé)."""
        if self.subcategory_id.nature_defaut:
            self.nature = self.subcategory_id.nature_defaut
        if self.subcategory_id.calculable and self.mobility_id:
            try:
                self._calculer()
            except UserError as e:
                return {'warning': {'title': 'Calcul impossible', 'message': str(e)}}

    def action_calculer(self):
        for rec in self:
            if not rec.subcategory_id.calculable:
                raise UserError(
                    'Le calcul automatique est disponible uniquement pour les '
                    'sous-catégories liées à un barème (Soutien organisationnel, '
                    "Soutien à l'inclusion, Argent de poche, Trajet A/R international)."
                )
            rec._calculer()

    def _calculer(self):
        self.ensure_one()
        mobility = self.mobility_id
        if self.subcategory_id.type_calcul == 'voyage':
            self._calculer_voyage(mobility)
        else:
            self._calculer_indemnite_journaliere(mobility)
        # Pré-remplit le réalisé sur le prévu — reste modifiable manuellement
        # après coup (version light : assistance au calcul, pas de verrouillage).
        self.montant_realise = self.montant_prevu

    def _calculer_indemnite_journaliere(self, mobility):
        if self.subcategory_id.type_calcul == 'soutien_inclusion' and not mobility.jeune:
            raise UserError(
                "Le soutien à l'inclusion n'est calculable que si le "
                'participant est marqué « Jeune / moins d\'opportunités ».'
            )
        if not mobility.country_id:
            raise UserError(
                'Le pays de mission doit être renseigné sur la mobilité '
                'pour calculer ce montant.'
            )
        date_ref = (
            mobility.start_date or mobility.date_debut_proposee or fields.Date.today()
        )
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
        self.montant_journalier = rate[field_map[self.subcategory_id.type_calcul]]
        # periode_du/periode_au sont calculés séparément (_compute_periode),
        # inutile de les fixer ici.

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
        self.montant_journalier = montant
        # periode_du/periode_au (réduits à un seul jour) sont calculés
        # séparément (_compute_periode), inutile de les fixer ici.

    # ── Validation & génération de documents comptables ──────────────
    def action_valider(self):
        for rec in self:
            if rec.statut_validation != 'brouillon':
                raise UserError('Cette ligne est déjà validée.')
            if rec.nature not in ('recette', 'depense'):
                raise UserError(
                    "Seules les lignes de nature « Dépense » ou « Recette » "
                    "peuvent être validées en vue de générer un document "
                    "comptable — une indemnité volontaire n'en a pas besoin."
                )
            if not rec.montant_realise:
                raise UserError(
                    'Le montant réalisé doit être renseigné avant validation.'
                )
            rec.statut_validation = 'validee'

    def action_annuler_validation(self):
        for rec in self:
            if rec.statut_validation == 'document_genere':
                raise UserError(
                    'Un document a déjà été généré pour cette ligne — '
                    'annulez ou supprimez ce document avant de revenir en brouillon.'
                )
            rec.statut_validation = 'brouillon'

    def action_generer_document(self):
        for rec in self:
            if rec.statut_validation != 'validee':
                raise UserError(
                    'La ligne doit être validée avant de générer un document.'
                )
            if rec.nature == 'recette':
                rec._generer_facture()
            elif rec.nature == 'depense':
                rec._generer_bon_de_commande()
            else:
                raise UserError(
                    "Impossible de générer un document pour une ligne de "
                    "nature « Indemnité volontaire »."
                )
            rec.statut_validation = 'document_genere'

    def _ligne_description(self):
        self.ensure_one()
        return f'{self.subcategory_id.name} — {self.mobility_id.display_name}'

    def _generer_facture(self):
        """Recette : facture client (account.move, brouillon) — à
        compléter et valider par le comptable (compte, taxes...)."""
        self.ensure_one()
        partner = self.payeur_partner_id
        if not partner:
            raise UserError(
                'Le payeur (fiche) doit être renseigné pour générer une facture.'
            )
        product = self.subcategory_id._get_or_create_product()
        move = self.env['account.move'].sudo().create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_origin': self.mobility_id.name,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': self._ligne_description(),
                'quantity': 1,
                'price_unit': self.montant_realise,
            })],
        })
        self.invoice_id = move.id

    def _generer_bon_de_commande(self):
        """Dépense : bon de commande fournisseur (purchase.order,
        brouillon) — même principe que
        training.depense.intervenant.action_creer_bons_de_commande
        dans training_frmjc."""
        self.ensure_one()
        partner = self.beneficiaire_partner_id
        if not partner:
            raise UserError(
                'Le bénéficiaire (fiche) doit être renseigné pour générer '
                'un bon de commande.'
            )
        product = self.subcategory_id._get_or_create_product()
        po = self.env['purchase.order'].sudo().create({
            'partner_id': partner.id,
            'origin': self.mobility_id.name,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'name': self._ligne_description(),
                'product_qty': 1,
                'price_unit': self.montant_realise,
            })],
        })
        self.purchase_order_id = po.id

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f'{rec.subcategory_id.name} — {rec.mobility_id.display_name}'
                if rec.subcategory_id else rec.mobility_id.display_name
            )
