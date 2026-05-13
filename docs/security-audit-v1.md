# Security Audit — v0.1.0 baseline

Date: 2026-05-13
Scope: source tree at commit `bce2b35` (everything under `src/voice_notes/`).
Auditor: Claude Code agent under Michael Frostbutter direction.

This is a first-party audit. It covers application code only. Upstream
dependency CVEs are not enumerated; we rely on the dependency authors and
recommend a Dependabot or `pip-audit` run in CI.

## Summary

| Severity | Count | Status |
|---|---|---|
| Critical | 0 | — |
| High | 2 | 1 patched this pass, 1 documented (Phase 2) |
| Medium | 3 | 2 patched this pass, 1 documented |
| Low | 3 | 1 patched this pass, 2 noted |
| Informational | 7 | — |

No critical-severity issues. No remote code execution surface in application
code. All SQL queries use parameterized statements (one column-name footgun
hardened this pass). No eval, exec, subprocess, pickle, or `shell=True`.

## High

### H1 — API keys stored in plaintext SQLite
**Severity:** High
**Status:** Documented, scheduled for Phase 2.

OpenAI and Anthropic API keys saved via the setup wizard or Settings dialog
live in the `settings` table of the per-user SQLite DB. The DB file sits in
the OS-standard user-data directory, readable by anything running as the
same OS user.

**Why this is high:** anyone with read access to the user's account (other
local users with appropriate permissions, malware running as the user, a
backup that leaks) can extract the keys.

**Mitigations in place:**
- Keys never appear in stderr / logs (verified by grep).
- `QLineEdit.setEchoMode(Password)` hides them in the UI.
- Read precedence is env var first, then DB. Users on managed deployments
  can keep keys out of the DB entirely by setting `OPENAI_API_KEY` /
  `ANTHROPIC_API_KEY` in their environment.

**Recommendation:** migrate to the OS keystore via the `keyring` library
(macOS Keychain, Windows Credential Manager, Linux Secret Service). Fall
back to the SQLite path only if `keyring` raises. Track as Phase 2 issue.

### H2 — Internal LAN IP exposed in public repo
**Severity:** High (information disclosure, not exploitation)
**Status:** Patched this pass.

`core/ollama_parse.py` had `DEFAULT_BASE_URLS = ("http://localhost:11434",
"http://10.10.0.15:11434")`. The second URL is the McNasty homelab LXC IP
on the BWIT/Agenius internal LAN. Publishing internal infrastructure
topology in a public OSS repo is a leak.

**Fix this pass:** remove the LAN IP. Defaults now contain only
`http://localhost:11434`. Users wanting to reach a remote Ollama endpoint
configure it explicitly via Settings.

## Medium

### M1 — SQL column-name interpolation in `db_update`
**Severity:** Medium (footgun, no live vuln)
**Status:** Patched this pass.

```python
def db_update(item_id: int, fields: dict) -> dict | None:
    for col, val in fields.items():
        sets.append(f"{col} = ?")   # ← `col` is interpolated, not parameterized
        args.append(val)
```

Today, all callers pass hardcoded column names from a small set
(`item_type`, `title`, `body`, `priority`, `tags`, `status`). No live
SQL injection. But a future caller forwarding user input as a dict key
would inject SQL.

**Fix this pass:** add an explicit column allowlist. Unknown columns raise
`ValueError`.

### M2 — User-supplied .onnx files loaded by onnxruntime
**Severity:** Medium
**Status:** Documented + README warning added.

The "Custom model file" setting lets the user pick a `.onnx` or `.tflite`
file from disk. openWakeWord hands the file path to onnxruntime, which
parses and executes the graph. onnxruntime has had CVEs in the past
(e.g., CVE-2024-5187 unbounded memory consumption; older RCE-class
issues exist). A malicious `.onnx` could exploit a future runtime vuln.

**Mitigations:**
- Users only load files they choose via a file picker. No drive-by load.
- The README now warns: only use `.onnx` files you trained yourself or
  downloaded from openWakeWord's official model zoo.
- Keep `onnxruntime` updated.

### M3 — Dependency version ranges, no lockfile
**Severity:** Medium
**Status:** Documented.

`pyproject.toml` uses `>=` constraints. A compromised PyPI upload of any
transitive dep would be pulled on fresh install.

