from . import models
from . import wizards


def _post_init_hook(env):
    """Synchronise le catalogue de variables (template.variable) depuis le
    registre Python à l'installation et à chaque mise à jour du module."""
    env['template.variable']._sync_variables()
