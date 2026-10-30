"""Fail-closed admission from a source-bound, independently rechecked system rehearsal."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time

import phase8_3_h4e_contract as c
from phase8_3_h4e_source import digest

DIFFERENCES = [
    {'id': 'provider_boundary', 'real': 'fixed Step Plan DNS, TLS and remote service',
     'synthetic': 'fixed numeric loopback HTTP fixture; same budget proxy and socket guard',
     'uncovered': 'DNS, TLS, remote availability, remote model behavior and subscription debit'},
    {'id': 'data_owner', 'real': 'owner Home, existing OFF test profile and historical physical ledger',
     'synthetic': 'disposable owner, synthetic manual credential and independent 3+3+2 ledger with H1 UNKNOWN',
     'uncovered': 'real credential validity and private database contents'},
    {'id': 'source_identity', 'real': 'clean frozen project commit',
     'synthetic': 'independent Git snapshot with exactly the same full public source manifest',
     'uncovered': 'absolute paths and commit identifiers differ; they are retained without conflation'},
    {'id': 'dependency_mapping', 'real': 'installed interpreters, libraries and fixed model artifacts',
     'synthetic': 'same read-only interpreters and libraries; complete hash-identical model copy in disposable paths',
     'uncovered': 'owner-specific installation facts are synthetic; resolved dependency fingerprints must match'},
    {'id': 'kernel_ceiling', 'real': 'per-child Seatbelt; provider TCP443 plus fixed destination audit',
     'synthetic': 'same child policy factory, exact loopback substitution, separate WAN-denying executor policy',
     'uncovered': 'profiles are applied separately because different Seatbelt profiles cannot be nested'},
    {'id': 'trusted_controller', 'real': 'fixed-role launch, durable identity, GO and cleanup controller',
     'synthetic': 'same controller outside Seatbelt; no arbitrary command RPC, no model or Provider credential reads',
     'uncovered': 'owner explicitly accepted the controller exception; controller itself lacks a kernel WAN guarantee'},
    {'id': 'process_topology', 'real': 'controller owns the five child groups; executor receives bounded process handles',
     'synthetic': 'same IPC, descriptor transfer, kernel identity and release handshake',
     'uncovered': 'controller replaces direct Popen ownership from the old 40d49fc executor'},
    {'id': 'probe_bootstrap', 'real': 'direct frozen child entrypoint',
     'synthetic': 'kernel-denial probe then that same entrypoint; no Agent, SDK, tool, model or observer stub',
     'uncovered': 'a small probe bootstrap and read-only context file precede child initialization'},
    {'id': 'external_fixture', 'real': 'remote Provider exists independently of the five owned roles',
     'synthetic': 'one separately owned loopback fixture; five real executor roles remain exact',
     'uncovered': 'fixture startup and deterministic responses do not test remote concurrency or latency'},
    {'id': 'production_directory_inventory', 'real': 'existing production and historical directory inventory',
     'synthetic': 'small disposable inventory; actual owner parent profile is separately compiled and kernel-probed first',
     'uncovered': 'private file contents are not copied; directory-only selectors preserve content denial'},
]

_DEPENDENCIES = r'''
import hashlib,importlib.metadata as m,json,pathlib,sys
records={}
for d in m.distributions():
 name=d.metadata.get('Name','unknown')
 files={}
 for n in ('METADATA','RECORD'):
  p=pathlib.Path(d._path)/n
  if p.is_file():files[n]=hashlib.sha256(p.read_bytes()).hexdigest()
 records[name]={'version':d.version,'metadata':files}
core={}
for base in map(pathlib.Path,sys.path):
 if base.name!='site-packages' or not base.is_dir():continue
 for name in ('openai','httpx','httpcore','laya','mlx','yaml'):
  package=base/name
  if package.is_dir():
   for p in sorted(package.rglob('*')):
    if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}:
     core[str(p.relative_to(base))]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'version':sys.version,'executable_sha256':hashlib.sha256(pathlib.Path(sys.executable).resolve().read_bytes()).hexdigest(),
 'distribution_metadata_sha256':hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest(),
 'core_dependency_tree_sha256':hashlib.sha256(json.dumps(core,sort_keys=True).encode()).hexdigest(),
 'distributions':len(records),'core_files':len(core)}))
'''


def environment_fingerprint() -> dict:
    from phase8_3_h4e_launch import parent_environment
    from phase8_3_h4b_direct_child import HERMES_PYTHON
    from phase8_3_real_hermes_h2 import MODEL_PATH
    from phase8_3_native_rehearsal import model_files
    interpreters = {}
    for role, python in [('parent', Path(sys.executable)), ('native', HERMES_PYTHON)]:
        output = subprocess.check_output([str(python), '-I', '-B', '-c', _DEPENDENCIES],
            env=parent_environment(Path.home()), text=True, timeout=40)
        interpreters[role] = {'invocation': str(python), 'resolved': str(python.resolve()), **json.loads(output)}
    model = {str(file.relative_to(MODEL_PATH)): digest(file) for file in model_files(MODEL_PATH)}
    inventory = {'owner_top_level': sorted(p.name for p in Path.home().iterdir()),
        'hermes_top_level': sorted(p.name for p in (Path.home() / '.hermes').iterdir()),
        'projects_top_level': sorted(p.name for p in (Path.home() / 'Projects').iterdir())}
    return {'system': platform.system(), 'kernel': platform.release(), 'kernel_build': platform.version(),
        'machine': platform.machine(), 'macos': platform.mac_ver()[0], 'interpreters': interpreters,
        'model_files_sha256': model, 'parent_path': '/usr/bin:/bin',
        'production_scope_inventory_sha256': hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest()}


def evidence_files(context: dict) -> dict:
    root = Path(context['case_root'])
    runtime = Path(context['project']) / 'private/phase8_3_h4e_real'
    paths = [root / name for name in ('context.json', 'release.sha256', 'approval.json', 'worker.log',
        'worker-result.json', 'fixture.log', 'fixture-identity.json', 'parent-identity.json', 'supervisor.json',
        'verification.json', 'verify.log', 'outer-policy.sb')]
    paths += list((root / 'provenance').rglob('*')) + list((root / 'fixture').rglob('*'))
    paths += list((root / 'controller').glob('*.json'))
    if runtime.exists():
        for name in ('runs', 'logs', 'observer', 'recovery'):
            paths += list((runtime / name).rglob('*'))
        paths += list(runtime.glob('*.json'))
    result = {}
    for file in sorted(set(paths)):
        c.safe_path(file)
        if file.is_file():
            info = file.stat()
            if info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise c.H4EBlocked('rehearsal evidence is not private')
            result[str(file.relative_to(root))] = digest(file)
    return result


def verify_receipt(path: Path | None, *, source_sha: str, manifest: Path) -> dict:
    if path is None:
        raise c.H4EBlocked('complete system rehearsal receipt required')
    c.safe_path(path)
    if (not path.is_file() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077
            or path.stat().st_size > 4_000_000):
        raise c.H4EBlocked('private rehearsal receipt unavailable')
    report = json.loads(path.read_text())
    if (report.get('schema') != 'local-system-one/h4e-parity-receipt-v1'
            or report.get('status') != 'SYSTEM_REHEARSAL_PASS' or report.get('candidate_source_clean') is not True
            or report.get('candidate_source_sha') != source_sha
            or report.get('candidate_manifest_sha256') != digest(manifest)
            or report.get('differences') != DIFFERENCES or report.get('real_provider_requests') != 0
            or report.get('real_execution_authorized') is not False
            or type(report.get('created_at_unix')) not in (int, float)
            or not 0 <= time.time() - report['created_at_unix'] <= 86400):
        raise c.H4EBlocked('rehearsal receipt is stale, mismatched or incomplete')
    if report.get('environment') != environment_fingerprint():
        raise c.H4EBlocked('execution dependency or host environment drift')
    from phase8_3_h4e_rehearsal import CASES, reverify
    cases = report.get('scenarios')
    if (not isinstance(cases, list) or len(cases) != len(CASES)
            or [row.get('verification', {}).get('scenario') for row in cases] != list(CASES)):
        raise c.H4EBlocked('rehearsal fault matrix is incomplete')
    suite = c.safe_path(Path(report['suite_root']))
    if (suite.parent != Path('/private/tmp') or not re.fullmatch(r'h4e-parity-[a-z0-9_-]+', suite.name)
            or suite.stat().st_uid != os.getuid() or suite.stat().st_mode & 0o077):
        raise c.H4EBlocked('actual parent qualification data root is unsafe')
    qualification = report.get('actual_parent_policy', {})
    policy_file, log_file = c.safe_path(suite / 'actual-parent/policy.sb'), c.safe_path(suite / 'actual-parent/qualification.log')
    from phase8_3_h4e_controller import parent_policy
    first = json.loads(c.safe_path(Path(cases[0]['context'])).read_text())
    policy = parent_policy(manifest=suite / 'candidate.sha256', archive=Path(first['archive']), approval=None,
                           control_root=suite / 'actual-parent')
    if (digest(suite / 'candidate.sha256') != digest(manifest)
            or qualification.get('kernel_denied') != dict.fromkeys(('wan_tcp_v4', 'wan_tcp_v6', 'wan_udp', 'unlisted_loopback'), 1)
            or qualification.get('real_home_or_credential_contents_read') is not False
            or qualification.get('policy_bytes') != len(policy.encode())
            or qualification.get('policy_sha256') != hashlib.sha256(policy.encode()).hexdigest()
            or digest(policy_file) != qualification['policy_sha256']
            or digest(log_file) != qualification.get('kernel_log_sha256')):
        raise c.H4EBlocked('actual owner parent policy qualification changed or is missing')
    proofs = [json.loads(line[len('H4E_KERNEL_PROOF '):]) for line in log_file.read_text().splitlines()
              if line.startswith('H4E_KERNEL_PROOF ')]
    if proofs != [{'role': 'actual_parent', 'denied': qualification['kernel_denied']}]:
        raise c.H4EBlocked('actual parent kernel proof is missing or ambiguous')
    import phase8_3_h4e_runner as runner
    if runner.CONTROLLER is not None:
        current = runner.CONTROLLER.actual_parent_kernel()
    else:
        from phase8_3_h4e_rehearsal import qualify_actual_parent_policy
        with tempfile.TemporaryDirectory(prefix='h4e-parent-recheck-', dir='/private/tmp') as directory:
            current = qualify_actual_parent_policy(Path(directory), Path(first['archive']), manifest)
    if current.get('kernel_denied') != qualification['kernel_denied']:
        raise c.H4EBlocked('actual parent kernel enforcement changed')
    for row in cases:
        context_path = c.safe_path(Path(row['context']))
        context = json.loads(context_path.read_text())
        if (context.get('candidate_source_sha') != source_sha
                or context.get('manifest_sha256') != digest(manifest)
                or evidence_files(context) != row.get('evidence_sha256')):
            raise c.H4EBlocked('rehearsal original evidence changed')
        # Recompute the native/HMAC/model/budget/recovery verdict; a PASS label is insufficient.
        import phase8_3_h4e_runner as runner
        verdict = (runner.CONTROLLER.reverify(context_path) if runner.CONTROLLER is not None
                   else reverify(context_path, source_manifest=manifest))
        if verdict != row['verification']:
            raise c.H4EBlocked('rehearsal independent verdict changed')
    return {'status': 'SYSTEM_REHEARSAL_VERIFIED', 'scenario_count': len(cases),
            'actual_parent_offline_policy_kernel_reverified': True,
            'receipt_sha256': digest(path), 'real_execution_authorized': False,
            'readiness': 'ELIGIBLE_FOR_OWNER_AND_INDEPENDENT_REVIEW_ONLY'}
