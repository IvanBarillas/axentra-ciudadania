#!/usr/bin/env python3
"""Instala el CLI oficial verificado y compila CSS sin Node.js ni Django.

Copiado verbatim de axentra-core-django/tools/tailwind.py (mismo mecanismo:
binario oficial fijado por versión y SHA256, sin red en tiempo de build una
vez instalado, sin Tailwind Browser/CDN — mismo patrón ya usado en
axentra-mod-tramites y axentra-mod-situaciones-de-vida). Único cambio real:
la ruta de salida, que sigue la convención de Django de namespacing por app
(ciudadania/static/ciudadania/...) para no colisionar con otras apps al
correr collectstatic.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
LOCK = json.loads((ROOT / 'tools/tailwind.lock.json').read_text())


def cli_path():
    system = {'Linux': 'linux', 'Darwin': 'macos', 'Windows': 'windows'}.get(platform.system())
    arch = {'x86_64': 'x64', 'AMD64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine())
    suffix = '-musl' if system == 'linux' and list(Path('/lib').glob('ld-musl-*.so.1')) else ''
    asset = f'tailwindcss-{system}-{arch}{suffix}' + ('.exe' if system == 'windows' else '')
    if asset not in LOCK['assets']:
        raise SystemExit(f'Plataforma no soportada: {platform.system()} {platform.machine()}')
    return asset, ROOT / '.tools' / LOCK['version'] / asset


def verify(path, asset):
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == LOCK['assets'][asset]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'build', 'watch'])
    args = parser.parse_args()
    asset, binary = cli_path()
    if args.command == 'install':
        if not verify(binary, asset):
            url = f"https://github.com/tailwindlabs/tailwindcss/releases/download/{LOCK['version']}/{asset}"
            binary.parent.mkdir(parents=True, exist_ok=True)
            with urlopen(url, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != LOCK['assets'][asset]:
                raise SystemExit('SHA256 incorrecto; no se instalará el ejecutable.')
            with tempfile.NamedTemporaryFile(dir=binary.parent, delete=False) as temp:
                temp.write(data)
                temp_path = Path(temp.name)
            temp_path.chmod(0o755)
            os.replace(temp_path, binary)
        print(f"Tailwind {LOCK['version']}: {binary}")
        return
    if not verify(binary, asset):
        raise SystemExit('CLI ausente o alterado. Ejecuta: python tools/tailwind.py install')
    output = ROOT / 'ciudadania/static/ciudadania/css/tailwind.css'
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [str(binary), '-i', str(ROOT / 'assets/css/tailwind.css'), '-o', str(output), '--minify']
    if args.command == 'watch':
        command.append('--watch=always')
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
