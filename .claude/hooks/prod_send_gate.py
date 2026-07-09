#!/usr/bin/env python3
"""Issue #1148 — Gate: Prod-Send-Deny (Baustein C aus #1147).

PreToolUse:Bash-Hook: verhindert, dass ein Bash-Kommando aus einer
Claude-Session einen echten Mail-Versand gegen das Produktivsystem
ausloest — weder ueber Prod-Send-Endpoints (Python-Port 8000, Go-Port
8090, `gregor20.henemm.com` ohne `staging.`-Praefix) noch ueber eine
direkte SMTP-Verbindung zu `smtp.resend.com`. Staging und reine
GET-/Lese-Kommandos bleiben unbeeinflusst.

Blockregel Send-Pfad (alle drei Bedingungen zusammen):
  1. Send-Trigger-Pfad im Kommando (`.../send` oder Scheduler-Batch-Route)
  2. Prod-Ziel im Kommando (Port 8000/8090 oder gregor20.henemm.com)
  3. Kommando ist NICHT beweisbar GET (POST-Indikator vorhanden)

Blockregel SMTP (unabhaengig davon): `smtp.resend.com` UND ein
Verbindungs-Indikator (reine Textsuche/grep bleibt erlaubt).

Obfuskations-Fallback: da alle Checks per regex.search() auf dem
kompletten rohen Kommando-String arbeiten (kein Tokenizing), wird ein
in `sh -c "..."`/`eval "..."` verstecktes Kommando automatisch mit
erfasst.

Override: `.claude/user_override_token.json` (v2-Format), TTL 1h,
Verbrauch pro abgewendetem Block-Treffer — siehe
docs/specs/modules/gate_1148_prod_send_deny.md.

Exit-Codes: 0 = erlaubt, 2 = blockiert.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import hook_utils

_SEND_PATH_PATTERNS = [
    re.compile(r"/send\b"),
    re.compile(r"/api/scheduler/(?:trip-reports|alert-checks|radar-alert-checks)\b"),
]

_PROD_TARGET_PATTERNS = [
    re.compile(r":8000\b"),
    re.compile(r":8090\b"),
    re.compile(r"(?<!staging\.)gregor20\.henemm\.com"),
]

_POST_INDICATOR_PATTERNS = [
    re.compile(r"-X\s*POST", re.IGNORECASE),
    re.compile(r"--request[\s=]+POST", re.IGNORECASE),  # F001: curl-Alias zu -X POST
    # F002 (curl -F/--form, Multipart) ist NICHT hier -- siehe
    # _has_form_post_indicator(): toolunabhaengiger -F-Scan blockte
    # faelschlich grep -F/awk -F/tail -F (F009, Adversary-Fix-Runde 2).
    re.compile(r"--json\b"),  # F003: curl --json (impliziert POST)
    re.compile(r"--data-raw"),
    re.compile(r"--data-binary"),
    re.compile(r"--data\b"),
    re.compile(r"-d\s"),
    re.compile(r"\bhttp\s+POST\b"),
    re.compile(r"wget\s+--post-data"),
    re.compile(r"--method[\s=]+POST", re.IGNORECASE),  # F004: wget --method=POST
    re.compile(r"requests\.post\("),
]

_SMTP_HOST = "smtp.resend.com"
_SMTP_CONNECTION_INDICATORS = [
    re.compile(r"openssl\s+s_client"),
    re.compile(r"\bswaks\b"),
    re.compile(r"\bnc\s"),
    re.compile(r"\bncat\b"),  # F005
    re.compile(r"\bsocat\b"),  # F005
    re.compile(r"\btelnet\b"),
    re.compile(r"\bpython3?\s+-c\b"),
    re.compile(r"\bsmtplib\b"),
    re.compile(r"curl\s+smtp://"),
]

_TOKEN_TTL = timedelta(hours=1)

# F006: Flags, deren Argument Freitext ist (Issue-/PR-Kommentar, Commit-
# Message, Titel) — nie ein tatsaechlich ausgefuehrtes Kommando. Identisches
# Muster wie SECRETS_FREETEXT_FLAGS in bash_gate.py (Plugin).
_FREETEXT_FLAGS = {"-m", "--message", "--body", "--title", "-F", "--form"}
_FREETEXT_LEADING_COMMANDS = {"gh", "git"}
_NESTED_SHELL_RE = re.compile(r"\b(?:ba|z|da|k)?sh\s+-c\b|\beval\b")
_COMMAND_SUBSTITUTION_RE = re.compile(r"\$\(|`")
# F007 (Adversary-Fix-Runde 2): Shell-Metazeichen ausserhalb von Quotes
# verketten weitere, tatsaechlich ausgefuehrte Kommandos an einen
# Freitext-Wert -- die gh/git-Freitext-Ausnahme darf dann nicht greifen.
_SHELL_METACHAR_RE = re.compile(r"[;&|\n]")

# F008 (Adversary-Fix-Runde 2): ${IFS}/$IFS ist Bashs Standard-Feldtrenner
# und expandiert zur Laufzeit zu Leerzeichen -- fuer den Python-Regex-Scan
# aber nicht. Alle \s-verankerten Indikator-Regexe wuerden dadurch
# umgangen, obwohl Host/Port/Pfad literal sichtbar bleiben. Deshalb wird
# JEDE ${IFS}-Variante vor jedem weiteren Scan durch ein echtes Leerzeichen
# ersetzt (deckt ${IFS}, ${IFS%??}, $IFS, $IFS$9 ab).
_IFS_OBFUSCATION_RE = re.compile(r"\$\{IFS[^}]*\}|\$IFS(?:\$\d+)?")

# F009 (Adversary-Fix-Runde 2): -F/--form ist nur bei curl/wget ein
# POST-Indikator (Multipart-Upload) -- bei grep/awk/tail/strings ist es ein
# harmloses, toolspezifisches Flag (Fixed-String-Suche, Feldtrenner,
# Follow-Retry) ohne jeden HTTP-Bezug.
_FORM_FLAG_RE = re.compile(r"(?<![\w-])-F(?![\w-])|--form\b")
_FORM_FLAG_TOOLS = {"curl", "wget"}

# F010 (Adversary-Fix-Runde 3): Backslash-Newline-Zeilenfortsetzung ist
# Standard-Bash-Syntax und wird beim Parsen komplett entfernt -- ein
# `\s`-verankertes Indikator-Pattern (z.B. `-X\s*POST`) sieht dadurch den
# Backslash als Nicht-Whitespace-Zeichen und matched nicht, obwohl Bash das
# Kommando real zusammenhaengend ausfuehrt.
_LINE_CONTINUATION_RE = re.compile(r"\\\r?\n")

# F012 (Adversary-Fix-Runde 3): alltaegliche Kommando-Praefixe veraendern
# das shlex-fuehrende Token, ohne dass sich am tatsaechlich ausgefuehrten
# Tool etwas aendert -- muessen bei der Fuehrungstoken-Bestimmung
# uebersprungen werden (Wrapper-Namen sowie `VAR=wert`-Zuweisungen).
_WRAPPER_PREFIX_TOKENS = {
    "sudo", "env", "command", "nice", "nohup", "time", "stdbuf",
    "timeout", "doas",
}
_ENV_ASSIGNMENT_RE = re.compile(r"^\w+=")


def _is_send_endpoint_path(command: str) -> bool:
    return any(p.search(command) for p in _SEND_PATH_PATTERNS)


def _targets_prod(command: str) -> bool:
    return any(p.search(command) for p in _PROD_TARGET_PATTERNS)


def _leading_token(command: str) -> str:
    """Liefert das tatsaechlich ausgefuehrte fuehrende Kommando-Token, oder
    "" wenn nicht sicher bestimmbar (nicht parsbares Quoting, leeres
    Kommando, oder nur Wrapper-/Zuweisungs-Token ohne folgendes Kommando).

    F012: ueberspringt Wrapper-Praefixe (`sudo`, `env`, ...) und
    Umgebungsvariablen-Zuweisungen (`VAR=wert`), da diese das erste Token
    veraendern, ohne dass sich am tatsaechlich ausgefuehrten Tool etwas
    aendert. Wendet zusaetzlich `Path(...).name` an, damit Absolutpfade
    (`/usr/bin/curl`) auf den reinen Toolnamen abgebildet werden.
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return ""
    for tok in tokens:
        if _ENV_ASSIGNMENT_RE.match(tok):
            continue
        base = Path(tok).name
        if base in _WRAPPER_PREFIX_TOKENS:
            continue
        return base
    return ""


