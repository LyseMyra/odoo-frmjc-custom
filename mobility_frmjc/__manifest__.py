{
    'name': 'Volontariat / Mobilités FRMJC',
    'version': '19.0.1.0.0',
    'summary': 'Pilotage des mobilités internationales (SC, CES, VSI) - FRMJC Bretagne Pays de la Loire',
    'description': """
        Module de pilotage opérationnel, pédagogique et financier des mobilités
        de volontariat international (Service Civique, Corps Européen de Solidarité,
        Volontariat Service International), après la sélection du volontaire.
        Couvre le pipeline du parcours, les structures partenaires, les conventions
        de subvention et habilitations LEAD, le suivi financier et l'export/import
        au format BM (Beneficiary Module).
    """,
    'author': 'FRMJC Bretagne - Pays de la Loire',
    'website': 'https://www.frmjc-bretagne-paysdelaloire.org',
    'category': 'Human Resources',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'website',
        'survey',
        'purchase',
        'account',
    ],

    'data': [
        # Sécurité — en premier (groupes avant les modèles qui y référencent)
        'security/mobility_security.xml',
        'security/ir.model.access.csv',

        # Données de référence
        'data/mobility_structure_role_data.xml',
        'data/mobility_data.xml',
        'data/mobility_rate_country_data.xml',
        'data/mobility_rate_travel_data.xml',
        'data/mobility_finance_forfaits_data.xml',
        'data/mobility_product_category_data.xml',
        'data/mobility_finance_subcategory_data.xml',

        # Vues back-office
        'views/res_partner_views.xml',
        'views/mobility_structure_role_views.xml',
        'views/mobility_document_views.xml',
        'views/mobility_grant_views.xml',
        'views/mobility_habilitation_views.xml',
        'views/mobility_activity_views.xml',
        'views/mobility_rate_country_views.xml',
        'views/mobility_rate_travel_views.xml',
        'views/mobility_finance_subcategory_views.xml',
        'views/mobility_finance_line_views.xml',
        'views/mobility_mobility_views.xml',
        'views/mobility_export_bm_wizard_views.xml',
        'views/mobility_import_bm_wizard_views.xml',
        'views/mobility_import_fiche_wizard_views.xml',

        # Portail public
        'views/portal_fiche_renseignement.xml',

        # Menus — toujours en dernier
        'views/menus.xml',
    ],

    'demo': [],

    'installable': True,
    'application': True,
    'auto_install': False,
}
