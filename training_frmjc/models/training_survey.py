import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TrainingSurvey(models.Model):
    _name = 'training.survey'
    _description = 'Enquête de formation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'session_id, type_enquete'

    # ── Relations ─────────────────────────────────────────────────────
    session_id = fields.Many2one(
        'training.session', string='Session',
        required=True, ondelete='cascade', index=True,
    )
    survey_id = fields.Many2one(
        'survey.survey', string='Questionnaire Odoo',
        required=True, ondelete='restrict',
    )
    bloc_id = fields.Many2one(
        'training.bloc', string='Bloc de compétences',
        domain=[('type_bloc', '=', 'bc')],
        help='Renseigner pour les enquêtes liées à un BC spécifique (fin de BC).',
    )

    # ── Type et statut ────────────────────────────────────────────────
    type_enquete = fields.Selection([
        ('fin_bc',      'Fin de bloc de compétences'),
        ('post_6mois',  'Post-formation 6 mois'),
        ('satisfaction', 'Satisfaction formation'),
        ('autre',        'Autre'),
    ], string="Type d'enquête", required=True, tracking=True)

    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('envoye',    'Envoyée'),
        ('clos',      'Clôturée'),
    ], string='Statut', default='brouillon', required=True, tracking=True)

    # ── Dates ─────────────────────────────────────────────────────────
    date_envoi = fields.Datetime(string='Date d\'envoi', readonly=True)
    date_cloture = fields.Date(string='Date de clôture')

    # ── Compteurs ─────────────────────────────────────────────────────
    nb_invitations = fields.Integer(
        string='Invitations', compute='_compute_nb_reponses', store=False,
    )
    nb_reponses = fields.Integer(
        string='Réponses reçues', compute='_compute_nb_reponses', store=False,
    )
    taux_reponse = fields.Float(
        string='Taux de réponse (%)', compute='_compute_nb_reponses', store=False,
        digits=(4, 1),
    )

    notes = fields.Text(string='Notes')

    # ── Compute ───────────────────────────────────────────────────────
    def _compute_display_name(self):
        labels = dict(self._fields['type_enquete'].selection)
        for rec in self:
            label = labels.get(rec.type_enquete, rec.type_enquete or '?')
            session = rec.session_id.name or '?'
            rec.display_name = f'{label} — {session}'

    def _compute_nb_reponses(self):
        UserInput = self.env['survey.user_input']
        for rec in self:
            if not rec.survey_id:
                rec.nb_invitations = rec.nb_reponses = 0
                rec.taux_reponse = 0.0
                continue
            all_inputs = UserInput.search([('survey_id', '=', rec.survey_id.id)])
            done = all_inputs.filtered(lambda i: i.state == 'done')
            nb_inv = len(all_inputs)
            nb_rep = len(done)
            rec.nb_invitations = nb_inv
            rec.nb_reponses = nb_rep
            rec.taux_reponse = (nb_rep / nb_inv * 100) if nb_inv else 0.0

    # ── Actions ───────────────────────────────────────────────────────
    def action_envoyer(self):
        """Crée une invitation survey.user_input par stagiaire accepté et envoie l'email."""
        self.ensure_one()
        if not self.survey_id:
            raise UserError('Aucun questionnaire associé.')
        inscriptions = self.session_id.inscription_ids.filtered(
            lambda i: i.statut == 'accepte' and i.partner_id.email
        )
        if not inscriptions:
            raise UserError(
                'Aucun stagiaire accepté avec une adresse email dans cette session.'
            )
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        nb = 0
        for insc in inscriptions:
            user_input = self.env['survey.user_input'].sudo().create({
                'survey_id': self.survey_id.id,
                'partner_id': insc.partner_id.id,
                'email': insc.partner_id.email,
            })
            survey_url = (
                f'{base_url}/survey/start/'
                f'{self.survey_id.access_token}/{user_input.access_token}'
            )
            self.env['mail.mail'].sudo().create({
                'subject': f'{self.survey_id.title} — {self.session_id.name}',
                'body_html': f"""
                    <p>Bonjour {insc.partner_id.name},</p>
                    <p>Nous vous invitons à répondre à l'enquête :
                    <strong>{self.survey_id.title}</strong>.</p>
                    <p><a href="{survey_url}">Accéder à l'enquête</a></p>
                    <p>Merci pour votre participation.</p>
                    <p>L'équipe FRMJC</p>
                """,
                'email_to': insc.partner_id.email,
                'auto_delete': True,
            }).send()
            nb += 1

        self.write({'statut': 'envoye', 'date_envoi': fields.Datetime.now()})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Enquête envoyée',
                'message': f'{nb} invitation(s) envoyée(s).',
                'type': 'success',
            },
        }

    def action_clore(self):
        self.write({'statut': 'clos'})

    def action_remettre_brouillon(self):
        self.filtered(lambda r: r.statut != 'clos').write({'statut': 'brouillon'})

    def action_ouvrir_questionnaire(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.survey_id.title,
            'res_model': 'survey.survey',
            'res_id': self.survey_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_voir_resultats(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Réponses — {self.survey_id.title}',
            'res_model': 'survey.user_input',
            'domain': [('survey_id', '=', self.survey_id.id)],
            'view_mode': 'list,form',
            'context': {'default_survey_id': self.survey_id.id},
        }

    # ── Cron ──────────────────────────────────────────────────────────
    @api.model
    def _cron_envoyer_enquetes_post_6mois(self):
        """Envoie les enquêtes post-formation 6 mois aux sessions terminées il y a 6 mois."""
        from datetime import date
        from dateutil.relativedelta import relativedelta

        seuil = date.today() - relativedelta(months=6)
        sessions = self.env['training.session'].search([
            ('statut', '=', 'termine'),
            ('date_fin', '=', seuil),
        ])
        for session in sessions:
            enquetes = self.search([
                ('session_id', '=', session.id),
                ('type_enquete', '=', 'post_6mois'),
                ('statut', '=', 'brouillon'),
            ])
            for enquete in enquetes:
                try:
                    enquete.action_envoyer()
                except Exception as exc:
                    _logger.warning('Enquête post 6 mois session %s: %s', session.id, exc)
