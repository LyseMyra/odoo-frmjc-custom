"""Suppression de la section « Motivations » du dossier d'inscription.

La lettre de motivation est déjà demandée dans les pièces justificatives :
le champ texte libre `motivations` devient inutile, on supprime la colonne
orpheline.
"""


def migrate(cr, version):
    cr.execute(
        "ALTER TABLE training_inscription DROP COLUMN IF EXISTS motivations"
    )