**Recommendation:** ship a lockfile (`uv.lock` or `pip-compile` output)
in the repo so end users get reproducible installs. Add `pip-audit` to
CI. Phase 2.

## Low

### L1 — WAV tempfile cleanup on crash
**Severity:** Low
**Status:** Documented (left as-is for v0.1).

`core/stt.py` writes the captured audio to a system tempfile via
`tempfile.NamedTemporaryFile(delete=False, suffix=".wav")`, then removes
it in `finally`. If the process crashes between write and remove, the
file lingers in `$TMPDIR` until the OS reaps temp.

OS-standard tempfile permissions (`0600` on Linux/macOS, ACL-restricted
on Windows) limit the impact to the owning user. Worth fixing eventually
by writing into the user-data dir we already manage.

### L2 — `print(...)` instead of `logging`
**Severity:** Low
**Status:** Documented.

Three `print(..., file=sys.stderr)` calls in `__main__.py` for early-init
failures (font load, theme apply, wizard). None include sensitive data.
Recommendation: switch to the `logging` module so log destinations and
levels are configurable. Phase 2.

### L3 — ElevenLabs `voice_id` interpolated into URL
**Severity:** Low
**Status:** Noted.

```python
f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
```

`voice_id` is selected from the response of ElevenLabs' own voice list
endpoint. Trusting an upstream API response slightly more than ideal.
A URL-quoted interpolation would be defense-in-depth.

## Informational (no action required)

- **I1 — No telemetry.** Zero outbound calls except: HF Hub download of
  the Whisper model on first run, openWakeWord model download on first
  Active Listening, user-configured Ollama / OpenAI / Anthropic /
  ElevenLabs requests.
- **I2 — Parameterized SQL.** All user-controlled values flow through
  `?` placeholders. Confirmed by `grep` across the source tree.
- **I3 — No code-execution surface.** No `eval`, `exec`, `os.system`,
  `subprocess`, `pickle.loads`, `shell=True`, or `__import__` of
  user-controlled names.
- **I4 — TLS verification on by default.** `requests` defaults are not
  overridden.
- **I5 — Download integrity.** Whisper model from HuggingFace Hub
  (HTTPS, signature-verified by `huggingface_hub`). openWakeWord models
  from GitHub Releases (HTTPS).
- **I6 — QSS injection-safe.** Theme renders via `string.Template.substitute`
  with a controlled token dict from `theme/tokens.py`. User input never
  enters the QSS string.
- **I7 — JSON-parsed LLM responses.** Parser response dicts are populated
  into `QLineEdit` / `QTextEdit` / `QComboBox` widgets that do not execute
  text content. Tags stored to DB as a JSON-encoded list. No deserialization
  beyond `json.loads`.

## Patches landed this pass

1. **H2 fix:** removed `10.10.0.15:11434` from `DEFAULT_BASE_URLS` in
   `core/ollama_parse.py`. Old comment referencing the McNasty box removed.
2. **M1 fix:** `db_update` validates `col` against an allowlist; unknown
   columns raise `ValueError`. Existing callers unaffected.
3. **M2 fix:** README "Custom wake words" section warns about loading
   only trusted `.onnx` files.
4. **L3 fix:** ElevenLabs `voice_id` is now URL-encoded before
   interpolation.

## Open follow-ups

- [ ] H1 — keyring-based API key storage. Issue to file.
- [ ] M3 — add `pip-audit` to CI and ship a lockfile. Issue to file.
- [ ] L1 — move WAV temp into the user-data dir.
- [ ] L2 — replace `print(..., file=sys.stderr)` with `logging`.

## Audit reproducibility

```bash
# Re-run the patterns this audit used:
rg -n 'eval|exec|os\.system|subprocess|pickle\.|shell=True|__import__' src/
rg -n 'execute\(|sqlite3' src/voice_notes/core/db.py
rg -n 'api_key|API_KEY|password|token|secret' src/
rg -n 'requests\.|httpx\.|urlopen|http://|https://' src/
rg -n 'tempfile|NamedTemporaryFile' src/
rg -n 'json\.loads' src/
rg -n 'al_model_path|VOICE_NOTES_DATA_DIR|onnx|tflite' src/
```
