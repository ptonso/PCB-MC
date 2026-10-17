import argparse
import hashlib
import os
import re
import sys
import zipfile

import requests

API_BASE = "https://data.4tu.nl/v3"
DEFAULT_DOI = "10.4121/7c6e5bda-eecf-4feb-8a3a-7f823b1b0140.v1"
DOI_RE = re.compile(r"10\.4121/([0-9a-f-]{36})(?:\.v(\d+))?")


def parse_doi(doi: str) -> tuple[str, str]:
    match = DOI_RE.search(doi)
    if not match:
        sys.exit(f"could not parse a 4TU dataset UUID out of DOI {doi}")
    uuid, version = match.groups()
    return uuid, version or "1"


def list_files(uuid: str, version: str) -> list[dict]:
    url = f"{API_BASE}/datasets/{uuid}/versions/{version}/ro-crate-metadata.json"
    resp = requests.get(url)
    resp.raise_for_status()
    graph = resp.json()["@graph"]
    return [item for item in graph if item.get("@type") == "File"]


def md5sum(path: str, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(file_info: dict, output_dir: str, chunk_size: int = 1 << 20) -> str:
    dest = os.path.join(output_dir, file_info["name"])
    if os.path.exists(dest) and os.path.getsize(dest) == int(file_info.get("contentSize", -1)):
        print(f"skip (already downloaded): {file_info['name']}")
        return dest

    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    partial = dest + ".part"
    with requests.get(file_info["contentUrl"], stream=True) as resp:
        resp.raise_for_status()
        with open(partial, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                f.write(chunk)
    os.replace(partial, dest)

    print(f"downloaded: {file_info['name']} ({int(file_info.get('contentSize', 0)) / 1e6:.1f} MB)")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the PCB-MC dataset from 4TU.ResearchData")
    parser.add_argument("--doi", default=DEFAULT_DOI)
    parser.add_argument("--output", default="./data/PCB-MC")
    parser.add_argument("--md5", help="expected MD5 of the downloaded archive; the script exits on a mismatch")
    parser.add_argument("--extract", action="store_true", help="extract downloaded .zip archives into --output")
    args = parser.parse_args()

    uuid, version = parse_doi(args.doi)
    files = list_files(uuid, version)
    os.makedirs(args.output, exist_ok=True)
    for file_info in files:
        dest = download_file(file_info, args.output)
        if args.md5 and md5sum(dest) != args.md5:
            sys.exit(f"checksum mismatch for {dest}: expected {args.md5}")
        if args.extract and dest.endswith(".zip"):
            zipfile.ZipFile(dest).extractall(args.output)


if __name__ == "__main__":
    main()
