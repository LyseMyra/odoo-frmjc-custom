import uuid
import logging
from datetime import timedelta
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class TrainingFormateurSemaine(models.Model):
    _name = 'training.formateur.semaine'
    _description = 'Liste de présence hebdomadaire — intervenant'
    _order = 'week_start desc, intervenant_id'

    session_id = fields.Many2one(
        'training.session', required=True, ondelete='cascade', index=True,
        string='Session',
    )
    intervenant_id = fields.Many2one(
        'res.partner', required=True, ondelete='cascade', index=True,
        string='Intervenant',
    )
    week_start = fields.Date(required=True, index=True, string='Semaine du (lundi)')
    token = fields.Char(
        string='Token', copy=False, index=True,
        default=lambda self: str(uuid.uuid4()),
    )
    email_envoye_le = fields.Datetime(string='Email envoyé le')
    demi_journee_ids = fields.One2many(
        'training.formateur.demi_journee', 'semaine_id', string='Demi-journées',
    )
    nb_signes = fields.Integer(
        string='Signées', compute='_compute_nb', store=False,
    )
    nb_total_dj = fields.Integer(
        string='Total', compute='_compute_nb', store=False,
    )

    _semaine_unique = models.Constraint(
        'UNIQUE(session_id, intervenant_id, week_start)',
        'Un enregistrement existe déjà pour cet intervenant, cette session et cette semaine.',
    )

    def _compute_display_name(self):
        for rec in self:
            week_str = rec.week_start.strftime('%d/%m/%Y') if rec.week_start else '?'
            rec.display_name = f'{rec.intervenant_id.name or "?"} — Semaine du {week_str}'

    def _compute_nb(self):
        for rec in self:
            djs = rec.demi_journee_ids
            rec.nb_total_dj = len(djs)
            rec.nb_signes = len(djs.filtered(lambda d: d.statut == 'signe'))

    def action_envoyer_email(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        dj_labels = {'matin': 'Matin', 'apres_midi': 'Après-midi'}
        nb_envoyes = 0
        for rec in self:
            if not rec.intervenant_id.email:
                _logger.warning('Intervenant sans email : %s', rec.intervenant_id.name)
                continue
            if not rec.demi_journee_ids:
                continue
            week_str = rec.week_start.strftime('%d/%m/%Y') if rec.week_start else '?'
            rows = ''.join(
                '<tr>'
                f'<td style="padding:4px 8px;border:1px solid #ddd;">'
                f'{dj.date.strftime("%A %d/%m").capitalize() if dj.date else "?"}</td>'
                f'<td style="padding:4px 8px;border:1px solid #ddd;">'
                f'{dj_labels.get(dj.demi_journee, "")}</td>'
                '</tr>'
                for dj in rec.demi_journee_ids.sorted(lambda r: (r.date, r.demi_journee))
            )
            try:
                self.env['mail.mail'].sudo().create({
                    'subject': (
                        f'Listes de présence — Semaine du {week_str}'
                        f' — {rec.session_id.name}'
                    ),
                    'body_html': f"""
                        <p>Bonjour {rec.intervenant_id.name},</p>
                        <p>Vous intervenez durant la semaine du <strong>{week_str}</strong>
                        pour la session <strong>{rec.session_id.name}</strong>.</p>
                        <p>Demi-journées à valider :</p>
                        <table style="border-collapse:collapse;margin-bottom:12px;">
                          <thead><tr>
                            <th style="padding:4px 8px;border:1px solid #ddd;background:#f5f5f5;">Jour</th>
                            <th style="padding:4px 8px;border:1px solid #ddd;background:#f5f5f5;">Demi-journée</th>
                          </tr></thead>
                          <tbody>{rows}</tbody>
                        </table>
                        <p>Chaque demi-journée devient active le jour J (matin avant 13h,
                        après-midi à partir de 13h). Le lien reste valide toute la semaine.</p>
                        <p>
                          <a href="{base_url}/formation/intervenant/{rec.token}"
                             style="background:#1a5276;color:#fff;padding:10px 20px;
                                    border-radius:4px;text-decoration:none;display:inline-block;">
                            Accéder à ma liste de présence
                          </a>
                        </p>
                        <p>L'équipe FRMJC</p>
                    """,
                    'email_to': rec.intervenant_id.email,
                    'auto_delete': False,
                }).send()
                rec.email_envoye_le = fields.Datetime.now()
                nb_envoyes += 1
            except Exception as exc:
                _logger.warning('Envoi liste formateur semaine %s: %s', rec.id, exc)
        return nb_envoyes

    @api.model
    def _cron_envoyer_listes_semaine(self):
        """Envoie les listes de la semaine en cours chaque lundi matin."""
        from datetime import date
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        records = self.search([
            ('week_start', '=', monday),
            ('email_envoye_le', '=', False),
        ])
        if records:
            records.action_envoyer_email()


class TrainingFormateurDemiJournee(models.Model):
    _name = 'training.formateur.demi_journee'
    _description = 'Demi-journée de présence — intervenant'
    _order = 'date, demi_journee'

    semaine_id = fields.Many2one(
        'training.formateur.semaine', required=True, ondelete='cascade', index=True,
        string='Semaine',
    )
    date = fields.Date(required=True, string='Date')
    demi_journee = fields.Selection([
        ('matin', 'Matin'),
        ('apres_midi', 'Après-midi'),
    ], required=True, string='Demi-journée')
    signature = fields.Binary(string='Signature intervenant', attachment=True)
    signature_filename = fields.Char(default='signature_intervenant.png')
    signe_le = fields.Datetime(string='Signé le')
    statut = fields.Selection([
        ('en_attente', 'En attente'),
        ('signe', 'Signé'),
    ], default='en_attente', required=True, string='Statut')

    _dj_unique = models.Constraint(
        'UNIQUE(semaine_id, date, demi_journee)',
        'Un enregistrement existe déjà pour cette demi-journée dans cette semaine.',
    )

    def get_attendances(self):
        """Retourne tous les stagiaires de la session pour cette demi-journée."""
        self.ensure_one()
        return self.env['training.attendance'].search([
            ('session_id', '=', self.semaine_id.session_id.id),
            ('date', '=', self.date),
            ('demi_journee', '=', self.demi_journee),
        ], order='partner_id')

    def action_telecharger_feuille(self):
        return self.env.ref('training_frmjc.report_feuille_presence_dj').report_action(self)
