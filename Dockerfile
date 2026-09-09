ARG UBUNTU_IMAGE=ubuntu:26.04@sha256:513c074113a871b51a8d16ab445c88779d6452d937a164fb5cc479f32668a41d
FROM ${UBUNTU_IMAGE}
ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
LABEL org.opencontainers.image.title="LAMP+" \
      org.opencontainers.image.source="https://github.com/ahmed-sami94/LAMP-" \
      org.opencontainers.image.licenses="GPL-3.0-only" \
      org.opencontainers.image.version="2.0.0-rc.1"
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    apache2 mariadb-server mariadb-client php8.5-fpm php8.5-cli php8.5-mysql \
    php8.5-curl php8.5-zip php8.5-mbstring php8.5-xml php8.5-gd php8.5-intl \
    php8.5-bcmath php8.5-sqlite3 ca-certificates curl unzip \
    python3 python3-flask python3-requests python3-gunicorn python3-yaml \
 supervisor tini passwd util-linux \
 && if dpkg-query -W pebble >/dev/null 2>&1; then apt-get purge -y pebble; fi \
 && rm -f /usr/bin/pebble && rm -rf /var/lib/apt/lists/*
RUN groupadd -g 1500 lampadmin && useradd -u 1500 -g lampadmin -M -s /usr/sbin/nologin lampadmin \
    && groupadd -g 1600 lampsites && useradd -u 1600 -g lampsites -M -s /usr/sbin/nologin lampfiles \
 && usermod -aG lampsites www-data \
 && a2dissite 000-default && a2enmod proxy proxy_http proxy_fcgi headers rewrite remoteip \
 && mkdir -p /opt/lampplus /srv/sites /var/lib/lampplus /var/backups/lampplus /run/lampplus
RUN rm -rf /var/lib/mysql /var/lib/mariadb && install -d -o mysql -g mysql /var/lib/mysql
COPY dependencies.lock.json /opt/lampplus/dependencies.lock.json
COPY tools/download.py /opt/lampplus/download.py
RUN python3 /opt/lampplus/download.py ${TARGETARCH}
COPY config/phpmyadmin/ /opt/lampplus/phpmyadmin/
RUN rm -rf /opt/lampplus/phpmyadmin/vendor \
 && COMPOSER_ALLOW_SUPERUSER=1 composer install --working-dir=/opt/lampplus/phpmyadmin --no-dev --no-scripts --no-plugins --prefer-dist --no-interaction \
 && composer audit --working-dir=/opt/lampplus/phpmyadmin --no-dev
COPY runtime/ /opt/lampplus/
COPY panel/ /opt/lampplus/panel/
COPY assets/ /opt/lampplus/panel/static/brand/
COPY entrypoint.sh /entrypoint.sh
COPY config/supervisord.conf /etc/supervisor/conf.d/lampplus.conf
COPY LICENSE THIRD_PARTY_NOTICES.md /usr/share/doc/lampplus/
RUN chmod +x /entrypoint.sh /opt/lampplus/lampctl \
    && ln -s /opt/lampplus/lampctl /usr/local/bin/lampctl \
    && dpkg-query -W > /opt/lampplus/packages.txt
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 CMD python3 /opt/lampplus/health.py
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
