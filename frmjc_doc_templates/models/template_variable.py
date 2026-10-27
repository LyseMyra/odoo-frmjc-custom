from odoo import models, fields, api

from . import variable_registry


class TemplateVariable(models.Model):
    _name = 'template.variable'
    _description = 'Variable disponible pour les modèles de documents'
    _order = 'model_id, code'

    code = fields.Char(
        required=True, readonly=True,
        help="Nom de la balise, à écrire dans le document entre "
             "doubles accolades.",
    )
    tag = fields.Char(
        string='Balise à utiliser', compute='_compute_tag',
        help="À copier-coller tel quel dans le document Word.",
    )
    description = fields.Char(required=True, readonly=True)
    model_id = fields.Many2one(
        'ir.model', readonly=True, ondelete='cascade',
        string='Document applicable à',
        help="Vide = variable globale, disponible pour tous les documents.",
    )
    source_module = fields.Char(string='Module', readonly=True)

    _code_model_uniq = models.Constraint(
        'unique(code, model_id)',
        "Cette variable existe déjà pour ce modèle.",
    )

    @api.depends('code')
    def _compute_tag(self):
        for rec in self:
            rec.tag = '{{ %s }}' % rec.code if rec.code else ''

    @api.model
    def _sync_variables(self):
        """(Re)synchronise les enregistrements depuis le registre Python
        (variable_registry). Appelé à l'installation et à chaque mise à
        jour du module (post_init_hook) : c'est la seule façon dont ce
        catalogue change, il n'est jamais éditer à la main."""
        IrModel = self.env['ir.model']
        seen_ids = []

        def _upsert(code, meta, model_id):
            rec = self.search([('code', '=', code), ('model_id', '=', model_id)], limit=1)
            vals = {
                'code': code,
                'description': meta['description'],
                'model_id': model_id,
                'source_module': meta.get('module', ''),
            }
            if rec:
                rec.write(vals)
            else:
                rec = self.create(vals)
            seen_ids.append(rec.id)

        for code, meta in variable_registry.get_global_variables().items():
            _upsert(code, meta, False)

        for model_name in variable_registry.all_models():
            model_rec = IrModel.sudo().search([('model', '=', model_name)], limit=1)
            if not model_rec:
                continue
            for code, meta in variable_registry.get_variables(model_name).items():
                _upsert(code, meta, model_rec.id)

        stale = self.search([('id', 'not in', seen_ids)]) if seen_ids else self.search([])
        stale.unlink()
