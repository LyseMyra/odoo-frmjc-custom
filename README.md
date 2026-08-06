# Commandes utiles

## Surveiller les logs

sudo tail -f /var/log/odoo/odoo.log

## Lancer Odoo normalement

sudo -u odoo /opt/odoo/venv/bin/python /opt/odoo/odoo/odoo-bin \
    -c /etc/odoo.conf \
    -d frmjc_dev

## Mettre à jour un module spécifique

sudo -u odoo /opt/odoo/venv/bin/python /opt/odoo/odoo/odoo-bin \
    -c /etc/odoo.conf \
    -d frmjc_dev \
    -u training_frmjc \
    --stop-after-init \
    --log-level=warn

ou

sudo -u odoo /opt/odoo/venv/bin/python /opt/odoo/odoo/odoo-bin \
    -c /etc/odoo.conf \
    -d frmjc_dev \
    -u mobility_frmjc \
    --stop-after-init \
    --log-level=warn

## Mettre à jour les deux modules en même temps

sudo -u odoo /opt/odoo/venv/bin/python /opt/odoo/odoo/odoo-bin \
    -c /etc/odoo.conf \
    -d frmjc_dev \
    -u training_frmjc,mobility_frmjc \
    --stop-after-init \
    --log-level=warn

## Installer le module mobility_frmjc pour la première fois

sudo -u odoo /opt/odoo/venv/bin/python /opt/odoo/odoo/odoo-bin \
    -c /etc/odoo.conf \
    -d frmjc_dev \
    -i mobility_frmjc \
    --stop-after-init \
    --log-level=warn
