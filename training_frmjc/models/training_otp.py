import random
import string
import uuid
from datetime import timedelta

from odoo import models, fields, api


class TrainingOtp(models.Model):
    _name = 'training.otp'
    _description = 'Code OTP pour authentification portail candidat'
    _order = 'date_creation desc'

    email = fields.Char(string='Email', required=True, index=True)
    code = fields.Char(string='Code OTP', required=True)
    date_creation = fields.Datetime(string='Créé le', default=fields.Datetime.now)
    date_expiry = fields.Datetime(string='Expiration', required=True)
    token = fields.Char(string='Token session', index=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Partenaire')
    utilise = fields.Boolean(string='Utilisé', default=False)

    @api.model
    def generate_otp(self, email):
        """Génère un code OTP, l'envoie par email et retourne l'enregistrement OTP."""
        email = email.strip().lower()

        # Invalider les OTP non utilisés pour cet email
        self.sudo().search([
            ('email', '=', email),
            ('utilise', '=', False),
        ]).unlink()

        code = ''.join(random.choices(string.digits, k=6))
        expiry = fields.Datetime.now() + timedelta(minutes=15)

        partner = self.env['res.partner'].sudo().search(
            [('email', '=ilike', email)], limit=1
        )

        otp = self.sudo().create({
            'email': email,
            'code': code,
            'date_expiry': expiry,
            'partner_id': partner.id if partner else False,
        })

        self.env['mail.mail'].sudo().create({
            'subject': f'Votre code de connexion FRMJC : {code}',
            'body_html': f'''
                <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
                    <h2 style="color:#2c3e50;">Connexion à votre espace candidat</h2>
                    <p>Bonjour,</p>
                    <p>Votre code de connexion est :</p>
                    <div style="font-size:2.5em;font-weight:bold;letter-spacing:12px;
                                color:#2c3e50;background:#f0f4f8;padding:16px;
                                border-radius:6px;text-align:center;margin:16px 0;">
                        {code}
                    </div>
                    <p>Ce code est valable <strong>15 minutes</strong>.</p>
                    <p style="color:#888;font-size:0.9em;">
                        Si vous n'avez pas demandé ce code, ignorez ce message.
                    </p>
                    <hr style="border:none;border-top:1px solid #eee;margin-top:24px;"/>
                    <p style="color:#aaa;font-size:0.8em;">FRMJC Bretagne – Pays de la Loire</p>
                </div>
            ''',
            'email_to': email,
            'auto_delete': True,
        }).send()

        return otp

    def verify(self, code):
        """Vérifie le code OTP. Retourne le token session en cas de succès."""
        self.ensure_one()
        if self.utilise:
            raise ValueError('Ce code a déjà été utilisé.')
        if fields.Datetime.now() > self.date_expiry:
            raise ValueError('Ce code a expiré. Veuillez en demander un nouveau.')
        if self.code != code.strip():
            raise ValueError('Code incorrect. Vérifiez le code reçu par email.')

        session_token = uuid.uuid4().hex

        # Trouver ou créer le partenaire
        if not self.partner_id:
            partner = self.env['res.partner'].sudo().create({
                'name': self.email,
                'email': self.email,
                'is_stagiaire_frmjc': True,
            })
            self.sudo().partner_id = partner

        self.sudo().write({'utilise': True, 'token': session_token})
        return session_token

    @api.model
    def find_by_token(self, token):
        """Retrouve un OTP valide depuis son token de session."""
        if not token:
            return self.browse()
        return self.sudo().search([
            ('token', '=', token),
            ('utilise', '=', True),
        ], limit=1)

    @api.model
    def nettoyer_expires(self):
        """Cron : supprime les OTP expirés de plus de 24h."""
        from datetime import timedelta
        seuil = fields.Datetime.now() - timedelta(hours=24)
        self.sudo().search([('date_expiry', '<', seuil)]).unlink()
