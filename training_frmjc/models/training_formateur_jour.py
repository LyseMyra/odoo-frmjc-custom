import uuid
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class TrainingFormateurJour(models.Model):
    _name = 'training.formateur.jour'
    _description = 'Liste de présence journalière — intervenant'
    _order = 'date desc, intervenant_id'

    session_id = fields.Many2one(
        'training.session', required=True, ondelete='cascade', index=True,
        string='Session',
    )
    intervenant_id = fields.Many2one(
        'res.partner', required=True, ondelete='cascade', index=True,
        string='Intervenant',
    )
    date = fields.Date(required=True, index=True, string='Date')
    token = fields.Char(
        string='Token', copy=False, index=True,
        default=lambda self: str(uuid.uuid4()),
    )
    envoye_le = fields.Datetime(string='Email envoyé le')
    confirme_le = fields.Datetime(string='Confirmé le')
    nb_presents = fields.Integer(string='Présents confirmés', compute='_compute_nb', store=False)
    nb_total = fields.Integer(string='Total', compute='_compute_nb', store=False)

    _formateur_jour_unique = models.Constraint(
        'UNIQUE(session_id, intervenant_id, date)',
        'Un enregistrement existe déjà pour cet intervenant, cette session et cette date.',
    )

    def _compute_display_name(self):
        for rec in self:
            date_str = rec.date.strftime('%d/%m/%Y') if rec.date else '?'
            rec.display_name = f'{rec.intervenant_id.name or "?"} — {date_str}'

    def _compute_nb(self):
        Attendance = self.env['training.attendance']
        for rec in self:
            atts = Attendance.search([
                ('session_id', '=', rec.session_id.id),
                ('date', '=', rec.date),
                ('intervenant_id', '=', rec.intervenant_id.id),
            ])
            rec.nb_total = len(atts)
            rec.nb_presents = len(atts.filtered(lambda a: a.valide_intervenant))

    def get_attendances(self):
        """Retourne tous les stagiaires attendus ce jour dans la session, quel que soit l'intervenant assigné."""
        self.ensure_one()
        return self.env['training.attendance'].search([
            ('session_id', '=', self.session_id.id),
            ('date', '=', self.date),
        ], order='partner_id, demi_journee')

    def action_envoyer_email(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        dj_labels = {'matin': 'Matin', 'apres_midi': 'Après-midi'}
        nb_envoyes = 0
        sans_email = []
        sans_stagiaires = []
        for rec in self:
            if not rec.intervenant_id.email:
                sans_email.append(rec.intervenant_id.name or '?')
                continue
            attendances = rec.get_attendances()
            if not attendances:
                sans_stagiaires.append(
                    f'{rec.intervenant_id.name} ({rec.date.strftime("%d/%m/%Y") if rec.date else "?"})'
                )
                continue
            date_str = rec.date.strftime('%d/%m/%Y') if rec.date else '?'
            # Dédoublonner par stagiaire (une ligne par stagiaire, matin+AM groupés)
            stagiaires_vus = {}
            for a in attendances:
                nom = a.partner_id.name or '?'
                dj = dj_labels.get(a.demi_journee, '')
                stagiaires_vus.setdefault(nom, []).append(dj)
            stagiaires_html = ''.join(
                f'<li>{nom} ({" + ".join(djs)})</li>'
                for nom, djs in sorted(stagiaires_vus.items())
            )
            try:
                self.env['mail.mail'].sudo().create({
                    'subject': f'Liste de présence du {date_str} — {rec.session_id.name}',
                    'body_html': f"""
                        <p>Bonjour {rec.intervenant_id.name},</p>
                        <p>Vous intervenez le <strong>{date_str}</strong> pour la session
                        <strong>{rec.session_id.name}</strong>.</p>
                        <p>Stagiaires attendus ({len(stagiaires_vus)}) :</p>
                        <ul>{stagiaires_html}</ul>
                        <p>Merci de confirmer les présences après votre intervention en cliquant
                        sur le lien ci-dessous.</p>
                        <p>
                            <a href="{base_url}/formation/formateur/{rec.token}"
                               style="background:#1a5276;color:#fff;padding:10px 20px;
                                      border-radius:4px;text-decoration:none;display:inline-block;">
                                Confirmer les présences
                            </a>
                        </p>
                        <p>L'équipe FRMJC</p>
                    """,
                    'email_to': rec.intervenant_id.email,
                    'auto_delete': False,
                }).send()
                rec.envoye_le = fields.Datetime.now()
                nb_envoyes += 1
            except Exception as exc:
                _logger.warning('Envoi liste formateur %s: %s', rec.id, exc)
        if sans_email:
            _logger.warning('Intervenants sans email (liste non envoyée) : %s', ', '.join(sans_email))
        if sans_stagiaires:
            _logger.warning('Aucun stagiaire trouvé pour : %s', ', '.join(sans_stagiaires))
        return nb_envoyes

    @api.model
    def _cron_envoyer_listes_jour(self):
        today = fields.Date.today()
        records = self.search([
            ('date', '=', today),
            ('envoye_le', '=', False),
        ])
        if records:
            records.action_envoyer_email()
