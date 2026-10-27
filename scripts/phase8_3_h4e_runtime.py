"""Owned local MLX runtime with a separately recorded, non-Provider warmup."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time

import phase8_3_h4e_contract as c
from phase8_3_h4e_source import digest
from phase8_3_h4d_readiness import MODEL_REV, MODEL_SHA


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, required=True)
    args = p.parse_args()
    if args.model.name != MODEL_REV or digest(args.model / 'model.safetensors') != MODEL_SHA:
        raise c.H4EBlocked('pinned local model required')
    package = c.ROOT / 'local_system_one'
    spec = importlib.util.spec_from_file_location('local_system_one', package / '__init__.py',
                                                submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules['local_system_one'] = module
    spec.loader.exec_module(module)
    from local_system_one.engine import DecisionEngine
    from local_system_one.health import ANEHealthGate
    from local_system_one.router import DecisionRouter
    from local_system_one.service import create_server
    from local_system_one.runtime.mlx import MLXRuntime
    os.umask(0o077)
    evidence = (c.PRIVATE / 'logs/model.private.jsonl').open('x', buffering=1)
    lock = threading.Lock()
    def emit(kind):
        with lock:
            evidence.write(json.dumps({'kind': kind, 'monotonic': time.monotonic(),
                'implementation': 'local_system_one.runtime.mlx.MLXRuntime',
                'model_revision': MODEL_REV, 'weights_sha256': MODEL_SHA}) + '\n')
            evidence.flush(); os.fsync(evidence.fileno())
    model = MLXRuntime(args.model)
    model.predict({'task': 'Read a missing file', 'result': 'File not found'},
                  {'type': 'choice', 'instructions': 'Choose the completion state.',
                   'criteria': {'complete': 'done', 'verify': 'check evidence', 'continue': 'more work'}})
    emit('warmup_complete')
    original = model.predict
    def predict(*args, **kwargs):
        emit('inference_attempted')
        result = original(*args, **kwargs)
        emit('inference_completed')
        return result
    model.predict = predict
    engine = DecisionEngine(mlx=model, ane=None, router=DecisionRouter(), health=ANEHealthGate(available=False))
    with create_server(engine, host='127.0.0.1', port=18782) as server:
        server.serve_forever(poll_interval=.1)


if __name__ == '__main__':
    main()
