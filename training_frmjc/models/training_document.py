from odoo import models, fields


class TrainingDocument(models.Model):
    _name = 'training.document'
    _description = 'Document généré (convention, attestation, certificat...)'

    name = fields.Char(string='Nom', required=True)
    type_document = fields.Selection(
        selection=[
            ('convention_prestation', 'Convention de prestation'),
            ('convention_alternance', 'Convention d\'alternance'),
            ('convention_formation', 'Convention de formation'),
            ('attestation_mensuelle', 'Attestation mensuelle de présence'),
            ('certificat_module', 'Certificat de réalisation par module'),
            ('certificat_complet', 'Certificat de réalisation complet'),
            ('autre', 'Autre'),
        ],
        string='Type de document',
    )
    session_id = fields.Many2one(
        'training.session',
        string='Session liée',
    )
    stagiaire_id = fields.Many2one(
        'res.partner',
        string='Stagiaire lié',
    )
    date_generation = fields.Datetime(string='Date de génération')
    date_envoi = fields.Datetime(string='Date d\'envoi')
    statut_signature = fields.Selection(
        selection=[
            ('non_requise', 'Non requise'),
            ('en_attente', 'En attente'),
            ('signee', 'Signée'),
        ],
        string='Statut de signature',
        default='non_requise',
    )
    fichier_pdf = fields.Binary(string='Fichier PDF')