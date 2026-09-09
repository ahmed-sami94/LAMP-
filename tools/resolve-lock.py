"""Resolve official release downloads; review and commit the resulting lock."""
import hashlib
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]

def read(url, headers=None):
    request = urllib.request.Request(url, headers={"User-Agent": "LAMPplus-release", **(headers or {})})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()

def api(url):
    return json.loads(read(url))

def artifact(url, digest=None):
    expected = None
    if digest:
        expected = digest.removeprefix("sha256:")
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise RuntimeError("Invalid upstream SHA256")
    content = read(url)
    actual = hashlib.sha256(content).hexdigest()
    if expected is not None and actual != expected:
        raise RuntimeError("Upstream checksum mismatch")
    return {"url": url, "sha256": actual}


def main():
    token = api("https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/ubuntu:pull")["token"]
    manifest = read("https://registry-1.docker.io/v2/library/ubuntu/manifests/26.04", {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json",
    })
    previous = json.loads((ROOT / "dependencies.lock.json").read_text())
    lock = {"ubuntu": "ubuntu:26.04@sha256:" + hashlib.sha256(manifest).hexdigest(),
            "caddy": previous["caddy"], "artifacts": {}}
    fb = api("https://api.github.com/repos/gtsteffaniak/filebrowser/releases/latest")
    for arch in ("amd64", "arm64"):
        entry = next(x for x in fb["assets"] if x["name"] == f"linux-{arch}-filebrowser")
        lock["artifacts"]["filebrowser-" + arch] = artifact(entry["browser_download_url"], entry["digest"])
    pma = api("https://www.phpmyadmin.net/home_page/version.json")["version"]
    pma_url = f"https://files.phpmyadmin.net/phpMyAdmin/{pma}/phpMyAdmin-{pma}-all-languages.tar.gz"
    lock["artifacts"]["phpmyadmin"] = artifact(pma_url, read(pma_url + ".sha256").decode().split()[0])
    composer = api("https://getcomposer.org/versions")["stable"][0]
    composer_url = "https://getcomposer.org" + composer["path"]
    lock["artifacts"]["composer"] = artifact(composer_url, read(composer_url + ".sha256sum").decode().split()[0])
    wpcli = api("https://api.github.com/repos/wp-cli/wp-cli/releases/latest")
    wpasset = next(x for x in wpcli["assets"] if x["name"].endswith(".phar"))
    lock["artifacts"]["wp"] = artifact(wpasset["browser_download_url"], wpasset.get("digest"))
    wp = next(x for x in api("https://api.wordpress.org/core/version-check/1.7/")["offers"] if x["response"] == "upgrade")
    lock["artifacts"]["wordpress"] = artifact(f"https://wordpress.org/wordpress-{wp['version']}.tar.gz")
    joomla = api("https://api.github.com/repos/joomla/joomla-cms/releases/latest")
    jasset = next(x for x in joomla["assets"] if x["name"].endswith("Full_Package.tar.gz"))
    lock["artifacts"]["joomla"] = artifact(jasset["browser_download_url"], jasset["digest"])
    lock["versions"] = {"filebrowser": fb["tag_name"], "phpmyadmin": pma, "wordpress": wp["version"], "joomla": joomla["tag_name"], "composer": composer["version"], "wpcli": wpcli["tag_name"]}
    (ROOT / "dependencies.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    print(json.dumps(lock["versions"]))


if __name__ == "__main__":
    main()
