{
    'name': 'Formations FRMJC',
    'version': '19.0.1.0.0',
    'summary': 'Gestion des formations DEJEPS - FRMJC Bretagne Pays de la Loire',
    'description': """
        Module de gestion des formations professionnelles de la FRMJC.
        Couvre le cycle complet : habilitation DRAJES, référentiel pédagogique,
        ruban pédagogique, inscription des candidats, suivi des présences,
        conventions, certification et délivrance du diplôme.
    """,
    'author': 'FRMJC Bretagne - Pays de la Loire',
    'website': 'https://www.frmjc-bretagne-paysdelaloire.org',
    'category': 'Education',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'portal',
        'hr',
        'purchase',
        'account',
        'website',
        'survey',
    ],

    'data': [
        # Sécurité — en premier (groupes avant les modèles qui y référencent)
        'security/training_security.xml',
        'security/ir.model.access.csv',

        # Données de référence (séquences, crons)
        'data/training_paperformat.xml',
        'data/data.xml',
        'data/data_conventions.xml',
        'data/data_crons_presences.xml',
        'data/data_crons_surveys.xml',

        # Vues back-office
        'views/training_habilitation_views.xml',
        'views/training_formation_views.xml',
        'views/training_bloc_views.xml',
        'views/training_module_views.xml',
        'views/training_week_views.xml',
        'views/training_week_line_views.xml',
        'views/training_ruban_wizard_views.xml',
        'views/training_ruban_import_wizard_views.xml',
        'views/training_session_views.xml',
        'views/training_inscription_views.xml',
        'views/training_dropout_views.xml',
        'views/training_pieces_wizard_views.xml',
        'views/training_convention_views.xml',
        'views/training_alternance_views.xml',
        'views/training_certification_views.xml',
        'views/training_jury_session_views.xml',
        'views/training_attendance_views.xml',
        'views/training_monthly_report_views.xml',
        'views/training_depense_intervenant_views.xml',
        'views/training_formateur_semaine_views.xml',
        'views/training_survey_views.xml',
        'views/training_dashboard_views.xml',

        # Portail
        'views/portal_inscription.xml',
        'views/portal_stagiaire.xml',
        'views/portal_formateur.xml',
        'views/portal_intervenant_semaine.xml',

        # Rapports
        'report/training_ruban_report.xml',
        'report/training_controles_report.xml',
        'report/training_conventions_report.xml',
        'report/training_convocation_report.xml',
        'report/training_attestation_mensuelle_report.xml',
        'report/training_attestation_entree_report.xml',
        'report/training_certification_convocation_a_report.xml',
        'report/training_certification_convocation_jury_report.xml',
        'report/training_certificat_realisation_report.xml',
        'report/training_contrat_prestation_report.xml',
        'report/training_feuille_presence_report.xml',
        'report/training_attestation_abandon_report.xml',

        # Menus — toujours en dernier
        'views/menus.xml',
    ],

    'demo': [],

    'installable': True,
    'application': True,
    'auto_install': False,
}