def _has_form_post_indicator(command: str) -> bool:
    """F009: -F/--form zaehlt nur als POST-Indikator, wenn das fuehrende
    Kommando-Token curl oder wget ist. Fail-closed: bei verschachtelter
    Shell oder nicht bestimmbarem fuehrenden Token wird trotzdem geblockt,
    da sich das ausfuehrende Tool dann nicht sicher ausschliessen laesst.
    """
    if not _FORM_FLAG_RE.search(command):
        return False
    if _NESTED_SHELL_RE.search(command):
        return True
    leading = _leading_token(command)
    if not leading:
        return True
    return leading in _FORM_FLAG_TOOLS


def _is_provably_get(command: str) -> bool:
    """True wenn kein POST-Indikator vorkommt — Kommando gilt dann als GET."""
    if any(p.search(command) for p in _POST_INDICATOR_PATTERNS):
        return False
    if _has_form_post_indicator(command):
        return False
    return True


def _is_smtp_connection(command: str) -> bool:
    if _SMTP_HOST not in command:
        return False
    return any(p.search(command) for p in _SMTP_CONNECTION_INDICATORS)


def _is_blocked_send(command: str) -> bool:
    return (
        _is_send_endpoint_path(command)
        and _targets_prod(command)
        and not _is_provably_get(command)
    )


