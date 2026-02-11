import argparse
import logging
import os

from .config import ConfigError, load_config
from .engine import run


DEFAULT_CONFIG_PATH = "/config/config.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description="MinIO file mover for Bots EDI")
    parser.add_argument(
        "--config",
        default=os.environ.get("MINIO_HELPER_CONFIG", DEFAULT_CONFIG_PATH),
        help="Path to config YAML (default: /config/config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("MINIO_HELPER_LOG_LEVEL", "INFO"),
        help="Log level (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        logging.getLogger("minio_helper").error("Config error: %s", exc)
        return 2
    except FileNotFoundError:
        logging.getLogger("minio_helper").error("Config file not found: %s", args.config)
        return 2

    return run(config, dict(os.environ))
