import logging
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def _fmt_heure(h):
    if not h and h != 0:
        return 'à définir'
    return f'{int(h)}h{int(round((h % 1) * 60)):02d}'


class TrainingCertification(models.Model):
    _name = 'training.certification'
    _description = "Certification d'un bloc de compétences"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'session_id, bloc_id, inscription_id'

    # ── Relations principales ──────────────────────────────────────
    inscription_id = fields.Many2one(
        'training.inscription', required=True, ondelete='cascade',
        index=True, string='Inscription', tracking=True,
    )
    partner_id = fields.Many2one(
        related='inscription_id.partner_id', store=True, readonly=True, string='Stagiaire',
    )
    session_id = fields.Many2one(
        related='inscription_id.session_id', store=True, readonly=True, string='Session',
    )
    formation_id = fields.Many2one(
        related='inscription_id.formation_id', store=True, readonly=True, string='Formation',
    )
    bloc_id = fields.Many2one(
        'training.bloc', required=True, ondelete='restrict',
        index=True, string='Bloc de compétences',
        domain=[('type_bloc', '=', 'bc')],
    )

    # ── Circuit ────────────────────────────────────────────────────
    type_circuit = fields.Selection([
        ('a', 'Circuit A — Certification en structure'),
        ('b', 'Circuit B — Jury à l\'OF'),
    ], string='Circuit', required=True, tracking=True)

    # ── Statut ─────────────────────────────────────────────────────
    statut = fields.Selection([
        ('brouillon',       'Brouillon'),
        ('planifie',        'Planifié'),
        ('convoque',        'Convoqué'),
        ('realise',         'Réalisé'),
        ('resultat_saisi',  'Résultat saisi'),
        ('valide',          'Validé'),
        ('transmis',        'Transmis DRAJES'),
    ], default='brouillon', required=True, tracking=True)

    # ── Circuit A : certification en structure ─────────────────────
    certificateur_id = fields.Many2one(
        'res.partner', string='Certificateur',
        domain=[('is_company', '=', False)],
        help='Professionnel évaluateur pour le Circuit A',
    )
    date_certification_a = fields.Date(string='Date (A)')
    heure_debut_a = fields.Float(string='Heure de début (A)', digits=(4, 2))
    lieu_certification_a = fields.Char(string='Lieu (A)')
    convocation_a_envoyee = fields.Boolean(default=False, string='Convocation A envoyée')
    date_convocation_a = fields.Date(string='Date envoi convocation A', readonly=True)

    # ── Circuit B : jury OF ────────────────────────────────────────
    jury_session_id = fields.Many2one(
        'training.jury.session', string='Session jury',
        domain="[('session_id','=',session_id),('bloc_id','=',bloc_id)]",
    )
    ordre_passage = fields.Integer(string='Ordre de passage')
    numero_commission = fields.Integer(string='N° commission', default=0,
        help='Numéro de commission dans la session jury (Circuit B). 0 = non affecté.')
    heure_debut_b = fields.Float(string='Heure de passage (B)', digits=(4, 2))
    heure_fin_b = fields.Float(string='Heure de fin (B)', digits=(4, 2))
    convocation_b_envoyee = fields.Boolean(default=False, string='Convocation B envoyée')

    # ── Résultats ──────────────────────────────────────────────────
    resultat = fields.Selection([
        ('admis',    'Admis(e)'),
        ('ajourne',  'Ajourné(e)'),
        ('dispense', 'Dispensé(e)'),
        ('absent',   'Absent(e)'),
    ], string='Résultat', tracking=True)
    mention = fields.Selection([
        ('insuffisant', 'Insuffisant'),
        ('passable',    'Passable'),
        ('assez_bien',  'Assez bien'),
        ('bien',        'Bien'),
        ('tres_bien',   'Très bien'),
    ], string='Mention')
    points = fields.Float(string='Points / Note', digits=(4, 2))
    observations = fields.Text(string='Observations jury')
    date_resultat = fields.Date(string='Date des résultats')
    valide_par_id = fields.Many2one('res.partner', string='Validé par', readonly=True)
    date_validation = fields.Date(string='Date de validation', readonly=True)

    # ── Diplôme / DRAJES ──────────────────────────────────────────
    numero_diplome = fields.Char(string='N° de diplôme')
    date_diplome = fields.Date(string='Date du diplôme')
    date_transmission_drajes = fields.Date(string='Date transmission DRAJES', readonly=True)

    # ── Relations enfants ──────────────────────────────────────────
    document_ids = fields.One2many(
        'training.certification.document', 'certification_id', string='Documents',
    )
    expense_ids = fields.One2many(
        'training.expense', 'certification_id', string='Dépenses',
    )

    # ── Contrainte d'unicité ───────────────────────────────────────
    _cert_unique = models.Constraint(
        'UNIQUE(inscription_id, bloc_id)',
        'Une certification existe déjà pour ce stagiaire et ce bloc de compétences.',
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.partner_id.name or "?"} — {rec.bloc_id.name or "?"}'

    # ── Workflow Circuit A ─────────────────────────────────────────
    def action_planifier_circuit_a(self):
        for rec in self:
            if not rec.certificateur_id or not rec.date_certification_a:
                raise UserError('Renseignez le certificateur et la date avant de planifier.')
        self.write({'statut': 'planifie'})

    def action_convoquer_circuit_a(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            if not rec.certificateur_id:
                raise UserError(f'{rec.display_name} : certificateur manquant.')
            date_str = rec.date_certification_a.strftime('%d/%m/%Y') if rec.date_certification_a else '?'
            heure = _fmt_heure(rec.heure_debut_a)
            lieu = f' au {rec.lieu_certification_a}' if rec.lieu_certification_a else ''
            # Email stagiaire
            if rec.partner_id.email:
                self.env['mail.mail'].sudo().create({
                    'subject': f'Convocation — Certification {rec.bloc_id.name} — {date_str}',
                    'body_html': f"""
                        <p>Bonjour {rec.partner_id.name},</p>
                        <p>Vous êtes convoqué(e) pour la certification du bloc
                        <strong>{rec.bloc_id.name}</strong>
                        le <strong>{date_str} à {heure}</strong>{lieu}.</p>
                        <p>Évaluateur : <strong>{rec.certificateur_id.name}</strong></p>
                        <p>Merci de vous présenter avec l'ensemble de votre dossier de validation.</p>
                        <p>L'équipe FRMJC</p>
                    """,
                    'email_to': rec.partner_id.email,
                    'auto_delete': True,
                }).send()
            # Email certificateur
            if rec.certificateur_id.email:
                self.env['mail.mail'].sudo().create({
                    'subject': f'Évaluation {rec.bloc_id.name} — {rec.partner_id.name} — {date_str}',
                    'body_html': f"""
                        <p>Bonjour {rec.certificateur_id.name},</p>
                        <p>Vous êtes sollicité(e) pour évaluer
                        <strong>{rec.partner_id.name}</strong>
                        sur le bloc <strong>{rec.bloc_id.name}</strong>
                        le <strong>{date_str} à {heure}</strong>{lieu}.</p>
                        <p>Merci de nous confirmer votre disponibilité.</p>
                        <p>L'équipe FRMJC</p>
                    """,
                    'email_to': rec.certificateur_id.email,
                    'auto_delete': True,
                }).send()
            rec.write({
                'statut': 'convoque',
                'convocation_a_envoyee': True,
                'date_convocation_a': fields.Date.today(),
            })

    # ── Workflow Circuit B ─────────────────────────────────────────
    def action_planifier_circuit_b(self):
        for rec in self:
            if not rec.jury_session_id:
                raise UserError('Associez une session jury avant de planifier.')
        self.write({'statut': 'planifie'})

    def action_convoquer_circuit_b(self):
        for rec in self:
            if not rec.jury_session_id:
                raise UserError(f'{rec.display_name} : session jury manquante.')
            js = rec.jury_session_id
            date_str = js.date.strftime('%d/%m/%Y') if js.date else '?'
            heure = _fmt_heure(rec.heure_debut_b)
            lieu = f' au {js.lieu}' if js.lieu else ''
            if rec.partner_id.email:
                self.env['mail.mail'].sudo().create({
                    'subject': f'Convocation — Jury {rec.bloc_id.name} — {date_str}',
                    'body_html': f"""
                        <p>Bonjour {rec.partner_id.name},</p>
                        <p>Vous êtes convoqué(e) devant le jury pour la certification du bloc
                        <strong>{rec.bloc_id.name}</strong>
                        le <strong>{date_str} à {heure}</strong>{lieu}.</p>
                        <p>Merci de vous présenter avec votre dossier de validation.</p>
                        <p>L'équipe FRMJC</p>
                    """,
                    'email_to': rec.partner_id.email,
                    'auto_delete': True,
                }).send()
            rec.write({'statut': 'convoque', 'convocation_b_envoyee': True})

    # ── Étapes communes ────────────────────────────────────────────
    def action_marquer_realise(self):
        self.write({'statut': 'realise'})

    def action_saisir_resultat(self):
        for rec in self:
            if not rec.resultat:
                raise UserError('Saisissez le résultat avant de valider.')
        self.write({'statut': 'resultat_saisi', 'date_resultat': fields.Date.today()})

    def action_valider(self):
        for rec in self:
            if rec.statut != 'resultat_saisi':
                raise UserError('Le résultat doit être saisi avant validation.')
        self.write({
            'statut': 'valide',
            'valide_par_id': self.env.user.partner_id.id,
            'date_validation': fields.Date.today(),
        })

    def action_transmettre_drajes(self):
        self.write({
            'statut': 'transmis',
            'date_transmission_drajes': fields.Date.today(),
        })

    def action_remettre_brouillon(self):
        self.filtered(lambda r: r.statut != 'transmis').write({'statut': 'brouillon'})

    # ── Impressions ────────────────────────────────────────────────
    def action_imprimer_convocation_a(self):
        return self.env.ref(
            'training_frmjc.report_certification_convocation_a'
        ).report_action(self)

    def action_imprimer_convocation_candidat_b(self):
        return self.env.ref(
            'training_frmjc.report_certification_convocation_candidat_b'
        ).report_action(self)

    def action_imprimer_certificat(self):
        return self.env.ref(
            'training_frmjc.report_certificat_realisation'
        ).report_action(self.inscription_id)
