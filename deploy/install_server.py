"""Install the staged Pate bundle under the unprivileged deshin account."""

import os
import secrets
import shutil
import subprocess
import tarfile
from pathlib import Path


HOME = Path.home()
ROOT = HOME / "pate-runtime"
STAGING = ROOT / "staging"
SECRETS = ROOT / "secrets"
UNITS = HOME / ".config/systemd/user"


def write_private(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8") as output:
        output.write(value)
    path.chmod(0o600)


def main() -> None:
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, exist_ok=True)
    SECRETS.mkdir(mode=0o700, exist_ok=True)
    UNITS.mkdir(parents=True, exist_ok=True)

    with tarfile.open(STAGING / "pate-app-20261012.tar.gz", "r:gz") as bundle:
        bundle.extractall(ROOT / "app", filter="data")

    credential = STAGING / "config.json"
    if credential.exists():
        os.replace(credential, SECRETS / "crm.json")
        (SECRETS / "crm.json").chmod(0o600)

    password_path = SECRETS / "operator-password.txt"
    password_file = SECRETS / "operator.htpasswd"
    if not password_path.exists() and not password_file.exists():
        password = secrets.token_urlsafe(24)
        result = subprocess.run(
            ["/usr/bin/htpasswd", "-niB", "operator"],
            input=password + "\n",
            text=True,
            check=True,
            capture_output=True,
        )
        write_private(password_path, password + "\n")
        write_private(password_file, result.stdout)

    shutil.copyfile(STAGING / "nginx.conf", ROOT / "nginx.conf")
    (ROOT / "nginx.conf").chmod(0o600)
    for name in ("pate-web.service", "pate-venues.service", "pate-proxy.service"):
        shutil.copyfile(STAGING / name, UNITS / name)
        (UNITS / name).chmod(0o644)

    print("Staged app, private CRM config, proxy config, and user services installed.")


if __name__ == "__main__":
    main()
