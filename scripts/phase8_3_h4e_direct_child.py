"""One H4E native task under Seatbelt; no fallback, tool replay or SDK retry."""
from __future__ import annotations

import argparse
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import sys
import sqlite3
import stat
import threading
import time

import phase8_3_h4e_contract as contract
import phase8_3_h4b_direct_child as native
from phase8_3_h4e_sdk_guard import H4EStop, install_runtime_guards
from phase8_3_h4e_proxy import inherited_listener


def bind_native():
    native.PRIVATE = contract.PRIVATE
    native.CASE_ID = contract.CASE_ID
    native.CASE_DIR = contract.CASE
    native.TARGET_PREFIX = 'h4e_absent_'
    native.CUSTOM_TOOLSET = 'phase83-h4e-one-read-file-only'
    native.HERMES_INSTALL = contract.SOURCE


def install_once_tool_guard(target: Path, deadline: float) -> dict:
    native.install_readonly_tool_guard(target)
    from tools.registry import registry
    original = registry.dispatch
    state = {'tool_calls': 0, 'tool_violations': 0}
    lock = threading.Lock()

    def once(name, args, *extra, **kwargs):
        with lock:
            if (state['tool_calls'] or name != 'read_file' or not isinstance(args, dict)
                    or args.get('path') != str(target) or set(args) - {'path', 'offset', 'limit'}):
                state['tool_violations'] += 1
                raise H4EStop() from None
            try:
                contract.remaining(deadline)
            except contract.H4EBlocked:
                state['tool_violations'] += 1
                raise H4EStop() from None
            state['tool_calls'] += 1
        return original(name, args, *extra, **kwargs)

    registry.dispatch = once
    return state


def preflight_constructor(toolset: str) -> None:
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from hermes_cli.oneshot import _create_session_db_for_oneshot
    from run_agent import AIAgent
    runtime = resolve_runtime_provider(requested=contract.PROVIDER, target_model=contract.MODEL)
    store = _create_session_db_for_oneshot()
    agent = AIAgent(api_key=runtime['api_key'], base_url=runtime['base_url'], session_db=store,
                    provider=runtime['provider'], model=contract.MODEL,
                    api_mode=runtime.get('api_mode'), credential_pool=runtime.get('credential_pool'),
                    enabled_toolsets=[toolset], quiet_mode=True, platform='cli', fallback_model=None)
    agent.close()
    store.close()


def require_native_store() -> None:
    import hermes_state
    import hermes_cli.oneshot as oneshot
    if Path(hermes_state.__file__).resolve() != contract.SOURCE / 'hermes_state.py':
        raise H4EStop()
    fixed = native.TEST_HOME / 'state.db'
    original_check = hermes_state.preflight_db_writability
    def exact_file_check(path, *, db_label='state.db', directory_only=False):
        if path != fixed:
            return original_check(path, db_label=db_label, directory_only=directory_only)
        # Seatbelt grants the SQLite files, not arbitrary directory writes. Check
        # those files and an actual rollback-only writer lock instead of os.access(home).
        contract.safe_path(fixed)
        for file in (fixed, fixed.with_name('state.db-wal'), fixed.with_name('state.db-shm')):
            if file == fixed or file.exists() or file.is_symlink():
                info = file.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or info.st_mode & 0o077 or not os.access(file, os.R_OK | os.W_OK)):
                    raise H4EStop()
        with sqlite3.connect(f'file:{fixed}?mode=rw', uri=True, timeout=1) as db:
            db.execute('BEGIN IMMEDIATE'); db.rollback()
    hermes_state.preflight_db_writability = exact_file_check
    original = oneshot._create_session_db_for_oneshot
    def required():
        store = original()
        if store is None or store.db_path != fixed:
            raise H4EStop()
        return store
    oneshot._create_session_db_for_oneshot = required


