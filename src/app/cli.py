import argparse
import os
import sys
import configparser
from typing import Optional

from src.app.core import send_mail
from src.app.debug import DebugBuffer

DEFAULT_CONFIG_PATH = "config.ini"

def load_config(path: str) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if os.path.exists(path):
        cfg.read(path, encoding="utf-8")
    return cfg

def resolve_option(cli: Optional[str], env_key: Optional[str],
                   cfg: configparser.ConfigParser, section: str,
                   option: str, default: Optional[str] = None) -> Optional[str]:
    if cli is not None:
        return cli
    if env_key and (val := os.getenv(env_key)) not in (None, ""): 
        return val
    if cfg.has_option(section, option):
        return cfg.get(section, option)
    return default

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="gregor-zwanzig", description="Gregor Zwanzig CLI")
    parser.add_argument("--report", choices=["evening", "morning", "alert"], help="Berichtstyp")
    parser.add_argument("--channel", choices=["email", "none"], help="Ausgabekanal")
    parser.add_argument("--dry-run", action="store_true", help="Kein Versand, nur Console")
    parser.add_argument("--config", default=None, help="Pfad zu Konfigurationsdatei (INI)")
    parser.add_argument("--debug", choices=["info", "verbose"], default=None, help="Console-Log-Level")

    args = parser.parse_args(argv)
    cfg_path = args.config or DEFAULT_CONFIG_PATH
    cfg = load_config(cfg_path)

    dbg = DebugBuffer()
    dbg.add(f"cfg.path: {cfg_path}")

    report = resolve_option(args.report, "GZ_REPORT", cfg, "run", "report", default="evening")
    channel = resolve_option(args.channel, "GZ_CHANNEL", cfg, "run", "channel", default="email")
    debug_level = resolve_option(args.debug, "GZ_DEBUG", cfg, "run", "debug", default="info")

    dbg.add(f"report: {report}")
    dbg.add(f"channel: {channel}")
    dbg.add(f"debug: {debug_level}")
    dbg.add(f"dry_run: {args.dry_run}")

    subject = f"GZ {report.title()} Report"
    body = "This is a placeholder report body.\n\n[DEBUG]\n" + dbg.email_subset()

    print(dbg.as_text())

    if channel == "email" and not args.dry_run:
        send_mail(subject, body)
        print("Email sent.")
    else:
        print("No email sent (channel != email or dry-run).")

    return 0

if __name__ == "__main__":
    sys.exit(main())
