#!/usr/bin/env bash
# Eseguire SOLTANTO sul Raspberry, come utente del desktop: bash deploy/install.sh
set -euo pipefail

if [[ "$(uname -s)" != Linux ]] || [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model; then
  echo 'Installazione annullata: questo script è riservato a Raspberry Pi OS.' >&2
  exit 1
fi
if [[ $EUID -eq 0 ]]; then
  echo 'Esegui come utente del desktop, senza sudo davanti allo script.' >&2
  exit 1
fi
if [[ ! -f /etc/os-release ]] || ! grep -Eq '(^ID=(raspbian|debian)$|^ID_LIKE=.*debian)' /etc/os-release; then
  echo 'Sistema non supportato: usare Raspberry Pi OS Desktop.' >&2
  exit 1
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# I percorsi vengono inseriti in unit systemd e desktop entry, senza shell escaping.
if [[ ! "$project_dir" =~ ^/[a-zA-Z0-9_./-]+$ ]]; then
  echo 'Sposta il progetto in un percorso senza spazi o caratteri speciali (es. ~/SmartGreenhouse).' >&2
  exit 1
fi
if [[ -f "$project_dir/.env" ]] && ! grep -Eq '^DATA_DIR=data$' "$project_dir/.env"; then
  echo 'Questa installazione richiede DATA_DIR=data nel file .env (directory protetta da systemd).' >&2
  exit 1
fi
cd -- "$project_dir"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip python3-gpiozero python3-lgpio
if apt-cache show chromium >/dev/null 2>&1; then
  sudo apt-get install -y chromium
else
  sudo apt-get install -y chromium-browser
fi
python3 -m venv --system-site-packages .venv-pi
.venv-pi/bin/python -m pip install -r requirements-pi.txt
mkdir -p data
chmod 700 data
if [[ ! -f .env ]]; then
  cp deploy/raspberry.env.example .env
fi
chmod 600 .env
sudo usermod -aG gpio "$(id -un)"
export GREENHOUSE_INSTALL_USER="$(id -un)" GREENHOUSE_INSTALL_GROUP="$(id -gn)" GREENHOUSE_INSTALL_PROJECT="$project_dir"
.venv-pi/bin/python - <<'PY'
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

project = Path(os.environ['GREENHOUSE_INSTALL_PROJECT'])
replacements = {
    '@@PROJECT@@': str(project), '@@USER@@': os.environ['GREENHOUSE_INSTALL_USER'],
    '@@GROUP@@': os.environ['GREENHOUSE_INSTALL_GROUP'],
}
def render(name):
    content = (project / 'deploy' / name).read_text()
    for key, value in replacements.items():
        content = content.replace(key, value)
    return content

with TemporaryDirectory(prefix='greenhouse-install-') as tmp:
    unit = Path(tmp) / 'smart-greenhouse.service'
    unit.write_text(render('smart-greenhouse.service.in'))
    subprocess.run(['sudo', 'install', '-m', '644', str(unit), '/etc/systemd/system/smart-greenhouse.service'], check=True)

autostart = Path.home() / '.config' / 'autostart'
autostart.mkdir(parents=True, exist_ok=True)
(autostart / 'smart-greenhouse-kiosk.desktop').write_text(render('smart-greenhouse-kiosk.desktop.in'))

# labwc usa il proprio autostart. Preserva gli avvii standard e le impostazioni esistenti.
labwc = Path.home() / '.config' / 'labwc' / 'autostart'
labwc.parent.mkdir(parents=True, exist_ok=True)
if not labwc.exists():
    system_autostart = Path('/etc/xdg/labwc/autostart')
    labwc.write_text(system_autostart.read_text() if system_autostart.exists() else '#!/bin/sh\n')
line = f'{project}/.venv-pi/bin/python {project}/deploy/kiosk.py &'
content = labwc.read_text()
if line not in content.splitlines():
    labwc.write_text(content.rstrip() + '\n\n# Smart Greenhouse\n' + line + '\n')
labwc.chmod(0o755)
PY
sudo systemctl daemon-reload
sudo systemctl enable --now smart-greenhouse.service
echo 'Installato. Verifica: systemctl status smart-greenhouse e http://localhost:5000'
echo 'Il file .env preesistente è stato conservato; una nuova installazione usa mock.'
echo 'Abilita Desktop Autologin e disattiva Screen Blanking nelle impostazioni del Raspberry.'
echo 'Al prossimo login del desktop partirà il Kiosk. Per il controllo reale leggere README.md.'
