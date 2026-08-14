import uuid

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class MobilityMobility(models.Model):
    _name = "mobility.mobility"
    _description = "Mobilité de volontariat"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "name"

    # ── Identification ─────────────────────────────────────────────
    name = fields.Char(
        string="Référence mobilité",
        required=True,
        copy=False,
        default="Nouveau",
        tracking=True,
    )
    prn = fields.Char(
        string="PRN",
        copy=False,
        index=True,
        help="Clé unique BM par mobilité/participant — jamais réutilisé.",
    )
    reference_projet = fields.Char(string="Référence projet")
    action_cle = fields.Char(
        string="Action clé",
        help="Terminologie Erasmus+ (ex : ESC51 - Volontariat).",
    )

    # ── Relations réglementaires ──────────────────────────────────
    grant_id = fields.Many2one(
        "mobility.grant",
        string="Convention de subvention",
        tracking=True,
        ondelete="restrict",
    )
    habilitation_id = fields.Many2one(
        "mobility.habilitation",
        string="Habilitation label LEAD",
        tracking=True,
        ondelete="restrict",
    )
    lead_partner_id = fields.Many2one(
        related="habilitation_id.organisme_lead_id",
        string="Organisme LEAD",
        readonly=True,
        store=True,
    )
    activity_id = fields.Many2one(
        "mobility.activity",
        string="Activité",
        tracking=True,
        ondelete="restrict",
    )

    # ── Volontaire ──────────────────────────────────────────────────
    # participant_id n'est PAS required : une mobilité peut être créée
    # avec seulement les champs de classification (voir plus bas), le
    # lien du formulaire public envoyé à la structure d'accueil, et le
    # volontaire n'existe alors pas encore comme fiche contact.
    participant_id = fields.Many2one(
        "res.partner",
        string="Volontaire",
        tracking=True,
        ondelete="restrict",
    )
    participant_nom = fields.Char(string="Nom du volontaire")
    participant_prenom = fields.Char(string="Prénom du volontaire")
    email = fields.Char(
        string="Email participant",
        help="Pré-rempli depuis la fiche contact à la sélection du "
        "volontaire, mais modifiable et conservé indépendamment "
        "(fige la valeur au moment de la mobilité pour l'export BM).",
    )
    sexe = fields.Selection(
        selection=[("m", "Homme"), ("f", "Femme"), ("o", "Autre")],
        string="Sexe",
    )
    date_naissance = fields.Date(string="Date de naissance")
    age = fields.Integer(
        string="Âge",
        compute="_compute_age",
        store=True,
        help="Âge à la date de début réelle de mobilité, ou à la date de "
        "début proposée si la date réelle n'est pas encore connue.",
    )
    nationalite_id = fields.Many2one("res.country", string="Nationalité")
    pays_residence_id = fields.Many2one("res.country", string="Pays de résidence")
    ville_residence = fields.Char(string="Ville de résidence")
    jeune = fields.Boolean(
        string='Participant "Jeune" / moins d\'opportunités',
        help="Conditionne l'obligation d'autres champs (soutien à "
        "l'inclusion, RQTH...).",
    )

    # ── Structures ──────────────────────────────────────────────────
    sending_partner_id = fields.Many2one(
        "res.partner",
        string="Structure d'envoi",
        domain=[("structure_role_ids.code", "=", "envoi")],
    )
    hosting_partner_id = fields.Many2one(
        "res.partner",
        string="Structure d'accueil",
        domain=[("structure_role_ids.code", "=", "accueil")],
    )
    housing_partner_id = fields.Many2one(
        "res.partner",
        string="Hébergement",
        domain=[("structure_role_ids.code", "=", "hebergement")],
    )
    tutor_partner_id = fields.Many2one(
        "res.partner",
        string="Tuteur / Responsable",
    )
    support_partner_id = fields.Many2one(
        "res.partner",
        string="Organisme de soutien",
        domain=[("structure_role_ids.code", "=", "soutien")],
    )

    # ── Classification ────────────────────────────────────────────
    programme = fields.Selection(
        selection=[
            ("sc", "Service Civique (SC)"),
            ("ces", "Corps Européen de Solidarité (CES)"),
            ("vsi", "Volontariat Service International (VSI)"),
        ],
        string="Programme",
        required=True,
        tracking=True,
    )
    mobility_direction = fields.Selection(
        selection=[("accueil", "Accueil"), ("envoi", "Envoi")],
        string="Type mobilité",
        required=True,
        tracking=True,
    )
    mobility_duration = fields.Selection(
        selection=[
            ("court", "Court terme (15 à 59 jours)"),
            ("long", "Long terme (2 à 12 mois / 60 à 365 jours)"),
        ],
        string="Durée mobilité",
    )
    volunteering_type = fields.Selection(
        selection=[("individuel", "Individuel"), ("equipe", "Équipe")],
        string="Type de volontariat",
    )
    role_consortium = fields.Selection(
        selection=[
            ("porteur", "Porteur de projet"),
            ("lead", "LEAD (coordination)"),
        ],
        string="Rôle consortium",
    )

    # ── Lieu et dates de mission ────────────────────────────────────
    country_id = fields.Many2one("res.country", string="Pays de mission")
    department_id = fields.Many2one(
        "res.country.state",
        string="Département",
    )
    city = fields.Char(string="Ville de mission")
    # Non required : dates RÉELLES de mission, connues seulement une fois
    # l'arrivée du volontaire confirmée — ni à la création, ni via le
    # formulaire public (qui ne collecte que les dates proposées de
    # l'offre, ci-dessous). Renseignées plus tard par le secrétariat.
    start_date = fields.Date(string="Date de début", tracking=True)
    end_date = fields.Date(string="Date de fin", tracking=True)
    duree_jours = fields.Integer(
        string="Durée (jours)",
        compute="_compute_duree_jours",
        store=True,
    )

    # ── Offre ──────────────────────────────────────────────────────
    # Renseignée par la structure d'accueil via le formulaire public :
    # l'offre est individuelle par mobilité (même au sein d'une activité
    # partagée, §18.6), contrairement aux dates proposées de l'activité
    # elle-même qui n'existent plus sur mobility.activity (cf. correction
    # utilisateur — ces dates concernent l'offre, pas l'activité).
    offer_code = fields.Char(
        string="ID de l'offre",
        help="Identifiant technique BM, individuel par mobilité — distinct "
        "du code activité même en cas d'activité partagée (§18.6). "
        "Renseigné par la structure d'accueil via le formulaire public.",
    )
    titre_offre = fields.Char(string="Titre de l'offre")
    date_publication_offre = fields.Date(string="Date de publication")
    date_selection_offre = fields.Date(string="Date de sélection")
    statut_offre = fields.Selection(
        selection=[
            ("brouillon", "Brouillon"),
            ("publiee", "Publiée"),
            ("validee", "Validée"),
            ("cloturee", "Clôturée"),
        ],
        string="Statut offre",
    )
    source_offre = fields.Char(string="Source offre")
    date_debut_proposee = fields.Date(
        string="Date de début proposée",
        help="Date proposée par la structure d'accueil au moment de "
        "l'offre — distincte de la date de début réelle (ci-dessous), "
        "connue seulement une fois l'arrivée du volontaire confirmée.",
    )
    date_fin_proposee = fields.Date(
        string="Date de fin proposée",
        help="Idem, date de fin proposée au moment de l'offre.",
    )

    # ── Mission ──────────────────────────────────────────────────────
    heures_semaine = fields.Float(string="Nombre heures / semaine")
    langue_travail = fields.Char(string="Langue de travail")

    # ── Soutien linguistique & voyage ────────────────────────────────
    # Les clés de sélection reprennent volontairement les valeurs DICT
    # exactes attendues par l'export BM (§13 du cahier), pour éviter tout
    # mapping supplémentaire en Phase 10.
    soutien_linguistique_type = fields.Selection(
        selection=[
            ("LANGUAGE_SUPPORT_COURSE", "Cours de soutien linguistique"),
            ("LANGUAGE_SUPPORT_NO", "Non couvert"),
            ("LANGUAGE_SUPPORT_GRANT", "Subvention"),
        ],
        string="Soutien linguistique",
    )
    transport_principal = fields.Selection(
        selection=[
            ("PLANE", "Avion"),
            ("TRAIN", "Train"),
            ("BUS", "Bus"),
            ("CARPOOLING", "Covoiturage"),
            ("CAR_MOTORBIKE", "Voiture / moto"),
        ],
        string="Moyen de transport principal",
    )
    voyage_vert = fields.Boolean(string="Voyage vert (écoresponsable)")
    tranche_kilometrique = fields.Selection(
        selection=[
            ("BAND_09", "0-9 km (non éligible)"),
            ("BAND_11", "10-99 km"),
            ("BAND_20", "100-499 km (code provisoire)"),
            ("BAND_30", "500-1999 km"),
            ("BAND_40", "2000-2999 km"),
            ("BAND_50", "3000-3999 km"),
            ("BAND_60", "4000-7999 km (code provisoire)"),
            ("BAND_70", "8000 km et plus (code provisoire)"),
        ],
        string="Tranche kilométrique",
        help="BAND_09/11/30/40/50 confirmées par un échantillon BM réel ; "
        "BAND_20/60/70 provisoires (montants officiels confirmés par "
        "le guide Erasmus+, code BM exact non encore vérifié) — cf. "
        "mobility.rate.travel.",
    )
    distance_reelle = fields.Integer(string="Distance réelle (km)")
    force_majeure = fields.Boolean(string="Force majeure")
    force_majeure_explication = fields.Text(
        string="Explication force majeure",
        help="Obligatoire si « Force majeure » est cochée.",
    )
    rapport_demande_le = fields.Date(string="Rapport participant demandé le")
    rapport_recu_le = fields.Date(string="Rapport participant reçu le")

    # ── Suivi individuel (accompagnement) ────────────────────────────
    frequence_suivi = fields.Selection(
        selection=[
            ("hebdomadaire", "Hebdomadaire"),
            ("mensuelle", "Mensuelle"),
            ("trimestrielle", "Trimestrielle"),
        ],
        string="Fréquence de suivi",
    )
    mode_suivi = fields.Char(string="Mode de suivi")
    date_dernier_entretien = fields.Date(string="Dernier entretien")
    date_prochain_entretien = fields.Date(string="Prochain entretien")
    observations_suivi = fields.Text(string="Observations")

    # ── Suivi pédagogique (§15 du cahier) ─────────────────────────────
    objectifs_pedagogiques = fields.Text(string="Objectifs définis")
    objectifs_atteints = fields.Char(string="Objectifs atteints")
    points_forts = fields.Text(string="Points forts")
    axes_amelioration = fields.Text(string="Axes d'amélioration")
    evaluation_intermediaire = fields.Char(string="Évaluation intermédiaire")
    evaluation_finale = fields.Char(string="Évaluation finale (prévisionnelle)")

    # ── Fiche de renseignement (formulaire public, §4) ────────────────
    # Champs collectés directement auprès du volontaire via le formulaire
    # public (sans authentification, accès par portal_token). Volontairement
    # indépendants de la fiche contact du participant (comme `email`
    # ci-dessus) : ils figent l'information au moment de la mobilité plutôt
    # que de modifier le contact partagé, et évitent d'écrire des données
    # non vérifiées sur une fiche partenaire depuis un accès public.
    portal_token = fields.Char(string="Token portail", copy=False, index=True)
    telephone = fields.Char(string="Téléphone participant")
    id_document_numero = fields.Char(string="N° pièce d'identité / passeport")
    id_document_validite = fields.Date(string="Validité pièce d'identité")
    besoins_particuliers = fields.Text(
        string="Besoins particuliers",
        help="Allergies, traitement médical, régime alimentaire...",
    )

    # Contact d'urgence
    contact_urgence_nom = fields.Char(string="Contact d'urgence — Nom")
    contact_urgence_lien = fields.Char(string="Lien avec le volontaire")
    contact_urgence_adresse = fields.Char(string="Contact d'urgence — Adresse")
    contact_urgence_telephone = fields.Char(string="Contact d'urgence — Téléphone")
    contact_urgence_email = fields.Char(string="Contact d'urgence — Email")

    # Structures d'envoi et d'accueil — saisies via le formulaire public
    # (rempli par la structure d'accueil, qui connaît les deux). Le
    # contrôleur recherche un res.partner existant par OID, et n'en crée
    # un nouveau (avec ces champs) que s'il n'en trouve pas — cf.
    # sending_partner_id / hosting_partner_id pour le lien formel une
    # fois résolu. Ces champs restent la trace brute de la saisie.
    sending_org_nom = fields.Char(string="Structure d'envoi — Nom")
    sending_org_oid_saisi = fields.Char(string="Structure d'envoi — OID")
    sending_org_nom_legal = fields.Char(string="Structure d'envoi — Nom légal")
    sending_org_adresse = fields.Char(string="Structure d'envoi — Adresse")
    sending_org_type_organisme = fields.Char(
        string="Structure d'envoi — Type d'organisme"
    )
    sending_org_email = fields.Char(string="Structure d'envoi — Email")
    sending_org_telephone = fields.Char(string="Structure d'envoi — Téléphone")
    sending_contact_nom = fields.Char(string="Coordinateur structure envoi")
    sending_contact_email = fields.Char(string="Email coordinateur")
    sending_contact_telephone = fields.Char(string="Téléphone coordinateur")

    hosting_org_nom = fields.Char(string="Structure d'accueil — Nom")
    hosting_org_oid_saisi = fields.Char(string="Structure d'accueil — OID")
    hosting_org_nom_legal = fields.Char(string="Structure d'accueil — Nom légal")
    hosting_org_adresse = fields.Char(string="Structure d'accueil — Adresse")
    hosting_org_type_organisme = fields.Char(
        string="Structure d'accueil — Type d'organisme"
    )
    hosting_org_email = fields.Char(string="Structure d'accueil — Email")
    hosting_org_telephone = fields.Char(string="Structure d'accueil — Téléphone")
    hosting_contact_nom = fields.Char(string="Référent structure d'accueil")
    hosting_contact_email = fields.Char(string="Email référent")
    hosting_contact_telephone = fields.Char(string="Téléphone référent")

    # Déclaration sur l'honneur
    declaration_acceptee = fields.Boolean(string="Déclaration sur l'honneur acceptée")
    date_declaration = fields.Date(string="Date de déclaration")
    lieu_declaration = fields.Char(string="Lieu de déclaration")
    signature_nom = fields.Char(
        string="Signature (nom complet saisi)",
        help="Confirmation par saisie du nom — pas de pad de signature "
        "graphique dans cette première version.",
    )
    fiche_renseignement_soumise_le = fields.Datetime(string="Fiche soumise le")

    # ── Convention de volontariat (référence externe, §5) ────────────
    # Produite sur une plateforme externe — le module ne fait que stocker
    # une référence et, éventuellement, un lien vers le document déposé.
    # convention_numero est généré automatiquement à la création (code
    # interne dérivé de la référence mobilité, ex. CV-MOB/2026/0001) et
    # n'est plus saisissable manuellement (readonly=True) — cf. create().
    convention_numero = fields.Char(
        string="Numéro de convention (volontariat)",
        readonly=True,
        copy=False,
        help="Généré automatiquement (CV- + référence mobilité).",
    )
    convention_date = fields.Date(string="Date de convention")
    convention_document_id = fields.Many2one(
        "mobility.document",
        string="Document de convention",
        domain=[("document_type", "=", "convention_volontariat")],
        help="Sélectionner le document correspondant déposé dans l'onglet "
        "Documents (type « Convention volontariat »).",
    )

    # ── Fiche de renseignement (gate de passage en Placement) ────────
    fiche_renseignement_validee = fields.Boolean(
        string="Fiche de renseignement validée",
        help="Coché une fois la fiche de renseignement du volontaire "
        "complète et vérifiée — condition de passage à l'étape "
        "« Placement en cours » (§4 du cahier).",
    )

    # ── Pipeline ──────────────────────────────────────────────────────
    # « annule » et « abandon » sont des sorties de parcours, atteignables
    # depuis plusieurs étapes différentes (pas seulement la précédente) —
    # volontairement absentes de statusbar_visible pour ne pas polluer la
    # barre de progression du parcours nominal, mais restent sélectionnables
    # via les boutons dédiés ci-dessous depuis n'importe quelle étape active.
    status = fields.Selection(
        selection=[
            ("selectionne", "Sélectionné"),
            ("formalites", "Formalités en cours"),
            ("placement", "Placement en cours"),
            ("mission", "En mission"),
            ("termine", "Terminé"),
            ("suivi_post", "Suivi post-mission"),
            ("annule", "Annulé"),
            ("abandon", "Abandon en cours de mission"),
        ],
        string="Statut",
        default="selectionne",
        required=True,
        tracking=True,
    )

    # ── Sortie de parcours (annulation / abandon) ────────────────────
    date_sortie = fields.Date(
        string="Date de sortie",
        help="Date d'annulation, ou dernier jour effectif en cas "
        "d'abandon en cours de mission.",
    )
    motif_sortie = fields.Text(
        string="Motif (annulation / abandon)",
        help="À renseigner avant de cliquer sur « Annuler la mobilité » "
        "ou « Déclarer un abandon ».",
    )

    # ── Avenants (prolongation / réduction, §2 — contrat modifié) ────
    avenant_ids = fields.One2many(
        "mobility.avenant",
        "mobility_id",
        string="Avenants",
    )
    nb_avenants = fields.Integer(
        string="Nb avenants",
        compute="_compute_nb_avenants",
    )

    # ── Alertes d'éligibilité (§20, non bloquantes) ───────────────────
    eligibility_alerts = fields.Text(
        string="Alertes d'éligibilité",
        compute="_compute_eligibility_alerts",
        store=True,
        help="Recalculées et affichées à chaque enregistrement — "
        "informatives, elles ne bloquent jamais la sauvegarde.",
    )

    # ── Documents ──────────────────────────────────────────────────
    document_ids = fields.One2many(
        "mobility.document",
        "mobility_id",
        string="Documents",
    )

    # ── Finance (grand livre) ────────────────────────────────────────
    finance_line_ids = fields.One2many(
        "mobility.finance.line",
        "mobility_id",
        string="Grand livre financier",
    )
    nb_documents = fields.Integer(
        string="Nb documents",
        compute="_compute_nb_documents",
    )

    # ── Responsable / société ────────────────────────────────────────
    user_id = fields.Many2one(
        "res.users",
        string="Responsable suivi",
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Société",
        default=lambda self: self.env.company,
    )

    # ── Contraintes SQL ────────────────────────────────────────────
    _unique_prn = models.Constraint(
        "UNIQUE(prn)", "Ce PRN est déjà utilisé par une autre mobilité."
    )

    # ── Création ───────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nouveau") == "Nouveau":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("mobility.mobility")
                    or "Nouveau"
                )
            if not vals.get("email") and vals.get("participant_id"):
                partner = self.env["res.partner"].browse(vals["participant_id"])
                vals["email"] = partner.email
            if not vals.get("portal_token"):
                vals["portal_token"] = uuid.uuid4().hex
            if not vals.get("convention_numero"):
                vals["convention_numero"] = f"CV-{vals['name']}"
        return super().create(vals_list)

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends("date_naissance", "start_date", "date_debut_proposee")
    def _compute_age(self):
        for rec in self:
            ref_date = rec.start_date or rec.date_debut_proposee
            if rec.date_naissance and ref_date:
                rec.age = relativedelta(ref_date, rec.date_naissance).years
            else:
                rec.age = 0

    @api.depends("start_date", "end_date")
    def _compute_duree_jours(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.duree_jours = (rec.end_date - rec.start_date).days
            else:
                rec.duree_jours = 0

    @api.depends("document_ids")
    def _compute_nb_documents(self):
        for rec in self:
            rec.nb_documents = len(rec.document_ids)

    @api.depends("avenant_ids")
    def _compute_nb_avenants(self):
        for rec in self:
            rec.nb_avenants = len(rec.avenant_ids)

    # ── Export BM (§12 du cahier) ────────────────────────────────────
    def _get_finance_bm_summary(self):
        """Agrège le grand livre par poste (durée / subvention par jour /
        total), au format observé dans l'échantillon BM réel (colonnes
        Durée + Subvention par jour répétées pour SO/JAMO/ADP)."""
        self.ensure_one()
        postes = (
            "soutien_organisationnel",
            "soutien_inclusion",
            "argent_poche",
            "cout_exceptionnel",
            "voyage",
        )
        summary = {}
        for poste in postes:
            lignes = self.finance_line_ids.filtered(
                lambda l, p=poste: l.subcategory_id.code == p
            )
            summary[poste] = {
                "nb_jours": sum(lignes.mapped("nb_jours")),
                "montant_journalier": lignes[:1].montant_journalier,
                "total": sum(lignes.mapped("montant_realise")),
            }
        summary["total_general"] = sum(self.finance_line_ids.mapped("montant_realise"))
        return summary

    def _check_bm_export_ready(self):
        """Contrôle préalable obligatoire avant export BM (§12) : renvoie
        la liste des erreurs bloquantes pour cette mobilité (liste vide
        si prête à exporter)."""
        self.ensure_one()
        erreurs = []
        champs_requis = [
            ("prn", "PRN"),
            ("offer_code", "ID de l'offre"),
            ("participant_id", "Volontaire"),
            ("email", "Email participant"),
            ("sexe", "Sexe"),
            ("date_naissance", "Date de naissance"),
            ("nationalite_id", "Nationalité"),
            ("country_id", "Pays de mission"),
            ("start_date", "Date de début"),
            ("end_date", "Date de fin"),
            ("transport_principal", "Moyen de transport (DICT)"),
            ("tranche_kilometrique", "Tranche kilométrique (DICT)"),
            ("soutien_linguistique_type", "Soutien linguistique (DICT)"),
        ]
        for field_name, label in champs_requis:
            if not self[field_name]:
                erreurs.append(f"{self.name} : champ « {label} » manquant.")
        if self.force_majeure and not self.force_majeure_explication:
            erreurs.append(f"{self.name} : explication force majeure manquante.")
        couts_exceptionnels = self.finance_line_ids.filtered(
            lambda l: l.subcategory_id.code == "cout_exceptionnel"
        )
        if couts_exceptionnels.filtered(lambda l: not l.justificatif_id):
            erreurs.append(
                f"{self.name} : justificatif manquant pour un coût exceptionnel."
            )
        return erreurs

    # ── Règles d'éligibilité ────────────────────────
    # Mécanisme retenu pour les règles non bloquantes : un champ calculé
    # stocké (`eligibility_alerts`), recalculé à chaque enregistrement et
    # affiché en bandeau d'avertissement sur la fiche — visible dès la
    # sauvegarde, sans jamais empêcher celle-ci. Seule la règle « âge »,
    # explicitement marquée bloquante dans le cahier, lève une exception.

    def _alerte_duree_cumulee_ces(self):
        """Règle 2 : durée cumulée des mobilités CES d'un même participant
        ≤ 12 mois, sans chevauchement de dates — alerte + validation
        manuelle (non bloquant)."""
        self.ensure_one()
        if self.programme != "ces" or not self.participant_id:
            return None
        mobilites = (
            self.env["mobility.mobility"].search(
                [
                    ("participant_id", "=", self.participant_id.id),
                    ("programme", "=", "ces"),
                ]
            )
            | self
        )
        mobilites = mobilites.filtered(lambda m: m.start_date and m.end_date)
        for a in mobilites:
            for b in mobilites:
                if (
                    a.id < b.id
                    and a.start_date <= b.end_date
                    and b.start_date <= a.end_date
                ):
                    return (
                        "Chevauchement de dates détecté entre plusieurs "
                        "mobilités CES de ce même participant."
                    )
        total_jours = sum((m.end_date - m.start_date).days for m in mobilites)
        if total_jours > 365:
            return (
                f"Durée cumulée des mobilités CES de ce participant : "
                f"{total_jours} jours — au-delà du plafond de 12 mois."
            )
        return None

    def _alerte_deuxieme_mobilite_longue(self):
        """Règle 3 : une 2e mobilité longue (>2 mois) n'est normalement
        autorisée que si jeune=Oui ou cas justifié — alerte, pas de
        blocage automatique."""
        self.ensure_one()
        if self.mobility_duration != "long" or not self.participant_id:
            return None
        autres = self.env["mobility.mobility"].search(
            [
                ("participant_id", "=", self.participant_id.id),
                ("mobility_duration", "=", "long"),
                ("id", "!=", self.id),
            ]
        )
        if autres and not self.jeune:
            return (
                "Ce participant a déjà une autre mobilité longue "
                "(>2 mois). Une deuxième mobilité longue n'est "
                "normalement autorisée que si le participant est "
                "marqué « Jeune » ou sur cas justifié."
            )
        return None

    def _alerte_agence_nationale(self):
        """Règle 5 : le pays de l'activité (individuel) ou au moins un
        participant (équipe) doit correspondre au pays de l'agence
        nationale associée à l'habilitation — alerte informative."""
        self.ensure_one()
        country = (
            self.habilitation_id.agence_nationale_country_id
            if self.habilitation_id
            else False
        )
        if not country or not self.country_id:
            return None
        if self.volunteering_type == "equipe" and self.activity_id:
            equipe = self.env["mobility.mobility"].search(
                [
                    ("activity_id", "=", self.activity_id.id),
                ]
            )
            pays_ok = (
                country in equipe.mapped("pays_residence_id")
                or self.country_id == country
            )
        else:
            pays_ok = self.country_id == country
        if not pays_ok:
            return (
                f"Le pays de mission ne correspond pas au pays de "
                f"l'agence nationale ({country.name}) associée à "
                f"l'habilitation — vérification recommandée."
            )
        return None

    @api.depends(
        "programme",
        "participant_id",
        "start_date",
        "end_date",
        "mobility_duration",
        "jeune",
        "habilitation_id",
        "habilitation_id.agence_nationale_country_id",
        "country_id",
        "volunteering_type",
        "activity_id",
        "pays_residence_id",
    )
    def _compute_eligibility_alerts(self):
        for rec in self:
            alertes = list(
                filter(
                    None,
                    [
                        rec._alerte_duree_cumulee_ces(),
                        rec._alerte_deuxieme_mobilite_longue(),
                        rec._alerte_agence_nationale(),
                    ],
                )
            )
            rec.eligibility_alerts = "\n".join(alertes) if alertes else False

    # ── Contraintes Python ─────────────────────────────────────────
    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date <= rec.start_date:
                raise ValidationError(
                    "La date de fin doit être postérieure à la date de début."
                )

    @api.constrains("force_majeure", "force_majeure_explication")
    def _check_force_majeure(self):
        for rec in self:
            if rec.force_majeure and not rec.force_majeure_explication:
                raise ValidationError(
                    "L'explication est obligatoire quand « Force majeure » "
                    "est cochée."
                )

    @api.constrains("date_naissance", "start_date", "date_debut_proposee")
    def _check_age_eligibilite(self):
        """Règle 1 (§20) : le volontaire doit avoir entre 18 et 30 ans à la
        date de début de mobilité — seule règle explicitement bloquante.
        Contrôlée dès que possible sur la date proposée, avant même que la
        date réelle ne soit connue."""
        for rec in self:
            ref_date = rec.start_date or rec.date_debut_proposee
            if rec.date_naissance and ref_date:
                age_debut = relativedelta(ref_date, rec.date_naissance).years
                if not (18 <= age_debut <= 30):
                    raise ValidationError(
                        "Le volontaire doit avoir entre 18 et 30 ans à la "
                        f"date de début de mobilité (âge calculé : {age_debut} ans)."
                    )

    # ── Actions de workflow ────────────────────────────────────────
    def action_marquer_formalites(self):
        self.write({"status": "formalites"})

    def action_valider_fiche_renseignement(self):
        """Validation manuelle back-office de la fiche de renseignement
        soumise via le formulaire public (§4 du cahier)."""
        for rec in self:
            if not rec.fiche_renseignement_soumise_le:
                raise UserError(
                    "La fiche de renseignement n'a pas encore été soumise "
                    "par le volontaire."
                )
            rec.fiche_renseignement_validee = True

    def action_ouvrir_fiche_renseignement(self):
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        return {
            "type": "ir.actions.act_url",
            "url": f"{base_url}/mobilite/fiche/{self.portal_token}",
            "target": "new",
        }

    def action_marquer_placement(self):
        for rec in self:
            if not rec.fiche_renseignement_validee:
                raise UserError(
                    "La fiche de renseignement doit être validée avant de "
                    "passer en « Placement en cours »."
                )
        self.write({"status": "placement"})

    def action_marquer_mission(self):
        for rec in self:
            structure_ok = (
                rec.hosting_partner_id
                if rec.mobility_direction == "accueil"
                else rec.sending_partner_id
            )
            if not structure_ok:
                raise UserError(
                    "La structure d'accueil (ou d'envoi) doit être confirmée "
                    "avant de passer en « En mission »."
                )
            # Règle 4 (§20) : une mobilité « Équipe » nécessite au moins 5
            # participants liés à la même activité, dont au moins 2 pays
            # de résidence différents 
            if rec.volunteering_type == "equipe" and rec.activity_id:
                equipe = self.search([("activity_id", "=", rec.activity_id.id)])
                if len(equipe) < 5:
                    raise UserError(
                        "Une mobilité « Équipe » nécessite au moins 5 "
                        f"participants liés à la même activité "
                        f"({len(equipe)} actuellement)."
                    )
                pays_distincts = equipe.mapped("pays_residence_id")
                if len(pays_distincts) < 2:
                    raise UserError(
                        "Une mobilité « Équipe » nécessite des participants "
                        "provenant d'au moins 2 pays différents."
                    )
        self.write({"status": "mission"})

    def action_marquer_termine(self):
        self.write({"status": "termine"})

    def action_marquer_suivi_post(self):
        self.write({"status": "suivi_post"})

    def action_marquer_selectionne(self):
        self.write({"status": "selectionne"})

    def action_marquer_annule(self):
        """Sortie de parcours avant mission (désistement, visa refusé,
        aucune structure trouvée...) — atteignable depuis n'importe quelle
        étape antérieure à « En mission »."""
        for rec in self:
            if not rec.motif_sortie:
                raise UserError(
                    "Merci de renseigner le motif avant d'annuler la mobilité."
                )
            rec.date_sortie = rec.date_sortie or fields.Date.today()
        self.write({"status": "annule"})

    def action_marquer_abandon(self):
        """Sortie de parcours en cours de mission (le volontaire rentre
        avant la fin prévue). La date de fin réelle est alignée sur la
        date de sortie effective si elle est antérieure, pour que les
        lignes financières calculables (indemnités) se resynchronisent
        automatiquement sur la durée réellement effectuée."""
        for rec in self:
            if not rec.motif_sortie:
                raise UserError(
                    "Merci de renseigner le motif avant de déclarer l'abandon."
                )
            rec.date_sortie = rec.date_sortie or fields.Date.today()
            if rec.end_date and rec.date_sortie < rec.end_date:
                rec.end_date = rec.date_sortie
        self.write({"status": "abandon"})

    # ── Fiche de renseignement : logique partagée ─────────────────────
    # Utilisée à la fois par le formulaire public (portal_fiche_renseignement)
    # et par l'import Excel (mobility.import.fiche.wizard) — un seul et même
    # chemin de résolution/écriture, quel que soit le canal de saisie.
    @api.model
    def _find_or_create_participant(self, post):
        email = (post.get("email") or "").strip()
        Partner = self.env["res.partner"]
        partner = Partner.search([("email", "=", email)], limit=1) if email else False
        if partner:
            return partner
        prenom = (post.get("participant_prenom") or "").strip()
        nom = (post.get("participant_nom") or "").strip()
        name = f"{prenom} {nom}".strip() or email
        return Partner.create({
            "name": name or "Volontaire (à compléter)",
            "email": email or False,
            "is_company": False,
        })

    @api.model
    def _find_or_create_structure(self, post, prefix, role_code):
        """Cherche un partenaire structure par OID ; en crée un nouveau
        avec les champs saisis si aucune correspondance n'est trouvée.
        Ne modifie jamais un partenaire déjà existant (le rapprochement
        par OID ne fait que lier, il n'écrase pas des données déjà
        connues du secrétariat)."""
        oid = (post.get(f"{prefix}_oid_saisi") or "").strip()
        Partner = self.env["res.partner"]
        if oid:
            partner = Partner.search([("oid", "=", oid)], limit=1)
            if partner:
                return partner

        nom = (post.get(f"{prefix}_nom") or post.get(f"{prefix}_nom_legal") or "").strip()
        if not nom:
            return False

        role = self.env["mobility.structure.role"].search(
            [("code", "=", role_code)], limit=1,
        )
        return Partner.create({
            "name": nom,
            "is_company": True,
            "oid": oid or False,
            "nom_legal": post.get(f"{prefix}_nom_legal"),
            "adresse_legale": post.get(f"{prefix}_adresse"),
            "type_organisme": post.get(f"{prefix}_type_organisme") or False,
            "email": post.get(f"{prefix}_email"),
            "phone": post.get(f"{prefix}_telephone"),
            "structure_role_ids": [(4, role.id)] if role else False,
        })

    @api.model
    def _build_fiche_vals(self, post):
        """Construit le dict de valeurs pour écrire les informations de la
        fiche de renseignement (§4) à partir d'un dict « post-like » —
        mêmes clés que le formulaire public (participant_prenom, email,
        sending_org_nom...). `fields.Date.to_date` accepte indifféremment
        une chaîne 'AAAA-MM-JJ' ou un objet date/datetime, ce qui permet de
        réutiliser exactement ce même code que la valeur vienne du POST
        HTML du formulaire ou d'une cellule Excel déjà parsée."""
        participant = self._find_or_create_participant(post)
        sending_partner = self._find_or_create_structure(post, "sending_org", "envoi")
        hosting_partner = self._find_or_create_structure(post, "hosting_org", "accueil")

        def _many2one_id(field_name):
            value = post.get(field_name)
            return int(value) if value else False

        return {
            "participant_id": participant.id if participant else False,
            "participant_prenom": post.get("participant_prenom"),
            "participant_nom": post.get("participant_nom"),
            "email": post.get("email"),
            "telephone": post.get("telephone"),
            "date_naissance": fields.Date.to_date(post.get("date_naissance")),
            "nationalite_id": _many2one_id("nationalite_id"),
            "pays_residence_id": _many2one_id("pays_residence_id"),
            "ville_residence": post.get("ville_residence"),
            "id_document_numero": post.get("id_document_numero"),
            "id_document_validite": fields.Date.to_date(post.get("id_document_validite")),
            "besoins_particuliers": post.get("besoins_particuliers"),
            "contact_urgence_nom": post.get("contact_urgence_nom"),
            "contact_urgence_lien": post.get("contact_urgence_lien"),
            "contact_urgence_adresse": post.get("contact_urgence_adresse"),
            "contact_urgence_telephone": post.get("contact_urgence_telephone"),
            "contact_urgence_email": post.get("contact_urgence_email"),

            # Mission / lieu — les dates RÉELLES (start_date/end_date) ne
            # sont pas collectées ici : connues seulement à l'arrivée
            # effective du volontaire, renseignées plus tard par le
            # secrétariat.
            "country_id": _many2one_id("country_id"),
            "city": post.get("city"),

            # Offre
            "offer_code": post.get("offer_code"),
            "titre_offre": post.get("titre_offre"),
            "date_publication_offre": fields.Date.to_date(post.get("date_publication_offre")),
            "date_selection_offre": fields.Date.to_date(post.get("date_selection_offre")),
            "date_debut_proposee": fields.Date.to_date(post.get("date_debut_proposee")),
            "date_fin_proposee": fields.Date.to_date(post.get("date_fin_proposee")),
            "source_offre": post.get("source_offre"),

            # Structure d'envoi
            "sending_partner_id": sending_partner.id if sending_partner else False,
            "sending_org_nom": post.get("sending_org_nom"),
            "sending_org_oid_saisi": post.get("sending_org_oid_saisi"),
            "sending_org_nom_legal": post.get("sending_org_nom_legal"),
            "sending_org_adresse": post.get("sending_org_adresse"),
            "sending_org_type_organisme": post.get("sending_org_type_organisme"),
            "sending_org_email": post.get("sending_org_email"),
            "sending_org_telephone": post.get("sending_org_telephone"),
            "sending_contact_nom": post.get("sending_contact_nom"),
            "sending_contact_email": post.get("sending_contact_email"),
            "sending_contact_telephone": post.get("sending_contact_telephone"),

            # Structure d'accueil
            "hosting_partner_id": hosting_partner.id if hosting_partner else False,
            "hosting_org_nom": post.get("hosting_org_nom"),
            "hosting_org_oid_saisi": post.get("hosting_org_oid_saisi"),
            "hosting_org_nom_legal": post.get("hosting_org_nom_legal"),
            "hosting_org_adresse": post.get("hosting_org_adresse"),
            "hosting_org_type_organisme": post.get("hosting_org_type_organisme"),
            "hosting_org_email": post.get("hosting_org_email"),
            "hosting_org_telephone": post.get("hosting_org_telephone"),
            "hosting_contact_nom": post.get("hosting_contact_nom"),
            "hosting_contact_email": post.get("hosting_contact_email"),
            "hosting_contact_telephone": post.get("hosting_contact_telephone"),

            # Déclaration — vrai à la fois si la case HTML a été cochée
            # (valeur 'on' envoyée par le POST) et si la cellule Excel
            # contient un booléen déjà résolu par l'assistant d'import.
            "declaration_acceptee": bool(post.get("declaration_acceptee")),
            "date_declaration": fields.Date.to_date(post.get("date_declaration")) or fields.Date.today(),
            "lieu_declaration": post.get("lieu_declaration"),
            "signature_nom": post.get("signature_nom"),
            "fiche_renseignement_soumise_le": fields.Datetime.now(),
        }

    @api.model
    def _cron_terminer_missions_echues(self):
        """Passe en 'Terminé' les mobilités en mission dont la date de fin
        est dépassée (déclencheur §2 du cahier : 'Date de fin de mission
        atteinte')."""
        today = fields.Date.today()
        mobilities = self.search(
            [
                ("status", "=", "mission"),
                ("end_date", "<", today),
            ]
        )
        if mobilities:
            mobilities.write({"status": "termine"})

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            name = rec.name or "?"
            if rec.participant_id:
                name += f" — {rec.participant_id.name}"
            rec.display_name = name
