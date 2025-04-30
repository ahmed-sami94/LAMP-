FROM ubuntu:latest

LABEL maintainer="you@example.com"
ENV DEBIAN_FRONTEND=noninteractive

# Set DNS
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf

# Install required packages
RUN apt-get update && apt-get install -y \
    apache2 \
    mariadb-server \
    php \
    php-mysql \
    php-cli \
    php-curl \
    php-zip \
    php-mbstring \
    php-xml \
    wget \
    unzip \
    nano \
    curl \
    && apt-get clean

# phpMyAdmin manual installation
RUN mkdir -p /var/www/html/phpmyadmin && \
    wget https://files.phpmyadmin.net/phpMyAdmin/5.2.1/phpMyAdmin-5.2.1-all-languages.zip -O /tmp/pma.zip && \
    unzip /tmp/pma.zip -d /tmp && \
    mv /tmp/phpMyAdmin-5.2.1-all-languages/* /var/www/html/phpmyadmin && \
    rm -rf /tmp/pma.zip /tmp/phpMyAdmin-5.2.1-all-languages

# Set MySQL root password and create admin user
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Apache setup
RUN echo "ServerName localhost" >> /etc/apache2/apache2.conf
COPY apache/index.html /var/www/html/index.html
COPY mo/ /var/www/html/mo/

# Permissions
RUN chown -R www-data:www-data /var/www/html

# Install File Browser
RUN curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

EXPOSE 80 3306 8080
RUN mkdir -p /var/run/mysqld && chown mysql:mysql /var/run/mysqld

ENTRYPOINT ["/entrypoint.sh"]
