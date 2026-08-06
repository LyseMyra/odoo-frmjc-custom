import base64
from datetime import date, datetime
import pytz
from odoo import fields, http
from odoo.http import request


def _current_demi_journee():
    """Retourne la demi-journée active en heure locale France."""
    tz = pytz.timezone('Europe/Paris')
    now_local = datetime.now(tz)
    return 'matin' if now_local.hour < 13 else 'apres_midi'


class PortalFormateur(http.Controller):

    # ── Nouveau portail hebdomadaire ──────────────────────────────────

    @http.route('/formation/intervenant/<string:token>', type='http', auth='public', website=True)
    def intervenant_semaine(self, token, **kw):
        semaine = request.env['training.formateur.semaine'].sudo().search(
            [('token', '=', token)], limit=1,
        )
        if not semaine:
            return request.not_found()

        today = date.today()
        current_dj = _current_demi_journee()

        djs_data = []
        for dj in semaine.demi_journee_ids.sorted(lambda r: (r.date, r.demi_journee)):
            is_active = (
                dj.date == today
                and dj.demi_journee == current_dj
                and dj.statut == 'en_attente'
            )
            is_past = (
                dj.date < today
                or (dj.date == today and current_dj == 'apres_midi' and dj.demi_journee == 'matin')
            )
            atts = dj.get_attendances()
            djs_data.append({
                'dj': dj,
                'attendances': atts,
                'is_active': is_active,
                'is_past': is_past,
            })

        signed_id = int(kw.get('signed', 0))
        return request.render('training_frmjc.portal_intervenant_semaine', {
            'semaine': semaine,
            'djs_data': djs_data,
            'today': today,
            'signed_id': signed_id,
        })

    @http.route(
        '/formation/intervenant/<string:token>/valider/<int:dj_id>',
        type='http', auth='public', website=True, methods=['POST'], csrf=True,
    )
    def intervenant_valider_dj(self, token, dj_id, **post):
        semaine = request.env['training.formateur.semaine'].sudo().search(
            [('token', '=', token)], limit=1,
        )
        dj = request.env['training.formateur.demi_journee'].sudo().browse(dj_id)
        if not semaine or not dj.exists() or dj.semaine_id.id != semaine.id:
            return request.not_found()

        today = date.today()
        current_dj = _current_demi_journee()
        if dj.date != today or dj.demi_journee != current_dj or dj.statut == 'signe':
            return request.redirect(f'/formation/intervenant/{token}')

        now = fields.Datetime.now()
        attendances = dj.get_attendances()
        for att in attendances:
            val = post.get(f'presence_{att.id}')
            note = (post.get(f'note_{att.id}') or '').strip()
            vals = {}
            if note:
                vals['note_formateur'] = note
            if val == 'present':
                vals['valide_intervenant'] = True
                vals['valide_intervenant_le'] = now
                if att.statut == 'a_confirmer':
                    vals['statut'] = 'present'
                    vals['confirme_le'] = now
            elif val == 'absent':
                vals['valide_intervenant'] = False
                if att.statut in ('a_confirmer', 'present'):
                    vals['statut'] = 'absent'
            if vals:
                att.sudo().write(vals)

        sig_data = post.get('signature_data', '').strip()
        if sig_data and sig_data != 'data:,':
            raw = sig_data.split(',', 1)[-1]
            try:
                dj.sudo().write({
                    'signature': base64.b64decode(raw),
                    'signe_le': now,
                    'statut': 'signe',
                })
            except Exception:
                pass

        return request.redirect(f'/formation/intervenant/{token}?signed={dj_id}')

    # ── Ancien portail journalier (conservé pour les données existantes) ──

    @http.route('/formation/formateur/<string:token>', type='http', auth='public', website=True)
    def formateur_presences(self, token, **kw):
        fj = request.env['training.formateur.jour'].sudo().search(
            [('token', '=', token)], limit=1
        )
        if not fj:
            return request.not_found()
        attendances = fj.get_attendances()
        return request.render('training_frmjc.portal_formateur_presences', {
            'fj': fj,
            'attendances': attendances,
            'already_confirmed': bool(fj.confirme_le),
        })

    @http.route(
        '/formation/formateur/<string:token>/valider',
        type='http', auth='public', website=True, methods=['POST'], csrf=True,
    )
    def formateur_valider(self, token, **post):
        fj = request.env['training.formateur.jour'].sudo().search(
            [('token', '=', token)], limit=1
        )
        if not fj:
            return request.not_found()

        attendances = fj.get_attendances()
        now = fields.Datetime.now()

        for att in attendances:
            val = post.get(f'presence_{att.id}')
            note = (post.get(f'note_{att.id}') or '').strip()
            vals = {}

            if note:
                vals['note_formateur'] = note

            if val == 'present':
                vals['valide_intervenant'] = True
                vals['valide_intervenant_le'] = now
                if att.statut == 'a_confirmer':
                    # L'intervenant confirme la présence même sans confirmation du stagiaire
                    vals['statut'] = 'present'
                    vals['confirme_le'] = now
            elif val == 'absent':
                vals['valide_intervenant'] = False
                if att.statut in ('a_confirmer', 'present'):
                    vals['statut'] = 'absent'

            if vals:
                att.sudo().write(vals)

        fj.sudo().write({'confirme_le': now})

        nb_confirmes = len(attendances.filtered(lambda a: a.valide_intervenant))
        return request.render('training_frmjc.portal_formateur_confirme', {
            'fj': fj,
            'nb_total': len(attendances),
            'nb_confirmes': nb_confirmes,
        })
