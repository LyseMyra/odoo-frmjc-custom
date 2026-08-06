import base64
import logging
from datetime import date, timedelta

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class TrainingMonthlyReport(models.Model):
    _name = 'training.monthly.report'
    _description = 'Rapport mensuel de présence'
    _order = 'annee desc, mois desc, inscription_id'

    # ── Relations ─────────────────────────────────────────────────────
    inscription_id = fields.Many2one(
        'training.inscription', string='Inscription',
        required=True, ondelete='cascade', index=True,
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

    # ── Période ───────────────────────────────────────────────────────
    annee = fields.Integer(string='Année', required=True)
    mois = fields.Integer(string='Mois', required=True)
    periode = fields.Char(
        string='Période', compute='_compute_periode', store=True,
    )

    # ── Heures ────────────────────────────────────────────────────────
    heures_centre = fields.Float(
        string='Heures en centre', compute='_compute_heures', store=True,
    )
    heures_entreprise = fields.Float(
        string='Heures en entreprise', compute='_compute_heures', store=True,
    )
    heures_total = fields.Float(
        string='Total heures', compute='_compute_heures', store=True,
    )
    jours_presents = fields.Integer(
        string='Jours présents', compute='_compute_heures', store=True,
    )
    jours_absents = fields.Integer(
        string='Jours absents', compute='_compute_heures', store=True,
    )

    # ── Documents ─────────────────────────────────────────────────────
    convocation_pdf = fields.Binary(string='Convocation PDF', attachment=True)
    convocation_pdf_filename = fields.Char()
    convocation_envoyee_le = fields.Datetime(string='Convocation envoyée le')

    attestation_pdf = fields.Binary(string='Attestation de présence PDF', attachment=True)
    attestation_pdf_filename = fields.Char()

    certificat_financeur_pdf = fields.Binary(
        string='Certificat financeur PDF', attachment=True,
    )
    certificat_financeur_pdf_filename = fields.Char()

    # ── Statut ────────────────────────────────────────────────────────
    statut = fields.Selection([
        ('brouillon',           'Brouillon'),
        ('convocation_envoyee', 'Convocation envoyée'),
        ('attestation_generee', 'Attestation générée'),
        ('signe',               'Signé'),
        ('transmis',            'Transmis'),
    ], string='Statut', default='brouillon', required=True)

    notes = fields.Text(string='Notes')

    # ── Unicité ───────────────────────────────────────────────────────
    _rapport_unique = models.Constraint(
        'UNIQUE(inscription_id, annee, mois)',
        'Un rapport mensuel existe déjà pour ce stagiaire et ce mois.',
    )

    # ── Compute ───────────────────────────────────────────────────────
    @api.depends('annee', 'mois')
    def _compute_periode(self):
        for rec in self:
            if rec.annee and rec.mois:
                rec.periode = f'{rec.annee:04d}-{rec.mois:02d}'
            else:
                rec.periode = ''

    @api.depends('inscription_id', 'annee', 'mois')
    def _compute_heures(self):
        Attendance = self.env['training.attendance']
        WeekLine = self.env['training.week.line']
        for rec in self:
            if not (rec.inscription_id and rec.annee and rec.mois):
                rec.heures_centre = rec.heures_entreprise = 0.0
                rec.heures_total = rec.jours_presents = rec.jours_absents = 0
                continue

            periode = f'{rec.annee:04d}-{rec.mois:02d}'
            presences = Attendance.search([
                ('inscription_id', '=', rec.inscription_id.id),
                ('mois_annee', '=', periode),
            ])

            heures_c = sum(
                p.heures for p in presences if p.statut in ('present',)
            )
            jours_p = len({p.date for p in presences if p.statut == 'present'})
            jours_a = len({p.date for p in presences if p.statut == 'absent'})

            # Heures entreprise : jours de session sans ligne de ruban × 7 h
            session = rec.inscription_id.session_id
            heures_e = 0.0
            if session:
                all_lines = WeekLine.search([
                    ('session_id', '=', session.id),
                ])
                centre_dates = {
                    l.date_jour for l in all_lines
                    if l.date_jour
                    and l.date_jour.year == rec.annee
                    and l.date_jour.month == rec.mois
                }
                for week in session.week_ids:
                    if not week.date_debut:
                        continue
                    d = week.date_debut
                    while d <= week.date_fin:
                        if (d.weekday() < 5
                                and d.year == rec.annee
                                and d.month == rec.mois
                                and d not in centre_dates):
                            heures_e += 7.0
                        d += timedelta(days=1)

            rec.heures_centre = heures_c
            rec.heures_entreprise = heures_e
            rec.heures_total = heures_c + heures_e
            rec.jours_presents = jours_p
            rec.jours_absents = jours_a

    def _compute_display_name(self):
        mois_fr = {
            1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
            5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
            9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre',
        }
        for rec in self:
            mois_label = mois_fr.get(rec.mois, str(rec.mois))
            stagiaire = rec.partner_id.name or '?'
            rec.display_name = f'{stagiaire} — {mois_label} {rec.annee}'

    # ── Actions ───────────────────────────────────────────────────────
    def action_generer_convocation(self):
        self.ensure_one()
        report_action = self.env.ref(
            'training_frmjc.report_training_convocation', raise_if_not_found=False,
        )
        if not report_action:
            return
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            report_action, [self.id],
        )
        mois_fr = {
            1:'Janvier', 2:'Février', 3:'Mars', 4:'Avril', 5:'Mai', 6:'Juin',
            7:'Juillet', 8:'Août', 9:'Septembre', 10:'Octobre', 11:'Novembre', 12:'Décembre',
        }
        mois_label = mois_fr.get(self.mois, str(self.mois))
        nom = (self.partner_id.name or 'stagiaire').replace(' ', '_')
        filename = f'Convocation_{mois_label}_{self.annee}_{nom}.pdf'
        self.write({
            'convocation_pdf': base64.b64encode(pdf_content),
            'convocation_pdf_filename': filename,
        })

    def action_generer_attestation(self):
        self.ensure_one()
        report_action = self.env.ref(
            'training_frmjc.report_training_attestation_mensuelle', raise_if_not_found=False,
        )
        if not report_action:
            return
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            report_action, [self.id],
        )
        nom = (self.partner_id.name or 'stagiaire').replace(' ', '_')
        filename = f'Attestation_{self.periode}_{nom}.pdf'
        self.write({
            'attestation_pdf': base64.b64encode(pdf_content),
            'attestation_pdf_filename': filename,
            'statut': 'attestation_generee',
        })

    def action_envoyer_convocation(self):
        """Génère et envoie la convocation par email."""
        for rec in self:
            if not rec.convocation_pdf:
                rec.action_generer_convocation()
            if not rec.partner_id.email:
                continue
            try:
                attachment = self.env['ir.attachment'].create({
                    'name': rec.convocation_pdf_filename or 'convocation.pdf',
                    'datas': rec.convocation_pdf,
                    'mimetype': 'application/pdf',
                    'res_model': self._name,
                    'res_id': rec.id,
                })
                mail = self.env['mail.mail'].sudo().create({
                    'subject': (
                        f'Convocation — {rec.periode} — '
                        f'{rec.formation_id.display_name}'
                    ),
                    'body_html': f"""
                        <p>Bonjour {rec.partner_id.name},</p>
                        <p>Veuillez trouver ci-jointe votre convocation
                        pour le mois de {rec.periode}.</p>
                        <p><em>Les horaires et pauses sont à préciser
                        collectivement.</em></p>
                        <p>Cordialement,<br/>L'équipe FRMJC</p>
                    """,
                    'email_to': rec.partner_id.email,
                    'attachment_ids': [(4, attachment.id)],
                    'auto_delete': True,
                })
                mail.send()
                rec.write({
                    'convocation_envoyee_le': fields.Datetime.now(),
                    'statut': 'convocation_envoyee',
                })
            except Exception as exc:
                _logger.warning('Envoi convocation %s: %s', rec.id, exc)

    def get_presences_par_semaine(self):
        """Retourne [(semaine_label, [(date, dj_matin, dj_aprem), ...]), ...]
        pour le template QWeb de l'attestation mensuelle."""
        from collections import defaultdict
        Attendance = self.env['training.attendance']
        periode = f'{self.annee:04d}-{self.mois:02d}'
        presences = Attendance.search([
            ('inscription_id', '=', self.inscription_id.id),
            ('mois_annee', '=', periode),
        ], order='date, demi_journee')

        # Group by date
        par_date = defaultdict(dict)
        for p in presences:
            par_date[p.date][p.demi_journee] = p

        # Group by ISO week
        par_semaine = defaultdict(list)
        for d in sorted(par_date.keys()):
            semaine_key = d.strftime('%Y-S%V')
            par_semaine[semaine_key].append((d, par_date[d]))

        jours_fr = {0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi', 4: 'Vendredi'}
        result = []
        for semaine_key in sorted(par_semaine.keys()):
            rows = par_semaine[semaine_key]
            d_debut = rows[0][0]
            label = f'Semaine du {d_debut.strftime("%d/%m/%Y")}'
            result.append((label, [
                (d, jours_fr.get(d.weekday(), ''), presences_dict)
                for d, presences_dict in rows
            ]))
        return result

    def get_jours_entreprise(self):
        """Retourne la liste des dates de jours en entreprise pour ce mois."""
        WeekLine = self.env['training.week.line']
        session = self.inscription_id.session_id
        if not session:
            return []

        all_lines = WeekLine.search([('session_id', '=', session.id)])
        centre_dates = {
            l.date_jour for l in all_lines
            if l.date_jour
            and l.date_jour.year == self.annee
            and l.date_jour.month == self.mois
        }
        enterprise_days = []
        for week in session.week_ids:
            if not week.date_debut:
                continue
            d = week.date_debut
            while d <= week.date_fin:
                if (d.weekday() < 5
                        and d.year == self.annee
                        and d.month == self.mois
                        and d not in centre_dates):
                    enterprise_days.append(d)
                d += timedelta(days=1)
        return sorted(enterprise_days)

    def get_semaines_calendrier(self):
        """Retourne la structure calendrier complète pour l'attestation mensuelle.
        Chaque semaine : dict {'jours': [...6 dicts jour...], 'tot_stage': float, 'tot_centre': float}
        Chaque jour : {'code', 'date'|None, 'in_month', 'h_stage'|None, 'h_centre'|None, 'motif'}
        h_stage/h_centre = None → pas un jour de ce type ; 0.0 → absent ; >0 → heures présentes."""
        import calendar as cal_mod

        if not (self.annee and self.mois and self.inscription_id):
            return []

        Attendance = self.env['training.attendance']
        WeekLine = self.env['training.week.line']
        session = self.inscription_id.session_id

        # Heures de présence (centre) et motifs
        periode = f'{self.annee:04d}-{self.mois:02d}'
        presences = Attendance.search([
            ('inscription_id', '=', self.inscription_id.id),
            ('mois_annee', '=', periode),
        ])
        h_par_date = {}
        motif_par_date = {}
        for p in presences:
            if p.statut == 'present':
                h_par_date[p.date] = h_par_date.get(p.date, 0.0) + p.heures
            if p.motif_absence and p.date not in motif_par_date:
                motif_par_date[p.date] = p.motif_absence

        # Jours formation en centre vs jours dans la session (alternance)
        centre_dates = set()
        session_dates = set()
        if session:
            all_lines = WeekLine.search([('session_id', '=', session.id)])
            for ln in all_lines:
                if ln.date_jour and ln.date_jour.year == self.annee and ln.date_jour.month == self.mois:
                    centre_dates.add(ln.date_jour)
            for week in session.week_ids:
                if not (week.date_debut and week.date_fin):
                    continue
                d = week.date_debut
                while d <= week.date_fin:
                    if d.year == self.annee and d.month == self.mois:
                        session_dates.add(d)
                    d += timedelta(days=1)

        premier = date(self.annee, self.mois, 1)
        dernier = date(self.annee, self.mois, cal_mod.monthrange(self.annee, self.mois)[1])
        lundi_debut = premier - timedelta(days=premier.weekday())

        codes = ['L', 'M', 'M', 'J', 'V', 'S']
        semaines = []
        lundi = lundi_debut
        while lundi <= dernier:
            jours = []
            tot_stage = 0.0
            tot_centre = 0.0
            for i, code in enumerate(codes):
                d = lundi + timedelta(days=i)
                in_month = (d.month == self.mois and d.year == self.annee)
                is_weekday = i < 5

                h_stage = None
                h_centre = None
                motif = ''

                if in_month and is_weekday:
                    motif = motif_par_date.get(d, '')
                    if d in centre_dates:
                        h_centre = h_par_date.get(d, 0.0)
                        tot_centre += h_centre
                    elif d in session_dates:
                        h_stage = 7.0
                        tot_stage += h_stage

                jours.append({
                    'code': code,
                    'date': d if in_month else None,
                    'in_month': in_month,
                    'h_stage': h_stage,
                    'h_centre': h_centre,
                    'motif': motif,
                })

            semaines.append({
                'jours': jours,
                'tot_stage': tot_stage,
                'tot_centre': tot_centre,
            })
            lundi += timedelta(days=7)

        return semaines

    # ── Crons ────────────────────────────────────────────────────────
    @api.model
    def _cron_generer_rapports_mensuels(self):
        """Génère les rapports du mois précédent pour toutes les sessions actives."""
        today = date.today()
        mois = today.month - 1 or 12
        annee = today.year if today.month > 1 else today.year - 1

        sessions = self.env['training.session'].search([('statut', '=', 'en_cours')])
        for session in sessions:
            for insc in session.inscription_ids.filtered(
                lambda i: i.statut == 'accepte'
            ):
                existing = self.search([
                    ('inscription_id', '=', insc.id),
                    ('annee', '=', annee),
                    ('mois', '=', mois),
                ], limit=1)
                if not existing:
                    self.create({
                        'inscription_id': insc.id,
                        'annee': annee,
                        'mois': mois,
                    })
