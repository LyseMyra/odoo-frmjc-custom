from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TrainingSession(models.Model):
    _name = 'training.session'
    _description = 'Session de formation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc'
    _rec_name = 'name'

    # ── Identification ─────────────────────────────────────────────
    name = fields.Char(
        string='Nom de la session',
        required=True,
        tracking=True,
        help='Ex : DEJEPS Animation 2024-2026'
    )
    numero_drajes = fields.Char(
        string='Numéro de session DRAJES',
        tracking=True,
        help='Numéro attribué par la DRAJES pour cette session'
    )

    # ── Relations principales ──────────────────────────────────────
    habilitation_id = fields.Many2one(
        'training.habilitation',
        string='Habilitation',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    formation_id = fields.Many2one(
        'training.formation',
        string='Formation',
        required=True,
        tracking=True,
        ondelete='restrict',
    )
    responsable_id = fields.Many2one(
        'res.partner',
        string='Responsable pédagogique',
        required=True,
        tracking=True,
        domain=[('is_company', '=', False)],
    )
    responsable_email = fields.Char(
        related='responsable_id.email',
        string='Email responsable',
        readonly=True,
    )
    responsable_phone = fields.Char(
        related='responsable_id.phone',
        string='Téléphone responsable',
        readonly=True,
    )

    # ── Dates ──────────────────────────────────────────────────────
    date_debut = fields.Date(
        string='Date de début',
        required=True,
        tracking=True,
    )
    date_fin = fields.Date(
        string='Date de fin',
        required=True,
        tracking=True,
    )

    # ── Statut ─────────────────────────────────────────────────────
    statut = fields.Selection(
        selection=[
            ('brouillon', 'Brouillon'),
            ('ouvert', 'Ouvert'),
            ('en_cours', 'En cours'),
            ('termine', 'Terminé'),
            ('annule', 'Annulé'),
        ],
        string='Statut',
        default='brouillon',
        required=True,
        tracking=True,
    )

    # ── Relations enfants ──────────────────────────────────────────
    week_ids = fields.One2many(
        'training.week',
        'session_id',
        string='Semaines',
    )
    inscription_ids = fields.One2many(
        'training.inscription',
        'session_id',
        string='Inscriptions',
    )
    depense_intervenant_ids = fields.One2many(
        'training.depense.intervenant',
        'session_id',
        string='Dépenses intervenants',
    )
    intervenant_ids = fields.Many2many(
        'res.partner',
        compute='_compute_intervenant_ids',
        string='Intervenants effectifs',
    )
    nb_stagiaires = fields.Integer(
        string='Nombre de stagiaires',
        compute='_compute_nb_stagiaires',
        store=True,
    )

    # ── Agrégats financiers (dépenses) ────────────────────────────
    nb_depenses_a_commander = fields.Integer(
        string='Dépenses à commander',
        compute='_compute_depenses',
        store=True,
        help='Nombre de dépenses validées sans bon de commande',
    )
    total_depenses_validees = fields.Float(
        string='Total dépenses validées (€)',
        compute='_compute_depenses',
        store=True, digits=(12, 2),
    )
    total_depenses_commandees = fields.Float(
        string='Total dépenses commandées (€)',
        compute='_compute_depenses',
        store=True, digits=(12, 2),
    )

    # ── Agrégats financiers (recettes) ────────────────────────────
    nb_stagiaires_acceptes = fields.Integer(
        string='Stagiaires acceptés',
        compute='_compute_recettes',
        store=True,
    )
    total_recettes_theoriques = fields.Float(
        string='Recettes théoriques (€)',
        compute='_compute_recettes',
        store=True, digits=(12, 2),
        help='Somme des recettes théoriques de tous les stagiaires acceptés',
    )
    total_recettes_reelles = fields.Float(
        string='Recettes réelles (€)',
        compute='_compute_recettes',
        store=True, digits=(12, 2),
        help='Somme des recettes réelles (présences + absences justifiées)',
    )
    ecart_recettes = fields.Float(
        string='Écart recettes (€)',
        compute='_compute_recettes',
        store=True, digits=(12, 2),
        help='Impact financier total des absences injustifiées',
    )

    # ── Agrégats financiers (marge) ───────────────────────────────
    marge_nette = fields.Float(
        string='Marge nette (€)',
        compute='_compute_marge',
        store=True, digits=(12, 2),
        help='Recettes réelles − dépenses commandées',
    )
    cout_par_stagiaire = fields.Float(
        string='Coût / stagiaire (€)',
        compute='_compute_marge',
        store=True, digits=(10, 2),
        help='Dépenses commandées ÷ nb stagiaires acceptés',
    )

    # ── Informations complémentaires ───────────────────────────────
    lieu_formation = fields.Char(
        string='Lieu de la formation',
        default='En itinérance',
        help='Ex : En itinérance, Rennes, ...',
    )
    nature_action = fields.Char(
        string='Nature de l\'action',
        help='Ex : DEJEPS DPTR',
    )
    signataire_nom = fields.Char(
        string='Signataire (nom)',
        help='Nom du représentant légal pour les documents officiels',
    )
    signataire_titre = fields.Char(
        string='Signataire (titre)',
        default='Directrice / Directeur',
    )
    volume_heures_prevues = fields.Float(
        string='Volume d\'heures prévu (h)',
        help='Volume total d\'heures de formation planifiées (rempli manuellement ou calculé)',
    )
    notes = fields.Text(string='Notes internes')

    # ── Contraintes SQL ────────────────────────────────────────────
    _numero_drajes_unique = models.Constraint(
        'UNIQUE(numero_drajes)',
        'Ce numéro de session DRAJES existe déjà.'
    )

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends('week_ids.week_line_ids.intervenant_id')
    def _compute_intervenant_ids(self):
        for rec in self:
            rec.intervenant_ids = rec.week_ids.week_line_ids.mapped('intervenant_id')

    @api.depends('inscription_ids')
    def _compute_nb_stagiaires(self):
        for rec in self:
            rec.nb_stagiaires = len(rec.inscription_ids)

    @api.depends(
        'inscription_ids.statut',
        'inscription_ids.montant_theorique',
        'inscription_ids.montant_reel',
        'inscription_ids.ecart_montant',
    )
    def _compute_recettes(self):
        for rec in self:
            acceptes = rec.inscription_ids.filtered(lambda i: i.statut == 'accepte')
            rec.nb_stagiaires_acceptes = len(acceptes)
            rec.total_recettes_theoriques = sum(acceptes.mapped('montant_theorique'))
            rec.total_recettes_reelles = sum(acceptes.mapped('montant_reel'))
            rec.ecart_recettes = sum(acceptes.mapped('ecart_montant'))

    @api.depends(
        'depense_intervenant_ids.statut',
        'depense_intervenant_ids.montant_total',
    )
    def _compute_depenses(self):
        for rec in self:
            a_commander = rec.depense_intervenant_ids.filtered(
                lambda d: d.statut == 'valide'
            )
            commandees = rec.depense_intervenant_ids.filtered(
                lambda d: d.statut == 'bc_cree'
            )
            rec.nb_depenses_a_commander = len(a_commander)
            rec.total_depenses_validees = sum(a_commander.mapped('montant_total'))
            rec.total_depenses_commandees = sum(commandees.mapped('montant_total'))

    @api.depends('total_recettes_reelles', 'total_depenses_commandees', 'nb_stagiaires_acceptes')
    def _compute_marge(self):
        for rec in self:
            rec.marge_nette = rec.total_recettes_reelles - rec.total_depenses_commandees
            rec.cout_par_stagiaire = (
                rec.total_depenses_commandees / rec.nb_stagiaires_acceptes
                if rec.nb_stagiaires_acceptes else 0.0
            )

    # ── Actions ────────────────────────────────────────────────────
    def action_creer_bons_de_commande(self):
        """Crée un bon de commande par intervenant pour toutes les dépenses
        au statut 'valide'. Les dépenses déjà en 'bc_cree' sont ignorées."""
        self.ensure_one()
        depenses = self.depense_intervenant_ids.filtered(lambda d: d.statut == 'valide')
        if not depenses:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aucune dépense à commander',
                    'message': 'Validez des dépenses (statut "Validée") avant de créer un bon de commande.',
                    'type': 'warning',
                    'sticky': False,
                },
            }

        pos_crees = self.env['purchase.order']
        for partner in depenses.mapped('partner_id'):
            depenses_partner = depenses.filtered(lambda d: d.partner_id == partner)
            lignes = []
            for d in depenses_partner:
                uom = d.product_id.uom_id
                lignes.append((0, 0, {
                    'product_id': d.product_id.id,
                    'name': d.description or d.product_id.display_name,
                    'product_qty': d.quantite,
                    'price_unit': d.prix_unitaire,
                    'product_uom_id': uom.id if uom else False,
                    'date_planned': fields.Datetime.now(),
                }))
            po = self.env['purchase.order'].sudo().create({
                'partner_id': partner.id,
                'origin': self.name,
                'order_line': lignes,
            })
            po.button_confirm()
            depenses_partner.write({
                'statut': 'bc_cree',
                'purchase_order_id': po.id,
            })
            pos_crees |= po

        return {
            'type': 'ir.actions.act_window',
            'name': 'Bons de commande créés',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pos_crees.ids)],
            'target': 'current',
        }

    # ── Contraintes Python ─────────────────────────────────────────
    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_debut and rec.date_fin:
                if rec.date_fin <= rec.date_debut:
                    raise ValidationError(
                        'La date de fin doit être postérieure '
                        'à la date de début.'
                    )

    @api.constrains('formation_id', 'habilitation_id')
    def _check_coherence_formation_habilitation(self):
        for rec in self:
            if (rec.formation_id and rec.habilitation_id and
                    rec.formation_id.type_formation !=
                    rec.habilitation_id.type_formation):
                raise ValidationError(
                    'Le type de formation ne correspond pas '
                    'au type de l\'habilitation.'
                )

    # ── Actions de workflow ────────────────────────────────────────
    def action_ouvrir(self):
        self.write({'statut': 'ouvert'})

    def action_demarrer(self):
        self.write({'statut': 'en_cours'})

    def action_terminer(self):
        self.write({'statut': 'termine'})

    def action_annuler(self):
        self.write({'statut': 'annule'})

    def action_brouillon(self):
        self.write({'statut': 'brouillon'})

    def get_weeks_par_annee(self):
        """Retourne [(annee_str, nb_semaines, semaines_recordset), ...] pour le PDF planning."""
        from collections import OrderedDict
        groupes = OrderedDict()
        for week in self.week_ids.sorted('date_debut'):
            annee = str(week.date_debut.year)
            if annee not in groupes:
                groupes[annee] = []
            groupes[annee].append(week.id)
        return [
            (annee, len(ids), self.env['training.week'].browse(ids))
            for annee, ids in groupes.items()
        ]

    def get_weeks_par_mois(self):
        """Retourne [(label_mois, semaines_recordset), ...] trié chronologiquement."""
        from collections import defaultdict
        groupes = defaultdict(list)
        for week in self.week_ids.sorted('numero_semaine'):
            groupes[week.date_debut.strftime('%Y-%m')].append(week.id)
        return [
            (
                self.env['training.week'].browse(ids[0]).date_debut.strftime('%B %Y').capitalize(),
                self.env['training.week'].browse(ids),
            )
            for ids in [groupes[k] for k in sorted(groupes)]
        ]

    def get_bilan_bc(self):
        """Retourne [(bloc_name, total_heures), ...] pour les BCs, triés par nom."""
        totaux = {}
        for line in self.week_ids.mapped('week_line_ids'):
            bloc = line.module_id.bloc_id
            if bloc and bloc.type_bloc in ('bc', 'transversal'):
                totaux[bloc.name] = totaux.get(bloc.name, 0.0) + line.heures
        return sorted(totaux.items(), key=lambda x: x[0])

    def action_ouvrir_ruban_wizard(self):
        ctx = {
            'default_session_id': self.id,
        }
        if self.date_debut:
            ctx['default_date_debut_souhaitee'] = str(self.date_debut)
        if self.date_fin:
            ctx['default_date_fin_approximative'] = str(self.date_fin)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Construction du ruban pédagogique',
            'res_model': 'training.ruban.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    @api.model
    def _cron_generer_presences(self):
        """Génère les présences pour les semaines imminentes (7 jours) dont tous
        les intervenants sont définis."""
        from datetime import date, timedelta
        today = date.today()
        horizon = today + timedelta(days=7)
        weeks = self.env['training.week'].search([
            ('session_id.statut', '=', 'en_cours'),
            ('type_semaine', '=', 'formation'),
            ('date_debut', '>=', today),
            ('date_debut', '<=', horizon),
            ('all_intervenants_definis', '=', True),
        ])
        if weeks:
            weeks.action_generer_presences()

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            name = rec.name or '?'
            if rec.date_debut and rec.date_fin:
                name += f' ({rec.date_debut.year}–{rec.date_fin.year})'
            rec.display_name = name