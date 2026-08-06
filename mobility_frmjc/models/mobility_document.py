from odoo import models, fields


class MobilityDocument(models.Model):
    _name = 'mobility.document'
    _description = 'Document lié à une mobilité (objet transversal)'
    _order = 'upload_date desc'

    # ── Rattachements ──────────────────────────────────────────────
    mobility_id = fields.Many2one(
        'mobility.mobility',
        string='Mobilité',
        ondelete='cascade',
        help="Non obligatoire : un document peut être déposé avant la "
             "création formelle du dossier de mobilité (ex : fiche de "
             "renseignement reçue avant sélection définitive).",
    )
    activity_id = fields.Many2one(
        'mobility.activity',
        string='Activité / offre liée',
        help='Optionnel.',
    )
    participant_id = fields.Many2one(
        'res.partner',
        string='Volontaire',
        help="Optionnel, redondant avec la mobilité une fois liée — utile "
             "pour les documents déposés avant la création du dossier "
             "(ex : fiche de renseignement).",
    )

    # ── Classification ────────────────────────────────────────────
    document_type = fields.Selection(
        selection=[
            ('fiche_renseignement', 'Fiche renseignement'),
            ('convention_volontariat', 'Convention volontariat'),
            ('visa', 'VISA'),
            ('attestation_hebergement', 'Attestation hébergement'),
            ('attestation_transport', 'Attestation transport'),
            ('attestation_fin_volontariat', 'Attestation fin de volontariat'),
            ('justificatif_finance', 'Justificatif finance'),
            ('autre', 'Autre'),
        ],
        string='Type de document',
        required=True,
        default='autre',
    )
    statut = fields.Selection(
        selection=[
            ('a_emettre', 'À émettre'),
            ('valide', 'Valide'),
            ('a_remettre', 'À remettre'),
        ],
        string='Statut',
        required=True,
        default='a_emettre',
    )

    # ── Fichier ────────────────────────────────────────────────────
    attachment = fields.Binary(string='Pièce jointe', attachment=True)
    attachment_filename = fields.Char()
    upload_date = fields.Date(string="Date d'ajout", default=fields.Date.today)
    emis_par = fields.Char(
        string='Émis par',
        help='Ex : structure d\'accueil, plateforme BM, DRAJES... — saisie libre.',
    )
    notes = fields.Text(string='Remarques')

    # ── Représentation ────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            label = dict(rec._fields['document_type'].selection).get(
                rec.document_type, '?'
            )
            if rec.participant_id:
                label += f' — {rec.participant_id.name}'
            rec.display_name = label
