"""Variables pour les documents liés à training.dropout
(attestation d'abandon)."""

from .variable_registry import register_variable

MODULE = 'training_frmjc'
MODEL = 'training.dropout'

MOTIF_LABELS = {
    'personnel': 'Raison personnelle',
    'professionnel': 'Raison professionnelle',
    'medical': 'Raison médicale',
    'pedagogique': 'Difficulté pédagogique',
    'financier': 'Difficulté financière',
    'reorientation': 'Réorientation de projet',
    'autre': 'Autre',
}

STATUT_EMPLOI_LABELS = {
    'salarie': 'Salarié',
    'independant': 'Indépendant',
    'demandeur_emploi': "Demandeur d'emploi",
    'etudiant': 'Étudiant',
    'benevole': 'Bénévole',
    'autre': 'Autre',
}

TYPE_RUPTURE_LABELS = {
    'rupture_contrat_travail': "Rupture du contrat de travail avec l'entreprise",
    'rupture_contrat_formation': "Rupture du contrat de formation avec l'OF",
    'abandon_formation': 'Abandon de la formation',
}


def register(code, description, getter):
    register_variable(MODEL, code, description, getter, module=MODULE)


def _date_fr(d):
    return d.strftime('%d/%m/%Y') if d else ''


register('stagiaire_nom', 'Nom complet du stagiaire', lambda r: r.partner_id.name or '')
register('stagiaire_email', 'Email du stagiaire', lambda r: r.partner_id.email or '')
register('stagiaire_telephone', 'Téléphone du stagiaire', lambda r: r.partner_id.phone or '')
register('stagiaire_adresse', 'Adresse du stagiaire', lambda r: r.partner_id.street or '')

register('formation_intitule', 'Intitulé de la formation',
          lambda r: r.inscription_id.formation_id.intitule or '')
register('formation_type', 'Type de diplôme (ex. DEJEPS), en majuscules',
          lambda r: (r.session_id.habilitation_id.type_formation or '').upper())
register('session_nom', 'Nom de la session', lambda r: r.session_id.name or '')
register('session_numero_drajes', 'N° FOROMES / DRAJES de la session',
          lambda r: r.session_id.numero_drajes or '')
register('session_date_debut', 'Date de début de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_debut))
register('session_date_fin', 'Date de fin de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_fin))
register('coordonnateur_nom', 'Nom du coordonnateur de la formation',
          lambda r: r.session_id.responsable_id.name or '')
register('statut_stagiaire', "Statut du stagiaire (salarié, demandeur d'emploi...)",
          lambda r: STATUT_EMPLOI_LABELS.get(
              r.inscription_id.statut_emploi, r.inscription_id.statut_emploi or ''))
register('signataire_nom', "Nom de la personne signataire du document",
          lambda r: r.session_id.signataire_nom or '')
register('signataire_titre', "Titre/fonction de la personne signataire",
          lambda r: r.session_id.signataire_titre or '')
register('dossier_numero', 'Référence du dossier d\'inscription',
          lambda r: r.inscription_id.reference or '')

register('date_abandon', "Date de l'abandon (JJ/MM/AAAA)", lambda r: _date_fr(r.date_abandon))
register('type_rupture', "Objet de la rupture (classification DRAJES)",
          lambda r: TYPE_RUPTURE_LABELS.get(r.type_rupture, r.type_rupture or ''))
register('semaine_abandon', "Semaine d'abandon", lambda r: r.semaine_abandon_id.name or '')
register('motif_abandon', "Motif de l'abandon",
          lambda r: MOTIF_LABELS.get(r.motif, r.motif or ''))
register('commentaire_abandon', "Commentaire sur l'abandon", lambda r: r.description or '')

register('remboursement_applicable', 'Remboursement applicable (Oui/Non)',
          lambda r: 'Oui' if r.remboursement_applicable else 'Non')
register('montant_remboursement', 'Montant du remboursement (€)',
          lambda r: ('%.2f' % r.montant_remboursement) if r.montant_remboursement else '')
