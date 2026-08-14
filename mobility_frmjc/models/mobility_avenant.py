from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class MobilityAvenant(models.Model):
    _name = 'mobility.avenant'
    _description = "Avenant au contrat de mobilité (prolongation / réduction)"
    _order = 'date desc, id desc'

    mobility_id = fields.Many2one(
        'mobility.mobility', string='Mobilité', required=True, ondelete='cascade',
    )
    date = fields.Date(string="Date de l'avenant", default=fields.Date.today, required=True)
    type_avenant = fields.Selection(
        selection=[
            ('prolongation', 'Prolongation'),
            ('reduction', 'Réduction'),
            ('autre', 'Autre modification'),
        ],
        string='Type', required=True, default='prolongation',
    )
    # Enregistrée automatiquement à la création (cf. create()) — trace la
    # date de fin telle qu'elle était juste avant cet avenant, sans jamais
    # être modifiable après coup. C'est la succession de ces valeurs, avenant
    # après avenant, qui constitue l'historique complet des prolongations.
    ancienne_date_fin = fields.Date(string='Ancienne date de fin', readonly=True)
    nouvelle_date_fin = fields.Date(string='Nouvelle date de fin', required=True)
    motif = fields.Text(string='Motif', required=True)
    document_id = fields.Many2one(
        'mobility.document', string="Document d'avenant",
        domain=[('document_type', '=', 'avenant')],
    )
    state = fields.Selection(
        selection=[('brouillon', 'Brouillon'), ('applique', 'Appliqué')],
        string='Statut', default='brouillon', required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('ancienne_date_fin') and vals.get('mobility_id'):
                mobility = self.env['mobility.mobility'].browse(vals['mobility_id'])
                vals['ancienne_date_fin'] = mobility.end_date
        return super().create(vals_list)

    @api.constrains('mobility_id', 'nouvelle_date_fin')
    def _check_nouvelle_date_fin(self):
        for rec in self:
            if (rec.mobility_id.start_date
                    and rec.nouvelle_date_fin <= rec.mobility_id.start_date):
                raise ValidationError(
                    "La nouvelle date de fin doit être postérieure à la date "
                    "de début de la mobilité."
                )

    def action_appliquer(self):
        """Applique l'avenant : met à jour la date de fin de la mobilité.
        Les lignes financières calculables se resynchronisent d'elles-mêmes
        (periode_au → nb_jours → montant_prévu → écart forment déjà une
        chaîne de champs calculés dépendant de mobility_id.end_date) — nul
        besoin de les recalculer manuellement ni de toucher au montant
        réalisé déjà saisi."""
        for rec in self:
            if rec.state == 'applique':
                raise UserError('Cet avenant a déjà été appliqué.')
            ancienne = rec.ancienne_date_fin or rec.mobility_id.end_date
            rec.mobility_id.end_date = rec.nouvelle_date_fin
            rec.state = 'applique'
            rec.mobility_id.message_post(
                body=(
                    f"Avenant appliqué ({dict(rec._fields['type_avenant'].selection).get(rec.type_avenant)}) : "
                    f"date de fin modifiée de {ancienne or '?'} à {rec.nouvelle_date_fin}. "
                    f"Motif : {rec.motif}"
                )
            )

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            label = dict(rec._fields['type_avenant'].selection).get(rec.type_avenant, '?')
            rec.display_name = f'{label} — {rec.mobility_id.display_name}'
