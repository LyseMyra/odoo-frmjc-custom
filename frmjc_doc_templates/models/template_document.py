import io
import logging

from odoo import models, fields
from odoo.exceptions import UserError

from .variable_registry import build_context

_logger = logging.getLogger(__name__)

try:
    from docxtpl import DocxTemplate
except ImportError:
    DocxTemplate = None


class TemplateDocument(models.Model):
    _name = 'template.document'
    _description = 'Modèle de document (.docx)'
    _order = 'name'

    name = fields.Char(required=True)
    model_id = fields.Many2one(
        'ir.model', required=True, ondelete='cascade', string='Document applicable à',
        help="Modèle Odoo sur lequel ce document peut être généré "
             "(ex. Dossier d'inscription).",
    )
    model_name = fields.Char(related='model_id.model', store=True, readonly=True)
    file = fields.Binary(string='Fichier .docx', required=True, attachment=True)
    file_name = fields.Char(string='Nom du fichier')
    active = fields.Boolean(default=True)
    notes = fields.Text(
        string='Notes',
        help="Notes internes sur ce modèle (pas affichées dans le document généré).",
    )

    def generate(self, record):
        """Génère le document pour UN enregistrement. Renvoie les octets
        du .docx rempli."""
        self.ensure_one()
        if DocxTemplate is None:
            raise UserError(
                "La bibliothèque Python « docxtpl » n'est pas installée sur "
                "le serveur. Demande à ton administrateur de l'installer :\n"
                "pip install docxtpl"
            )
        if record._name != self.model_name:
            raise UserError(
                f"Ce modèle de document est prévu pour « {self.model_name} », "
                f"pas pour « {record._name} »."
            )
        context = build_context(record)
        try:
            doc = DocxTemplate(io.BytesIO(bytes(self.file)))
            doc.render(context)
        except Exception as exc:
            _logger.exception("Échec de génération du document %s", self.name)
            raise UserError(
                f"Erreur lors de la génération du document : {exc}\n\n"
                "Vérifie que toutes les balises {{ ... }} utilisées dans le "
                "fichier Word correspondent bien à des variables du "
                "catalogue (menu Documents > Catalogue des variables)."
            ) from exc
        output = io.BytesIO()
        doc.save(output)
        return output.getvalue()
