"""Refonte de la section « Expériences » du dossier d'inscription.

Les champs libres/synthétiques sont remplacés par une liste structurée
(`training.inscription.experience`, One2many). Aucune reprise automatique
n'est possible (texte libre → lignes) : on supprime simplement les colonnes
devenues orphelines.
"""


def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE training_inscription
            DROP COLUMN IF EXISTS experiences_pro,
            DROP COLUMN IF EXISTS experience_animation,
            DROP COLUMN IF EXISTS experience_encadrement
        """
    )
