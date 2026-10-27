{
    'name': 'Modèles de documents FRMJC',
    'version': '20.0.1.0.0',
    'summary': "Génération de documents .docx à partir de modèles uploadés, "
               "avec un catalogue de variables cherchable",
    'description': """
        Système générique de modèles de documents au format .docx.

        Permet d'uploader un modèle Word contenant des balises
        {{ variable }}, et de générer un document rempli à partir d'un
        enregistrement Odoo (dossier d'inscription, mobilité, etc.).

        Ce module ne connaît aucune règle métier lui-même : chaque module
        applicatif (training_frmjc, mobility_frmjc, les futurs modules)
        déclare ses propres variables pour ses propres modèles. Le
        catalogue de variables disponibles est visible et cherchable
        directement dans Odoo, et se met à jour automatiquement à chaque
        mise à jour du module.

        Nécessite la bibliothèque Python 'docxtpl' sur le serveur :
            pip install docxtpl
    """,
    'author': 'FRMJC Bretagne - Pays de la Loire',
    'website': 'https://www.frmjc-bretagne-paysdelaloire.org',
    'category': 'Productivity',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'training_frmjc',
    ],

    'data': [
        'security/ir.access.csv',

        'views/template_variable_views.xml',
        'views/template_document_views.xml',
        'views/template_generate_wizard_views.xml',
        'views/training_inscription_views.xml',
        'views/menus.xml',

        'data/template_document_data.xml',
        'data/sync_variables_data.xml',
    ],

    'post_init_hook': '_post_init_hook',

    'demo': [],

    'installable': True,
    'application': False,
    'auto_install': False,
}
