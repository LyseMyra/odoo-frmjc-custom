from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError


class TrainingRubanWizard(models.TransientModel):
    _name = 'training.ruban.wizard'
    _description = 'Assistant de construction du ruban pédagogique'

    state = fields.Selection(
        selection=[
            ('etape1', 'Paramétrage'),
            ('etape2', 'Sélection des semaines'),
        ],
        default='etape1',
    )

    # ── Étape 1 ────────────────────────────────────────────────────
    session_id = fields.Many2one(
        'training.session',
        string='Session',
        required=True,
    )
    date_debut_souhaitee = fields.Date(
        string='Date de début souhaitée',
        required=True,
    )
    date_fin_approximative = fields.Date(
        string='Date de fin approximative',
        required=True,
    )

    # ── Étape 2 ────────────────────────────────────────────────────
    semaine_candidate_ids = fields.One2many(
        'training.ruban.wizard.semaine',
        'wizard_id',
        string='Semaines candidates',
    )
    nb_semaines_formation_selectionnees = fields.Integer(
        string='Semaines de formation sélectionnées',
        compute='_compute_compteurs',
    )
    nb_semaines_hors_formation = fields.Integer(
        string='Semaines hors-formation',
        compute='_compute_compteurs',
    )

    @api.onchange('session_id')
    def _onchange_session_id(self):
        if self.session_id:
            self.date_debut_souhaitee = self.session_id.date_debut
            self.date_fin_approximative = self.session_id.date_fin

    @api.depends('semaine_candidate_ids.selectionnee', 'semaine_candidate_ids.type_semaine')
    def _compute_compteurs(self):
        for rec in self:
            sel = rec.semaine_candidate_ids.filtered('selectionnee')
            rec.nb_semaines_formation_selectionnees = len(
                sel.filtered(lambda s: s.type_semaine == 'formation')
            )
            rec.nb_semaines_hors_formation = len(
                sel.filtered(lambda s: s.type_semaine != 'formation')
            )

    # ── Étape 1 → 2 ────────────────────────────────────────────────
    def action_generer_semaines(self):
        self.ensure_one()
        if self.date_fin_approximative <= self.date_debut_souhaitee:
            raise UserError('La date de fin doit être postérieure à la date de début.')

        self.semaine_candidate_ids.unlink()

        jours_feries = self._get_jours_feries(
            self.date_debut_souhaitee, self.date_fin_approximative
        )

        # Semaines déjà construites pour cette session : indexées par date_debut
        existing_weeks = {w.date_debut: w for w in self.session_id.week_ids}

        date_courante = self.date_debut_souhaitee
        date_courante -= timedelta(days=date_courante.weekday())

        candidates = []
        while date_courante <= self.date_fin_approximative:
            date_fin_semaine = date_courante + timedelta(days=4)
            jours_feries_semaine = [
                j for j in jours_feries
                if date_courante <= j <= date_fin_semaine
            ]
            if not jours_feries_semaine:
                existing = existing_weeks.get(date_courante)
                candidates.append({
                    'wizard_id': self.id,
                    'date_debut': date_courante,
                    'date_fin': date_fin_semaine,
                    'statut_propose': 'a_statut_libre',
                    'contient_jour_ferie': False,
                    'selectionnee': bool(existing),
                    'type_semaine': existing.type_semaine if existing else 'formation',
                    'numero_semaine': existing.numero_semaine if existing else 0,
                })
            date_courante += timedelta(days=7)

        self.env['training.ruban.wizard.semaine'].create(candidates)
        self.state = 'etape2'
        return self._reopen_wizard()

    def _get_jours_feries(self, date_debut, date_fin):
        leaves = self.env['resource.calendar.leaves'].search([
            ('date_from', '<=', fields.Datetime.to_datetime(date_fin)),
            ('date_to', '>=', fields.Datetime.to_datetime(date_debut)),
        ])
        return {leave.date_from.date() for leave in leaves}

    def _reopen_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'training.ruban.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_retour_etape1(self):
        self.state = 'etape1'
        return self._reopen_wizard()

    # ── Étape 2 → Fin ──────────────────────────────────────────────
    def action_valider_selection(self):
        self.ensure_one()
        selectionnees = self.semaine_candidate_ids.filtered('selectionnee').sorted('date_debut')
        if not selectionnees:
            raise UserError('Aucune semaine sélectionnée.')

        nb_formation = len(selectionnees.filtered(lambda s: s.type_semaine == 'formation'))
        if nb_formation != 20:
            raise UserError(
                f'Le DEJEPS exige exactement 20 semaines de formation '
                f'(sélectionnées : {nb_formation}).'
            )

        # Remplacer les semaines existantes par la nouvelle sélection
        self.session_id.week_ids.unlink()
        formation_counter = 0
        for candidate in selectionnees:
            is_formation = candidate.type_semaine == 'formation'

            if is_formation:
                # Semaines de formation : plage lun→ven, auto-numérotation 1..20
                formation_counter += 1
                numero = (candidate.numero_semaine
                          if candidate.numero_semaine > 0 else formation_counter)
                date_d = candidate.date_debut
                date_f = candidate.date_fin
            else:
                # Événements ponctuels (certification, remédiation…) : journée unique
                numero = candidate.numero_semaine  # 0 = non numéroté, OK
                date_j = candidate.date_jour or candidate.date_debut
                date_d = date_j
                date_f = date_j

            week = self.env['training.week'].create({
                'session_id': self.session_id.id,
                'numero_semaine': numero,
                'date_debut': date_d,
                'date_fin': date_f,
                'statut': 'incluse',
                'type_semaine': candidate.type_semaine,
                'motif_exclusion': candidate.motif_exclusion,
            })

            # Auto-remplissage depuis la répartition référentielle du module
            if is_formation and numero > 0:
                repartitions = self.env['training.module.repartition'].search([
                    ('semaine', '=', numero),
                    ('formation_id', '=', self.session_id.formation_id.id),
                ])
                for rep in repartitions:
                    self.env['training.week.line'].create({
                        'week_id': week.id,
                        'module_id': rep.module_id.id,
                        'jour': rep.jour,
                        'heures': rep.heures,
                    })

        # Fermer le wizard et retourner à la fiche session
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'training.session',
            'res_id': self.session_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
