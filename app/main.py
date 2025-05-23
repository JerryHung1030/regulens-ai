"""Entry point for the Regulens-AI application.

This provides a minimal command-line interface that mirrors a subset of the
planned GUI workflow. It loads API settings from ``config_default.yaml`` and
outputs the raw Markdown diff to ``stdout`` or a file.
"""

from pathlib import Path
import argparse
import sys
try:  # optional dependency
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback for minimal environments
    yaml = None

from .api_client import ApiClient
from .compare_manager import CompareManager, CompareError
from .export import to_pdf, to_txt
from .logger import logger


def _load_config(path: Path) -> dict:
    """Load configuration from YAML without requiring PyYAML."""
    text = path.read_text()
    if yaml is not None:
        return yaml.safe_load(text)
    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip().strip('"')
    return data


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Regulens-AI CLI")
    parser.add_argument("input", type=Path, help="input JSON file")
    parser.add_argument("reference", type=Path, help="reference JSON file")
    parser.add_argument("--txt", type=Path, help="export markdown result")
    parser.add_argument("--pdf", type=Path, help="export PDF result")
    args = parser.parse_args(argv)

    cfg = _load_config(Path("config_default.yaml"))
    client = ApiClient(cfg["base_url"], cfg["api_key"], timeout=cfg.get("timeout", 30))
    manager = CompareManager(client)

    logger.info("CLI compare %s vs %s", args.input, args.reference)
    try:
        resp = manager.compare(args.input, args.reference)
    except CompareError as exc:
        logger.error("CLI comparison failed: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    else:
        logger.info("CLI comparison succeeded")

    print(resp.result)
    if args.txt:
        logger.info("Exporting text to %s", args.txt)
        to_txt(resp.result, args.txt)
    if args.pdf:
        logger.info("Exporting PDF to %s", args.pdf)
        to_pdf(resp.result, args.pdf)


if __name__ == "__main__":
    main()
