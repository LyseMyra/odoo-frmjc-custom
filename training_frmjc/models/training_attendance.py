import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class TrainingAttendance(models.Model):
    _name = 'training.attendance'
    _description = 'Présence en formation'
    _order = 'date desc, inscription_id, demi_journee'

    # ── Relations ─────────────────────────────────────────────────────
    inscription_id = fields.Many2one(
        'training.inscription', string='Inscription',
        required=True, ondelete='cascade', index=True,
    )
    partner_id = fields.Many2one(
        related='inscription_id.partner_id', store=True, readonly=True, string='Stagiaire',
    )
    session_id = fields.Many2one(
        related='inscription_id.session_id', store=True, readonly=True, string='Session',
    )
    formation_id = fields.Many2one(
        related='inscription_id.formation_id', store=True, readonly=True, string='Formation',
    )

    # ── Planification ────────────────────────────────────────────────
    date = fields.Date(string='Date', required=True, index=True)
    demi_journee = fields.Selection([
        ('matin',      'Matin'),
        ('apres_midi', 'Après-midi'),
    ], string='Demi-journée', required=True, default='matin')
    heures = fields.Float(string='Heures', default=3.5)
    mois_annee = fields.Char(
        string='Mois (YYYY-MM)', compute='_compute_mois_annee', store=True, index=True,
    )

    # ── Statut ────────────────────────────────────────────────────────
    statut = fields.Selection([
        ('a_confirmer', 'À confirmer'),
        ('present',     'Présent(e)'),
        ('absent',      'Absent(e)'),
        ('justifie',    'Absent(e) justifié(e)'),
    ], string='Statut', default='a_confirmer', required=True)

    # ── Confirmation portail ──────────────────────────────────────────
    confirme_le = fields.Datetime(string='Confirmé le')
    signature = fields.Binary(string='Signature électronique', attachment=True)
    signature_filename = fields.Char(default='signature.png')

    # ── Absence ───────────────────────────────────────────────────────
    motif_absence = fields.Text(string='Motif / justificatif')
    justificatif = fields.Binary(string='Justificatif', attachment=True)
    justificatif_filename = fields.Char()
    date_justificatif = fields.Date(string='Date du justificatif')

    relance_envoyee = fields.Boolean(default=False, string='Relance envoyée')
    date_relance = fields.Date(string='Date de la relance')

    # ── Formateur ────────────────────────────────────────────────────
    intervenant_id = fields.Many2one(
        'res.partner', string='Intervenant', index=True,
        help='Intervenant responsable de cette demi-journée (défini lors de la génération)',
    )
    valide_intervenant = fields.Boolean(string='Confirmé par l\'intervenant', default=False)
    valide_intervenant_le = fields.Datetime(string='Confirmé par l\'intervenant le')
    note_formateur = fields.Text(string='Note intervenant')

    est_valide = fields.Boolean(
        string='Présence validée',
        compute='_compute_est_valide', store=True,
        help='Vraie si le stagiaire ET l\'intervenant ont tous deux confirmé',
    )

    # ── Contrainte d'unicité ─────────────────────────────────────────
    _presence_unique = models.Constraint(
        'UNIQUE(inscription_id, date, demi_journee)',
        'Une présence existe déjà pour ce stagiaire à cette date / demi-journée.',
    )

    @api.depends('statut', 'valide_intervenant')
    def _compute_est_valide(self):
        for rec in self:
            rec.est_valide = (rec.statut == 'present' and rec.valide_intervenant)

    @api.depends('date')
    def _compute_mois_annee(self):
        for rec in self:
            rec.mois_annee = rec.date.strftime('%Y-%m') if rec.date else ''

    def _compute_display_name(self):
        labels = {'matin': 'Matin', 'apres_midi': 'Après-midi'}
        for rec in self:
            date_str = rec.date.strftime('%d/%m/%Y') if rec.date else '?'
            dj = labels.get(rec.demi_journee, '?')
            rec.display_name = f'{rec.partner_id.name or "?"} — {date_str} ({dj})'

    # ── Actions back-office ───────────────────────────────────────────
    def action_marquer_present(self):
        now = fields.Datetime.now()
        self.write({
            'statut': 'present',
            'confirme_le': now,
            'valide_intervenant': True,
            'valide_intervenant_le': now,
        })

    def action_marquer_absent(self):
        self.write({'statut': 'absent'})

    def action_justifier(self):
        self.write({'statut': 'justifie'})

    # ── Crons ────────────────────────────────────────────────────────
    @api.model
    def _cron_marquer_absences(self):
        """Marque comme absent tout record 'à confirmer' dont le délai est dépassé."""
        from datetime import datetime
        import pytz
        now_utc = fields.Datetime.now()
        today = fields.Date.today()

        # France timezone (Europe/Paris) — simplifié : UTC+1 en hiver, UTC+2 en été
        # Déadlines France : 10h matin → UTC≈8h, 15h après-midi → UTC≈13h
        records = self.search([
            ('statut', '=', 'a_confirmer'),
            ('date', '<=', today),
        ])
        for rec in records:
            if rec.date < today:
                rec.statut = 'absent'
            elif rec.date == today:
                hour_utc = now_utc.hour
                if rec.demi_journee == 'matin' and hour_utc >= 8:
                    rec.statut = 'absent'
                elif rec.demi_journee == 'apres_midi' and hour_utc >= 13:
                    rec.statut = 'absent'

    @api.model
    def _cron_relancer_absences(self):
        """Envoie une relance pour les absences non justifiées du jour précédent."""
        from datetime import timedelta
        seuil = fields.Date.today() - timedelta(days=1)
        records = self.search([
            ('statut', '=', 'absent'),
            ('date', '<=', seuil),
            ('motif_absence', '=', False),
            ('justificatif', '=', False),
            ('relance_envoyee', '=', False),
        ])
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        labels_dj = {'matin': 'matin', 'apres_midi': 'après-midi'}
        for rec in records:
            if not rec.partner_id.email:
                continue
            try:
                token = rec.inscription_id.portal_token
                self.env['mail.mail'].sudo().create({
                    'subject': (
                        f'Absence à justifier — {rec.date.strftime("%d/%m/%Y")}'
                        f' ({labels_dj.get(rec.demi_journee, rec.demi_journee)})'
                    ),
                    'body_html': f"""
                        <p>Bonjour {rec.partner_id.name},</p>
                        <p>Nous n'avons pas reçu de confirmation de votre présence
                        pour la demi-journée du
                        <strong>{rec.date.strftime('%d/%m/%Y')}
                        ({labels_dj.get(rec.demi_journee, rec.demi_journee)})</strong>.</p>
                        <p>Merci de vous connecter à votre espace stagiaire pour
                        confirmer votre présence ou déposer un justificatif d'absence.</p>
                        <p>
                            <a href="{base_url}/espace-stagiaire/{token}/presences"
                               style="background:#1a5276;color:#fff;padding:10px 20px;
                                      border-radius:4px;text-decoration:none;">
                                Accéder à mes présences
                            </a>
                        </p>
                        <p>L'équipe FRMJC</p>
                    """,
                    'email_to': rec.partner_id.email,
                    'auto_delete': True,
                }).send()
                rec.write({
                    'relance_envoyee': True,
                    'date_relance': fields.Date.today(),
                })
            except Exception as exc:
                _logger.warning('Relance absence %s: %s', rec.id, exc)
