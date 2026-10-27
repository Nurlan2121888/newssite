"""Run the news importer silently and keep its execution log."""

import os
from pathlib import Path
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent


def main():
    python = ROOT / 'venv' / 'Scripts' / 'python.exe'
    log_directory = ROOT / 'logs'
    log_directory.mkdir(exist_ok=True)
    log_path = log_directory / 'fetch_news.log'

    with log_path.open('a', encoding='utf-8') as log:
        started = datetime.now(ZoneInfo('Asia/Baku')).isoformat(timespec='seconds')
        log.write(f'\n[{started}] News update started\n')
        log.flush()

        try:
            result = subprocess.run(
                [str(python), '-B', '-X', 'utf8', '-u', str(ROOT / 'manage.py'), 'fetch_news'],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=40 * 60,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            log.write(f'Update failed: {error}\n')
            return 1

        finished = datetime.now(ZoneInfo('Asia/Baku')).isoformat(timespec='seconds')
        log.write(f'[{finished}] News update finished; exit code {result.returncode}\n')
        return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
