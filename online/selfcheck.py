"""Probe installed wecom-cli generation, authorization, and wrapper coverage."""

import json
import subprocess

from . import wecom_cli

CURRENT_SERVICES = ("doc", "sheet", "smartsheet", "smartpage")


def wrapper_support(generation):
    if generation == "current":
        return {
            "documents": {"read": "supported", "write": "supported"},
            "sheets": {"read": "supported", "write": "supported"},
            "smartpages": {"create": "supported", "import": "supported", "structured_pages": "legacy-only"},
            "smartsheets": {"read": "supported", "write": "supported"},
        }
    if generation == "legacy":
        return {
            "documents": {"read": "unsupported", "write": "supported"},
            "sheets": {"read": "unsupported", "write": "supported"},
            "smartpages": "supported",
            "smartsheets": "supported",
        }
    return {
        "documents": "unknown",
        "sheets": "unknown",
        "smartpages": "unknown",
        "smartsheets": "unknown",
    }


def collect():
    version_text = _safe_text(wecom_cli.version)
    try:
        generation = wecom_cli.cli_generation(version_text)
    except ValueError:
        generation = "unknown"

    if generation == "unknown":
        auth = "not_checked"
    else:
        auth = _safe_text(lambda: wecom_cli.auth_status(cli_version=version_text))

    services = {}
    names = CURRENT_SERVICES if generation == "current" else (("doc",) if generation == "legacy" else ())
    for service in names:
        services[service] = "available" if _safe_available(service) else "unavailable"

    return {
        "version": version_text,
        "generation": generation,
        "auth_status": auth,
        "upgrade_recommended": generation == "legacy",
        "services": services,
        "python_wrappers": wrapper_support(generation),
    }


def _safe_text(func):
    try:
        return func()
    except (OSError, ValueError, subprocess.SubprocessError, wecom_cli.WecomCliError) as exc:
        return f"error: {exc}"


def _safe_available(service):
    try:
        return wecom_cli.service_available(service)
    except (OSError, subprocess.SubprocessError, wecom_cli.WecomCliError):
        return False


def main():
    print(json.dumps(collect(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
