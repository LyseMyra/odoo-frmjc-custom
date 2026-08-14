import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PortalFicheRenseignement(http.Controller):
    """Formulaire public (sans authentification) de la fiche de
    renseignement volontaire — §4 du cahier des charges.

    Rempli par la STRUCTURE D'ACCUEIL (pas le volontaire) : elle est la
    seule partie à disposer, dès ce stade, des informations sur le
    volontaire, l'offre, la structure d'envoi et sa propre structure. La
    mobilité est créée en amont par le secrétariat avec uniquement les
    champs de classification (programme, direction, durée, type de
    volontariat) — tout le reste (participant, structures, dates
    proposées de l'offre) est inconnu tant que ce formulaire n'a pas été
    soumis, d'où l'aspect non obligatoire de ces champs sur
    mobility.mobility. Les dates RÉELLES de mission (start_date/end_date,
    utilisées pour le calcul de durée) ne sont pas demandées ici : elles
    ne sont connues qu'à l'arrivée effective du volontaire et seront
    renseignées plus tard, par le secrétariat.

    L'accès se fait par un token opaque (portal_token) inclus dans le
    lien envoyé à la structure d'accueil, pas par un compte utilisateur.
    """

    def _get_mobility(self, token):
        return request.env['mobility.mobility'].sudo().search(
            [('portal_token', '=', token)], limit=1,
        )

    # NB : la résolution participant/structure et la construction du dict
    # de vals sont mutualisées sur mobility.mobility (_find_or_create_*,
    # _build_fiche_vals) — également utilisées par l'import Excel
    # (mobility.import.fiche.wizard), pour un seul chemin logique quel
    # que soit le canal de saisie.

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
        champs_requis = [
            ('participant_prenom', 'Prénom du volontaire'),
            ('participant_nom', 'Nom du volontaire'),
            ('email', 'Email du volontaire'),
            ('date_naissance', 'Date de naissance'),
            ('hosting_org_nom', "Nom de la structure d'accueil"),
        ]
        for field_name, label in champs_requis:
            if not post.get(field_name):
                errors[field_name] = 'Champ requis.'
        if not post.get('declaration_acceptee'):
            errors['declaration_acceptee'] = (
                "Vous devez confirmer la déclaration sur l'honneur pour "
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

        # La case n'est envoyée par le POST que si elle est cochée — sa
        # présence a déjà été vérifiée ci-dessus (champs_requis).
        post = dict(post, declaration_acceptee=True)
        vals = mobility._build_fiche_vals(post)
        mobility.sudo().write(vals)

        # Trace du dépôt — un mobility.document marqueur, pas un fichier
        # (la saisie est directe, pas un upload d'Excel comme auparavant).
        request.env['mobility.document'].sudo().create({
            'mobility_id': mobility.id,
            'participant_id': mobility.participant_id.id,
            'document_type': 'fiche_renseignement',
            'statut': 'valide',
            'upload_date': fields.Date.today(),
            'emis_par': mobility.hosting_org_nom or mobility.hosting_partner_id.name,
            'notes': (
                "Fiche de renseignement soumise via le formulaire public "
                "par la structure d'accueil."
            ),
        })

        return request.render('mobility_frmjc.portal_fiche_merci', {
            'mobility': mobility,
        })