def isolate_native_logs() -> None:
    import hermes_logging
    if Path(hermes_logging.__file__).resolve() != contract.SOURCE / 'hermes_logging.py':
        raise H4EStop()
    original = hermes_logging.setup_logging
    def setup(**kwargs):
        # Keep the official redacting formatter inside this one writable case.
        kwargs['hermes_home'] = contract.CASE
        return original(**kwargs)
    hermes_logging.setup_logging = setup


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-offline', action='store_true')
    mode.add_argument('--run-native', action='store_true')
    p.add_argument('--deadline-monotonic', type=float, required=True)
    p.add_argument('--provider-listener-fd', type=int)
    args = p.parse_args()
    bind_native()
    guard = None
    tools = {'tool_calls': 0, 'tool_violations': 0}
    start = time.monotonic()
    rc = 3
    listener_retained = False
    path = contract.CASE / ('offline_control.private.json' if args.check_offline else 'native_control.private.json')
    try:
        contract.remaining(args.deadline_monotonic)
        if args.run_native:
            if args.provider_listener_fd is None:
                raise H4EStop()
            with inherited_listener(os.dup(args.provider_listener_fd)):
                os.set_inheritable(args.provider_listener_fd, False)
            # The original inherited descriptor stays open until process exit.
            listener_retained = True
        if path.exists() or path.is_symlink():
            raise contract.H4EBlocked('child control evidence already exists')
        target, prompt = native.check_case()
        tools = install_once_tool_guard(target, args.deadline_monotonic)
        isolate_native_logs()
        proof = native.prepare_readonly_auth()
        guard = install_runtime_guards(args.deadline_monotonic, run_token=os.environ.get('H4E_RUN_TOKEN', ''))
        require_native_store()
        from hermes_cli.oneshot import run_oneshot, _validate_explicit_toolsets
        chosen, error = _validate_explicit_toolsets([native.CUSTOM_TOOLSET])
        if error is not None or chosen != [native.CUSTOM_TOOLSET]:
            raise H4EStop()
        if args.check_offline:
            preflight_constructor(native.CUSTOM_TOOLSET)
            import hermes_cli.oneshot as oneshot
            previous = oneshot._run_agent
            oneshot._run_agent = lambda *a, **k: ('H4E_OFFLINE', {'completed': True, 'failed': False})
            try:
                output = io.StringIO()
                with redirect_stdout(output):
                    rc = run_oneshot('SYNTHETIC_OFFLINE', model=contract.MODEL, provider=contract.PROVIDER,
                                     toolsets=[native.CUSTOM_TOOLSET], usage_file=None)
            finally:
                oneshot._run_agent = previous
            if rc != 0 or 'H4E_OFFLINE' not in output.getvalue() or guard.report()['sdk_create_attempts'] != 0:
                raise H4EStop()
            print(json.dumps({'status': 'H4E_NATIVE_PREFLIGHT_PASS', **proof,
                              'real_agent_constructed': True, 'real_agent_task_started': False,
                              'sdk_requests': 0, 'only_tool': 'read_file'}))
        else:
            rc = run_oneshot(prompt, model=contract.MODEL, provider=contract.PROVIDER,
                             toolsets=[native.CUSTOM_TOOLSET], usage_file=str(contract.CASE / 'usage.private.json'))
            time.sleep(min(3, max(0, args.deadline_monotonic - time.monotonic())))
            if guard.report()['stopped'] or tools['tool_calls'] != 1 or tools['tool_violations']:
                rc = 3
    except BaseException:
        rc = 3
        print(json.dumps({'status': 'H4E_CHILD_BLOCKED', 'credentials_printed': False}))
    finally:
        if contract.CASE.is_dir() and not path.exists() and not path.is_symlink():
            contract.write_new_json(path, {'case_id': contract.CASE_ID,
                'mode': 'offline_preflight' if args.check_offline else 'native',
                'started_monotonic': start, 'ended_monotonic': time.monotonic(),
                'deadline_monotonic': args.deadline_monotonic, 'exit_code': rc,
                'provider_listener_retained': listener_retained,
                'sdk': guard.report() if guard else None, **tools})
    raise SystemExit(rc if type(rc) is int else 3)


if __name__ == '__main__':
    main()
