"""Variables pour les documents liés à training.monthly.report
(attestation mensuelle de présence, convocation mensuelle)."""

from .variable_registry import register_variable

MODULE = 'training_frmjc'
MODEL = 'training.monthly.report'

MOIS_FR = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
    7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre',
    12: 'Décembre',
}


def register(code, description, getter):
    register_variable(MODEL, code, description, getter, module=MODULE)


def _date_fr(d):
    return d.strftime('%d/%m/%Y') if d else ''


register('rapport_mois', 'Mois du rapport, en toutes lettres',
          lambda r: MOIS_FR.get(r.mois, str(r.mois)))
register('rapport_annee', 'Année du rapport', lambda r: r.annee or '')

register('stagiaire_nom', 'Nom complet du stagiaire', lambda r: r.partner_id.name or '')

register('session_nom', 'Nom de la session', lambda r: r.session_id.name or '')
register('session_date_debut', 'Date de début de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_debut))
register('session_date_fin', 'Date de fin de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_fin))

register('formation_type', 'Type de formation (ex. DEJEPS), en majuscules',
          lambda r: (r.session_id.habilitation_id.type_formation or '').upper())
register('formation_specialite', 'Spécialité de la formation',
          lambda r: r.session_id.habilitation_id.specialite or '')
register('formation_mention', 'Mention de la formation',
          lambda r: r.session_id.habilitation_id.mention or '')
register('habilitation_numero', "Numéro d'habilitation",
          lambda r: r.session_id.habilitation_id.numero or '')

register('coordinateur_nom', 'Nom du ou de la responsable/coordinateur·rice de la session',
          lambda r: r.session_id.responsable_id.name or '')
