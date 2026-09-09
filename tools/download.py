import hashlib
import json
import pathlib
import sys
import tarfile
import urllib.request

root = pathlib.Path('/opt/lampplus')
lock = json.loads((root / 'dependencies.lock.json').read_text())
for name in ('phpmyadmin', 'composer', 'wp', 'wordpress', 'joomla', 'filebrowser-' + sys.argv[1]):
    item = lock['artifacts'][name]
    request = urllib.request.Request(item['url'], headers={'User-Agent': 'LAMPplus-build'})
    with urllib.request.urlopen(request, timeout=180) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != item['sha256']:
        raise RuntimeError('Checksum mismatch: ' + name)
    if name in ('composer', 'wp') or name.startswith('filebrowser-'):
        path = pathlib.Path('/usr/local/bin') / ('filebrowser' if name.startswith('filebrowser-') else name)
        path.write_bytes(data)
        path.chmod(0o755)
    elif name == 'phpmyadmin':
        archive = root / 'phpmyadmin.tar.gz'
        archive.write_bytes(data)
        with tarfile.open(archive) as tar:
            top = tar.getmembers()[0].name.split('/')[0]
            tar.extractall(root, filter='data')
        (root / top).rename(root / 'phpmyadmin')
        archive.unlink()
    else:
        (root / (name + '.tar.gz')).write_bytes(data)
