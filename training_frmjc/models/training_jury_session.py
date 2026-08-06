from odoo import models, fields, api
from odoo.exceptions import UserError


def _fmt_heure(h):
    if not h and h != 0:
        return '?'
    return f'{int(h)}h{int(round((h % 1) * 60)):02d}'


class TrainingJurySession(models.Model):
    _name = 'training.jury.session'
    _description = 'Session de jury (Circuit B)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    # ── Identification ─────────────────────────────────────────────
    session_id = fields.Many2one(
        'training.session', required=True, ondelete='cascade',
        index=True, string='Session de formation',
    )
    bloc_id = fields.Many2one(
        'training.bloc', required=True, ondelete='restrict',
        string='Bloc de compétences',
        domain=[('type_bloc', '=', 'bc')],
    )
    date = fields.Date(required=True, string='Date du jury')
    heure_debut = fields.Float(string='Heure de début', digits=(4, 2))
    heure_fin = fields.Float(string='Heure de fin', digits=(4, 2))
    lieu = fields.Char(string='Lieu')
    duree_creneau = fields.Float(
        string='Durée par candidat (h)', default=0.5,
        help='Ex : 0.5 = 30 min, 0.75 = 45 min',
    )

    # ── Jury ───────────────────────────────────────────────────────
    jury_membre_ids = fields.Many2many(
        'res.partner',
        'training_jury_membre_rel', 'jury_id', 'partner_id',
        string='Membres du jury',
        domain=[('is_company', '=', False)],
    )

    # ── Candidats ──────────────────────────────────────────────────
    certification_ids = fields.One2many(
        'training.certification', 'jury_session_id', string='Candidats',
    )
    nb_candidats = fields.Integer(
        string='Nb candidats', compute='_compute_nb_candidats',
    )

    # ── Statut ─────────────────────────────────────────────────────
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('planifie',  'Planifié'),
        ('convoque',  'Convoqué'),
        ('realise',   'Réalisé'),
        ('clos',      'Clos'),
    ], default='brouillon', required=True, tracking=True)

    notes = fields.Text(string='Notes')

    # ── Compute ───────────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            date_str = rec.date.strftime('%d/%m/%Y') if rec.date else '?'
            rec.display_name = f'Jury {rec.bloc_id.name or "?"} — {date_str}'

    def _compute_nb_candidats(self):
        for rec in self:
            rec.nb_candidats = len(rec.certification_ids)

    # ── Actions ───────────────────────────────────────────────────
    def action_planifier(self):
        self.write({'statut': 'planifie'})

    def action_affecter_creneaux(self):
        """Affecte les créneaux horaires aux candidats par ordre alphabétique."""
        for rec in self:
            if not rec.heure_debut:
                raise UserError('Renseignez l\'heure de début avant d\'affecter les créneaux.')
            if not rec.certification_ids:
                raise UserError('Aucun candidat dans cette session jury.')
            candidats = rec.certification_ids.sorted(lambda c: c.partner_id.name or '')
            heure = rec.heure_debut
            duree = rec.duree_creneau or 0.5
            for i, cert in enumerate(candidats):
                cert.write({
                    'heure_debut_b': heure,
                    'heure_fin_b': heure + duree,
                    'ordre_passage': i + 1,
                })
                heure += duree
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Créneaux affectés',
                'message': f'{sum(len(r.certification_ids) for r in self)} candidat(s) planifié(s).',
                'type': 'success',
            },
        }

    def action_convoquer_jury(self):
        """Envoie les convocations à chaque candidat + aux membres du jury."""
        for rec in self:
            if not rec.certification_ids:
                raise UserError('Aucun candidat à convoquer.')

            # Convoquer les candidats
            for cert in rec.certification_ids.filtered(
                lambda c: c.statut in ('brouillon', 'planifie')
            ):
                cert.action_convoquer_circuit_b()

            # Convoquer les membres du jury
            date_str = rec.date.strftime('%d/%m/%Y') if rec.date else '?'
            lieu = f' au {rec.lieu}' if rec.lieu else ''
            candidats_html = ''.join(
                f'<tr><td style="padding:.3rem .6rem;">{c.ordre_passage or "—"}</td>'
                f'<td style="padding:.3rem .6rem;">{c.partner_id.name}</td>'
                f'<td style="padding:.3rem .6rem;">{_fmt_heure(c.heure_debut_b)} – {_fmt_heure(c.heure_fin_b)}</td></tr>'
                for c in rec.certification_ids.sorted('ordre_passage')
            )
            for membre in rec.jury_membre_ids:
                if not membre.email:
                    continue
                self.env['mail.mail'].sudo().create({
                    'subject': f'Jury {rec.bloc_id.name} — {date_str}',
                    'body_html': f"""
                        <p>Bonjour {membre.name},</p>
                        <p>Vous êtes membre du jury pour le bloc <strong>{rec.bloc_id.name}</strong>
                        le <strong>{date_str}{lieu}</strong>.</p>
                        <table border="0" cellspacing="0" style="border-collapse:collapse;width:100%">
                          <thead><tr style="background:#eee;">
                            <th style="padding:.3rem .6rem;text-align:left;">N°</th>
                            <th style="padding:.3rem .6rem;text-align:left;">Candidat</th>
                            <th style="padding:.3rem .6rem;text-align:left;">Créneau</th>
                          </tr></thead>
                          <tbody>{candidats_html}</tbody>
                        </table>
                        <p style="margin-top:1rem;">L'équipe FRMJC</p>
                    """,
                    'email_to': membre.email,
                    'auto_delete': True,
                }).send()

            rec.write({'statut': 'convoque'})

    def action_marquer_realise(self):
        for rec in self:
            rec.certification_ids.filtered(
                lambda c: c.statut == 'convoque'
            ).write({'statut': 'realise'})
        self.write({'statut': 'realise'})

    def action_clore(self):
        self.write({'statut': 'clos'})

    def get_commissions(self):
        """Retourne [(num, [membres], [certifications]), ...] groupés par numero_commission.
        Membres: groupés par paires dans jury_membre_ids (commission 1 = indices 0-1, etc.).
        Certifications: filtrées par numero_commission."""
        membres = list(self.jury_membre_ids)
        certs_par_comm = {}
        for cert in self.certification_ids.sorted('heure_debut_b'):
            num = cert.numero_commission or 0
            certs_par_comm.setdefault(num, []).append(cert)

        nb_pairs = max(1, len(membres) // 2 or 1) if membres else 1
        commissions = []
        for i in range(nb_pairs):
            num = i + 1
            pair = membres[i * 2: i * 2 + 2]
            certs = certs_par_comm.get(num, [])
            commissions.append({'num': num, 'membres': pair, 'certs': certs})

        # Candidats sans commission assignée → commission 0 rattachée à la 1ère
        sans_comm = certs_par_comm.get(0, [])
        if sans_comm and commissions:
            commissions[0]['certs'] = sans_comm + commissions[0]['certs']
        elif sans_comm:
            commissions.append({'num': 1, 'membres': membres, 'certs': sans_comm})

        return commissions

    def action_imprimer_convocation_jury(self):
        return self.env.ref(
            'training_frmjc.report_certification_convocation_jury'
        ).report_action(self)
