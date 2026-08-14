from odoo import models, fields


class MobilityFinanceSubcategory(models.Model):
    _name = 'mobility.finance.subcategory'
    _description = 'Sous-catégorie de ligne financière (budget prévisionnel/réalisé)'
    _order = 'categorie, sequence, name'

    name = fields.Char(string='Sous-catégorie', required=True)
    code = fields.Char(
        string='Code',
        required=True,
        help='Identifiant technique stable (utilisé pour les contraintes et '
             "le calcul depuis les barèmes).",
    )
    sequence = fields.Integer(string='Séquence', default=10)
    categorie = fields.Selection(
        selection=[
            ('structures', 'Structures'),
            ('transport', 'Transport'),
            ('hebergement', 'Hébergement'),
            ('indemnites', 'Indemnités'),
            ('divers', 'Divers'),
            ('financement', 'Financement (recettes)'),
        ],
        string='Catégorie',
        required=True,
        help="Grande catégorie budgétaire (§ budget prévisionnel/réalisé). "
             "« Financement » regroupe les recettes (côté RECETTES du "
             "budget prévisionnel — ERASMUS+, autres financements...).",
    )
    compte_comptable = fields.Char(
        string='Compte comptable',
        help='Ex : 604300 — pour le rapprochement avec la comptabilité '
             '(EBP, export Odoo produit...).',
    )
    nature_defaut = fields.Selection(
        selection=[
            ('indemnite', 'Indemnité volontaire'),
            ('depense', 'Dépense'),
            ('recette', 'Recette'),
        ],
        string='Nature par défaut',
        help="Pré-remplit le champ Nature d'une ligne financière à la "
             'sélection de cette sous-catégorie — reste modifiable.',
    )
    calculable = fields.Boolean(
        string='Calculable depuis un barème',
        help="Active le bouton « Calculer » sur les lignes utilisant cette "
             'sous-catégorie.',
    )
    type_calcul = fields.Selection(
        selection=[
            ('soutien_organisationnel', 'Barème pays — Soutien organisationnel (A1)'),
            ('soutien_inclusion', "Barème pays — Soutien à l'inclusion (A2)"),
            ('argent_poche', 'Barème pays — Argent de poche (A3)'),
            ('voyage', 'Barème voyage'),
        ],
        string='Barème utilisé',
        help='Détermine quel barème le bouton Calculer applique — requis '
             'si « Calculable depuis un barème » est coché.',
    )

    # ── Produit associé (facturation / bons de commande) ─────────────
    # Un seul produit par sous-catégorie, réutilisé par toutes les lignes
    # financières qui la partagent — pas un produit par ligne. Créé à la
    # demande (cf. _get_or_create_product), pas au chargement du module.
    product_categ_id = fields.Many2one(
        'product.category', string='Catégorie produit',
        help='Catégorie Odoo (Inventaire) dans laquelle ranger le produit '
             'généré pour cette sous-catégorie.',
    )
    product_id = fields.Many2one(
        'product.product', string='Produit associé', readonly=True, copy=False,
    )

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'Une sous-catégorie avec ce code existe déjà.'
    )

    def _compute_display_name(self):
        for rec in self:
            categorie_label = dict(rec._fields['categorie'].selection).get(rec.categorie, '')
            rec.display_name = f'{categorie_label} / {rec.name}' if categorie_label else rec.name

    def _get_or_create_product(self):
        """Trouve (par référence interne = code technique) ou crée le
        produit service associé à cette sous-catégorie, et le mémorise
        pour les prochains appels — garantit un seul produit par
        sous-catégorie, jamais un par ligne financière."""
        self.ensure_one()
        if self.product_id:
            return self.product_id
        Product = self.env['product.product'].sudo()
        product = Product.search([('default_code', '=', self.code)], limit=1)
        if not product:
            categorie_label = dict(self._fields['categorie'].selection).get(self.categorie, '')
            vals = {
                'name': f'{categorie_label} - {self.name}' if categorie_label else self.name,
                'default_code': self.code,
                'type': 'service',
                'categ_id': self.product_categ_id.id if self.product_categ_id else False,
                'purchase_ok': True,
                'sale_ok': True,
            }
            if self.compte_comptable:
                account = self.env['account.account'].sudo().search(
                    [('code', '=', self.compte_comptable)], limit=1,
                )
                if account:
                    # Meilleur effort : ne force rien si le plan comptable
                    # n'a pas (encore) ce compte — à ajuster par le
                    # comptable si besoin.
                    vals['property_account_expense_id'] = account.id
                    vals['property_account_income_id'] = account.id
            product = Product.create(vals)
        self.product_id = product.id
        return product
