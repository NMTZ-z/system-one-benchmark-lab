"""Canonical parent launch environment, shared by real admission and synthetic rehearsal."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def parent_environment(owner: Path) -> dict:
    return {'HOME': str(owner), 'PATH': '/usr/bin:/bin', 'LANG': 'en_US.UTF-8',
        'PYTHONDONTWRITEBYTECODE': '1', 'GIT_OPTIONAL_LOCKS': '0',
        'HERMES_DISABLE_LAZY_INSTALLS': '1', 'HERMES_PM_AUTO_SYNC': '0'}


def command(entry: Path, arguments: list[str]) -> list[str]:
    return [sys.executable, '-B', str(entry), *arguments]


def main():
    os.umask(0o077)
    import phase8_3_h4e_runner as runner
    import phase8_3_h4e_contract as c
    from phase8_3_h4e_controller import Controller, parent_policy
    args = runner.parse_arguments()
    if args.controller_fd is not None:
        raise c.H4EBlocked('controller descriptor is internal to the canonical launcher')
    root = Path(tempfile.mkdtemp(prefix='h4e-controller-', dir='/private/tmp'))
    root.chmod(0o700); (root / 'tmp').mkdir(mode=0o700)
    environment = parent_environment(Path.home()); environment['TMPDIR'] = str(root / 'tmp')
    controller = Controller(source_sha=args.frozen_sha, manifest=args.release_manifest,
        approval=args.authorization, control_root=root, rehearsal_receipt=args.rehearsal_receipt,
        execute=args.execute_real_step_plan, source_archive=args.source_archive)
    policy = parent_policy(manifest=args.release_manifest, archive=args.source_archive, approval=args.authorization,
        control_root=root, receipt=args.rehearsal_receipt, real_dns=args.execute_real_step_plan)
    raise SystemExit(controller.run(command(ROOT / 'scripts/phase8_3_h4e_runner.py', sys.argv[1:]),
                                   environment, ROOT, policy))


if __name__ == '__main__':
    main()
