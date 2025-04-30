#!/bin/bash

# Initialize MariaDB data directory if not already initialized
if [ ! -d "/var/lib/mysql/mysql" ]; then
  echo "Initializing MariaDB..."
  mysql_install_db --user=mysql --ldata=/var/lib/mysql
fi

# Start MariaDB in the background
echo "Starting MariaDB..."
mysqld_safe --skip-networking &
sleep 5

# Configure MySQL users
echo "Configuring MySQL users..."
mysql -uroot <<EOF
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED BY 'admin';
CREATE USER IF NOT EXISTS 'admin'@'localhost' IDENTIFIED BY 'admin';
GRANT ALL PRIVILEGES ON *.* TO 'admin'@'localhost' WITH GRANT OPTION;
FLUSH PRIVILEGES;
EOF

# Shutdown MariaDB to restart it properly
mysqladmin -uroot -padmin shutdown

# Start MariaDB in the foreground
echo "Starting MariaDB (foreground)..."
mysqld_safe --bind-address=0.0.0.0 &
sleep 5

# Start File Browser
echo "Starting File Browser..."
filebrowser -r /var/www/html --address 0.0.0.0 --port 8080 &

# Start Apache
echo "Starting Apache..."
apachectl -D FOREGROUND
