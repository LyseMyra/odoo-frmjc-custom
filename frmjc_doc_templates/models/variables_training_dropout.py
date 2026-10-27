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
register('session_nom', 'Nom de la session', lambda r: r.session_id.name or '')
register('session_date_debut', 'Date de début de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_debut))
register('session_date_fin', 'Date de fin de la session (JJ/MM/AAAA)',
          lambda r: _date_fr(r.session_id.date_fin))
register('dossier_numero', 'Référence du dossier d\'inscription',
          lambda r: r.inscription_id.reference or '')

register('date_abandon', "Date de l'abandon (JJ/MM/AAAA)", lambda r: _date_fr(r.date_abandon))
register('semaine_abandon', "Semaine d'abandon", lambda r: r.semaine_abandon_id.name or '')
register('motif_abandon', "Motif de l'abandon",
          lambda r: MOTIF_LABELS.get(r.motif, r.motif or ''))
register('commentaire_abandon', "Commentaire sur l'abandon", lambda r: r.description or '')

register('remboursement_applicable', 'Remboursement applicable (Oui/Non)',
          lambda r: 'Oui' if r.remboursement_applicable else 'Non')
register('montant_remboursement', 'Montant du remboursement (€)',
          lambda r: ('%.2f' % r.montant_remboursement) if r.montant_remboursement else '')
