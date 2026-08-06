from odoo import models, fields


class TrainingModuleRepartition(models.Model):
    _name = 'training.module.repartition'
    _description = "Répartition hebdomadaire planifiée d'un module"
    _order = 'semaine, jour'
    _rec_name = 'module_id'

    module_id = fields.Many2one(
        'training.module', required=True, ondelete='cascade', string='Module',
    )
    formation_id = fields.Many2one(
        related='module_id.formation_id', store=True, readonly=True,
        string='Formation',
    )
    semaine = fields.Integer(string='N° semaine', required=True)
    jour = fields.Selection([
        ('lundi', 'Lundi'),
        ('mardi', 'Mardi'),
        ('mercredi', 'Mercredi'),
        ('jeudi', 'Jeudi'),
        ('vendredi', 'Vendredi'),
    ], string='Jour', required=True)
    heures = fields.Float(string='Heures', required=True, digits=(4, 1))

    _check_heures = models.Constraint(
        'CHECK(heures > 0)', "Le nombre d'heures doit être positif.",
    )
