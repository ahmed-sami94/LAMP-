"""Read only regular files/directories from a private backup, as the website UID."""
import sys
import tarfile
from pathlib import Path

destination = Path(sys.argv[1])
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz") as archive:
    for member in archive:
        if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
            raise ValueError("Backup contains links or special files; restore refused.")
        archive.extract(member, destination, filter="data")
