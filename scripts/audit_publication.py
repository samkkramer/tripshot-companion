"""Offline publication guard: tracked files/index, optional ALL Git objects.

Never reads ignored/untracked files, remote credentials, tunnel profiles, or
browser state. Findings contain location/category only, never matched values.
This supplements a maintained secret scanner; it is not proof of zero secrets.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024
FIXTURES = {'data/example_ride.json', 'data/example_live.json', 'data/stop_names.example.json'}
RULES = {
    'openai-key': r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}',
    'github-token': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    'aws-access-key': r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'private-key': r'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
    'jwt': r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}',
    'bearer-token': r'(?i)\bbearer\s+[A-Za-z0-9._-]{20,}',
    'credential-literal': r'''(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|sessionid|session_token)\b["']?\s*[:=]\s*["']?([A-Za-z0-9_./+=:$-]{8,})''',
    'credential-url': r'''(?i)https?://[^\s"'<>`/]+:[^\s"'<>`/@]+@''',
}
PRIVACY = {
    'personal-machine-path': r'(?i)\b[A-Z]:[\\/]+Users[\\/]+(?!Public[\\/]|<|YOUR_)[A-Za-z0-9_.-]+[\\/]',
    'operational-fingerprint': r'(?i)(?:expectedProfileHash|expectedOriginalHash|profile.{0,20}SHA-?256|tunnel[- ]ID fingerprint)[^\r\n]{0,80}?[0-9a-f]{12,64}',
}


@dataclass(frozen=True)
class Finding:
    location: str
    line: int
    category: str
    object_id: str | None = None


def git(*args, root=ROOT):
    return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.PIPE)


def forbidden(path):
    p = Path(path)
    parts = [s.lower() for s in p.parts]
    name = p.name.lower()
    if path.startswith('data/') and path not in FIXTURES:
        return True
    return (any(x.startswith('.venv') or x in {'venv', 'node_modules', '__pycache__', '.migration',
                '.aws', '.ssh', '.azure', '.gcp', 'private', 'captures', 'exports'} for x in parts)
            or (name.startswith('.env') and name != '.env.example')
            or name in {'.npmrc', '.pypirc', '.netrc', '.git-credentials', 'tripshot-local.yaml', 'tripshot-local.yml',
                        'eta_before.json', 'eta_after.json', 'directions.txt', 'eta_comparison.txt'}
            or 'credentials' in name or 'secrets' in name
            or name.endswith(('.exe', '.dll', '.msi', '.pem', '.key', '.p12', '.pfx', '.har', '.pcap', '.dump', '.bak', '.log', '.db'))
            or '.sqlite' in name
            or '.bak.' in name or '.local.' in name or '.private.' in name)


def scan_text(text, location, object_id=None):
    findings = []
    privacy = []
    for category, pattern in RULES.items():
        for match in re.finditer(pattern, text):
            if category == 'credential-literal' and match.group(1).lower().startswith(('env:', 'file:')):
                continue
            findings.append(Finding(location, text.count('\n', 0, match.start()) + 1, category, object_id))
    for category, pattern in PRIVACY.items():
        for match in re.finditer(pattern, text):
            privacy.append(Finding(location, text.count('\n', 0, match.start()) + 1, category, object_id))
    return findings, privacy


def decode(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    if b'\0' in raw:
        raise UnicodeError('Unexpected binary content')
    return raw.decode('utf-8-sig')


def audit(root=ROOT, *, staged=False, history=False):
    root = Path(root).resolve()
    findings, privacy = [], []
    records = git('ls-files', '--stage', '-z', root=root).decode('utf-8').split('\0')
    modes = {}
    for record in records:
        if not record:continue
        header, path = record.split('\t', 1)
        mode, _, stage = header.split()
        modes[path] = mode
        if stage != '0':findings.append(Finding(path, 0, 'unmerged-index-entry'))
    paths = list(modes)
    if staged:
        changed = set(git('diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z', root=root).decode('utf-8').split('\0'))
        paths = [p for p in paths if p in changed]
    scanned = 0

    def inspect(raw, path, oid=None):
        nonlocal scanned
        scanned += 1
        if len(raw) > MAX_BYTES:
            findings.append(Finding(path, 0, 'oversized-content-needs-review', oid)); return
        try:
            text = decode(raw)
        except UnicodeError:
            findings.append(Finding(path, 0, 'binary-or-encoding-needs-review', oid)); return
        f, p = scan_text(text, path, oid)
        findings.extend(f); privacy.extend(p)

    for path in paths:
        if modes[path] == '120000':
            findings.append(Finding(path, 0, 'symlink-needs-publication-review'))
            continue
        if forbidden(path):
            findings.append(Finding(path, 0, 'private-or-generated-path'))
            continue
        if staged:
            inspect(git('show', ':' + path, root=root), path)
        else:
            target = root / path
            if target.is_symlink() or not target.resolve().is_relative_to(root):
                findings.append(Finding(path, 0, 'symlink-outside-publication-scope')); continue
            if not target.is_file():
                findings.append(Finding(path, 0, 'missing-tracked-file')); continue
            inspect(target.read_bytes(), path)

    counts = Counter()
    if history:
        # Includes internal refs/reflogs and orphan objects, not just HEAD additions.
        names = {}
        for line in git('rev-list', '--objects', '--all', '--reflog', root=root).decode('utf-8').splitlines():
            oid, _, path = line.partition(' ')
            if path:
                names.setdefault(oid, path)
                if forbidden(path):findings.append(Finding(path, 0, 'historical-private-path', oid))
        objects = git('cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype) %(objectsize)', root=root)
        for line in objects.decode('ascii').splitlines():
            oid, kind, size = line.split()
            counts[kind] += 1
            if kind not in ('blob', 'commit', 'tag'):continue
            path = names.get(oid, '<' + kind + '>')
            if int(size) > MAX_BYTES:
                findings.append(Finding(path, 0, 'oversized-git-object-needs-review', oid)); continue
            inspect(git('cat-file', kind, oid, root=root), path, oid)
    return {'tracked_files_checked': len(paths), 'content_units_checked': scanned,
            'git_objects': dict(counts), 'findings': [asdict(f) for f in findings],
            'privacy_warnings': [asdict(f) for f in privacy]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true', help='Inspect actual index bytes for changed files')
    parser.add_argument('--history', action='store_true', help='Also inspect all local Git objects, including orphan objects')
    args = parser.parse_args()
    report = audit(staged=args.staged, history=args.history)
    print(json.dumps(report, indent=2))
    return 1 if report['findings'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
