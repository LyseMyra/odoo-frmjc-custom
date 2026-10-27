"""Variables pour les documents liés à training.formateur.demi_journee
(feuille de présence).

Note : la liste des stagiaires présents et leurs signatures restent sur
le rapport QWeb (tableau), pas adaptées au système de variables à plat.
"""

from .variable_registry import register_variable

MODULE = 'training_frmjc'
MODEL = 'training.formateur.demi_journee'


def register(code, description, getter):
    register_variable(MODEL, code, description, getter, module=MODULE)


def _date_fr(d):
    return d.strftime('%d/%m/%Y') if d else ''


register('session_nom', 'Nom de la session', lambda r: r.semaine_id.session_id.name or '')
register('date_demi_journee', 'Date de la demi-journée (JJ/MM/AAAA)',
          lambda r: _date_fr(r.date))
register('demi_journee_label', 'Demi-journée (Matin / Après-midi)',
          lambda r: 'Matin' if r.demi_journee == 'matin' else 'Après-midi')
register('intervenant_nom', "Nom de l'intervenant·e",
          lambda r: r.semaine_id.intervenant_id.name or '')
