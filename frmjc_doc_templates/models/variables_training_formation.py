"""Variables pour les documents liés à training.formation."""

from .variable_registry import register_variable

MODULE = 'training_frmjc'
MODEL = 'training.formation'


def register(code, description, getter):
    register_variable(MODEL, code, description, getter, module=MODULE)


register('formation_intitule', 'Intitulé de la formation',
          lambda r: r.intitule or r.name or '')
register('formation_type', 'Type de formation (ex. DEJEPS), en majuscules',
          lambda r: (r.type_formation or '').upper())
register('formation_specialite', 'Spécialité de la formation', lambda r: r.specialite or '')
register('formation_mention', 'Mention de la formation', lambda r: r.mention or '')
register('formation_volume_centre', 'Volume horaire en centre',
          lambda r: r.volume_centre or '')
register('formation_volume_entreprise', "Volume horaire en entreprise/structure d'accueil",
          lambda r: r.volume_entreprise or '')
register('formation_tarif_horaire', 'Tarif horaire (€)',
          lambda r: ('%.2f' % r.tarif_horaire) if r.tarif_horaire else '')
register('formation_nb_stagiaires_max', 'Effectif maximum de stagiaires',
          lambda r: r.nb_stagiaires_max or '')
register('formation_responsable_nom', 'Nom du ou de la responsable pédagogique',
          lambda r: r.responsable_pedagogique_id.name or '')
