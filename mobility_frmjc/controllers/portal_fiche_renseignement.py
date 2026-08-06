import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PortalFicheRenseignement(http.Controller):
    """Formulaire public (sans authentification) de la fiche de
    renseignement volontaire — §4 du cahier des charges. L'accès se fait
    par un token opaque (portal_token) inclus dans le lien envoyé au
    volontaire après sa sélection, pas par un compte utilisateur."""

    def _get_mobility(self, token):
        return request.env['mobility.mobility'].sudo().search(
            [('portal_token', '=', token)], limit=1,
        )

    @http.route(
        '/mobilite/fiche/<string:token>', type='http',
        auth='public', website=True, sitemap=False,
    )
    def fiche_form(self, token, **kwargs):
        mobility = self._get_mobility(token)
        if not mobility:
            return request.render('mobility_frmjc.portal_fiche_notfound')
        if mobility.fiche_renseignement_validee:
            return request.render('mobility_frmjc.portal_fiche_validee', {
                'mobility': mobility,
            })
        pays_list = request.env['res.country'].sudo().search([], order='name')
        return request.render('mobility_frmjc.portal_fiche_renseignement_form', {
            'mobility': mobility,
            'token': token,
            'pays_list': pays_list,
            'errors': {},
            'post': {},
        })

    @http.route(
        '/mobilite/fiche/<string:token>/enregistrer', type='http',
        auth='public', methods=['POST'], csrf=True, website=True,
    )
    def fiche_submit(self, token, **post):
        mobility = self._get_mobility(token)
        if not mobility:
            return request.redirect('/')
        if mobility.fiche_renseignement_validee:
            return request.render('mobility_frmjc.portal_fiche_validee', {
                'mobility': mobility,
            })

        errors = {}
        if not post.get('date_naissance'):
            errors['date_naissance'] = 'Champ requis.'
        if not post.get('email'):
            errors['email'] = 'Champ requis.'
        if not post.get('declaration_acceptee'):
            errors['declaration_acceptee'] = (
                'Vous devez confirmer la déclaration sur l\'honneur pour '
                'valider le formulaire.'
            )

        if errors:
            pays_list = request.env['res.country'].sudo().search([], order='name')
            return request.render('mobility_frmjc.portal_fiche_renseignement_form', {
                'mobility': mobility,
                'token': token,
                'pays_list': pays_list,
                'errors': errors,
                'post': post,
            })

        def _country_id(field_name):
            value = post.get(field_name)
            return int(value) if value else False

        vals = {
            'email': post.get('email'),
            'telephone': post.get('telephone'),
            'date_naissance': fields.Date.to_date(post.get('date_naissance')),
            'nationalite_id': _country_id('nationalite_id'),
            'pays_residence_id': _country_id('pays_residence_id'),
            'ville_residence': post.get('ville_residence'),
            'id_document_numero': post.get('id_document_numero'),
            'id_document_validite': fields.Date.to_date(post.get('id_document_validite')),
            'besoins_particuliers': post.get('besoins_particuliers'),
            'contact_urgence_nom': post.get('contact_urgence_nom'),
            'contact_urgence_lien': post.get('contact_urgence_lien'),
            'contact_urgence_adresse': post.get('contact_urgence_adresse'),
            'contact_urgence_telephone': post.get('contact_urgence_telephone'),
            'contact_urgence_email': post.get('contact_urgence_email'),
            'sending_org_nom': post.get('sending_org_nom'),
            'sending_org_oid_saisi': post.get('sending_org_oid_saisi'),
            'sending_contact_nom': post.get('sending_contact_nom'),
            'sending_contact_email': post.get('sending_contact_email'),
            'sending_contact_telephone': post.get('sending_contact_telephone'),
            'declaration_acceptee': True,
            'date_declaration': fields.Date.today(),
            'lieu_declaration': post.get('lieu_declaration'),
            'signature_nom': post.get('signature_nom'),
            'fiche_renseignement_soumise_le': fields.Datetime.now(),
        }
        mobility.sudo().write(vals)

        # Trace du dépôt — un mobility.document marqueur, pas un fichier
        # (la saisie est directe, pas un upload d'Excel comme auparavant).
        request.env['mobility.document'].sudo().create({
            'mobility_id': mobility.id,
            'participant_id': mobility.participant_id.id,
            'document_type': 'fiche_renseignement',
            'statut': 'valide',
            'upload_date': fields.Date.today(),
            'emis_par': mobility.participant_id.name,
            'notes': "Fiche de renseignement soumise via le formulaire public.",
        })

        return request.render('mobility_frmjc.portal_fiche_merci', {
            'mobility': mobility,
        })
