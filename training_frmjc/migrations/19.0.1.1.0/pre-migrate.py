"""Réalignement des options des champs statut_emploi et type_contrat.

- statut_emploi : 'salarie_cdi' et 'salarie_cdd' sont fusionnés vers 'salarie'
  (le détail CDI/CDD reste porté par type_contrat).
- type_contrat : 'independant', 'benevole' et 'autre' n'existent plus et sont
  remis à vide (re-saisie manuelle si nécessaire).
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE training_inscription
           SET statut_emploi = 'salarie'
         WHERE statut_emploi IN ('salarie_cdi', 'salarie_cdd')
        """
    )
    cr.execute(
        """
        UPDATE training_inscription
           SET type_contrat = NULL
         WHERE type_contrat IN ('independant', 'benevole', 'autre')
        """
    )
