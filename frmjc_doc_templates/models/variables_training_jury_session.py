"""Variables pour les documents liés à training.jury.session
(convocation jury)."""

from .variable_registry import register_variable

MODULE = 'training_frmjc'
MODEL = 'training.jury.session'

JOURS_FR = {0: 'lundi', 1: 'mardi', 2: 'mercredi', 3: 'jeudi', 4: 'vendredi',
            5: 'samedi', 6: 'dimanche'}
MOIS_FR = {1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril', 5: 'mai', 6: 'juin',
           7: 'juillet', 8: 'août', 9: 'septembre', 10: 'octobre', 11: 'novembre',
           12: 'décembre'}


def register(code, description, getter):
    register_variable(MODEL, code, description, getter, module=MODULE)


def _date_fr(d):
    if not d:
        return ''
    return f"{JOURS_FR.get(d.weekday(), '')} {d.day} {MOIS_FR.get(d.month, '')} {d.year}"


register('bloc_nom', 'Nom du bloc de compétences évalué', lambda r: r.bloc_id.name or '')

register('formation_type', 'Type de formation (ex. DEJEPS), en majuscules',
          lambda r: (r.session_id.habilitation_id.type_formation or '').upper())
register('formation_specialite', 'Spécialité de la formation',
          lambda r: r.session_id.habilitation_id.specialite or '')
register('formation_mention', 'Mention de la formation',
          lambda r: r.session_id.habilitation_id.mention or '')
register('session_numero_drajes', 'N° FOROMES / DRAJES de la session',
          lambda r: r.session_id.numero_drajes or '')
register('habilitation_numero', "Numéro d'habilitation DRAJES",
          lambda r: r.session_id.habilitation_id.numero or '')

register('date_jury', 'Date du jury (jour en toutes lettres)', lambda r: _date_fr(r.date))
register('lieu_jury', "Lieu de l'épreuve", lambda r: r.lieu or '')
register('nb_candidats', 'Nombre de candidats', lambda r: r.nb_candidats or '')
register('nb_commissions', 'Nombre de commissions',
          lambda r: len(r.get_commissions()) if hasattr(r, 'get_commissions') else '')
register('deroulement_notes', "Notes sur le déroulement de la journée",
          lambda r: r.notes or '')
