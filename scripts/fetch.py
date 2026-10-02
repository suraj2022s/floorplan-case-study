"""Download a file over several connections at once and verify its checksum.

Standard library only, so it runs before any environment is set up.

Why it exists: on a lossy or throttled line a single connection can be very slow while the
line itself has room to spare. Splitting the file into byte ranges and fetching them in
parallel uses that room. Every download is checked against a SHA-256 before it is accepted,
so the result is byte-identical to the original whatever route the bytes took.

    python scripts/fetch.py <url> <destination> [--sha256 HEX] [--connections N]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import threading
import time
import urllib.request
from pathlib import Path

CHUNK = 1 << 16
USER_AGENT = "floorplan-fetch/1.0"


def _request(url: str, first: int | None = None, last: int | None = None):
    headers = {"User-Agent": USER_AGENT}
    if first is not None:
        headers["Range"] = f"bytes={first}-{last}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)


def remote_size(url: str) -> int:
    with _request(url, 0, 0) as response:
        content_range = response.headers.get("Content-Range", "")
        if "/" in content_range:
            return int(content_range.rsplit("/", 1)[1])
    raise RuntimeError(f"server did not report a size for {url}; ranges are not supported")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(
    url: str,
    destination: Path,
    sha256: str | None = None,
    connections: int = 12,
    quiet: bool = False,
) -> Path:
    """Fetch `url` to `destination`. Skips the download when a verified copy is present."""
    destination = Path(destination)
    if destination.is_file() and (sha256 is None or sha256_of(destination) == sha256):
        if not quiet:
            print(f"{destination.name}: already present")
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    size = remote_size(url)
    connections = max(1, min(connections, size // (1 << 20) or 1))
    step = -(-size // connections)
    ranges = [(i * step, min(size, (i + 1) * step) - 1) for i in range(connections)]
    parts = [destination.with_name(f"{destination.name}.part{i}") for i in range(connections)]
    done = [0] * connections
    errors: list[str] = []

    def worker(i: int) -> None:
        first, last = ranges[i]
        wanted = last - first + 1
        for _attempt in range(12):
            have = parts[i].stat().st_size if parts[i].exists() else 0
            done[i] = have
            if have >= wanted:
                return
            try:
                with _request(url, first + have, last) as response, open(parts[i], "ab") as out:
                    while True:
                        block = response.read(CHUNK)
                        if not block:
                            break
                        out.write(block)
                        done[i] += len(block)
            except Exception:  # dropped connection: resume from what is on disk
                time.sleep(2)
        if (parts[i].stat().st_size if parts[i].exists() else 0) < wanted:
            errors.append(f"range {first}-{last} did not complete")

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(connections)]
    started = time.time()
    for thread in threads:
        thread.start()
    last_report = 0.0
    while any(thread.is_alive() for thread in threads):
        time.sleep(0.5)
        if not quiet and time.time() - last_report > 5:
            last_report = time.time()
            got = sum(done)
            rate = got / max(time.time() - started, 1e-6)
            print(f"{destination.name}: {got / 1e6:6.1f} / {size / 1e6:.1f} MB "
                  f"({rate / 1e3:.0f} kB/s)", flush=True)
    if errors:
        raise RuntimeError(f"{destination.name}: " + "; ".join(errors))

    temporary = destination.with_name(destination.name + ".assembling")
    with open(temporary, "wb") as out:
        for part in parts:
            with open(part, "rb") as handle:
                for block in iter(lambda: handle.read(1 << 20), b""):
                    out.write(block)
    actual = sha256_of(temporary)
    if sha256 is not None and actual != sha256:
        temporary.unlink()
        for part in parts:
            part.unlink(missing_ok=True)
        raise RuntimeError(f"{destination.name}: checksum mismatch, expected {sha256}, "
                           f"got {actual}. The download was discarded.")
    temporary.replace(destination)
    for part in parts:
        part.unlink(missing_ok=True)
    if not quiet:
        elapsed = time.time() - started
        print(f"{destination.name}: done, {size / 1e6:.1f} MB in {elapsed:.0f} s, "
              f"sha256 {actual[:16]}… {'verified' if sha256 else '(not checked)'}")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("url")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--connections", type=int, default=12)
    arguments = parser.parse_args()
    download(arguments.url, arguments.destination, arguments.sha256, arguments.connections)
    return 0


if __name__ == "__main__":
    sys.exit(main())
