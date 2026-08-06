from odoo import models, fields, api
from odoo.exceptions import UserError


class TrainingDepenseIntervenant(models.Model):
    _name = 'training.depense.intervenant'
    _description = 'Dépense liée à un intervenant de session'
    _order = 'session_id, partner_id, date_depense'

    # ── Relations ──────────────────────────────────────────────────
    session_id = fields.Many2one(
        'training.session',
        string='Session',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Intervenant',
        required=True,
        index=True,
    )

    # ── Produit (filtré sur les produits DEJEPS) ───────────────────
    product_id = fields.Many2one(
        'product.product',
        string='Produit / Prestation',
        required=True,
        domain=[('name', 'ilike', 'DEJEPS')],
    )

    # ── Montants ───────────────────────────────────────────────────
    quantite = fields.Float(
        string='Quantité',
        required=True,
        default=1.0,
        digits=(8, 2),
        help='Exemple : nombre de jours, de repas, de nuitées…',
    )
    prix_unitaire = fields.Float(
        string='Prix unitaire (€)',
        required=True,
        digits=(10, 2),
    )
    montant_total = fields.Float(
        string='Montant total (€)',
        compute='_compute_montant_total',
        store=True,
        digits=(10, 2),
    )

    # ── Informations complémentaires ───────────────────────────────
    description = fields.Char(
        string='Description',
        help='Précision libre (ex : nuitée du 12/08, trajet Rennes-Brest…)',
    )
    date_depense = fields.Date(
        string='Date',
        default=fields.Date.today,
    )
    justificatif = fields.Binary(string='Justificatif', attachment=True)
    justificatif_filename = fields.Char()

    # ── Workflow ───────────────────────────────────────────────────
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('valide',    'Validée'),
        ('bc_cree',   'Bon de commande créé'),
    ], string='Statut', default='brouillon', required=True)

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Bon de commande',
        readonly=True,
        copy=False,
    )

    # ── Compute ────────────────────────────────────────────────────
    @api.depends('quantite', 'prix_unitaire')
    def _compute_montant_total(self):
        for rec in self:
            rec.montant_total = rec.quantite * rec.prix_unitaire

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.prix_unitaire = self.product_id.standard_price or self.product_id.lst_price
            if not self.description:
                self.description = self.product_id.name

    # ── Actions workflow ───────────────────────────────────────────
    def action_valider(self):
        self.write({'statut': 'valide'})

    def action_remettre_brouillon(self):
        self.filtered(lambda r: r.statut == 'valide').write({'statut': 'brouillon'})

    def unlink(self):
        bc_crees = self.filtered(lambda r: r.statut == 'bc_cree')
        if bc_crees:
            noms = ', '.join(bc_crees.mapped('display_name'))
            raise UserError(
                f"Impossible de supprimer une dépense dont le bon de commande a déjà été créé.\n"
                f"Supprimez d'abord le bon de commande associé, puis repassez la dépense en brouillon.\n\n"
                f"Dépense(s) concernée(s) : {noms}"
            )
        return super().unlink()

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            prod = rec.product_id.name or '?'
            date = rec.date_depense.strftime('%d/%m/%Y') if rec.date_depense else '?'
            rec.display_name = f'{rec.partner_id.name or "?"} — {prod} — {date}'
