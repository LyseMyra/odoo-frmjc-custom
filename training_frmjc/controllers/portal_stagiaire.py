import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

COOKIE_NAME = 'frmjc_portal_token'


def _get_current_partner():
    token = request.httprequest.cookies.get(COOKIE_NAME)
    if not token:
        return None
    otp = request.env['training.otp'].sudo().find_by_token(token)
    return otp.partner_id if otp else None


class PortalStagiaire(http.Controller):

    # ─────────────────────────────────────────────────────────────────
    # Tableau de bord principal (liste des inscriptions acceptées)
    # ─────────────────────────────────────────────────────────────────

    @http.route('/espace-stagiaire', type='http', auth='public', website=True)
    def espace_index(self, **kwargs):
        partner = _get_current_partner()
        if not partner:
            return request.redirect('/formation/auth?next=/espace-stagiaire')

        inscriptions = request.env['training.inscription'].sudo().search([
            ('partner_id', '=', partner.id),
            ('statut', '=', 'accepte'),
        ])

        if len(inscriptions) == 1:
            return request.redirect(
                f'/espace-stagiaire/{inscriptions[0].portal_token}'
            )

        return request.render('training_frmjc.portal_stagiaire_select', {
            'partner': partner,
            'inscriptions': inscriptions,
        })

    # ─────────────────────────────────────────────────────────────────
    # Tableau de bord d'une inscription acceptée
    # ─────────────────────────────────────────────────────────────────

    @http.route('/espace-stagiaire/<string:token>', type='http', auth='public', website=True)
    def espace_dashboard(self, token, **kwargs):
        partner = _get_current_partner()
        if not partner:
            return request.redirect(f'/formation/auth?next=/espace-stagiaire/{token}')

        insc = request.env['training.inscription'].sudo().search([
            ('portal_token', '=', token),
            ('partner_id', '=', partner.id),
        ], limit=1)

        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        if insc.statut != 'accepte':
            return request.redirect(f'/formation/dossier/{token}/confirme')

        conventions = request.env['training.convention'].sudo().search([
            ('inscription_id', '=', insc.id),
        ])

        alternances = request.env['training.alternance'].sudo().search([
            ('inscription_id', '=', insc.id),
            ('statut', '!=', 'archive'),
        ])
        has_alternance = bool(alternances)

        champs_manquants = []
        if not partner.numero_secu:
            champs_manquants.append('N° sécurité sociale')
        if not partner.date_naissance:
            champs_manquants.append('Date de naissance')
        if not partner.street:
            champs_manquants.append('Adresse')

        return request.render('training_frmjc.portal_stagiaire_dashboard', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'conventions': conventions,
            'nb_conventions_a_signer': len(conventions.filtered(
                lambda c: c.statut in ('a_signer', 'en_cours_signature')
            )),
            'champs_manquants': champs_manquants,
            'alternances': alternances,
            'has_alternance': has_alternance,
        })

    # ─────────────────────────────────────────────────────────────────
    # Liste des conventions
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/conventions',
        type='http', auth='public', website=True,
    )
    def espace_conventions(self, token, **kwargs):
        partner = _get_current_partner()
        if not partner:
            return request.redirect(
                f'/formation/auth?next=/espace-stagiaire/{token}/conventions'
            )

        insc = request.env['training.inscription'].sudo().search([
            ('portal_token', '=', token),
            ('partner_id', '=', partner.id),
            ('statut', '=', 'accepte'),
        ], limit=1)

        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        conventions = request.env['training.convention'].sudo().search([
            ('inscription_id', '=', insc.id),
        ])

        return request.render('training_frmjc.portal_stagiaire_conventions', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'conventions': conventions,
        })

    # ─────────────────────────────────────────────────────────────────
    # Détail d'une convention (avec lien vers Odoo Sign si disponible)
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/convention/<int:convention_id>',
        type='http', auth='public', website=True,
    )
    def espace_convention_detail(self, token, convention_id, **kwargs):
        partner = _get_current_partner()
        if not partner:
            return request.redirect(
                f'/formation/auth?next=/espace-stagiaire/{token}/convention/{convention_id}'
            )

        insc = request.env['training.inscription'].sudo().search([
            ('portal_token', '=', token),
            ('partner_id', '=', partner.id),
            ('statut', '=', 'accepte'),
        ], limit=1)

        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        convention = request.env['training.convention'].sudo().browse(convention_id)
        if not convention.exists() or convention.inscription_id.id != insc.id:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        # Trouver le lien de signature Odoo Sign pour ce partenaire
        sign_url = None
        if convention.sign_request_id and 'sign.request.item' in request.env:
            sign_item = request.env['sign.request.item'].sudo().search([
                ('sign_request_id', '=', convention.sign_request_id.id),
                ('partner_id', '=', partner.id),
            ], limit=1)
            if sign_item and sign_item.state not in ('completed', 'canceled'):
                base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
                # URL Odoo Sign v17+ : /sign/document/<request_id>/<access_token>
                sign_url = (
                    f"{base_url}/sign/document"
                    f"/{convention.sign_request_id.id}"
                    f"/{sign_item.access_token}"
                )

        return request.render('training_frmjc.portal_stagiaire_convention_detail', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'convention': convention,
            'sign_url': sign_url,
        })

    # ─────────────────────────────────────────────────────────────────
    # Documents du stagiaire
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/documents',
        type='http', auth='public', website=True,
    )
    def espace_documents(self, token, **kwargs):
        partner = _get_current_partner()
        if not partner:
            return request.redirect(
                f'/formation/auth?next=/espace-stagiaire/{token}/documents'
            )

        insc = request.env['training.inscription'].sudo().search([
            ('portal_token', '=', token),
            ('partner_id', '=', partner.id),
            ('statut', '=', 'accepte'),
        ], limit=1)

        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        # Documents générés liés à cette inscription ou session
        documents = request.env['training.document'].sudo().search([
            '|',
            ('stagiaire_id', '=', partner.id),
            ('session_id', '=', insc.session_id.id),
        ])

        return request.render('training_frmjc.portal_stagiaire_documents', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'documents': documents,
        })

    # ─────────────────────────────────────────────────────────────────
    # Présences — liste
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/presences',
        type='http', auth='public', website=True,
    )
    def espace_presences(self, token, **kwargs):
        partner = _get_current_partner()
        if not partner:
            return request.redirect(
                f'/formation/auth?next=/espace-stagiaire/{token}/presences'
            )
        insc = request.env['training.inscription'].sudo().search([
            ('portal_token', '=', token),
            ('partner_id', '=', partner.id),
            ('statut', '=', 'accepte'),
        ], limit=1)
        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        from datetime import date, timedelta
        today = date.today()
        horizon = today + timedelta(days=30)

        presences = request.env['training.attendance'].sudo().search([
            ('inscription_id', '=', insc.id),
            ('date', '>=', today - timedelta(days=90)),
            ('date', '<=', horizon),
        ], order='date desc, demi_journee')

        # Seules les présences du jour peuvent être confirmées
        a_confirmer_aujourd_hui = presences.filtered(
            lambda p: p.statut == 'a_confirmer' and p.date == today
        )
        a_confirmer_autre = presences.filtered(
            lambda p: p.statut == 'a_confirmer' and p.date != today
        )
        passees = presences.filtered(lambda p: p.statut != 'a_confirmer')

        return request.render('training_frmjc.portal_stagiaire_presences', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'today': today,
            'presences_a_confirmer': a_confirmer_aujourd_hui,
            'presences_a_confirmer_autre': a_confirmer_autre,
            'presences_passees': passees,
        })

    # ─────────────────────────────────────────────────────────────────
    # Présences — confirmation demi-journée
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/presences/<int:att_id>/confirmer',
        type='http', auth='public', website=True,
        methods=['GET', 'POST'],
    )
    def espace_presence_confirmer(self, token, att_id, **kwargs):
        partner = _get_current_partner()
        if not partner:
            return request.redirect(
                f'/formation/auth?next=/espace-stagiaire/{token}/presences/{att_id}/confirmer'
            )
        insc = request.env['training.inscription'].sudo().search([
            ('portal_token', '=', token),
            ('partner_id', '=', partner.id),
            ('statut', '=', 'accepte'),
        ], limit=1)
        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        att = request.env['training.attendance'].sudo().browse(att_id)
        if not att.exists() or att.inscription_id.id != insc.id:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        from datetime import date as _date
        if att.date != _date.today():
            return request.redirect(f'/espace-stagiaire/{token}/presences')

        erreur = None
        if request.httprequest.method == 'POST':
            signature_data = kwargs.get('signature_data', '').strip()
            if not signature_data or signature_data == 'data:,':
                erreur = 'Veuillez apposer votre signature avant de confirmer.'
            else:
                import base64
                # signature_data est un data-URL PNG : "data:image/png;base64,XXXX"
                if ',' in signature_data:
                    b64 = signature_data.split(',', 1)[1]
                else:
                    b64 = signature_data
                try:
                    sig_bytes = base64.b64decode(b64)
                    att.write({
                        'statut': 'present',
                        'confirme_le': fields.Datetime.now(),
                        'signature': base64.b64encode(sig_bytes),
                        'signature_filename': 'signature.png',
                    })
                    return request.redirect(
                        f'/espace-stagiaire/{token}/presences?confirme=1'
                    )
                except Exception:
                    erreur = 'Signature invalide. Veuillez réessayer.'

        return request.render('training_frmjc.portal_stagiaire_presence_confirmer', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'att': att,
            'erreur': erreur,
        })

    # ─────────────────────────────────────────────────────────────────
    # Présences — dépôt de justificatif d'absence
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/presences/<int:att_id>/justifier',
        type='http', auth='public', website=True,
        methods=['GET', 'POST'],
    )
    def espace_presence_justifier(self, token, att_id, **kwargs):
        partner = _get_current_partner()
        if not partner:
            return request.redirect(f'/formation/auth')
        insc = request.env['training.inscription'].sudo().search([
            ('portal_token', '=', token),
            ('partner_id', '=', partner.id),
            ('statut', '=', 'accepte'),
        ], limit=1)
        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        att = request.env['training.attendance'].sudo().browse(att_id)
        if not att.exists() or att.inscription_id.id != insc.id:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        saved = False
        if request.httprequest.method == 'POST':
            motif = kwargs.get('motif_absence', '').strip()
            vals = {'motif_absence': motif or False}
            # Fichier justificatif
            justif_file = request.httprequest.files.get('justificatif')
            if justif_file and justif_file.filename:
                import base64
                vals['justificatif'] = base64.b64encode(justif_file.read())
                vals['justificatif_filename'] = justif_file.filename
            if motif or vals.get('justificatif'):
                vals['statut'] = 'justifie'
            att.sudo().write(vals)
            saved = True

        return request.render('training_frmjc.portal_stagiaire_presence_justifier', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'att': att,
            'saved': saved,
        })

    # ─────────────────────────────────────────────────────────────────
    # Helpers — structure d'accueil / contacts
    # ─────────────────────────────────────────────────────────────────

    def _find_or_create_structure(self, vals):
        Partner = request.env['res.partner'].sudo()
        siret = (vals.get('structure_siret') or '').strip().replace(' ', '')
        nom = (vals.get('structure_nom') or '').strip()

        structure = None
        if siret:
            structure = Partner.search([('siret', '=', siret), ('is_company', '=', True)], limit=1)
        if not structure and nom:
            structure = Partner.search([('name', '=ilike', nom), ('is_company', '=', True)], limit=1)

        write_vals = {}
        for src, dst in [
            ('structure_siret', 'siret'),
            ('structure_forme_juridique', 'forme_juridique'),
            ('structure_convention_collective', 'convention_collective'),
            ('structure_code_idcc', 'code_idcc'),
            ('structure_street', 'street'),
            ('structure_zip', 'zip'),
            ('structure_city', 'city'),
        ]:
            v = (vals.get(src) or '').strip()
            if v:
                write_vals[dst] = v
        if siret:
            write_vals['siret'] = siret

        if structure:
            if write_vals:
                structure.write(write_vals)
        else:
            if not nom:
                return None
            create_vals = write_vals.copy()
            create_vals.update({'name': nom, 'is_company': True, 'is_structure_accueil': True})
            structure = Partner.create(create_vals)

        return structure

    def _find_or_create_person(self, structure, prefix, vals, extra_vals=None):
        """Find or create a contact (non-company) linked to structure."""
        if not structure:
            return None

        Partner = request.env['res.partner'].sudo()
        prenom = (vals.get(f'{prefix}_prenom') or '').strip()
        nom = (vals.get(f'{prefix}_nom') or '').strip()
        email = (vals.get(f'{prefix}_email') or '').strip().lower()
        phone = (vals.get(f'{prefix}_phone') or '').strip()

        nom_complet = ' '.join(filter(None, [prenom, nom]))
        if not nom_complet and not email:
            return None

        person = None
        if email:
            person = Partner.search([
                ('email', '=ilike', email),
                ('is_company', '=', False),
            ], limit=1)

        write_vals = {}
        if phone:
            write_vals['phone'] = phone
        if email:
            write_vals['email'] = email
        if nom_complet:
            write_vals['name'] = nom_complet
        write_vals['parent_id'] = structure.id

        if extra_vals:
            for k, v in extra_vals.items():
                if v:
                    write_vals[k] = v

        if person:
            person.write(write_vals)
        else:
            if not nom_complet:
                return None
            person = Partner.create({'is_company': False, **write_vals})

        return person

    def _get_insc_or_403(self, token):
        partner = _get_current_partner()
        if not partner:
            return None, None
        insc = request.env['training.inscription'].sudo().search([
            ('portal_token', '=', token),
            ('partner_id', '=', partner.id),
            ('statut', '=', 'accepte'),
        ], limit=1)
        return partner, insc

    def _alternance_form_data(self, alt):
        """Build a flat dict of form field values from an alternance record."""
        data = {
            'intitule_poste': alt.intitule_poste or '',
            'missions_principales': alt.missions_principales or '',
            'missions_complementaires': alt.missions_complementaires or '',
            'activites_coordination': alt.activites_coordination or '',
            'publics': alt.publics or '',
            'projet_alternance': alt.projet_alternance or '',
            'date_debut': str(alt.date_debut) if alt.date_debut else '',
            'date_fin': str(alt.date_fin) if alt.date_fin else '',
        }
        if alt.structure_id:
            s = alt.structure_id
            data.update({
                'structure_nom': s.name or '',
                'structure_siret': s.siret or '',
                'structure_forme_juridique': s.forme_juridique or '',
                'structure_convention_collective': s.convention_collective or '',
                'structure_code_idcc': s.code_idcc or '',
                'structure_street': s.street or '',
                'structure_zip': s.zip or '',
                'structure_city': s.city or '',
            })
        if alt.responsable_id:
            r = alt.responsable_id
            parts = (r.name or '').split(' ', 1)
            data.update({
                'resp_prenom': parts[0] if len(parts) > 1 else '',
                'resp_nom': parts[1] if len(parts) > 1 else parts[0],
                'resp_email': r.email or '',
                'resp_phone': r.phone or '',
            })
        if alt.tuteur_id:
            t = alt.tuteur_id
            parts = (t.name or '').split(' ', 1)
            data.update({
                'tuteur_prenom': parts[0] if len(parts) > 1 else '',
                'tuteur_nom': parts[1] if len(parts) > 1 else parts[0],
                'tuteur_email': t.email or '',
                'tuteur_phone': t.phone or '',
                'tuteur_date_naissance': str(t.date_naissance) if t.date_naissance else '',
                'tuteur_diplome': t.diplome or '',
                'tuteur_annee_diplome': t.annee_diplome or '',
                'tuteur_experience': t.experience_domaine_annees or '',
                'tuteur_carte_pro': t.numero_carte_pro or '',
            })
        return data

    def _save_alternance(self, alt, kwargs):
        """Write all form fields to the alternance record (and linked partners)."""
        structure = self._find_or_create_structure(kwargs)
        responsable = self._find_or_create_person(structure, 'resp', kwargs)
        tuteur_extra = {}
        for src, dst in [
            ('tuteur_date_naissance', 'date_naissance'),
            ('tuteur_diplome', 'diplome'),
            ('tuteur_carte_pro', 'numero_carte_pro'),
        ]:
            v = (kwargs.get(src) or '').strip()
            if v:
                tuteur_extra[dst] = v
        for src, dst in [
            ('tuteur_annee_diplome', 'annee_diplome'),
            ('tuteur_experience', 'experience_domaine_annees'),
        ]:
            v = kwargs.get(src)
            try:
                iv = int(v) if v else 0
                if iv:
                    tuteur_extra[dst] = iv
            except (ValueError, TypeError):
                pass
        tuteur = self._find_or_create_person(structure, 'tuteur', kwargs, tuteur_extra)

        vals = {}
        if structure:
            vals['structure_id'] = structure.id
        if responsable:
            vals['responsable_id'] = responsable.id
        if tuteur:
            vals['tuteur_id'] = tuteur.id
        for f in ('intitule_poste', 'publics', 'missions_principales',
                  'missions_complementaires', 'activites_coordination', 'projet_alternance'):
            if f in kwargs:
                vals[f] = kwargs[f] or False
        for f in ('date_debut', 'date_fin'):
            v = kwargs.get(f)
            vals[f] = v if v else False

        alt.sudo().write(vals)

    # ─────────────────────────────────────────────────────────────────
    # Structure d'accueil — liste
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/structure',
        type='http', auth='public', website=True,
    )
    def espace_structure_liste(self, token, **kwargs):
        partner, insc = self._get_insc_or_403(token)
        if not partner:
            return request.redirect(f'/formation/auth?next=/espace-stagiaire/{token}/structure')
        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        alternances = request.env['training.alternance'].sudo().search([
            ('inscription_id', '=', insc.id),
        ])
        return request.render('training_frmjc.portal_stagiaire_structure_liste', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'alternances': alternances,
        })

    # ─────────────────────────────────────────────────────────────────
    # Structure d'accueil — nouveau dossier
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/structure/nouveau',
        type='http', auth='public', website=True,
        methods=['GET', 'POST'],
    )
    def espace_structure_nouveau(self, token, **kwargs):
        partner, insc = self._get_insc_or_403(token)
        if not partner:
            return request.redirect(
                f'/formation/auth?next=/espace-stagiaire/{token}/structure/nouveau'
            )
        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        if request.httprequest.method == 'POST':
            alt = request.env['training.alternance'].sudo().create({
                'inscription_id': insc.id,
                'statut': 'brouillon',
            })
            self._save_alternance(alt, kwargs)
            return request.redirect(
                f'/espace-stagiaire/{token}/structure/{alt.id}?saved=1'
            )

        return request.render('training_frmjc.portal_stagiaire_structure_form', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'alt': None,
            'form_data': {},
            'saved': False,
            'is_new': True,
        })

    # ─────────────────────────────────────────────────────────────────
    # Structure d'accueil — modifier un dossier
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/structure/<int:alt_id>',
        type='http', auth='public', website=True,
        methods=['GET', 'POST'],
    )
    def espace_structure_edit(self, token, alt_id, **kwargs):
        partner, insc = self._get_insc_or_403(token)
        if not partner:
            return request.redirect(
                f'/formation/auth?next=/espace-stagiaire/{token}/structure/{alt_id}'
            )
        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        alt = request.env['training.alternance'].sudo().browse(alt_id)
        if not alt.exists() or alt.inscription_id.id != insc.id:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        saved = bool(kwargs.get('saved'))

        if request.httprequest.method == 'POST' and alt.statut in ('brouillon',):
            self._save_alternance(alt, kwargs)
            saved = True

        form_data = self._alternance_form_data(alt)

        return request.render('training_frmjc.portal_stagiaire_structure_form', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'alt': alt,
            'form_data': form_data,
            'saved': saved,
            'is_new': False,
        })

    # ─────────────────────────────────────────────────────────────────
    # Structure d'accueil — soumettre au secrétariat
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/structure/<int:alt_id>/soumettre',
        type='http', auth='public', website=True,
        methods=['POST'],
    )
    def espace_structure_soumettre(self, token, alt_id, **kwargs):
        partner, insc = self._get_insc_or_403(token)
        if not partner:
            return request.redirect(f'/formation/auth')
        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        alt = request.env['training.alternance'].sudo().browse(alt_id)
        if not alt.exists() or alt.inscription_id.id != insc.id:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        if alt.statut == 'brouillon':
            alt.action_soumettre()

        return request.redirect(f'/espace-stagiaire/{token}/structure?soumis=1')

    # ─────────────────────────────────────────────────────────────────
    # Mon profil — lecture et modification
    # ─────────────────────────────────────────────────────────────────

    @http.route(
        '/espace-stagiaire/<string:token>/profil',
        type='http', auth='public', website=True,
        methods=['GET', 'POST'],
    )
    def espace_profil(self, token, **kwargs):
        partner = _get_current_partner()
        if not partner:
            return request.redirect(
                f'/formation/auth?next=/espace-stagiaire/{token}/profil'
            )

        insc = request.env['training.inscription'].sudo().search([
            ('portal_token', '=', token),
            ('partner_id', '=', partner.id),
            ('statut', '=', 'accepte'),
        ], limit=1)

        if not insc:
            return request.render('training_frmjc.portal_stagiaire_403', {}, status=403)

        saved = False
        if request.httprequest.method == 'POST':
            # ── Champs partner ──────────────────────────────────────
            vals_partner = {}
            for f in ('street', 'zip', 'city', 'phone', 'numero_secu',
                       'lieu_naissance', 'sexe', 'situation_familiale'):
                if f in kwargs:
                    vals_partner[f] = kwargs[f] or False
            if kwargs.get('date_naissance'):
                vals_partner['date_naissance'] = kwargs['date_naissance']
            if kwargs.get('nationalite_id'):
                try:
                    vals_partner['nationalite_id'] = int(kwargs['nationalite_id'])
                except ValueError:
                    pass
            try:
                vals_partner['nombre_enfants'] = int(kwargs.get('nombre_enfants') or 0)
            except ValueError:
                pass
            if vals_partner:
                partner.sudo().write(vals_partner)

            # ── Champs inscription ──────────────────────────────────
            vals_insc = {}
            for f in ('statut_emploi', 'type_contrat', 'employeur_nom',
                       'employeur_adresse', 'mode_stagiaire', 'type_financement',
                       'sous_type_financement', 'structure_accueil', 'fonction_visee'):
                if f in kwargs:
                    vals_insc[f] = kwargs[f] or False
            for f in ('remuneration_mensuelle', 'volume_horaire_semaine'):
                if kwargs.get(f):
                    try:
                        vals_insc[f] = float(kwargs[f])
                    except ValueError:
                        pass
            if vals_insc:
                insc.sudo().write(vals_insc)

            saved = True

        pays_list = request.env['res.country'].sudo().search([], order='name')

        return request.render('training_frmjc.portal_stagiaire_profil', {
            'partner': partner,
            'insc': insc,
            'token': token,
            'pays_list': pays_list,
            'saved': saved,
        })
