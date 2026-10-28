# GitHub publication security review — 2026-10-28

## Outcome and scope

No credential findings were detected in the reviewed current files or existing Git history. This is a scoped local audit, not a guarantee that every possible secret format is detectable. No GitHub repository/remote was created, no files were pushed, no history was rewritten, and no tunnel/runtime configuration, credentials, or browser storage were inspected or changed during this review.

The owner explicitly approved retaining their Git author name/email. Those identities remain public if the history is published. Current documentation uses portable path examples and omits actual profile hashes/tunnel identity fingerprints. **Earlier commits still contain historical machine paths and non-credential deployment fingerprints.** They are not API keys, but a normal full-history push will expose those old versions. A new cleanup commit or `.gitignore` does not remove older content. If those metadata should also be withheld, review a history-cleaning plan before publication; do not assume this review anonymized history.

## Checks performed

- Reviewed the screenshot's `.gitignore` requirements: `.env` variants, environments, bytecode, dependency directories and generated builds. Existing rules already covered most; added `node_modules/` plus local credential-store/config, private notes, captures, database/dump and profile exclusions. `.env.example` remains permitted but must pass content review.
- Audited Git's tracked/index file list and all existing history, including internal refs/reflogs. Supplementary inspection reads every local blob/commit/tag object, including orphan objects; ignored/untracked private files are outside the scan scope and are never published by a normal reviewed Git push.
- Used **Gitleaks 8.30.1**, downloaded from the [official release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) and checked against its published archive checksum. Scans run locally with the default rules explicitly enabled, full redaction, no suppression file, and no content uploads. History scan returned zero findings. A separate directory scan covers an export of the exact staged publication files, not the entire working folder.
- The reviewed publication set contains **63 tracked files**. The original five application commits were scanned, followed by the publication-review changes. No private captures, executable/environment files, credentials or local runtime configurations appeared in tracked history. The only JSON data files are the three synthetic fixtures.
- Added `scripts/audit_publication.py`: redacted location/category-only findings, actual staged bytes rather than edited working copies, forbidden-path guards, symlink rejection and optional all-object history inspection. It supplements Gitleaks, not replaces it.
- Preserved all three synthetic JSON fixtures required by regression tests. Local source URLs, imported catalogs, service/timetable caches, raw captures, environments, backups and executables remain untracked/ignored. No real Northwestern account credentials, cookies, session tokens or API keys were detected in the publication scope. Public route/stop identifiers in source are not authentication credentials.
- Reran **111 offline tests**, including the original 105 and six publication-audit regressions, plus the real local MCP smoke test (18 tools). No shuttle runtime logic, dependencies or MCP contracts were changed.

Scanner binaries, downloaded archives, reports and temporary test/export files are under ignored `.migration/`, not part of publication. No live key validation, account revocation or credential-store scanning was performed. The historical playbook mentions an earlier screenshot credential exposure; repository scans cannot establish that key's revocation. The owner should verify that prior rotation separately without sharing the key.

## Reproduce before publishing

From this repository, inspect exactly what will be published:

```powershell
git status --short
git diff --cached --stat
.\.venv\Scripts\python.exe scripts/audit_publication.py --staged
.\.venv\Scripts\python.exe scripts/audit_publication.py --history
.\.venv\Scripts\python.exe run_regressions.py
.\.venv\Scripts\python.exe test_tripshot_mcp_local.py
```

The Python guard uses only the standard library and Git. `--staged` checks actual index contents for added/modified files, so removing a key from the working file after staging cannot hide the staged value. `--history` also checks all stored objects; privacy warnings are reported separately from credential/path errors. Nonzero exit means review the reported location/category without printing the matched value. Newly untracked files must be deliberately reviewed and staged before the staged scan can cover them. Never force-add ignored data to make a scan pass.

Also run the maintained scanner (install a trusted release locally; its executable is not committed):

```powershell
New-Item -ItemType Directory -Path .migration -Force | Out-Null
$scanIgnore = Join-Path (Get-Location) '.migration/publication-empty-ignore'
[IO.File]::WriteAllText($scanIgnore, '')
gitleaks git . --config .gitleaks.toml --gitleaks-ignore-path $scanIgnore --log-opts="--all --reflog --full-history" --redact=100 --ignore-gitleaks-allow --no-banner
gitleaks git . --config .gitleaks.toml --gitleaks-ignore-path $scanIgnore --staged --redact=100 --ignore-gitleaks-allow --no-banner
```

Use the scanner's default rules without broad repository allowlists or a baseline that hides old findings. Keep any report in an ignored private directory. The review used an explicit default-rules config and empty ignore file so existing environment/repository suppression settings could not silently weaken coverage. Do not scan or upload ignored runtime/profile directories as part of routine publication review.

## Publication boundary

1. Review the staged file list and the intended public history. Keep the approved author attribution; decide separately whether old non-credential metadata are acceptable. No history cleanup is required by the current credential findings, and none was performed.
2. Publish only the reviewed Git branch when separately authorized. Do not upload the entire project directory, an Explorer-created ZIP, `.git`, `.venv`, `.migration`, ignored local data or private operator backups. `.gitignore` does not protect a manual bulk upload or a force-add.
3. Enable GitHub secret scanning/push protection where available before the first push. They supplement local review and should not be bypassed to publish a genuine finding. See [GitHub secret scanning](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning) and [preventing leaks](https://docs.github.com/en/code-security/tutorials/secure-your-organization/prevent-data-leaks).
4. If any real credential is found, stop publication, coordinate revocation/rotation, then assess removal from history. A revert/new commit alone leaves it in history. Follow [GitHub's sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository); rewriting changes commit IDs and needs a reviewed plan because baseline tests/runbooks currently refer to earlier commits.
5. Choose a license separately before distributing the project; this review does not grant third-party timetable/data rights or invent a project license. This is a publication decision, not a secret-scanning finding.

Operational deployment/cutover approval is separate from GitHub publication. Public runbook examples are templates: the operator must privately verify current profile settings and record backup integrity information at the time of any approved cutover. No deployed state is inferred from these historical documents.
