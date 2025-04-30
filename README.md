# 🚀 LAMP+ Docker Image

A custom all-in-one **LAMP stack Docker image** built on Ubuntu with:

- Apache2
- PHP 8
- MariaDB (MySQL-compatible)
- phpMyAdmin
- File Browser (web-based file manager)
- PHP Monitoring Dashboard
- Beautiful custom welcome page
- GPLv3 Licensed and fully open-source

---

## 🌟 Features

- ✅ Ubuntu latest stable version
- ✅ Apache2 with styled welcome page
- ✅ PHP 8 + necessary extensions
- ✅ MariaDB with default credentials: `admin` / `admin`
- ✅ phpMyAdmin for easy DB access at `/phpmyadmin`
- ✅ File Browser running at port `8080` for browsing `/var/www/html`
- ✅ PHP monitoring script at `/mo`
- ✅ All in one container — **no Docker Compose required**
- ✅ Shared volume for live PHP editing

---

## 🗂️ File Structure
. ├── Dockerfile ├── entrypoint.sh ├── index.html # Custom Apache welcome page ├── mo/ # PHP monitoring scripts └── README.md


---

## 📦 How to Build and Run

```bash
# Clone the repository
git clone https://github.com/your-username/lampplus.git
cd lampplus

# Build the Docker image
docker build -t lampplus .

# Run the container
docker run -d \
  -p 80:80 \
  -p 3306:3306 \
  -p 8080:8080 \
  --name lampplus-container \
  -v $(pwd):/var/www/html/data \
  lampplus

🔗 Access Your Tools

Tool	URL
Apache Welcome	http://localhost/
phpMyAdmin	http://localhost/phpmyadmin
Monitoring	http://localhost/mo
File Browser	http://localhost:8080

🛠️ Customize
You can edit files directly in your local folder (/var/www/html) — changes reflect instantly inside the container thanks to the bind mount.
📜 License
This project is licensed under the GNU General Public License v3.0 (GPLv3).

Feel free to use, modify, and distribute under the terms of this license.

✉️ Maintainer
Ahmed Sami
📧 i@ahmed-sami.me


