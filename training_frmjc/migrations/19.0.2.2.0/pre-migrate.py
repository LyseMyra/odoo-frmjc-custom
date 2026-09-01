"""Refonte de la section « Documents » du dossier d'inscription.

- Suppression de « Justificatif de situation professionnelle » et « Autre
  document » (remplacés par la liste `training.inscription.document`).
- Ajout de justificatif d'identité, photo d'identité et attestation RQTH
  (nouvelles colonnes créées automatiquement à la mise à jour).
"""


def migrate(cr, version):
    # Colonnes de noms de fichiers devenues orphelines
    cr.execute(
        """
        ALTER TABLE training_inscription
            DROP COLUMN IF EXISTS justificatif_emploi,
            DROP COLUMN IF EXISTS justificatif_emploi_filename,
            DROP COLUMN IF EXISTS autre_document,
            DROP COLUMN IF EXISTS autre_document_filename
        """
    )
    # Pièces jointes rattachées aux champs supprimés
    cr.execute(
        """
        DELETE FROM ir_attachment
         WHERE res_model = 'training.inscription'
           AND res_field IN ('justificatif_emploi', 'autre_document')
        """
    )
