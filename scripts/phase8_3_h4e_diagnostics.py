"""Bounded stage receipts: never serialize exception text, arguments or paths."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sys
import threading
import time

_events = []
_lock = threading.Lock()


def exception_record(exc):
    origin = None
    trace = exc.__traceback__
    while trace is not None:
        name = Path(trace.tb_frame.f_code.co_filename).name
        if re.fullmatch(r'phase8_3_h4[bcde]_[a-z_]+\.py', name):
            origin = {'module': name, 'line': trace.tb_lineno}
        trace = trace.tb_next
    error = type(exc).__name__
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', error):
        error = 'Exception'
    number = getattr(exc, 'errno', None)
    return {'exception_type': error, 'errno': number if type(number) is int else None,
            'origin': origin}


def emit(stage, operation, event, exc=None, *, result=None):
    if not all(re.fullmatch(r'[a-z_][a-z0-9_.]{0,79}', x) for x in (stage, operation, event)):
        raise ValueError('diagnostic identifiers must be fixed labels')
    row = {'schema': 'local-system-one/h4e-stage-v1', 'stage': stage,
           'operation': operation, 'event': event, 'monotonic': time.monotonic()}
    if result is not None:
        if type(result) is not int or not -1 <= result <= 65535:
            raise ValueError('diagnostic result must be a bounded system status')
        row['result'] = result
    if exc is not None:
        row.update(exception_record(exc))
    with _lock:
        _events.append(row)
        print('H4E_DIAGNOSTIC ' + json.dumps(row, sort_keys=True), file=sys.stderr, flush=True)


def records():
    with _lock:
        return list(_events)


@contextmanager
def stage(name, operation):
    emit(name, operation, 'started')
    try:
        yield
    except BaseException as exc:
        emit(name, operation, 'failed', exc)
        raise
    else:
        emit(name, operation, 'completed')
