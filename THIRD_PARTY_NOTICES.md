# Third-party notices

LAMP+ source is GPLv3. The container combines independently licensed components;
their licenses and attribution are not replaced by the LAMP+ license.

| Component | Upstream | License |
| --- | --- | --- |
| Ubuntu packages | https://ubuntu.com/ | Individual package licenses in `/usr/share/doc/*/copyright` |
| Apache HTTP Server | https://httpd.apache.org/ | Apache-2.0 |
| PHP | https://www.php.net/ | PHP-3.01 and bundled notices |
| MariaDB | https://mariadb.org/ | GPL-2.0 and component notices |
| phpMyAdmin | https://www.phpmyadmin.net/ | GPL-2.0-only |
| FileBrowser Quantum | https://github.com/gtsteffaniak/filebrowser | Apache-2.0 and dependency notices |
| Composer | https://getcomposer.org/ | MIT |
| WP-CLI | https://wp-cli.org/ | MIT |
| WordPress | https://wordpress.org/ | GPL-2.0-or-later |
| Joomla | https://www.joomla.org/ | GPL-2.0-or-later |
| Flask / Werkzeug / Jinja | https://palletsprojects.com/ | BSD-3-Clause |
| Requests | https://requests.readthedocs.io/ | Apache-2.0 |
| Supervisor | https://supervisord.org/ | BSD-derived / upstream notices |
| Tini | https://github.com/krallin/tini | MIT |
| Lucide icons 1.43.0 | https://lucide.dev/ | ISC / MIT-derived icons; notice in `panel/static/icons/LICENSE` |

CMS archives and phpMyAdmin distributions include their license files. The release
SBOM and package manifest identify bundled dependency versions. Source download
URLs and checksums are recorded in `dependencies.lock.json`. Redistribution must
retain all upstream notices and satisfy the applicable source-offer obligations.

LAMP+ rebuilds phpMyAdmin's production vendor directory from the committed
`config/phpmyadmin/composer.lock`, within upstream version constraints, to replace
vulnerable bundled dependencies. Development dependencies, plugins and install
scripts are not executed. This packaging change is maintained by LAMP+, not an
official phpMyAdmin distribution modification endorsed by its authors.
