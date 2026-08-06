from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TrainingHabilitation(models.Model):
    _name = "training.habilitation"
    _description = "Habilitation DRAJES"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_obtention desc"
    _rec_name = "numero"

    # ── Champs principaux ──────────────────────────────────────────
    numero = fields.Char(
        string="Numéro d'habilitation",
        required=True,
        tracking=True,
        help="Ex : 22035-HABDE-0001",
    )
    type_formation = fields.Selection(
        selection=[
            ("dejeps", "DEJEPS"),
            ("desjeps", "DESJEPS"),
            ("bpjeps", "BPJEPS"),
            ("uniformation", "Uniformation"),
            ("interne", "Formation interne"),
        ],
        string="Type de formation",
        required=True,
        tracking=True,
    )
    specialite = fields.Char(string="Spécialité", tracking=True)
    mention = fields.Char(string="Mention", tracking=True)

    # ── Dates ──────────────────────────────────────────────────────
    date_obtention = fields.Date(
        string="Date d'obtention",
        required=True,
        tracking=True,
    )
    date_expiration = fields.Date(
        string="Date d'expiration",
        required=True,
        tracking=True,
        help="Valide 5 ans à compter de la date d'obtention",
    )

    # ── Statut calculé ─────────────────────────────────────────────
    statut = fields.Selection(
        selection=[
            ("valide", "Valide"),
            ("expiree", "Expirée"),
            ("bientot_expiree", "Expire bientôt (< 6 mois)"),
        ],
        string="Statut",
        compute="_compute_statut",
        store=True,
    )

    # ── Documents joints ───────────────────────────────────────────
    document_ids = fields.Many2many(
        "ir.attachment",
        string="Documents joints",
    )

    # ── Relations ──────────────────────────────────────────────────
    session_ids = fields.One2many(
        "training.session",
        "habilitation_id",
        string="Sessions associées",
    )
    nb_sessions = fields.Integer(
        string="Nombre de sessions",
        compute="_compute_nb_sessions",
    )

    # ── Contraintes SQL ────────────────────────────────────────────
    _numero_unique = models.Constraint(
        "UNIQUE(numero)", "Ce numéro d'habilitation existe déjà."
    )

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends("date_expiration")
    def _compute_statut(self):
        today = fields.Date.today()
        for rec in self:
            if not rec.date_expiration:
                rec.statut = False
                continue
            delta = (rec.date_expiration - today).days
            if delta < 0:
                rec.statut = "expiree"
            elif delta < 180:
                rec.statut = "bientot_expiree"
            else:
                rec.statut = "valide"

    @api.depends("session_ids")
    def _compute_nb_sessions(self):
        for rec in self:
            rec.nb_sessions = len(rec.session_ids)

    # ── Contrainte Python ──────────────────────────────────────────
    @api.constrains("date_obtention", "date_expiration")
    def _check_dates(self):
        for rec in self:
            if rec.date_obtention and rec.date_expiration:
                if rec.date_expiration <= rec.date_obtention:
                    raise ValidationError(
                        "La date d'expiration doit être postérieure "
                        "à la date d'obtention."
                    )

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            type_label = (rec.type_formation or "").upper()
            name = f"{rec.numero} ({type_label}"
            if rec.mention:
                name += f" - {rec.mention}"
            name += ")"
            rec.display_name = name