def _normalize_line_continuation(command: str) -> str:
    """Entfernt Backslash-Newline-Zeilenfortsetzungen (F010/F013) VOR jedem
    weiteren Scan. Bash entfernt `\\<Newline>` beim Parsen VOLLSTAENDIG
    (kein Ersatz-Whitespace) und fuehrt das Kommando zusammenhaengend aus
    -- ein eingefuegtes Leerzeichen wuerde ein Keyword, in dessen Mitte der
    Umbruch liegt (`--fo`+NL+`rm`, `PO`+NL+`ST`, `-`+NL+`F`, `s_cli`+NL+
    `ent`), faelschlich in zwei Woerter zerreissen und die zusammen-
    haengenden Indikator-Regexe verfehlen lassen (F013). Diese Entfernung
    macht nur den literalen Regex-Scan hier wieder treffsicher, sie
    veraendert nicht, was die Shell tatsaechlich ausfuehren wuerde. Ein
    echter Newline OHNE vorangehenden Backslash (Kommando-Verkettung)
    bleibt unveraendert und wird weiterhin von `_SHELL_METACHAR_RE`
    erfasst."""
    return _LINE_CONTINUATION_RE.sub("", command)


def _normalize_ifs(command: str) -> str:
    """Ersetzt bash-typische ${IFS}-Obfuskationsvarianten durch ein echtes
    Leerzeichen (F008). Bash expandiert ${IFS} zur Laufzeit selbst zu
    Leerzeichen -- diese Ersetzung macht also nur den literalen
    Regex-Scan hier wieder treffsicher, sie veraendert nicht, was die
    Shell tatsaechlich ausfuehren wuerde."""
    return _IFS_OBFUSCATION_RE.sub(" ", command)


