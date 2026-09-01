import base64
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

COOKIE_NAME = 'frmjc_portal_token'
COOKIE_MAX_AGE = 8 * 3600  # 8 heures


def _get_current_partner():
    """Récupère le partenaire authentifié depuis le cookie de session."""
    token = request.httprequest.cookies.get(COOKIE_NAME)
    if not token:
        return None
    otp = request.env['training.otp'].find_by_token(token)
    return otp.partner_id if otp else None


class PortalInscription(http.Controller):

    # ─────────────────────────────────────────────────────────────────
    # Index : liste des sessions ouvertes
    # ─────────────────────────────────────────────────────────────────

    @http.route('/formation/inscription', type='http', auth='public', website=True)
    def inscription_index(self, **kwargs):
        sessions = request.env['training.session'].sudo().search([
            ('statut', 'in', ('ouvert', 'en_cours')),
        ])
        partner = _get_current_partner()
        inscriptions = {}
        if partner:
            for insc in request.env['training.inscription'].sudo().search([
                ('partner_id', '=', partner.id),
            ]):
                inscriptions[insc.session_id.id] = insc
        return request.render('training_frmjc.portal_inscription_index', {
            'sessions': sessions,
            'partner': partner,
            'inscriptions': inscriptions,
        })

    # ─────────────────────────────────────────────────────────────────
    # Authentification OTP
    # ─────────────────────────────────────────────────────────────────

    @http.route('/formation/auth', type='http', auth='public', website=True)
    def auth_form(self, session_id=None, error=None, next=None, **kwargs):
        session = None
        if session_id:
            session = request.env['training.session'].sudo().browse(int(session_id))
            if not session.exists():
                session = None
        return request.render('training_frmjc.portal_auth_form', {
            'session_id': session_id,
            'session': session,
            'error': error,
            'next_url': next,
        })

    @http.route(
        '/formation/auth/envoyer', type='http', auth='public',
        methods=['POST'], csrf=True, website=True,
    )
    def auth_envoyer_otp(self, email='', session_id=None, next_url=None, **kwargs):
        email = (email or '').strip().lower()
        next_url = (next_url or '').strip()

        def _redirect_error(code):
            params = f'error={code}'
            if session_id:
                params += f'&session_id={session_id}'
            if next_url:
                params += f'&next={next_url}'
            return request.redirect(f'/formation/auth?{params}')

        if not email or '@' not in email:
            return _redirect_error('email_invalide')

        # ── Vérification email pour reconnexion (sans session_id) ──
        # Si session_id est fourni → nouvel inscrit → pas de restriction
        # Si pas de session_id → reconnexion → l'email doit être connu
        if not session_id:
            partner = request.env['res.partner'].sudo().search(
                [('email', '=ilike', email)], limit=1
            )
            if not partner:
                return _redirect_error('email_inconnu')
            has_access = (
                partner.is_stagiaire_frmjc
                or request.env['training.inscription'].sudo().search_count(
                    [('partner_id', '=', partner.id)]
                ) > 0
            )
            if not has_access:
                return _redirect_error('email_inconnu')

        try:
            otp = request.env['training.otp'].sudo().generate_otp(email)
        except Exception:
            _logger.exception("Échec envoi OTP pour %s", email)
            return _redirect_error('envoi_echoue')

        return request.render('training_frmjc.portal_auth_verify', {
            'email': email,
            'otp_id': otp.id,
            'session_id': session_id,
            'next_url': next_url,
            'error': None,
        })

    @http.route(
        '/formation/auth/verifier', type='http', auth='public',
        methods=['POST'], csrf=True, website=True,
    )
    def auth_verifier_otp(self, otp_id=None, code='', session_id=None, next_url=None, **kwargs):
        next_url = (next_url or '').strip()
        try:
            otp_id = int(otp_id)
        except (TypeError, ValueError):
            return request.redirect('/formation/auth?error=invalide')

        otp = request.env['training.otp'].sudo().browse(otp_id)
        if not otp.exists():
            return request.redirect('/formation/auth?error=invalide')

        try:
            token = otp.verify(code)
        except ValueError as exc:
            return request.render('training_frmjc.portal_auth_verify', {
                'email': otp.email,
                'otp_id': otp_id,
                'session_id': session_id,
                'next_url': next_url,
                'error': str(exc),
            })

        # Redirection post-authentification
        if session_id:
            redirect_url = f'/formation/inscription/{session_id}'
        elif next_url and next_url.startswith('/'):
            redirect_url = next_url
        else:
            redirect_url = '/formation/inscription'

        response = request.redirect(redirect_url)
        response.set_cookie(
            COOKIE_NAME, token,
            max_age=COOKIE_MAX_AGE, httponly=True, samesite='Lax',
        )
        return response

    @http.route('/formation/deconnexion', type='http', auth='public', website=True)
    def deconnexion(self, **kwargs):
        response = request.redirect('/formation/inscription')
        response.delete_cookie(COOKIE_NAME)
        return response

    # ─────────────────────────────────────────────────────────────────
    # Création / accès au dossier
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/formation/inscription/<int:session_id>',
        type='http', auth='public', website=True,
    )
    def inscription_session(self, session_id, **kwargs):
        session = request.env['training.session'].sudo().browse(session_id)
        if not session.exists():
            return request.not_found()

        partner = _get_current_partner()
        if not partner:
            return request.redirect(f'/formation/auth?session_id={session_id}')

        insc = request.env['training.inscription'].sudo().search([
            ('partner_id', '=', partner.id),
            ('session_id', '=', session_id),
        ], limit=1)

        if not insc:
            insc = request.env['training.inscription'].sudo().create({
                'partner_id': partner.id,
                'session_id': session_id,
                'statut': 'en_cours',
            })
            partner.sudo().write({'is_stagiaire_frmjc': True})

        return request.redirect(f'/formation/dossier/{insc.portal_token}')

    # ─────────────────────────────────────────────────────────────────
    # Formulaire multi-étapes
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/formation/dossier/<string:token>',
        type='http', auth='public', website=True,
    )
    def dossier_home(self, token, **kwargs):
        insc = self._get_inscription(token)
        if not insc:
            return request.redirect('/formation/inscription')
        partner = _get_current_partner()
        if not partner or partner.id != insc.partner_id.id:
            return request.redirect(f'/formation/auth?session_id={insc.session_id.id}')
        if insc.statut == 'accepte':
            return request.redirect(f'/espace-stagiaire/{token}')
        if insc.statut in ('soumis', 'complet', 'refuse', 'abandon'):
            return request.redirect(f'/formation/dossier/{token}/confirme')
        return request.redirect(f'/formation/dossier/{token}/etape/{insc.etape_portal or 1}')

    @http.route(
        '/formation/dossier/<string:token>/etape/<int:etape>',
        type='http', auth='public', website=True, methods=['GET', 'POST'],
    )
    def dossier_etape(self, token, etape, **kwargs):
        insc = self._get_inscription(token)
        if not insc:
            return request.redirect('/formation/inscription')
        partner = _get_current_partner()
        if not partner or partner.id != insc.partner_id.id:
            return request.redirect(f'/formation/auth?session_id={insc.session_id.id}')
        if insc.statut == 'accepte':
            return request.redirect(f'/espace-stagiaire/{token}')
        if insc.statut in ('soumis', 'complet', 'refuse', 'abandon'):
            return request.redirect(f'/formation/dossier/{token}/confirme')

        etape = max(1, min(etape, 8))

        if request.httprequest.method == 'POST':
            return self._traiter_etape(insc, etape, token)

        pays_list = request.env['res.country'].sudo().search([], order='name')
        return request.render('training_frmjc.portal_inscription_form', {
            'insc': insc,
            'partner': insc.partner_id,
            'session': insc.session_id,
            'etape': etape,
            'token': token,
            'pays_list': pays_list,
            'errors': {},
        })

    @http.route(
        '/formation/dossier/<string:token>/confirme',
        type='http', auth='public', website=True,
    )
    def dossier_confirme(self, token, **kwargs):
        insc = self._get_inscription(token)
        if not insc:
            return request.redirect('/formation/inscription')
        return request.render('training_frmjc.portal_inscription_confirme', {
            'insc': insc,
            'token': token,
        })

    # ─────────────────────────────────────────────────────────────────
    # Helpers privés
    # ─────────────────────────────────────────────────────────────────

    def _get_inscription(self, token):
        return request.env['training.inscription'].sudo().search(
            [('portal_token', '=', token)], limit=1
        )

    def _traiter_etape(self, insc, etape, token):
        p = request.params
        files = request.httprequest.files
        vals = {}
        partner_vals = {}

        if etape == 1:
            prenom = (p.get('prenom') or '').strip()
            nom = (p.get('nom') or '').strip()
            if prenom or nom:
                partner_vals['name'] = f'{prenom} {nom}'.strip()
            partner_vals['date_naissance'] = p.get('date_naissance') or False
            partner_vals['lieu_naissance'] = p.get('lieu_naissance', '')
            partner_vals['sexe'] = p.get('sexe', '')
            if p.get('nationalite_id'):
                try:
                    partner_vals['nationalite_id'] = int(p['nationalite_id'])
                except (TypeError, ValueError):
                    pass
            # Consentement RGPD (collecte et traitement des données)
            vals['conditions_acceptees'] = p.get('conditions_acceptees') == 'on'

        elif etape == 2:
            partner_vals.update({
                'street': p.get('street', ''),
                'zip': p.get('zip', ''),
                'city': p.get('city', ''),
                'phone': p.get('phone', ''),
            })

        elif etape == 3:
            vals.update({
                'statut_emploi': p.get('statut_emploi', ''),
                'employeur_nom': p.get('employeur_nom', ''),
                'employeur_adresse': p.get('employeur_adresse', ''),
                'type_contrat': p.get('type_contrat', ''),
                'rqth': p.get('rqth', ''),
                'mode_stagiaire': p.get('mode_stagiaire', ''),
                'type_financement': p.get('type_financement', ''),
                'sous_type_financement': p.get('sous_type_financement', ''),
            })
            for flt in ('remuneration_mensuelle', 'volume_horaire_semaine'):
                try:
                    vals[flt] = float(p.get(flt) or 0)
                except ValueError:
                    pass

        elif etape == 4:
            vals.update({
                'niveau_etudes': p.get('niveau_etudes', ''),
                'dernier_diplome': p.get('dernier_diplome', ''),
                'etablissement_formation': p.get('etablissement_formation', ''),
            })
            try:
                vals['annee_obtention'] = int(p.get('annee_obtention') or 0)
            except ValueError:
                pass
            # ── Expériences (liste dynamique) ──────────────────────
            form = request.httprequest.form
            lignes = zip(
                form.getlist('exp_annee_periode[]'),
                form.getlist('exp_heures[]'),
                form.getlist('exp_structure[]'),
                form.getlist('exp_fonction[]'),
            )
            commands = [(5, 0, 0)]
            for annee, heures, structure, fonction in lignes:
                annee = (annee or '').strip()
                heures = (heures or '').strip()
                structure = (structure or '').strip()
                fonction = (fonction or '').strip()
                if not any((annee, heures, structure, fonction)):
                    continue  # ligne entièrement vide → ignorée
                try:
                    heures_val = float(heures)
                except ValueError:
                    heures_val = 0.0
                if not (annee and structure and fonction) or heures_val <= 0:
                    pays_list = request.env['res.country'].sudo().search([], order='name')
                    return request.render('training_frmjc.portal_inscription_form', {
                        'insc': insc, 'partner': insc.partner_id,
                        'session': insc.session_id, 'etape': 4,
                        'token': token, 'pays_list': pays_list,
                        'errors': {'global': "Chaque expérience doit être entièrement "
                                             "renseignée : année/période, nombre d'heures, "
                                             "nom de la structure et fonction."},
                    })
                commands.append((0, 0, {
                    'annee_periode': annee,
                    'heures': heures_val,
                    'structure': structure,
                    'fonction': fonction,
                }))
            vals['experience_ids'] = commands

        elif etape == 5:
            vals.update({
                'projet_professionnel': p.get('projet_professionnel', ''),
                'structure_accueil': p.get('structure_accueil', ''),
                'fonction_visee': p.get('fonction_visee', ''),
            })

        elif etape == 6:
            doc_fields = {
                'cv': 'cv_filename',
                'lettre_motivation_doc': 'lettre_motivation_filename',
                'diplome_doc': 'diplome_filename',
                'justificatif_identite': 'justificatif_identite_filename',
                'photo_identite': 'photo_identite_filename',
                'attestation_rqth': 'attestation_rqth_filename',
            }
            for field_name, fname_field in doc_fields.items():
                uploaded = files.get(field_name)
                if uploaded and uploaded.filename:
                    data = uploaded.read()
                    if data:
                        vals[field_name] = base64.b64encode(data)
                        vals[fname_field] = uploaded.filename

            # ── Autres documents justificatifs (liste dynamique) ───
            form = request.httprequest.form
            kept_ids = set()
            for raw in form.getlist('autre_doc_keep[]'):
                try:
                    kept_ids.add(int(raw))
                except (TypeError, ValueError):
                    pass
            commands = [
                (2, doc.id, 0)
                for doc in insc.document_ids if doc.id not in kept_ids
            ]
            noms = form.getlist('autre_doc_nom[]')
            fichiers = files.getlist('autre_doc_fichier[]')
            for nom, fichier in zip(noms, fichiers):
                nom = (nom or '').strip()
                a_un_fichier = bool(fichier and fichier.filename)
                if not nom and not a_un_fichier:
                    continue  # ligne vide → ignorée
                data = fichier.read() if a_un_fichier else b''
                if not nom or not data:
                    pays_list = request.env['res.country'].sudo().search([], order='name')
                    return request.render('training_frmjc.portal_inscription_form', {
                        'insc': insc, 'partner': insc.partner_id,
                        'session': insc.session_id, 'etape': 6,
                        'token': token, 'pays_list': pays_list,
                        'errors': {'global': "Chaque document complémentaire doit avoir "
                                             "une nature renseignée et un fichier joint."},
                    })
                commands.append((0, 0, {
                    'name': nom,
                    'fichier': base64.b64encode(data),
                    'fichier_filename': fichier.filename,
                }))
            if commands:
                vals['document_ids'] = commands

        elif etape == 7:
            partner_vals.update({
                'numero_secu': p.get('numero_secu', ''),
                'situation_familiale': p.get('situation_familiale', ''),
            })
            try:
                partner_vals['nombre_enfants'] = int(p.get('nombre_enfants') or 0)
            except ValueError:
                pass
            vals['notes_candidat'] = p.get('notes_candidat', '')
            # Attestation sur l'honneur de l'exactitude des informations
            if p.get('attestation_exactitude') == 'on':
                import datetime
                vals['date_declaration'] = datetime.date.today()
            else:
                vals['date_declaration'] = False

        elif etape == 8:
            if p.get('action') == 'soumettre':
                if not insc.conditions_acceptees or not insc.date_declaration:
                    pays_list = request.env['res.country'].sudo().search([], order='name')
                    return request.render('training_frmjc.portal_inscription_form', {
                        'insc': insc, 'partner': insc.partner_id,
                        'session': insc.session_id, 'etape': 8,
                        'token': token, 'pays_list': pays_list,
                        'errors': {'global': "Vous devez accepter la collecte de vos données "
                                             "personnelles (étape 1) et certifier sur l'honneur "
                                             "l'exactitude des informations (étape 7)."},
                    })
                insc.sudo().write({'statut': 'soumis'})
                self._envoyer_confirmation(insc)
                return request.redirect(f'/formation/dossier/{token}/confirme')

        # Enregistrer et avancer
        next_etape = etape + 1 if etape < 8 else 8
        vals['etape_portal'] = max(insc.etape_portal or 1, next_etape)
        insc.sudo().write(vals)
        if partner_vals:
            insc.partner_id.sudo().write(partner_vals)

        return request.redirect(f'/formation/dossier/{token}/etape/{next_etape}')

    def _envoyer_confirmation(self, insc):
        try:
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            request.env['mail.mail'].sudo().create({
                'subject': f"Dossier reçu – {insc.reference}",
                'body_html': f"""
                    <p>Bonjour {insc.partner_id.name},</p>
                    <p>Votre dossier d'inscription <strong>{insc.reference}</strong>
                    pour la formation <strong>{insc.formation_id.display_name}</strong>
                    a bien été reçu et sera étudié par notre équipe.</p>
                    <p>Vous pouvez consulter votre dossier à tout moment :<br/>
                    <a href="{base_url}/formation/dossier/{insc.portal_token}/confirme">
                    Voir mon dossier</a></p>
                    <p>L'équipe FRMJC</p>
                """,
                'email_to': insc.partner_id.email,
                'auto_delete': True,
            }).send()
        except Exception:
            _logger.exception("Échec email confirmation inscription %s", insc.reference)
