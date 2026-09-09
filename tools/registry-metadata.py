"""Resolve the public candidate digest without a publishing credential."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request

repository = "ahmedsamigmail/lampplus"
with urllib.request.urlopen("https://auth.docker.io/token?service=registry.docker.io&scope=repository:" + repository + ":pull", timeout=30) as response:
    token = json.load(response)["token"]
request = urllib.request.Request("https://registry-1.docker.io/v2/" + repository + "/manifests/2.0.0-rc.1", headers={
    "Authorization": "Bearer " + token,
    "Accept": "application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json",
})
with urllib.request.urlopen(request, timeout=30) as response:
    data = response.read()
index = json.loads(data)
architectures = {m.get("platform", {}).get("architecture") for m in index.get("manifests", [])}
if not {"amd64", "arm64"} <= architectures:
    raise ValueError("Candidate must contain amd64 and arm64")
digest = "sha256:" + hashlib.sha256(data).hexdigest()
metadata = {"version": "2.0.0-rc.1", "source_commit": os.environ["GITHUB_SHA"], "image": repository + "@" + digest, "digest": digest}
Path("release-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
with open(os.environ["GITHUB_OUTPUT"], "a") as output:
    output.write("digest=" + digest + "\n")
print(repository + "@" + digest)
