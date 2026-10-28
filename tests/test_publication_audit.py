"""Offline publication safeguards; all fake credentials are generated at runtime."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.audit_publication import audit, forbidden, scan_text


class PublicationAuditTests(unittest.TestCase):
    def test_screenshot_and_private_paths_are_blocked(self):
        for path in ('node_modules/pkg/index.js', '.env', '.env.production', '.venv/Scripts/python.exe',
                     'data/sources.local.json', 'data/live_response.json', 'server.py.pre_v10.bak',
                     '.ssh/id_rsa', '.git-credentials', 'captures/request.har', 'notes.private.md'):
            self.assertTrue(forbidden(path), path)
        for path in ('server.py', '.env.example', 'data/example_live.json', 'data/example_ride.json',
                     'data/stop_names.example.json'):
            self.assertFalse(forbidden(path), path)

    def test_detection_never_includes_match_values(self):
        fake = 'sk-' + 'proj-' + 'Ab3X' * 12
        findings, _ = scan_text('api_key = "' + fake + '"', 'fixture.py')
        self.assertTrue(findings)
        self.assertNotIn(fake, str(findings))
        self.assertTrue(any(f.category == 'openai-key' for f in findings))

    def test_references_and_synthetic_fixtures_remain_allowed(self):
        findings, _ = scan_text('api_key: "env:CONTROL_PLANE_API_KEY"\npassword: "file:/private/value"', 'fixture')
        self.assertEqual(findings, [])

    def test_staged_scan_uses_index_even_if_worktree_is_cleaned(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            def run(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.PIPE)
            run('init', '--quiet')
            fake = 'gh' + 'p_' + 'Ab3X' * 10
            (root / 'app.py').write_text('token = "' + fake + '"', encoding='utf-8')
            run('add', '--', 'app.py')
            (root / 'app.py').write_text('value = 1', encoding='utf-8')
            self.assertTrue(audit(root, staged=True)['findings'])
            self.assertFalse(audit(root)['findings'])

    def test_orphan_git_blob_is_scanned_without_printing_secret(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.check_call(['git', 'init', '--quiet'], cwd=root)
            fake = 'AK' + 'IA' + 'B7' * 8
            subprocess.run(['git', 'hash-object', '-w', '--stdin'], input=fake.encode(), cwd=root,
                           stdout=subprocess.PIPE, check=True)
            report = audit(root, history=True)
            self.assertTrue(any(f['category'] == 'aws-access-key' for f in report['findings']))
            self.assertNotIn(fake, str(report))

    def test_staged_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.check_call(['git', 'init', '--quiet'], cwd=root)
            blob = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'],
                                           input=b'/outside/scope', cwd=root).decode().strip()
            subprocess.check_call(['git', 'update-index', '--add', '--cacheinfo',
                                   '120000,' + blob + ',external'], cwd=root)
            self.assertTrue(any(f['category'] == 'symlink-needs-publication-review'
                                for f in audit(root, staged=True)['findings']))
