"""Variables pour les documents liés à training.depense.intervenant
(convention de prestation).

Note : le rapport QWeb existant regroupe plusieurs lignes de dépense par
intervenant·e pour produire UN document. Le système de modèles .docx
fonctionne enregistrement par enregistrement : ces variables portent donc
sur UNE ligne de dépense à la fois (le contrat pour une seule prestation),
pas sur le regroupement complet. Pour un contrat couvrant plusieurs
lignes, génère-le plusieurs fois ou ajuste le modèle Word en conséquence.
"""

from .variable_registry import register_variable

MODULE = 'training_frmjc'
MODEL = 'training.depense.intervenant'


def register(code, description, getter):
    register_variable(MODEL, code, description, getter, module=MODULE)


def _date_fr(d):
    return d.strftime('%d/%m/%Y') if d else ''


register('intervenant_nom', "Nom de l'intervenant·e", lambda r: r.partner_id.name or '')
register('intervenant_siret', "SIRET/n° d'identification de l'intervenant·e",
          lambda r: r.partner_id.vat or '')
register('intervenant_structure', "Structure de rattachement de l'intervenant·e",
          lambda r: r.partner_id.parent_id.name or '')

register('formation_intitule', 'Intitulé de la formation',
          lambda r: r.session_id.formation_id.intitule or '')
register('session_lieu', 'Lieu de la formation', lambda r: r.session_id.lieu_formation or '')
register('session_date_debut', 'Date de début de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_debut))
register('session_date_fin', 'Date de fin de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_fin))
register('session_nb_stagiaires', 'Nombre de stagiaires acceptés dans la session',
          lambda r: r.session_id.nb_stagiaires_acceptes or '')

register('signataire_nom', 'Nom de la personne signataire pour la FRMJC',
          lambda r: r.session_id.signataire_nom or '')
register('signataire_titre', 'Titre/fonction de la personne signataire',
          lambda r: r.session_id.signataire_titre or 'représentant légal')

register('prestation_description', 'Description de la prestation',
          lambda r: r.description or (r.product_id.name if r.product_id else ''))
register('prestation_prix_unitaire', 'Prix unitaire (€)',
          lambda r: ('%.2f' % r.prix_unitaire) if r.prix_unitaire else '')
register('prestation_quantite', 'Quantité (jours)',
          lambda r: ('%.2f' % r.quantite) if r.quantite else '')
register('prestation_montant_total', 'Montant total (€)',
          lambda r: ('%.2f' % r.montant_total) if r.montant_total else '')
