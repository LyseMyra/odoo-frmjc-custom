"""Variables disponibles pour les documents liés au module training_frmjc.

Point d'extension : pour ajouter une variable, ajoute un appel à
``register()`` ci-dessous — elle apparaîtra automatiquement dans le
catalogue (menu Documents > Catalogue des variables) à la prochaine
mise à jour du module, sans rien à faire d'autre.
"""

from .variable_registry import register_variable

MODULE = 'training_frmjc'
MODEL_INSCRIPTION = 'training.inscription'

STATUT_EMPLOI_LABELS = {
    'salarie': 'Salarié',
    'independant': 'Indépendant',
    'demandeur_emploi': "Demandeur d'emploi",
    'etudiant': 'Étudiant',
    'benevole': 'Bénévole',
    'autre': 'Autre',
}


def register(code, description, getter):
    register_variable(MODEL_INSCRIPTION, code, description, getter, module=MODULE)


def _structure_nom(insc):
    if insc.structure_accueil_id:
        return insc.structure_accueil_id.name or ''
    return insc.structure_accueil or ''


def _date_fr(d):
    return d.strftime('%d/%m/%Y') if d else ''


register('stagiaire_nom', 'Nom complet du stagiaire',
          lambda r: r.partner_id.name or '')
register('stagiaire_email', 'Email du stagiaire',
          lambda r: r.partner_id.email or '')
register('stagiaire_telephone', 'Téléphone du stagiaire',
          lambda r: r.partner_id.phone or '')

register('structure_nom', "Nom de la structure d'accueil", _structure_nom)

register('formation_type', 'Type de formation (ex. DEJEPS), en majuscules',
          lambda r: (r.session_id.habilitation_id.type_formation or '').upper())
register('formation_specialite', 'Spécialité de la formation',
          lambda r: r.session_id.habilitation_id.specialite or '')
register('formation_mention', 'Mention de la formation',
          lambda r: r.session_id.habilitation_id.mention or '')

register('session_date_debut', 'Date de début de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_debut))
register('session_date_fin', 'Date de fin de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_fin))
register('session_volume_heures', 'Durée totale de la formation, en heures',
          lambda r: int(r.session_id.volume_heures_prevues)
          if r.session_id.volume_heures_prevues else '')
register('session_lieu', 'Lieu de la formation',
          lambda r: r.session_id.lieu_formation or 'En itinérance')
register('session_nature_action', "Nature de l'action de formation",
          lambda r: r.session_id.nature_action or '')

register('signataire_nom', 'Nom de la personne signataire du document',
          lambda r: r.session_id.signataire_nom or r.session_id.responsable_id.name or '')
register('signataire_titre', 'Titre/fonction de la personne signataire',
          lambda r: r.session_id.signataire_titre or 'Directrice / Directeur')

register('dossier_reference', "Référence du dossier d'inscription",
          lambda r: r.reference or '')
register('stagiaire_adresse', 'Adresse du stagiaire', lambda r: r.partner_id.street or '')
register('stagiaire_ville', 'Ville du stagiaire', lambda r: r.partner_id.city or '')
register('niveau_etudes', "Niveau d'études du candidat",
          lambda r: dict(r._fields['niveau_etudes'].selection or []).get(r.niveau_etudes, ''))
register('dernier_diplome', 'Dernier diplôme obtenu', lambda r: r.dernier_diplome or '')

register('formation_intitule', 'Intitulé de la formation',
          lambda r: r.formation_id.intitule or '')
register('date_naissance_stagiaire', 'Date de naissance du stagiaire (JJ/MM/AAAA)',
          lambda r: _date_fr(r.partner_id.date_naissance))
register('lieu_naissance_stagiaire', 'Lieu de naissance du stagiaire',
          lambda r: r.partner_id.lieu_naissance or '')
register('stagiaire_code_postal', 'Code postal du stagiaire',
          lambda r: r.partner_zip or '')
register('statut_stagiaire', "Statut du stagiaire (salarié, demandeur d'emploi...)",
          lambda r: STATUT_EMPLOI_LABELS.get(r.statut_emploi, r.statut_emploi or ''))
register('habilitation_numero', "Numéro d'habilitation DRAJES",
          lambda r: r.session_id.habilitation_id.numero or '')
register('session_numero_drajes', 'N° FOROMES / DRAJES de la session',
          lambda r: r.session_id.numero_drajes or '')
