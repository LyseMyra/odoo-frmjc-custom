from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TrainingWeek(models.Model):
    _name = 'training.week'
    _description = 'Semaine du planning (ruban pédagogique)'
    _order = 'date_debut'

    # ── Relation principale ────────────────────────────────────────
    session_id = fields.Many2one(
        'training.session',
        string='Session',
        required=True,
        ondelete='cascade',
    )
    formation_id = fields.Many2one(
        related='session_id.formation_id',
        string='Formation',
        store=True,
        readonly=True,
    )

    # ── Identification ──────────────────────────────────────────────
    numero_semaine = fields.Integer(
        string='Numéro de semaine',
        help='Numéro de la semaine calendaire (1 à 52)'
    )
    date_debut = fields.Date(
        string='Date de début',
        required=True,
    )
    date_fin = fields.Date(
        string='Date de fin',
        required=True,
    )

    # ── Statut et type ────────────────────────────────────────────
    statut = fields.Selection(
        selection=[
            ('valide', 'Valide'),
            ('exclue_auto', 'Exclue automatiquement (jour férié)'),
            ('exclue_manuelle', 'Exclue manuellement'),
            ('incluse', 'Incluse dans le ruban'),
        ],
        string='Statut',
        default='valide',
        required=True,
    )
    motif_exclusion = fields.Char(
        string='Motif d\'exclusion',
        help='Vacances scolaires, contrainte intervenant, événement local...'
    )

    type_semaine = fields.Selection(
        selection=[
            ('formation', 'Semaine de formation'),
            ('certification', 'Certification d\'un BC'),
            ('remediation', 'Remédiation d\'un BC'),
            ('rencontre_tuteurs', 'Rencontre tuteurs'),
            ('animation', 'Animation temps de formation'),
            ('autre', 'Autre'),
        ],
        string='Type de semaine',
        help='Vide si semaine de formation standard, sinon type hors-formation'
    )

    # ── Relations ──────────────────────────────────────────────────
    week_line_ids = fields.One2many(
        'training.week.line',
        'week_id',
        string='Affectations module/jour',
    )

    # ── Nom (requis par les vues calendrier / fil d'Ariane) ────────
    name = fields.Char(
        string='Libellé',
        compute='_compute_name',
        store=True,
    )

    # ── Contenu pédagogique de la semaine ──────────────────────────
    theme = fields.Char(
        string='Thème / Contenu',
        help='Description du programme de la semaine (ex : Conduire le projet - Dynamique de groupe)',
    )
    lieu = fields.Char(
        string='Lieu',
        default='À définir',
        help='Ville ou site de la semaine de formation',
    )
    blocs_competences = fields.Char(
        string='Blocs de compétences',
        help='BCs couverts cette semaine (ex : BC1 - BC2). '
             'Laissez vide et utilisez "Calculer depuis les modules" pour déduire automatiquement.',
    )

    # ── Date formatée pour les rapports ───────────────────────────
    date_range_str = fields.Char(
        string='Période (texte)',
        compute='_compute_date_range_str',
        store=True,
    )

    # ── Calculs ────────────────────────────────────────────────────
    volume_horaire_calcule = fields.Float(
        string='Volume horaire calculé (h)',
        compute='_compute_volume_horaire',
        store=True,
        help='Somme des heures affectées sur la semaine'
    )
    contient_jour_ferie = fields.Boolean(
        string='Contient un jour férié',
        default=False,
    )
    mois_annee = fields.Char(
        string='Mois',
        compute='_compute_mois_annee',
        store=True,
    )

    # ── Contrôle intervenants ──────────────────────────────────────
    all_intervenants_definis = fields.Boolean(
        string='Tous les intervenants définis',
        compute='_compute_intervenants', store=True,
    )
    nb_lignes_sans_intervenant = fields.Integer(
        string='Lignes sans intervenant',
        compute='_compute_intervenants', store=True,
    )

    # ── Résumés quotidiens pour la vue ruban ───────────────────────
    resume_lundi = fields.Char(
        string='Lundi', compute='_compute_resume_jours', store=True)
    resume_mardi = fields.Char(
        string='Mardi', compute='_compute_resume_jours', store=True)
    resume_mercredi = fields.Char(
        string='Mercredi', compute='_compute_resume_jours', store=True)
    resume_jeudi = fields.Char(
        string='Jeudi', compute='_compute_resume_jours', store=True)
    resume_vendredi = fields.Char(
        string='Vendredi', compute='_compute_resume_jours', store=True)

    # ── Contraintes Python ─────────────────────────────────────────
    # Pas de contrainte SQL UNIQUE sur numero_semaine car les événements non-formation
    # utilisent 0 (non numérotés) et plusieurs peuvent coexister.
    @api.constrains('session_id', 'numero_semaine')
    def _check_unique_numero(self):
        for rec in self:
            if rec.numero_semaine and rec.numero_semaine > 0:
                duplicates = self.search([
                    ('session_id', '=', rec.session_id.id),
                    ('numero_semaine', '=', rec.numero_semaine),
                    ('id', '!=', rec.id),
                ])
                if duplicates:
                    raise ValidationError(
                        f'Le numéro S{rec.numero_semaine} existe déjà '
                        f'pour cette session.'
                    )

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends('numero_semaine', 'type_semaine')
    def _compute_name(self):
        type_labels = dict(self._fields['type_semaine'].selection)
        for rec in self:
            num = f'S{rec.numero_semaine}' if rec.numero_semaine else 'Semaine'
            type_label = type_labels.get(rec.type_semaine, '')
            rec.name = f'{num} – {type_label}' if type_label else num

    @api.depends('week_line_ids.heures')
    def _compute_volume_horaire(self):
        for rec in self:
            rec.volume_horaire_calcule = sum(
                rec.week_line_ids.mapped('heures')
            )
            
    @api.depends('date_debut')
    def _compute_mois_annee(self):
        for rec in self:
            if rec.date_debut:
                rec.mois_annee = rec.date_debut.strftime('%Y-%m %B')
            else:
                rec.mois_annee = ''

    @api.depends('date_debut', 'date_fin')
    def _compute_date_range_str(self):
        mois_fr = {
            1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril',
            5: 'mai', 6: 'juin', 7: 'juillet', 8: 'août',
            9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre',
        }
        jours_fr = {0: 'lundi', 1: 'mardi', 2: 'mercredi',
                    3: 'jeudi', 4: 'vendredi', 5: 'samedi', 6: 'dimanche'}
        for rec in self:
            if rec.date_debut and rec.date_fin:
                d1, d2 = rec.date_debut, rec.date_fin
                if d1 == d2:
                    # Journée unique (certification, remédiation…)
                    rec.date_range_str = (
                        f"{jours_fr[d1.weekday()]} {d1.day} {mois_fr[d1.month]} {d1.year}"
                    )
                elif d1.month == d2.month and d1.year == d2.year:
                    rec.date_range_str = (
                        f"du {d1.day} au {d2.day} {mois_fr[d1.month]} {d1.year}"
                    )
                else:
                    rec.date_range_str = (
                        f"du {d1.day} {mois_fr[d1.month]} "
                        f"au {d2.day} {mois_fr[d2.month]} {d2.year}"
                    )
            else:
                rec.date_range_str = ''

    @api.depends('week_line_ids.jour', 'week_line_ids.module_id.code',
                 'week_line_ids.module_id.intitule', 'week_line_ids.heures')
    def _compute_resume_jours(self):
        for rec in self:
            for jour in ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi'):
                lignes = rec.week_line_ids.filtered(lambda l, j=jour: l.jour == j)
                labels = []
                for line in lignes:
                    if line.module_id.code:
                        labels.append(line.module_id.code)
                    elif line.module_id.intitule:
                        txt = line.module_id.intitule
                        labels.append(txt[:22] + '…' if len(txt) > 22 else txt)
                rec[f'resume_{jour}'] = ' · '.join(labels)

    @api.depends('week_line_ids', 'week_line_ids.intervenant_id')
    def _compute_intervenants(self):
        for rec in self:
            if not rec.week_line_ids:
                rec.all_intervenants_definis = False
                rec.nb_lignes_sans_intervenant = 0
            else:
                manquants = rec.week_line_ids.filtered(lambda l: not l.intervenant_id)
                rec.nb_lignes_sans_intervenant = len(manquants)
                rec.all_intervenants_definis = len(manquants) == 0

    def action_generer_presences(self):
        """Génère les présences pour toutes les inscriptions acceptées de cette semaine."""
        from odoo.exceptions import UserError
        from collections import defaultdict
        Attendance = self.env['training.attendance']
        FormateurSemaine = self.env['training.formateur.semaine']
        FormateurDJ = self.env['training.formateur.demi_journee']
        total_created = 0
        avertissements = []

        for week in self:
            if week.type_semaine != 'formation':
                continue

            # Vérifier les inscriptions acceptées
            inscriptions = week.session_id.inscription_ids.filtered(
                lambda i: i.statut == 'accepte'
            )
            if not inscriptions:
                nb_total = len(week.session_id.inscription_ids)
                if nb_total == 0:
                    avertissements.append(
                        f'Aucun dossier d\'inscription dans la session "{week.session_id.name}".'
                    )
                else:
                    avertissements.append(
                        f'{nb_total} inscription(s) dans la session mais aucune avec statut "Accepté". '
                        f'Acceptez les candidatures depuis le menu Inscriptions avant de générer les présences.'
                    )
                continue

            # Calculer heures, intervenant par date et par (date, demi_journee)
            date_hours = {}
            date_intervenant = {}
            date_dj_intervenant = {}  # {(date, dj): (intervenant_id, heures)}
            for line in week.week_line_ids:
                if not line.date_jour:
                    continue
                date_hours[line.date_jour] = (
                    date_hours.get(line.date_jour, 0.0) + line.heures
                )
                if line.intervenant_id:
                    existing = date_intervenant.get(line.date_jour, (None, 0.0))
                    if line.heures > existing[1]:
                        date_intervenant[line.date_jour] = (line.intervenant_id.id, line.heures)
                    # Déterminer la ou les demi-journées couvertes par cette ligne
                    if line.heure_debut >= 13:
                        djs_line = ['apres_midi']
                    elif 0 < line.heure_debut < 13:
                        djs_line = ['matin']
                    else:
                        djs_line = ['matin', 'apres_midi']
                    for dj in djs_line:
                        key = (line.date_jour, dj)
                        ex = date_dj_intervenant.get(key, (None, 0.0))
                        if line.heures > ex[1]:
                            date_dj_intervenant[key] = (line.intervenant_id.id, line.heures)

            if not date_hours:
                avertissements.append(
                    f'Semaine {week.name} : aucune date calculée sur les lignes de programme '
                    f'(vérifiez que la date de début de la semaine est renseignée).'
                )
                continue

            insc_ids = [i.id for i in inscriptions]
            for d, total_h in sorted(date_hours.items()):
                h_demi = round((total_h / 2.0) * 2) / 2
                intervenant_id = date_intervenant.get(d, (None,))[0]

                # Mettre à jour l'intervenant sur les présences existantes sans intervenant
                if intervenant_id:
                    Attendance.search([
                        ('inscription_id', 'in', insc_ids),
                        ('date', '=', d),
                        ('intervenant_id', '=', False),
                    ]).write({'intervenant_id': intervenant_id})

                for insc in inscriptions:
                    for dj in ('matin', 'apres_midi'):
                        exists = Attendance.search([
                            ('inscription_id', '=', insc.id),
                            ('date', '=', d),
                            ('demi_journee', '=', dj),
                        ], limit=1)
                        if not exists:
                            Attendance.create({
                                'inscription_id': insc.id,
                                'date': d,
                                'demi_journee': dj,
                                'heures': h_demi,
                                'statut': 'a_confirmer',
                                'intervenant_id': intervenant_id,
                            })
                            total_created += 1

            # Créer les fiches hebdomadaires intervenant (une par intervenant par semaine)
            session = week.session_id
            interv_djs = defaultdict(list)
            for (d, dj), (interv_id, _) in date_dj_intervenant.items():
                if interv_id:
                    interv_djs[interv_id].append((d, dj))

            for interv_id, dj_list in interv_djs.items():
                semaine = FormateurSemaine.search([
                    ('session_id', '=', session.id),
                    ('intervenant_id', '=', interv_id),
                    ('week_start', '=', week.date_debut),
                ], limit=1)
                if not semaine:
                    semaine = FormateurSemaine.create({
                        'session_id': session.id,
                        'intervenant_id': interv_id,
                        'week_start': week.date_debut,
                    })
                for d, dj in dj_list:
                    if not FormateurDJ.search([
                        ('semaine_id', '=', semaine.id),
                        ('date', '=', d),
                        ('demi_journee', '=', dj),
                    ], limit=1):
                        FormateurDJ.create({
                            'semaine_id': semaine.id,
                            'date': d,
                            'demi_journee': dj,
                        })

            if interv_djs:
                self.env.flush_all()

        if avertissements and not total_created:
            raise UserError('\n\n'.join(avertissements))

        message = f'{total_created} demi-journée(s) créée(s).'
        if avertissements:
            message += '\n\nAvertissements :\n' + '\n'.join(f'• {w}' for w in avertissements)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Présences générées' if total_created else 'Aucune présence créée',
                'message': message,
                'type': 'success' if total_created else 'warning',
                'sticky': bool(avertissements),
            },
        }

    def action_envoyer_listes_intervenants(self):
        """Envoie (ou renvoie) l'email hebdomadaire aux intervenants de cette semaine."""
        from odoo.exceptions import UserError
        FormateurSemaine = self.env['training.formateur.semaine']
        semaines = FormateurSemaine
        for week in self:
            if week.type_semaine != 'formation':
                continue
            semaines |= FormateurSemaine.search([
                ('session_id', '=', week.session_id.id),
                ('week_start', '=', week.date_debut),
            ])
        if not semaines:
            raise UserError(
                'Aucune fiche hebdomadaire trouvée pour cette semaine. '
                'Générez d\'abord les présences.'
            )
        nb = semaines.action_envoyer_email()
        sans_email = [
            r.intervenant_id.name for r in semaines if not r.intervenant_id.email
        ]
        message = f'Email hebdomadaire envoyé à {nb} intervenant(s).'
        if sans_email:
            message += f'\n⚠ Sans adresse email (non envoyé) : {", ".join(sans_email)}.'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Emails envoyés' if nb else 'Aucun email envoyé',
                'message': message,
                'type': 'success' if nb else 'warning',
                'sticky': bool(sans_email),
            },
        }

    def action_calculer_bc(self):
        """Déduit les blocs de compétences depuis les lignes de modules affectées."""
        for rec in self:
            blocs = rec.week_line_ids.mapped('module_id.bloc_id')
            blocs_sorted = blocs.sorted(lambda b: (b.type_bloc or '', b.name or ''))
            rec.blocs_competences = ' - '.join(b.name for b in blocs_sorted if b.name)

    def get_lignes_par_jour(self):
        """Retourne {jour: recordset} pour le template PDF ruban."""
        jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi']
        return {j: self.week_line_ids.filtered(lambda l, jour=j: l.jour == jour)
                for j in jours}

    # ── Contraintes Python ─────────────────────────────────────────
    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_debut and rec.date_fin:
                if rec.date_fin < rec.date_debut:
                    raise ValidationError(
                        'La date de fin doit être postérieure ou égale '
                        'à la date de début.'
                    )

    @api.constrains('statut', 'type_semaine')
    def _check_type_coherent(self):
        for rec in self:
            if rec.statut == 'incluse' and not rec.type_semaine:
                raise ValidationError(
                    'Une semaine incluse doit avoir un type défini '
                    '(formation ou hors-formation).'
                )

