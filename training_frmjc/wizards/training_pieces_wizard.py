from odoo import models, fields
from odoo.exceptions import UserError


class TrainingPiecesWizard(models.TransientModel):
    _name = 'training.pieces.wizard'
    _description = 'Demande de pièces manquantes'

    inscription_id = fields.Many2one(
        'training.inscription', string='Dossier', required=True, readonly=True
    )
    pieces_manquantes = fields.Text(
        string='Pièces manquantes',
        required=True,
    )
    message_complementaire = fields.Text(
        string='Message complémentaire (optionnel)',
    )

    def action_envoyer(self):
        self.ensure_one()
        insc = self.inscription_id
        if not insc.partner_id.email:
            raise UserError(
                f"Le candidat {insc.partner_id.name} n'a pas d'adresse email renseignée."
            )

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        lien_portail = f'{base_url}/formation/dossier/{insc.portal_token}'

        pieces_html = ''.join(
            f'<li>{ligne.strip()}</li>'
            for ligne in self.pieces_manquantes.splitlines()
            if ligne.strip()
        )

        body = f"""
            <p>Bonjour {insc.partner_id.name},</p>
            <p>Nous avons bien reçu votre dossier d'inscription
            <strong>{insc.reference}</strong> pour la formation
            <strong>{insc.formation_id.display_name}</strong>.</p>
            <p>Après vérification, il nous manque les pièces suivantes pour
            compléter votre dossier :</p>
            <ul>{pieces_html}</ul>
        """

        if self.message_complementaire:
            body += f'<p>{self.message_complementaire}</p>'

        body += f"""
            <p>Merci de les déposer dès que possible sur votre espace candidat :<br/>
            <a href="{lien_portail}">Accéder à mon dossier</a></p>
            <p>L'équipe FRMJC</p>
        """

        self.env['mail.mail'].sudo().create({
            'subject': f'Pièces manquantes — Dossier {insc.reference}',
            'body_html': body,
            'email_to': insc.partner_id.email,
            'auto_delete': True,
        }).send()

        insc.write({
            'statut': 'en_attente_pieces',
            'date_derniere_relance': fields.Date.today(),
            'nb_relances': insc.nb_relances + 1,
        })

        insc.message_post(
            body=(
                f'<b>Demande de pièces envoyée</b> à {insc.partner_id.email} :<br/>'
                f'{self.pieces_manquantes.replace(chr(10), "<br/>")}'
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        return {'type': 'ir.actions.act_window_close'}
