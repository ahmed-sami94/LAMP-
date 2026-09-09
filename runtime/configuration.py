"""Generate root-owned Apache and FPM configuration from validated records."""
import ipaddress
import json
from pathlib import Path
from common import STATE, SITES, hostname, identifier, php_limits

DENY_PRIVATE = '''
    <FilesMatch "(?i)^(\\.|wp-config\\.php|configuration\\.php|composer\\.(json|lock)|.*\\.(sql|bak|ini|log|env))">
        Require all denied
    </FilesMatch>
'''


def site_config(site):
    key = identifier(site["id"])
    host = hostname(site["hostname"])
    root = SITES / key / "public"
    limits = php_limits(site["php"])
    config = json.loads((STATE / "panel.json").read_text())
    proxy_https = "\n".join(
        f'SetEnvIfExpr "-R \'{ipaddress.ip_network(network)}\' && req(\'X-Forwarded-Proto\') == \'https\'" HTTPS=on'
        for network in config["proxies"]
    )
    Path(f"/etc/php/8.5/fpm/pool.d/{key}.conf").write_text(f'''[{key}]
user = {key}
group = {key}
listen = /run/php/{key}.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0660
pm = ondemand
pm.max_children = 5
pm.process_idle_timeout = 10s
clear_env = yes
security.limit_extensions = .php
php_admin_value[memory_limit] = {limits['memory']}M
php_admin_value[upload_max_filesize] = {limits['upload']}M
php_admin_value[post_max_size] = {limits['upload'] + 1}M
php_admin_value[max_execution_time] = {limits['timeout']}
php_admin_flag[display_errors] = off
php_admin_flag[log_errors] = on
php_admin_value[session.save_path] = /srv/sites/{key}/sessions
php_admin_value[upload_tmp_dir] = /srv/sites/{key}/tmp
php_admin_value[open_basedir] = /srv/sites/{key}:/usr/share/php:/etc/ssl/certs
''')
    Path(f"/etc/apache2/sites-enabled/{key}.conf").write_text(f'''<VirtualHost *:80>
    ServerName {host}
    DocumentRoot {root}
    {proxy_https}
    <Directory {root}>
        Options -Indexes -ExecCGI -FollowSymLinks +SymLinksIfOwnerMatch
        AllowOverride FileInfo
        Require all granted
        DirectoryIndex index.php index.html
        FallbackResource /index.php
        <FilesMatch "\\.php$">
            SetHandler "proxy:unix:/run/php/{key}.sock|fcgi://localhost/"
        </FilesMatch>
        {DENY_PRIVATE}
    </Directory>
</VirtualHost>
''')


def admin_config(config):
    host = hostname(config["host"])
    Path("/etc/apache2/ports.conf").write_text("Listen 80\nListen 127.0.0.1:8088\n")
    Path("/etc/apache2/conf-enabled/lampplus.conf").write_text('''ServerName localhost
ServerTokens Prod
ServerSignature Off
TraceEnable Off
Header always set X-Content-Type-Options nosniff
Header always set Referrer-Policy same-origin
''')
    Path("/etc/apache2/sites-enabled/000-admin.conf").write_text(f'''<VirtualHost *:80>
    ServerName invalid.local
    <Location />
        Require all denied
    </Location>
</VirtualHost>
<VirtualHost *:80>
    ServerName {host}
    ProxyPreserveHost On
    ProxyAddHeaders Off
    RequestHeader unset X-Lamp-Client
    RequestHeader set X-Lamp-Client "expr=%{{REMOTE_ADDR}}"
    ProxyPass / http://127.0.0.1:9000/ connectiontimeout=5 timeout=180
    ProxyPassReverse / http://127.0.0.1:9000/
</VirtualHost>
<VirtualHost 127.0.0.1:8088>
    ServerName tools.internal
    SetEnvIf X-Forwarded-Proto "^https$" HTTPS=on
    Alias /phpmyadmin /opt/lampplus/phpmyadmin
    <Directory /opt/lampplus/phpmyadmin>
        Options -Indexes
        AllowOverride None
        Require local
        DirectoryIndex index.php
        <FilesMatch "\\.php$">
            SetHandler "proxy:unix:/run/php/tools.sock|fcgi://localhost/"
        </FilesMatch>
    </Directory>
</VirtualHost>
''')
    Path("/etc/php/8.5/fpm/pool.d/www.conf").unlink(missing_ok=True)
    Path("/etc/php/8.5/fpm/pool.d/tools.conf").write_text('''[tools]
user = www-data
group = www-data
listen = /run/php/tools.sock
listen.owner = www-data
listen.mode = 0600
pm = ondemand
pm.max_children = 4
clear_env = yes
php_admin_flag[display_errors] = off
php_admin_value[session.save_path] = /var/lib/php/sessions
php_admin_value[upload_max_filesize] = 128M
php_admin_value[post_max_size] = 129M
''')