def _sanitize_freetext(command: str) -> str:
    """Entfernt Freitext-Flag-Werte (`--body`/`-m`/`--message`/`--title`/
    `-F`/`--form`) aus dem Scan-String, wenn das fuehrende Kommando-Token
    `gh` oder `git` ist — ein woertliches Zitat eines Block-Beispiels in
    einem Issue-/PR-Kommentar ist kein echter Send-Trigger (F006).

    Fail-closed: gibt das unveraenderte Roh-Kommando zurueck, sobald die
    Ausnahme nicht sicher anwendbar ist -- bei verschachtelter Shell
    (`sh -c`/`eval`), bei Shell-Metazeichen (`&&`/`;`/`|`/Newline), die ein
    an den Freitext-Wert angehaengtes, tatsaechlich ausgefuehrtes
    Folgekommando verketten koennten (F007), bei nicht parsbarem Quoting,
    oder wenn der Freitext-Wert selbst Command-Substitution
    (`$(`/Backtick) enthaelt, die von der Shell tatsaechlich ausgefuehrt
    wuerde. Der seltene False-Positive (legitimer gh/git-Freitext mit
    `;`/`&`) wird bewusst in Kauf genommen -- ein umgangener
    CRITICAL-Send-Trigger waere die schlechtere Alternative.
    """
    if _NESTED_SHELL_RE.search(command):
        return command
    if _SHELL_METACHAR_RE.search(command):
        return command
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return command
    if not tokens or tokens[0] not in _FREETEXT_LEADING_COMMANDS:
        return command

    sanitized: list[str] = []
    skip_next = False
    changed = False
    for tok in tokens:
        if skip_next:
            skip_next = False
            if _COMMAND_SUBSTITUTION_RE.search(tok):
                return command
            changed = True
            continue
        matched_attached = False
        for flag in _FREETEXT_FLAGS:
            if flag.startswith("--") and tok.startswith(flag + "="):
                value = tok[len(flag) + 1:]
                if _COMMAND_SUBSTITUTION_RE.search(value):
                    return command
                changed = True
                matched_attached = True
                break
        if matched_attached:
            continue
        if tok in _FREETEXT_FLAGS:
            skip_next = True
            changed = True
            continue
        sanitized.append(tok)
    if not changed:
        return command
    return " ".join(sanitized)


def _project_root() -> Path:
    root = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if root:
        return Path(root)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return Path.cwd()


def _active_workflow_name() -> str:
    return (
        os.environ.get("GZ_ACTIVE_WORKFLOW", "").strip()
        or os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "").strip()
    )


def _consume_token(token_path: Path, data: dict, workflow_name: str) -> None:
    tokens = data.get("tokens", {})
    tokens.pop(workflow_name, None)
    data["tokens"] = tokens
    fd, tmp_name = tempfile.mkstemp(
        dir=str(token_path.parent), prefix=".user_override_token_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh)
        os.rename(tmp_name, token_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def _has_valid_override(workflow_name: str) -> bool:
    """Prueft ein gueltiges, nicht abgelaufenes Token fuer workflow_name.

    Seiteneffekt bei Gueltigkeit: der Token-Eintrag wird sofort verbraucht
    (atomar aus der Datei entfernt) — der Aufruf ist damit einmalig.
    """
    if not workflow_name:
        return False
    token_path = _project_root() / ".claude" / "user_override_token.json"
    if not token_path.exists():
        return False
    try:
        data = json.loads(token_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    tokens = data.get("tokens", {}) if isinstance(data, dict) else {}
    entry = tokens.get(workflow_name)
    if not isinstance(entry, dict):
        return False
    try:
        created = datetime.fromisoformat(entry.get("created", ""))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return False
    if datetime.now(timezone.utc) - created > _TOKEN_TTL:
        return False
    _consume_token(token_path, data, workflow_name)
    return True


def _block(reason: str) -> None:
    print("=" * 70, file=sys.stderr)
    print("BLOCKED - Prod-Send-Deny (#1148)", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(reason, file=sys.stderr)
    print(
        "Falls dieser Send-Trigger absichtlich gegen Prod laufen soll: "
        "tippe woertlich 'override' im Chat, um ein Einmal-Token zu erzeugen.",
        file=sys.stderr,
    )
    print("=" * 70, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        tool_input = hook_utils.get_tool_input()
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    except Exception:
        command = ""
    if not command:
        sys.exit(0)

    scan_command = _sanitize_freetext(
        _normalize_ifs(_normalize_line_continuation(command))
    )

    is_smtp = _is_smtp_connection(scan_command)
    is_send = _is_blocked_send(scan_command)
    if not (is_smtp or is_send):
        sys.exit(0)

    if _has_valid_override(_active_workflow_name()):
        sys.exit(0)

    if is_smtp:
        _block(
            "Direkte SMTP-Verbindung zu smtp.resend.com erkannt — "
            "echter Mail-Versand waere moeglich."
        )
    else:
        _block(
            "Prod-Send-Trigger erkannt (Send-Endpoint + Prod-Ziel + "
            "kein beweisbares GET)."
        )


if __name__ == "__main__":
    main()
