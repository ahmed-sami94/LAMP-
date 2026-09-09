#!/bin/sh
set -eu
umask 027
python3 /opt/lampplus/bootstrap.py
unset LAMP_ADMIN_PASSWORD LAMP_ADMIN_PASSWORD_FILE
exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
