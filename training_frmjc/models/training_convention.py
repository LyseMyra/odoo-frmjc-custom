import base64
import logging

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class TrainingConvention(models.Model):
    _name = 'training.convention'
    _description = 'Convention de formation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'numero'
    _order = 'date_creation desc'

    # ── Identification ─────────────────────────────────────────────
    numero = fields.Char(
        string='Numéro', readonly=True, copy=False, default='Nouveau', index=True
    )
    type_convention = fields.Selection([
        ('alternance', "Convention d'alternance"),
        ('formation_continue', 'Convention de formation continue'),
        ('cefa', 'Fiche CEFA (apprentissage)'),
    ], string='Type', required=True, default='alternance', tracking=True)

    # ── Inscription liée ───────────────────────────────────────────
    inscription_id = fields.Many2one(
        'training.inscription', string='Dossier candidat',
        required=True, ondelete='restrict', tracking=True,
    )
    partner_id = fields.Many2one(
        related='inscription_id.partner_id', store=True, string='Stagiaire',
    )
    session_id = fields.Many2one(
        related='inscription_id.session_id', store=True, string='Session',
    )
    formation_id = fields.Many2one(
        related='inscription_id.formation_id', store=True, string='Formation',
    )

    # ── Structure d'accueil ────────────────────────────────────────
    structure_accueil_id = fields.Many2one(
        'res.partner', string="Structure d'accueil",
        domain=[('is_structure_accueil', '=', True)],
    )
    tuteur_id = fields.Many2one(
        'res.partner', string="Tuteur / Maître d'apprentissage",
    )
    representant_frmjc_id = fields.Many2one(
        'res.partner', string='Représentant FRMJC',
    )

    # ── Dates ──────────────────────────────────────────────────────
    date_creation = fields.Date(default=fields.Date.today, string='Date de création')
    date_debut = fields.Date(string='Date de début de formation')
    date_fin = fields.Date(string='Date de fin de formation')

    # ── Financement ────────────────────────────────────────────────
    cout_total = fields.Float(string='Coût total (€)', digits=(10, 2))
    financement_ids = fields.One2many(
        'training.convention.financement', 'convention_id', string='Plan de financement',
    )
    total_finance = fields.Float(
        compute='_compute_total_finance', store=True, string='Total financé (€)', digits=(10, 2),
    )
    ecart_financement = fields.Float(
        compute='_compute_total_finance', store=True, string='Écart (€)', digits=(10, 2),
    )

    # ── Workflow ───────────────────────────────────────────────────
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('generee', 'Générée'),
        ('a_signer', 'À signer'),
        ('en_cours_signature', 'En cours de signature'),
        ('signee', 'Signée'),
        ('archivee', 'Archivée'),
    ], string='Statut', default='brouillon', required=True, tracking=True)

    # ── Document PDF ───────────────────────────────────────────────
    document_pdf = fields.Binary(string='PDF généré', attachment=True, copy=False)
    document_pdf_filename = fields.Char()
    document_signe_pdf = fields.Binary(string='PDF signé', attachment=True, copy=False)
    document_signe_filename = fields.Char()
    date_signature = fields.Datetime(string='Date de signature', readonly=True)

    # ── Odoo Sign (optionnel — module Enterprise) ──────────────────
    # Stocké en Integer pour ne pas dépendre du module 'sign' au niveau champ
    sign_request_id = fields.Integer(
        string='ID Sign Request', copy=False, readonly=True,
    )
    sign_request_state = fields.Char(
        string='État signature', compute='_compute_sign_state', readonly=True,
    )

    # ── Computed sign state ────────────────────────────────────────
    @api.depends('sign_request_id')
    def _compute_sign_state(self):
        for rec in self:
            if rec.sign_request_id and 'sign.request' in self.env:
                req = self.env['sign.request'].browse(rec.sign_request_id)
                rec.sign_request_state = req.state if req.exists() else False
            else:
                rec.sign_request_state = False

    # ── Contrainte financement ─────────────────────────────────────
    @api.depends('financement_ids.montant')
    def _compute_total_finance(self):
        for rec in self:
            total = sum(rec.financement_ids.mapped('montant'))
            rec.total_finance = total
            rec.ecart_financement = rec.cout_total - total

    @api.constrains('financement_ids', 'cout_total')
    def _check_financement(self):
        for rec in self:
            if rec.cout_total > 0 and abs(rec.ecart_financement) > 0.01:
                raise ValidationError(
                    f"Le total des financements ({rec.total_finance:.2f} €) "
                    f"ne correspond pas au coût total ({rec.cout_total:.2f} €). "
                    f"Écart : {rec.ecart_financement:.2f} €."
                )

    # ── Création ───────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        seq_codes = {
            'alternance': 'training.convention.alternance',
            'formation_continue': 'training.convention.formation',
            'cefa': 'training.convention.cefa',
        }
        for vals in vals_list:
            if vals.get('numero', 'Nouveau') == 'Nouveau':
                code = seq_codes.get(vals.get('type_convention', 'alternance'),
                                     'training.convention.alternance')
                vals['numero'] = self.env['ir.sequence'].next_by_code(code) or 'Nouveau'
        return super().create(vals_list)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.numero} — {rec.partner_id.name or "?"}'

    # ── Actions workflow ───────────────────────────────────────────
    def action_generer_pdf(self):
        """Génère le PDF de la convention via le bon rapport QWeb."""
        self.ensure_one()
        report_refs = {
            'alternance': 'training_frmjc.report_convention_alternance',
            'formation_continue': 'training_frmjc.report_convention_formation',
            'cefa': 'training_frmjc.report_convention_cefa',
        }
        report_ref = report_refs.get(self.type_convention)
        if not report_ref:
            raise UserError("Type de convention non reconnu.")

        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            report_ref, res_ids=[self.id]
        )
        filename = f'{self.numero}.pdf'
        self.write({
            'document_pdf': base64.b64encode(pdf_content),
            'document_pdf_filename': filename,
            'statut': 'generee',
        })
        self.message_post(body=f"PDF de la convention généré : {filename}")

    def action_marquer_a_signer(self):
        self.ensure_one()
        if not self.document_pdf:
            raise UserError("Générez d'abord le PDF avant de passer à la signature.")
        self.write({'statut': 'a_signer'})

    def action_envoyer_signature(self):
        """Envoie la convention pour signature via Odoo Sign."""
        self.ensure_one()
        if not self.document_pdf:
            raise UserError("Générez d'abord le PDF de la convention.")

        # Vérification que le module sign est disponible
        if 'sign.request' not in self.env:
            raise UserError(
                "Le module 'Signature Électronique' (sign) n'est pas installé. "
                "Installez-le depuis Apps pour utiliser cette fonctionnalité."
            )

        # Créer l'attachement depuis le PDF généré
        attachment = self.env['ir.attachment'].sudo().create({
            'name': self.document_pdf_filename or f'{self.numero}.pdf',
            'datas': self.document_pdf,
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        })

        # Récupérer ou créer le rôle de signature
        role = self.env['sign.item.role'].search([('name', '=', 'Signataire')], limit=1)
        if not role:
            role = self.env['sign.item.role'].create({'name': 'Signataire', 'color': 4})

        # Items de signature selon type (positions dans le PDF)
        sign_items = []
        sig_type = self.env.ref('sign.sign_item_type_signature')
        date_type = self.env.ref('sign.sign_item_type_date', raise_if_not_found=False)

        # Stagiaire — bas gauche de la dernière page
        sign_items.append((0, 0, {
            'type_id': sig_type.id,
            'role_id': role.id,
            'page': 1,
            'posX': 0.05,
            'posY': 0.82,
            'width': 0.22,
            'height': 0.07,
            'required': True,
            'name': 'Signature stagiaire',
        }))

        # FRMJC — bas centre
        sign_items.append((0, 0, {
            'type_id': sig_type.id,
            'role_id': role.id,
            'page': 1,
            'posX': 0.39,
            'posY': 0.82,
            'width': 0.22,
            'height': 0.07,
            'required': True,
            'name': 'Signature FRMJC',
        }))

        # Structure d'accueil — bas droite (uniquement pour alternance / CEFA)
        if self.type_convention in ('alternance', 'cefa') and self.structure_accueil_id:
            sign_items.append((0, 0, {
                'type_id': sig_type.id,
                'role_id': role.id,
                'page': 1,
                'posX': 0.73,
                'posY': 0.82,
                'width': 0.22,
                'height': 0.07,
                'required': True,
                'name': "Signature structure d'accueil",
            }))

        # Créer le template Sign
        template = self.env['sign.template'].sudo().create({
            'attachment_id': attachment.id,
            'sign_item_ids': sign_items,
        })

        # Construire la liste des signataires
        request_items = []
        if self.partner_id:
            request_items.append((0, 0, {
                'partner_id': self.partner_id.id,
                'role_id': role.id,
                'mail_sent_order': 1,
            }))
        if self.representant_frmjc_id:
            request_items.append((0, 0, {
                'partner_id': self.representant_frmjc_id.id,
                'role_id': role.id,
                'mail_sent_order': 2,
            }))
        if self.type_convention in ('alternance', 'cefa') and self.structure_accueil_id:
            signer = self.tuteur_id or self.structure_accueil_id
            request_items.append((0, 0, {
                'partner_id': signer.id,
                'role_id': role.id,
                'mail_sent_order': 3,
            }))

        if not request_items:
            raise UserError("Aucun signataire défini. Vérifiez le dossier candidat.")

        # Créer la demande de signature
        req = self.env['sign.request'].sudo().create({
            'template_id': template.id,
            'request_item_ids': request_items,
            'reference': self.numero,
            'subject': f'Convention à signer — {self.numero} ({self.partner_id.name})',
            'message': (
                f'Bonjour,\n\n'
                f'Veuillez signer la convention {self.numero} '
                f'pour la formation {self.formation_id.display_name}.\n\n'
                f'Cordialement,\nFRMJC'
            ),
        })
        req.action_sent()

        self.write({
            'sign_request_id': req.id,
            'statut': 'en_cours_signature',
        })
        self.message_post(
            body=f"Convention envoyée pour signature à {len(request_items)} signataire(s)."
        )

    def _get_sign_request(self):
        """Retourne le sign.request si le module Sign est disponible."""
        if self.sign_request_id and 'sign.request' in self.env:
            req = self.env['sign.request'].browse(self.sign_request_id)
            return req if req.exists() else None
        return None

    def action_synchroniser_signature(self):
        """Synchronise le statut depuis la demande Odoo Sign."""
        for rec in self:
            req = rec._get_sign_request()
            if not req:
                continue
            if req.state == 'signed':
                att = self.env['ir.attachment'].search([
                    ('res_model', '=', 'sign.request'),
                    ('res_id', '=', req.id),
                    ('mimetype', '=', 'application/pdf'),
                ], limit=1, order='id desc')
                vals = {'statut': 'signee', 'date_signature': fields.Datetime.now()}
                if att:
                    vals['document_signe_pdf'] = att.datas
                    vals['document_signe_filename'] = att.name
                rec.write(vals)
                rec.message_post(body="Convention signée par toutes les parties.")

    def action_archiver(self):
        self.write({'statut': 'archivee'})

    def action_voir_sign_request(self):
        self.ensure_one()
        if not self.sign_request_id:
            raise UserError("Aucune demande de signature en cours.")
        if 'sign.request' not in self.env:
            raise UserError("Le module Signature (Odoo Enterprise) n'est pas installé.")
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sign.request',
            'res_id': self.sign_request_id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_imprimer(self):
        self.ensure_one()
        report_refs = {
            'alternance': 'training_frmjc.report_convention_alternance',
            'formation_continue': 'training_frmjc.report_convention_formation',
            'cefa': 'training_frmjc.report_convention_cefa',
        }
        return self.env.ref(report_refs[self.type_convention]).report_action(self)


class TrainingConventionFinancement(models.Model):
    _name = 'training.convention.financement'
    _description = 'Ligne de financement convention'
    _order = 'sequence, id'

    convention_id = fields.Many2one(
        'training.convention', required=True, ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    source = fields.Selection([
        ('opco', 'OPCO / Branche professionnelle'),
        ('cpf', 'CPF (Compte Personnel de Formation)'),
        ('france_travail', 'France Travail / Pôle Emploi'),
        ('region', 'Région / Conseil Régional'),
        ('frmjc', 'FRMJC (fonds propres)'),
        ('autofinancement', 'Autofinancement stagiaire'),
        ('employeur', 'Employeur / Structure d\'accueil'),
        ('autre', 'Autre'),
    ], string='Source', required=True)
    organisme = fields.Char(string='Organisme / Détail')
    montant = fields.Float(string='Montant (€)', digits=(10, 2))
    pourcentage = fields.Float(
        string='%', compute='_compute_pourcentage', store=True, digits=(5, 1),
    )

    @api.depends('montant', 'convention_id.cout_total')
    def _compute_pourcentage(self):
        for line in self:
            total = line.convention_id.cout_total
            line.pourcentage = (line.montant / total * 100) if total else 0.0
