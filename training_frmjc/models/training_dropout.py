import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class TrainingDropout(models.Model):
    _name = 'training.dropout'
    _description = 'Fiche abandon / interruption de formation'
    _inherit = ['mail.thread']
    _order = 'date_abandon desc'
    _rec_name = 'inscription_id'

    inscription_id = fields.Many2one(
        'training.inscription', string='Dossier d\'inscription',
        required=True, ondelete='cascade', tracking=True,
    )
    partner_id = fields.Many2one(
        related='inscription_id.partner_id', store=True, readonly=True,
        string='Candidat',
    )
    session_id = fields.Many2one(
        related='inscription_id.session_id', store=True, readonly=True,
        string='Session',
    )
    date_abandon = fields.Date(
        string='Date d\'abandon', required=True, default=fields.Date.today, tracking=True
    )
    motif = fields.Selection([
        ('personnel', 'Raison personnelle'),
        ('professionnel', 'Raison professionnelle'),
        ('medical', 'Raison médicale'),
        ('pedagogique', 'Difficulté pédagogique'),
        ('financier', 'Difficulté financière'),
        ('reorientation', 'Réorientation de projet'),
        ('autre', 'Autre'),
    ], string='Motif', required=True, tracking=True)
    description = fields.Text(string='Description / Commentaires')
    remboursement_applicable = fields.Boolean(
        string='Remboursement applicable', default=False
    )
    montant_remboursement = fields.Float(string='Montant remboursé (€)')
    semaine_abandon_id = fields.Many2one(
        'training.week', string='Semaine d\'abandon',
        domain="[('session_id', '=', session_id)]",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.inscription_id.sudo().write({'statut': 'abandon'})
        return records

    def _envoyer_attestation_abandon(self):
        """Génère le PDF d'attestation d'abandon et l'envoie par email au stagiaire."""
        self.ensure_one()
        email = self.partner_id.email
        if not email:
            _logger.info(
                'Attestation abandon non envoyée pour %s : pas d\'email.',
                self.partner_id.name,
            )
            return
        try:
            report = self.env['ir.actions.report']._get_report_from_name(
                'training_frmjc.tmpl_attestation_abandon'
            )
            pdf_content, _ = report.sudo()._render_qweb_pdf(self.ids)
            filename = (
                f'attestation_abandon_{self.partner_id.name or "stagiaire"}'
                f'_{self.date_abandon or fields.Date.today()}.pdf'
            ).replace(' ', '_')
            attachment = self.env['ir.attachment'].sudo().create({
                'name': filename,
                'type': 'binary',
                'datas': pdf_content,
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            motif_labels = {
                'personnel': 'Raison personnelle',
                'professionnel': 'Raison professionnelle',
                'medical': 'Raison médicale',
                'pedagogique': 'Difficulté pédagogique',
                'financier': 'Difficulté financière',
                'reorientation': 'Réorientation de projet',
                'autre': 'Autre',
            }
            date_str = (
                self.date_abandon.strftime('%d/%m/%Y')
                if self.date_abandon else fields.Date.today().strftime('%d/%m/%Y')
            )
            motif_str = motif_labels.get(self.motif, self.motif or '—')
            self.env['mail.mail'].sudo().create({
                'subject': (
                    f'Attestation d\'abandon de formation'
                    f' — {self.inscription_id.formation_id.intitule or self.session_id.name}'
                ),
                'body_html': f"""
                    <p>Bonjour {self.partner_id.name},</p>
                    <p>Nous vous adressons ci-joint l'attestation d'abandon concernant
                    votre participation à la formation
                    <strong>{self.inscription_id.formation_id.intitule or '—'}</strong>
                    (session : {self.session_id.name or '—'}).</p>
                    <p><strong>Date d'abandon :</strong> {date_str}<br/>
                    <strong>Motif :</strong> {motif_str}</p>
                    <p>Ce document vous est transmis à titre de preuve et peut être
                    communiqué à votre organisme financeur le cas échéant.</p>
                    <p>Cordialement,<br/>{self.env.company.name}</p>
                """,
                'email_to': email,
                'attachment_ids': [(4, attachment.id)],
                'auto_delete': False,
            }).send()
            _logger.info(
                'Attestation abandon envoyée à %s pour dossier %s.',
                email, self.inscription_id.reference,
            )
        except Exception as exc:
            _logger.warning(
                'Impossible d\'envoyer l\'attestation abandon %s : %s', self.id, exc,
            )

    def action_telecharger_attestation(self):
        return self.env.ref(
            'training_frmjc.report_training_attestation_abandon'
        ).report_action(self)

    def action_envoyer_attestation(self):
        """Bouton : renvoie l'attestation d'abandon par email."""
        for rec in self:
            rec._envoyer_attestation_abandon()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Email envoyé',
                'message': 'L\'attestation d\'abandon a été envoyée par email.',
                'type': 'success',
            },
        }

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f'Abandon {rec.partner_id.name or "?"}'
                f' – {rec.date_abandon or "?"}'
            )
