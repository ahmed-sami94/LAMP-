"""Extract pinned CMS packages as the destination's unprivileged website user."""
import sys
import tarfile
from pathlib import Path

archive, destination, kind = sys.argv[1:]
root = Path(destination)
if any(root.iterdir()):
    raise SystemExit("Destination must be empty.")
with tarfile.open(archive) as package:
    members = package.getmembers()
    for member in members:
        if kind == "wordpress":
            if not member.name.startswith("wordpress/"):
                raise ValueError("Unexpected package layout")
            member.name = member.name[len("wordpress/"):]
        if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
            raise ValueError("Links and special files are not allowed")
    package.extractall(root, members=[m for m in members if m.name], filter="data")
