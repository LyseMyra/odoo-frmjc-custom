"""Variables pour les documents liés à training.certification
(convocations certificateur et candidat)."""

from .variable_registry import register_variable

MODULE = 'training_frmjc'
MODEL = 'training.certification'


def register(code, description, getter):
    register_variable(MODEL, code, description, getter, module=MODULE)


JOURS_FR = {0: 'lundi', 1: 'mardi', 2: 'mercredi', 3: 'jeudi', 4: 'vendredi',
            5: 'samedi', 6: 'dimanche'}
MOIS_FR = {1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril', 5: 'mai', 6: 'juin',
           7: 'juillet', 8: 'août', 9: 'septembre', 10: 'octobre', 11: 'novembre',
           12: 'décembre'}


def _date_fr(d):
    """Date en toutes lettres, en français, sans dépendre de la locale du
    serveur (ex. 'lundi 23 novembre 2026')."""
    if not d:
        return ''
    return f"{JOURS_FR.get(d.weekday(), '')} {d.day} {MOIS_FR.get(d.month, '')} {d.year}"


def _heure_fmt(h):
    if not h:
        return 'à définir'
    return '%dh%02d' % (int(h), int(round((h % 1) * 60)))


register('bloc_nom', 'Nom du bloc de compétences évalué', lambda r: r.bloc_id.name or '')

register('formation_type', 'Type de formation (ex. DEJEPS), en majuscules',
          lambda r: (r.session_id.habilitation_id.type_formation or '').upper())
register('formation_specialite', 'Spécialité de la formation',
          lambda r: r.session_id.habilitation_id.specialite or '')
register('formation_mention', 'Mention de la formation',
          lambda r: r.session_id.habilitation_id.mention or '')

register('candidat_nom', 'Nom complet du candidat', lambda r: r.partner_id.name or '')
register('candidat_telephone', 'Téléphone du candidat', lambda r: r.partner_id.phone or '')

register('certificateur_nom', 'Nom du ou de la certificateur·rice',
          lambda r: r.certificateur_id.name or '')
register('certificateur_email', 'Email du ou de la certificateur·rice',
          lambda r: r.certificateur_id.email or '')
register('certificateur_telephone', 'Téléphone du ou de la certificateur·rice',
          lambda r: r.certificateur_id.phone or '')

register('date_certification_a', "Date de l'épreuve, circuit A (jour en toutes lettres)",
          lambda r: _date_fr(r.date_certification_a))
register('heure_certification_a', "Heure de l'épreuve, circuit A",
          lambda r: _heure_fmt(r.heure_debut_a))
register('lieu_certification_a', "Lieu de l'épreuve, circuit A",
          lambda r: r.lieu_certification_a or '')

register('date_jury', 'Date du jury, circuit B (jour en toutes lettres)',
          lambda r: _date_fr(r.jury_session_id.date) if r.jury_session_id else '')
register('heure_passage_b', 'Heure de passage du candidat, circuit B',
          lambda r: _heure_fmt(r.heure_debut_b))
register('lieu_jury', 'Lieu du jury, circuit B',
          lambda r: r.jury_session_id.lieu or '' if r.jury_session_id else '')
register('numero_commission', 'Numéro de commission, circuit B',
          lambda r: r.numero_commission or '')

register('responsable_nom', 'Nom du ou de la responsable de session',
          lambda r: r.session_id.responsable_id.name or '')
register('responsable_email', 'Email du ou de la responsable de session',
          lambda r: r.session_id.responsable_id.email or '')
register('responsable_telephone', 'Téléphone du ou de la responsable de session',
          lambda r: r.session_id.responsable_id.phone or '')
