"""Variables pour les documents liés à training.convention."""

from .variable_registry import register_variable

MODULE = 'training_frmjc'
MODEL = 'training.convention'


def register(code, description, getter):
    register_variable(MODEL, code, description, getter, module=MODULE)


def _date_fr(d):
    return d.strftime('%d/%m/%Y') if d else ''


def _structure(conv):
    return conv.structure_accueil_id or conv.inscription_id.structure_accueil_id


def _tuteur(conv):
    return conv.tuteur_id or conv.inscription_id.tuteur_id


def _rep_structure(conv):
    return conv.representant_structure_id or conv.inscription_id.representant_structure_id


register('convention_numero', 'Numéro de la convention', lambda r: r.numero or '')
register('convention_date_debut', 'Date de début de formation (JJ/MM/AAAA)',
          lambda r: _date_fr(r.date_debut))
register('convention_date_fin', 'Date de fin de formation (JJ/MM/AAAA)',
          lambda r: _date_fr(r.date_fin))
register('convention_date_creation', 'Date de création de la convention (JJ/MM/AAAA)',
          lambda r: _date_fr(r.date_creation))

register('stagiaire_nom', 'Nom complet du stagiaire', lambda r: r.partner_id.name or '')
register('stagiaire_email', 'Email du stagiaire', lambda r: r.partner_id.email or '')
register('stagiaire_telephone', 'Téléphone du stagiaire', lambda r: r.partner_id.phone or '')

register('formation_specialite', 'Spécialité de la formation',
          lambda r: r.formation_id.specialite or '')
register('formation_mention', 'Mention de la formation',
          lambda r: r.formation_id.mention or '')
register('formation_volume_centre', 'Volume horaire en centre',
          lambda r: r.formation_id.volume_centre or '')
register('formation_tarif_horaire', 'Tarif horaire de la formation (€)',
          lambda r: ('%.2f' % r.formation_id.tarif_horaire) if r.formation_id.tarif_horaire else '')
register('habilitation_numero', "Numéro d'habilitation de la session",
          lambda r: r.session_id.habilitation_id.numero or '' if r.session_id else '')

register('structure_nom', "Nom de la structure d'accueil", lambda r: _structure(r).name or '')
register('structure_adresse', "Adresse de la structure d'accueil",
          lambda r: _structure(r).street or '')
register('structure_cp', "Code postal de la structure d'accueil",
          lambda r: _structure(r).zip or '')
register('structure_ville', "Ville de la structure d'accueil",
          lambda r: _structure(r).city or '')
register('structure_telephone', "Téléphone de la structure d'accueil",
          lambda r: _structure(r).phone or '')
register('structure_email', "Email de la structure d'accueil",
          lambda r: _structure(r).email or '')
register('structure_siret', "SIRET de la structure d'accueil",
          lambda r: _structure(r).siret or '')

register('tuteur_nom', 'Nom du tuteur / conseiller·ère', lambda r: _tuteur(r).name or '')
register('tuteur_fonction', 'Fonction du tuteur / conseiller·ère',
          lambda r: _tuteur(r).function or '')
register('tuteur_telephone', 'Téléphone du tuteur / conseiller·ère',
          lambda r: _tuteur(r).phone or '')
register('tuteur_email', 'Email du tuteur / conseiller·ère', lambda r: _tuteur(r).email or '')

register('representant_structure_nom', 'Nom du représentant légal de la structure',
          lambda r: _rep_structure(r).name or '')
register('representant_structure_fonction', 'Fonction du représentant légal de la structure',
          lambda r: _rep_structure(r).function or '')

register('representant_frmjc_nom', 'Nom du représentant de la FRMJC',
          lambda r: r.representant_frmjc_id.name or '')
register('representant_frmjc_fonction', 'Fonction du représentant de la FRMJC',
          lambda r: r.representant_frmjc_id.function or '')

register('cout_total', 'Coût total de la formation (€)',
          lambda r: ('%.2f' % r.cout_total) if r.cout_total else '')
register('frais_inscription_montant', "Montant des frais d'inscription (€)",
          lambda r: ('%.2f' % r.frais_inscription_montant) if r.frais_inscription_montant else '')
register('frais_inscription_date_reglement', "Date de règlement des frais d'inscription",
          lambda r: _date_fr(r.frais_inscription_date_reglement))
