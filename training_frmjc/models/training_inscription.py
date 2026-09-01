import logging
import uuid

from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TrainingInscription(models.Model):
    _name = 'training.inscription'
    _description = "Dossier d'inscription à une formation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_inscription desc'
    _rec_name = 'reference'

    # ── Identification ─────────────────────────────────────────────
    reference = fields.Char(
        string='Référence', readonly=True, copy=False, default='Nouveau', index=True
    )
    partner_id = fields.Many2one(
        'res.partner', string='Candidat', required=True,
        ondelete='restrict', tracking=True,
    )
    session_id = fields.Many2one(
        'training.session', string='Session', required=True,
        ondelete='restrict', tracking=True,
    )
    formation_id = fields.Many2one(
        related='session_id.formation_id', store=True, readonly=True
    )
    date_inscription = fields.Date(
        string="Date d'inscription", default=fields.Date.today, tracking=True
    )

    # ── Portail ────────────────────────────────────────────────────
    portal_token = fields.Char(string='Token portail', copy=False, index=True)
    etape_portal = fields.Integer(string='Étape portail', default=1)

    # ── Workflow ───────────────────────────────────────────────────
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('en_cours', 'En cours de saisie'),
        ('soumis', 'Dossier soumis'),
        ('en_attente_pieces', 'En attente de pièces'),
        ('complet', 'Dossier complet'),
        ('accepte', 'Accepté'),
        ('refuse', 'Refusé'),
        ('abandon', 'Abandon'),
    ], string='Statut', default='brouillon', required=True, tracking=True)

    # ── Étape 3 : Situation professionnelle ────────────────────────
    statut_emploi = fields.Selection([
        ('salarie', 'Salarié'),
        ('independant', 'Indépendant'),
        ('demandeur_emploi', "Demandeur d'emploi"),
        ('etudiant', 'Étudiant'),
        ('benevole', 'Bénévole'),
        ('autre', 'Autre'),
    ], string="Statut d'emploi")
    employeur_nom = fields.Char(string='Employeur')
    employeur_adresse = fields.Char(string='Adresse employeur')
    type_contrat = fields.Selection([
        ('cdi', 'CDI'),
        ('cdd', 'CDD'),
        ('interim', 'Intérim'),
        ('apprentissage', 'Apprentissage'),
        ('professionnalisation', 'Professionnalisation'),
        ('sanscontract', 'Pas de contrat'),
    ], string='Type de contrat')
    remuneration_mensuelle = fields.Float(string='Rémunération brute mensuelle (€)')
    volume_horaire_semaine = fields.Float(string='Volume horaire hebdomadaire (h)')
    rqth = fields.Selection([
        ('oui', 'Oui'),
        ('non', 'Non'),
    ], string='RQTH (Reconnaissance de la Qualité de Travailleur Handicapé)')
    # ── Classification BPF (Bilan Pédagogique et Financier) ────────
    mode_stagiaire = fields.Selection([
        ('a', 'a — Salariés d\'employeurs privés hors apprentis'),
        ('b', 'b — Apprentis'),
        ('c', 'c — Personnes en recherche d\'emploi'),
        ('d', 'd — Particuliers à leurs propres frais'),
        ('e', 'e — Autres stagiaires'),
    ], string='Mode / Type de stagiaire', tracking=True)

    type_financement = fields.Selection([
        ('1',  '1 — Entreprises (formation de leurs salariés)'),
        ('2',  '2 — Organismes gestionnaires des fonds de la FP'),
        ('3',  '3 — Pouvoirs publics (agents publics)'),
        ('4',  '4 — Instances européennes'),
        ('5',  '5 — État'),
        ('6',  '6 — Conseils régionaux'),
        ('7',  '7 — France Travail (ex Pôle emploi)'),
        ('8',  '8 — Autres ressources publiques'),
        ('9',  '9 — Contrats individuels (à leurs frais)'),
        ('10', '10 — Autres organismes de formation (y compris CFA)'),
        ('11', '11 — Autres produits formation professionnelle'),
    ], string='Type de financement', tracking=True)

    sous_type_financement = fields.Selection([
        ('a', 'a — Contrats d\'apprentissage'),
        ('b', 'b — Contrats de professionnalisation'),
        ('c', 'c — Promotion / reconversion par alternance (Pro-A)'),
        ('d', 'd — Projets de transition professionnelle (PTP)'),
        ('e', 'e — Compte personnel de formation (CPF)'),
        ('f', 'f — Dispositifs spécifiques pour demandeurs d\'emploi'),
        ('g', 'g — Dispositifs spécifiques pour travailleurs non-salariés'),
        ('h', 'h — Plan de développement des compétences / autres'),
    ], string='Sous-type (type 2)', tracking=True)

    # ── Étape 4 : Formation initiale ───────────────────────────────
    niveau_etudes = fields.Selection([
        ('v', 'Niveau 3 (CAP/BEP)'),
        ('iv', 'Niveau 4 (Bac)'),
        ('iii', 'Niveau 5 (Bac+2)'),
        ('ii', 'Niveau 6 (Bac+3/4)'),
        ('i', 'Niveau 7/8 (Bac+5 et +)'),
    ], string="Niveau d'études")
    dernier_diplome = fields.Char(string='Dernier diplôme obtenu')
    annee_obtention = fields.Integer(string="Année d'obtention")
    etablissement_formation = fields.Char(string='Établissement')

    # ── Expériences (fusionné avec l'étape Prérequis) ──────────────
    experience_ids = fields.One2many(
        'training.inscription.experience', 'inscription_id', string='Expériences',
    )

    # ── Projet professionnel ──────────────────────────────────────
    projet_professionnel = fields.Text(string='Projet professionnel')
    structure_accueil = fields.Char(string="Structure d'accueil (saisie libre)")
    structure_accueil_id = fields.Many2one(
        'res.partner', string="Structure d'accueil (fiche)",
        domain=[('is_structure_accueil', '=', True)],
        help="Lier à une fiche structure pour les conventions",
    )
    fonction_visee = fields.Char(string='Fonction visée')

    # ── Documents ─────────────────────────────────────────────────
    cv = fields.Binary(string='CV', attachment=True)
    cv_filename = fields.Char()
    lettre_motivation_doc = fields.Binary(string='Lettre de motivation', attachment=True)
    lettre_motivation_filename = fields.Char()
    diplome_doc = fields.Binary(string='Copie de diplôme / attestation', attachment=True)
    diplome_filename = fields.Char()
    justificatif_identite = fields.Binary(string="Justificatif d'identité valide", attachment=True)
    justificatif_identite_filename = fields.Char()
    photo_identite = fields.Binary(string="Photo d'identité", attachment=True)
    photo_identite_filename = fields.Char()
    attestation_rqth = fields.Binary(string='Attestation RQTH', attachment=True)
    attestation_rqth_filename = fields.Char()
    document_ids = fields.One2many(
        'training.inscription.document', 'inscription_id',
        string='Autres documents justificatifs',
    )

    # ── Déclaration ──────────────────────────────────────────────
    conditions_acceptees = fields.Boolean(string='Conditions acceptées')
    date_declaration = fields.Date(string='Date de la déclaration sur l\'honneur')
    notes_candidat = fields.Text(string='Informations complémentaires (candidat)')

    # ── Secrétariat ────────────────────────────────────────────────
    notes_secretariat = fields.Text(string='Notes secrétariat', tracking=True)
    date_entretien = fields.Date(string="Date d'entretien")
    date_decision = fields.Date(string='Date de décision')
    motif_refus = fields.Text(string='Motif de refus')
    date_derniere_relance = fields.Date(string='Dernière relance envoyée')
    nb_relances = fields.Integer(string='Nb relances', default=0)

    # ── Contact post-acceptation ─────────────────────────────────
    email_pro = fields.Char(
        string='Email professionnel',
        help="Renseignable uniquement pour un dossier accepté, "
             "depuis le portail stagiaire ou le back-office.",
    )

    # ── Coordonnées candidat (related) ────────────────────────────
    partner_email = fields.Char(related='partner_id.email', readonly=True, string='Email')
    partner_phone = fields.Char(related='partner_id.phone', readonly=True, string='Téléphone')
    partner_street = fields.Char(related='partner_id.street', readonly=True, string='Adresse')
    partner_zip = fields.Char(related='partner_id.zip', readonly=True, string='Code postal')
    partner_city = fields.Char(related='partner_id.city', readonly=True, string='Ville')

    # ── Conventions ────────────────────────────────────────────────
    convention_ids = fields.One2many(
        'training.convention', 'inscription_id', string='Conventions',
    )
    nb_conventions = fields.Integer(
        compute='_compute_nb_conventions', store=True, string='Nb conventions',
    )

    # ── Alternance ─────────────────────────────────────────────────
    alternance_ids = fields.One2many(
        'training.alternance', 'inscription_id', string="Dossiers d'alternance",
    )
    nb_alternances = fields.Integer(
        compute='_compute_nb_alternances', store=True, string='Structures d\'accueil',
    )

    # ── Abandons ───────────────────────────────────────────────────
    dropout_ids = fields.One2many(
        'training.dropout', 'inscription_id', string='Abandons'
    )

    # ── Présences ──────────────────────────────────────────────────
    attendance_ids = fields.One2many(
        'training.attendance', 'inscription_id', string='Présences',
    )
    certification_ids = fields.One2many(
        'training.certification', 'inscription_id', string='Certifications',
    )
    heures_presentes = fields.Float(
        string='Heures présentes', compute='_compute_presence_stats',
        store=True, digits=(8, 2),
    )
    heures_prevues = fields.Float(
        string='Heures prévues', compute='_compute_presence_stats',
        store=True, digits=(8, 2),
    )
    taux_presence = fields.Float(
        string='Taux de présence (%)', compute='_compute_presence_stats',
        store=True, digits=(5, 1),
    )
    heures_facturables = fields.Float(
        string='Heures facturables', compute='_compute_presence_stats',
        store=True, digits=(8, 2),
        help='Heures présentes + heures absences justifiées (absences injustifiées déduites)',
    )

    # ── Champs financiers ──────────────────────────────────────────
    montant_theorique = fields.Float(
        string='Recette théorique (€)', compute='_compute_montants',
        store=True, digits=(10, 2),
        help='heures_prevues × tarif_horaire de la formation',
    )
    montant_reel = fields.Float(
        string='Recette réelle (€)', compute='_compute_montants',
        store=True, digits=(10, 2),
        help='heures_facturables × tarif_horaire (absences injustifiées déduites)',
    )
    ecart_montant = fields.Float(
        string='Écart (€)', compute='_compute_montants',
        store=True, digits=(10, 2),
        help='Montant théorique − montant réel : impact financier des absences injustifiées',
    )

    # ── Contrainte ─────────────────────────────────────────────────
    _unique_partner_session = models.Constraint(
        'UNIQUE(partner_id, session_id)',
        'Ce candidat a déjà un dossier pour cette session.',
    )

    # ── Création ───────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('training.inscription')
                    or 'Nouveau'
                )
            if not vals.get('portal_token'):
                vals['portal_token'] = uuid.uuid4().hex
        return super().create(vals_list)

    @api.depends(
        'attendance_ids.statut',
        'attendance_ids.heures',
        'session_id.week_ids.type_semaine',
        'session_id.week_ids.week_line_ids.heures',
    )
    def _compute_presence_stats(self):
        for rec in self:
            presentes = sum(
                a.heures for a in rec.attendance_ids if a.statut == 'present'
            )
            justifiees = sum(
                a.heures for a in rec.attendance_ids if a.statut == 'justifie'
            )
            prevues = sum(
                line.heures
                for week in rec.session_id.week_ids
                if week.type_semaine == 'formation'
                for line in week.week_line_ids
            )
            rec.heures_presentes = presentes
            rec.heures_prevues = prevues
            rec.heures_facturables = presentes + justifiees
            rec.taux_presence = (presentes / prevues * 100) if prevues else 0.0

    @api.depends('convention_ids')
    def _compute_nb_conventions(self):
        for rec in self:
            rec.nb_conventions = len(rec.convention_ids)

    @api.depends('alternance_ids')
    def _compute_nb_alternances(self):
        for rec in self:
            rec.nb_alternances = len(rec.alternance_ids)

    @api.depends('heures_prevues', 'heures_facturables', 'session_id.formation_id.tarif_horaire')
    def _compute_montants(self):
        for rec in self:
            tarif = rec.session_id.formation_id.tarif_horaire or 0.0
            rec.montant_theorique = rec.heures_prevues * tarif
            rec.montant_reel = rec.heures_facturables * tarif
            rec.ecart_montant = rec.montant_theorique - rec.montant_reel

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.reference} – {rec.partner_id.name or "?"}'

    # ── Workflow actions ───────────────────────────────────────────
    def action_soumettre(self):
        for rec in self:
            if not rec.conditions_acceptees or not rec.date_declaration:
                raise ValidationError(
                    "Le candidat doit accepter la collecte et le traitement de ses "
                    "données personnelles et certifier sur l'honneur l'exactitude "
                    "des informations avant soumission."
                )
            rec.write({'statut': 'soumis'})

    def action_attendre_pieces(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pièces manquantes',
            'res_model': 'training.pieces.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_inscription_id': self.id},
        }

    def action_marquer_complet(self):
        self.write({'statut': 'complet'})

    def action_accepter(self):
        for rec in self:
            rec.write({'statut': 'accepte', 'date_decision': fields.Date.today()})
            if rec.partner_id.email:
                base_url = rec.env['ir.config_parameter'].sudo().get_param('web.base.url')
                espace_url = f'{base_url}/espace-stagiaire/{rec.portal_token}'
                try:
                    rec.env['mail.mail'].sudo().create({
                        'subject': f'🎉 Félicitations ! Votre candidature est acceptée — {rec.reference}',
                        'body_html': f"""
                            <p>Bonjour {rec.partner_id.name},</p>
                            <p>Nous avons le plaisir de vous informer que votre dossier
                            d'inscription <strong>{rec.reference}</strong>
                            pour la formation <strong>{rec.formation_id.display_name}</strong>
                            a été <strong>accepté</strong>.</p>
                            <p>Vous pouvez dès maintenant accéder à votre espace stagiaire
                            pour suivre l'avancement de votre dossier, consulter et signer
                            vos conventions, et retrouver toutes les informations liées
                            à votre formation :</p>
                            <p style="text-align:center;">
                                <a href="{espace_url}"
                                   style="background:#2e7d32;color:#fff;padding:12px 24px;
                                          border-radius:4px;text-decoration:none;font-weight:bold;">
                                    Accéder à mon espace stagiaire
                                </a>
                            </p>
                            <p>L'équipe FRMJC</p>
                        """,
                        'email_to': rec.partner_id.email,
                        'auto_delete': True,
                    }).send()
                except Exception as e:
                    _logger.warning("Erreur envoi email acceptation %s: %s", rec.reference, e)

    def action_refuser(self):
        self.write({'statut': 'refuse', 'date_decision': fields.Date.today()})

    def action_conventions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Conventions',
            'res_model': 'training.convention',
            'view_mode': 'list,form',
            'domain': [('inscription_id', '=', self.id)],
            'context': {'default_inscription_id': self.id},
        }

    def action_voir_alternances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Structures d\'accueil — {self.reference}',
            'res_model': 'training.alternance',
            'view_mode': 'list,form',
            'domain': [('inscription_id', '=', self.id)],
            'context': {'default_inscription_id': self.id},
        }

    def action_ouvrir_portail(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return {
            'type': 'ir.actions.act_url',
            'url': f'{base_url}/formation/dossier/{self.portal_token}',
            'target': 'new',
        }

    def action_voir_presences(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Présences — {self.reference}',
            'res_model': 'training.attendance',
            'view_mode': 'list,form',
            'domain': [('inscription_id', '=', self.id)],
            'context': {'default_inscription_id': self.id},
        }

    def action_imprimer_certificat_realisation(self):
        return self.env.ref(
            'training_frmjc.report_certificat_realisation'
        ).report_action(self)

    # ── Relances automatiques (cron) ───────────────────────────────
    @api.model
    def action_envoyer_relances(self):
        from datetime import timedelta
        seuil = fields.Date.today() - timedelta(days=7)
        inscriptions = self.search([
            ('statut', 'in', ('en_cours', 'soumis', 'en_attente_pieces')),
            '|',
            ('date_derniere_relance', '<', seuil),
            ('date_derniere_relance', '=', False),
        ])
        for insc in inscriptions:
            if not insc.partner_id.email:
                continue
            try:
                self.env['mail.mail'].sudo().create({
                    'subject': f'Rappel – Dossier d\'inscription {insc.reference}',
                    'body_html': f"""
                        <p>Bonjour {insc.partner_id.name},</p>
                        <p>Votre dossier d\'inscription <strong>{insc.reference}</strong>
                        pour la formation <strong>{insc.formation_id.display_name}</strong>
                        est en attente de votre part (statut : <em>{insc.statut}</em>).</p>
                        <p><a href="{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/formation/dossier/{insc.portal_token}">
                        Accéder à mon dossier</a></p>
                        <p>L'équipe FRMJC</p>
                    """,
                    'email_to': insc.partner_id.email,
                    'auto_delete': True,
                }).send()
                insc.write({
                    'date_derniere_relance': fields.Date.today(),
                    'nb_relances': insc.nb_relances + 1,
                })
            except Exception:
                pass
