"""Exercise wheel and sdist installs outside the checkout, without publishing.

Run with Python containing pip, build and twine. Each artifact gets a separate
venv; no editable install, dev extras, camera, model or dataset is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Executed with -I from an empty directory. This exercises the installed console
# entry point as well as the public API, not a pytest import from src/.
PROBE = r'''
import hashlib, importlib.metadata, importlib.util, json, subprocess, sys
from pathlib import Path
import visiontrack
from visiontrack.tracking.tracker import ByteTracker

root = Path(visiontrack.__file__).resolve().parent
assert root.is_relative_to(Path(sys.prefix).resolve()), root
assert importlib.metadata.version('visiontrack-mot') == visiontrack.__version__
for name in ('scipy', 'matplotlib', 'pandas', 'onnxruntime', 'pytest'):
    assert importlib.util.find_spec(name) is None, name
cli_name = 'visiontrack.exe' if sys.platform == 'win32' else 'visiontrack'
cli = Path(sys.executable).parent / cli_name
def command(*args, success=True):
    result = subprocess.run([str(cli), *map(str, args)],
                            capture_output=True, text=True, timeout=120)
    assert (result.returncode == 0) == success, (args, result.stdout, result.stderr)
    return result
def snapshot(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}

command('eval', '--json')
if sys.argv[1] == 'core':
    assert importlib.util.find_spec('PIL') is None
    print(json.dumps({'version': visiontrack.__version__, 'core_cli': 'passed'}))
    sys.exit()

from visiontrack.lab import build_initiation_trace, canonical_json
out = Path.cwd() / 'demo with spaces'
command('lab-demo', out, '--with-initiation')
assert not out.exists(), 'preview wrote files'
command('lab-demo', out, '--with-initiation', '--write')
browser = out / 'try-in-browser'
report_text = (browser / 'report.json').read_text()
report = json.loads(report_text)
bundle = out / report['experiment']['experiment_id']
assert (bundle / 'report/report.json').read_bytes() == (browser / 'report.json').read_bytes()
before = snapshot(out)
trace_text = (browser / 'initiation-trace.json').read_text()
trace = json.loads(trace_text)
assert trace_text == canonical_json(build_initiation_trace(
    bundle, variant='bytetrack', start=0, end=10)) + '\n'
assert command('lab-initiation', bundle, '--variant', 'bytetrack', '--start', 0,
               '--end', 10, '--json').stdout == trace_text
command('lab-initiation', bundle, '--variant', 'bytetrack', '--start', 0, '--end', 10)
command('lab-demo', out, '--with-initiation', '--write', success=False)
assert before == snapshot(out), 'read-only diagnosis or refusal mutated output'
assert [row['public_track_ids'] for row in trace['frames'][:3]] == [[], [], [1]]
assert len(trace['frames']) == 10
assert trace['run_id'] == next(v for v in report['variants'] if v['name'] == 'bytetrack')['run_id']
assert trace['accuracy_claim'] is False and trace['physical_identity_verified'] is False
hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in root.rglob('*.py')}
assert trace['producer']['implementation_sha256'] == hashes
assert 'Frame 2:' in (browser / 'START_HERE.txt').read_text()
print(json.dumps({'version': visiontrack.__version__, 'report_id': report['report_id'],
                 'trace_id': trace['trace_id'], 'implementation_sha256': hashes,
                 'installed_module': str(root), 'guided_demo_and_readonly_replay': 'passed'}))
'''


def run(args: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True, timeout=600)


def probe(python: Path, mode: str, *, cwd: Path, env: dict[str, str]) -> dict:
    result = subprocess.run([str(python), '-I', '-c', PROBE, mode], cwd=cwd, env=env,
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f'Installed {mode} probe failed:\n{result.stdout}\n{result.stderr}')
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='new directory for distributions, isolated installs and receipt')
    parser.add_argument('--dist-dir', type=Path,
                        help='check already built distributions instead of building them')
    parser.add_argument('--with-web-contract', action='store_true',
                        help='also run the existing Node initiation import contract per install')
    args = parser.parse_args()
    output = args.output.resolve()
    # Exclusive creation preserves previous evidence. Keep failed runs for inspection.
    output.mkdir()
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
        env.pop(key, None)
    dist = args.dist_dir.resolve() if args.dist_dir else output / 'dist'
    if not args.dist_dir:
        run([sys.executable, '-m', 'build', '--outdir', str(dist), str(ROOT)],
            cwd=output, env=env)
    wheels, sdists = sorted(dist.glob('*.whl')), sorted(dist.glob('*.tar.gz'))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError('require exactly one wheel and one .tar.gz sdist')
    run([sys.executable, '-m', 'twine', 'check', str(wheels[0]), str(sdists[0])],
        cwd=output, env=env)
    expected = {
        p.relative_to(ROOT / 'src/visiontrack').as_posix():
        hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / 'src/visiontrack').rglob('*.py')
    }
    results = []
    for kind, artifact in (('wheel', wheels[0]), ('sdist', sdists[0])):
        work = output / kind
        work.mkdir()
        environment = work / 'venv'
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        run([str(python), '-I', '-m', 'pip', 'install', '--no-cache-dir', str(artifact)],
            cwd=work, env=env)
        core = probe(python, 'core', cwd=work, env=env)
        run([str(python), '-I', '-m', 'pip', 'install', '--no-cache-dir', f'{artifact}[lab]'],
            cwd=work, env=env)
        run([str(python), '-I', '-m', 'pip', 'check'], cwd=work, env=env)
        result = probe(python, 'lab', cwd=work, env=env)
        if result['implementation_sha256'] != expected:
            raise ValueError(f'{kind} installed source differs from the current package source')
        if args.with_web_contract:
            run(['npm', 'run', 'test:initiation-workflow'], cwd=ROOT,
                env={**env, 'VISIONTRACK_PYTHON': str(python)})
        result.update(kind=kind, artifact=artifact.name,
                      artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                      core=core, web_contract=args.with_web_contract)
        results.append(result)
        print(f'{kind}: isolated core + Lab installation and initiation replay passed', flush=True)
    if results[0]['report_id'] != results[1]['report_id']:
        raise ValueError('wheel and sdist generated different reports')
    if results[0]['trace_id'] != results[1]['trace_id']:
        raise ValueError('wheel and sdist generated different traces')
    receipt = {'schema': 'visiontrack.installed-package-check/v1', 'publication_performed': False,
               'results': results}
    path = output / 'receipt.json'
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'Installed-package verification passed. Local receipt: {path}')


if __name__ == '__main__':
    main()
