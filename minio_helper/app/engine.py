import logging
import os
import posixpath
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, List, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Config, Defaults, Endpoint, MatchSpec, RenameSpec, Rule
from .fs_transport import FileItem, delete_file, list_files
from .s3_transport import S3Client
from .util import (
    atomic_write_from_temp,
    ensure_dir,
    join_rel_path,
    normalize_s3_prefix,
    resolve_file_path,
    split_rel_name,
    stage_copy_to_temp,
)

LOGGER = logging.getLogger("minio_helper")


@dataclass(frozen=True)
class SourceItem:
    src_type: str
    src_path: str
    rel_name: str


def run(config: Config, env: Dict[str, str]) -> int:
    stop_event = threading.Event()
    max_workers = min(4, len(config.rules)) or 1

    LOGGER.info("Starting run with %d rule(s)", len(config.rules))

    had_failure = False
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_rule, rule, config.defaults, env, stop_event): rule.name
            for rule in config.rules
        }
        for future in as_completed(futures):
            rule_name = futures[future]
            try:
                ok = future.result()
            except Exception:  # pylint: disable=broad-exception-caught
                LOGGER.exception("Rule '%s' raised an exception", rule_name)
                ok = False
            if not ok:
                had_failure = True
                if config.defaults.exit_on_first_failure:
                    stop_event.set()

    if had_failure:
        LOGGER.error("Run completed with failures")
        return 1

    LOGGER.info("Run completed successfully")
    return 0


def run_rule(rule: Rule, defaults: Defaults, env: Dict[str, str], stop_event: threading.Event) -> bool:
    logger = logging.getLogger(f"minio_helper.rule.{rule.name}")

    mode = rule.mode if rule.mode is not None else defaults.mode
    if mode not in {"move", "copy"}:
        logger.error("Rule '%s' has invalid mode: %s", rule.name, mode)
        return False

    retries = rule.retries if rule.retries is not None else defaults.retries
    wait_seconds = rule.wait_seconds if rule.wait_seconds is not None else defaults.wait_seconds

    if rule.max_items is not None:
        max_items = rule.max_items
    elif defaults.max_items is not None:
        max_items = defaults.max_items
    else:
        max_items = 100

    if max_items < 0:
        logger.error("Rule '%s' max_items must be >= 0", rule.name)
        return False

    logger.info("Starting rule '%s'", rule.name)

    try:
        s3_client = None
        if rule.src.type == "s3" or rule.dest.type == "s3":
            s3_client = _build_s3_client(env)

        candidates = list_candidates(rule, defaults, env, max_items, s3_client)
        if not candidates:
            logger.info("Rule '%s' has no matching items", rule.name)
            return True

        with tempfile.TemporaryDirectory(prefix=f"minio_helper_{rule.name}_") as tmp_dir:
            for item in candidates:
                if stop_event.is_set():
                    logger.info("Rule '%s' stopping due to stop signal", rule.name)
                    return True
                ok = process_item(
                    rule=rule,
                    defaults=defaults,
                    env=env,
                    item=item,
                    mode=mode,
                    retries=retries,
                    wait_seconds=wait_seconds,
                    tmp_dir=tmp_dir,
                    logger=logger,
                    s3_client=s3_client,
                )
                if not ok:
                    logger.error("Rule '%s' failed on item '%s'", rule.name, item.rel_name)
                    return False
    except Exception:
        logger.exception("Rule '%s' failed", rule.name)
        return False

    logger.info("Rule '%s' completed", rule.name)
    return True


def list_candidates(
    rule: Rule,
    defaults: Defaults,
    env: Dict[str, str],
    max_items: int,
    s3_client: Optional[S3Client],
) -> List[SourceItem]:
    if rule.src.type == "file":
        src_dir = resolve_file_path(rule.src.path, defaults.base_file_path)
        items = list_files(src_dir)
        filtered = _filter_file_items(items, rule.src.match)
        filtered.sort(key=lambda item: (item.mtime, item.name))
        limited = filtered[:max_items]
        return [SourceItem("file", item.path, item.name) for item in limited]

    if s3_client is None:
        s3_client = _build_s3_client(env)
    bucket = _resolve_bucket(rule.src, defaults, env)
    prefix = normalize_s3_prefix(rule.src.path)
    keys = s3_client.list_keys(bucket, prefix)
    rel_keys = []
    for key in keys:
        if key.endswith("/"):
            continue
        rel = key[len(prefix):] if prefix else key
        if not rel:
            continue
        if rule.src.match and not rule.src.match.matches(rel):
            continue
        rel_keys.append((key, rel))
    rel_keys.sort(key=lambda item: item[0])
    limited = rel_keys[:max_items]
    return [SourceItem("s3", key, rel) for key, rel in limited]


def process_item(
    *,
    rule: Rule,
    defaults: Defaults,
    env: Dict[str, str],
    item: SourceItem,
    mode: str,
    retries: int,
    wait_seconds: int,
    tmp_dir: str,
    logger: logging.Logger,
    s3_client: Optional[S3Client],
) -> bool:
    for attempt in range(retries + 1):
        try:
            temp_path = stage_source(rule, defaults, env, item, tmp_dir, s3_client)
            try:
                dest_ref = write_destination(rule, defaults, env, item, temp_path, s3_client)
                if mode == "move":
                    delete_source(rule, defaults, env, item, s3_client)
                logger.info(
                    "Moved '%s' -> '%s' (%s)",
                    item.rel_name,
                    dest_ref,
                    mode,
                )
                return True
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Attempt %d failed for '%s': %s", attempt + 1, item.rel_name, exc
            )
            if attempt < retries:
                time.sleep(wait_seconds)
                continue
            return False
    return False


def stage_source(
    rule: Rule,
    defaults: Defaults,
    env: Dict[str, str],
    item: SourceItem,
    tmp_dir: str,
    s3_client: Optional[S3Client],
) -> str:
    if item.src_type == "file":
        return stage_copy_to_temp(item.src_path, tmp_dir)

    if s3_client is None:
        s3_client = _build_s3_client(env)
    bucket = _resolve_bucket(rule.src, defaults, env)
    fd, temp_path = tempfile.mkstemp(prefix="stage_", dir=tmp_dir)
    os.close(fd)
    s3_client.download(bucket, item.src_path, temp_path)
    return temp_path


def write_destination(
    rule: Rule,
    defaults: Defaults,
    env: Dict[str, str],
    item: SourceItem,
    temp_path: str,
    s3_client: Optional[S3Client],
) -> str:
    dest = rule.dest
    rel_path = _apply_rename(dest.rename, item.rel_name, env)

    if dest.type == "file":
        dest_dir = resolve_file_path(dest.path, defaults.base_file_path)
        dest_path = _join_os_path(dest_dir, rel_path)
        atomic_write_from_temp(temp_path, dest_path)
        return dest_path

    if s3_client is None:
        s3_client = _build_s3_client(env)
    bucket = _resolve_bucket(dest, defaults, env)
    prefix = normalize_s3_prefix(dest.path)
    key = posixpath.join(prefix, rel_path) if prefix else rel_path
    s3_client.upload(bucket, key, temp_path)
    return f"s3://{bucket}/{key}"


def delete_source(
    rule: Rule,
    defaults: Defaults,
    env: Dict[str, str],
    item: SourceItem,
    s3_client: Optional[S3Client],
) -> None:
    if item.src_type == "file":
        delete_file(item.src_path)
        return

    if s3_client is None:
        s3_client = _build_s3_client(env)
    bucket = _resolve_bucket(rule.src, defaults, env)
    s3_client.delete(bucket, item.src_path)


def _filter_file_items(items: List[FileItem], match: Optional[MatchSpec]) -> List[FileItem]:
    if match is None:
        return items
    return [item for item in items if match.matches(item.name)]


@lru_cache(maxsize=32)
def _load_timezone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def _resolve_local_timezone(env: Dict[str, str]) -> datetime.tzinfo:
    tz_name = env.get("MINIO_HELPER_TIMEZONE")
    if not tz_name:
        local_tz = datetime.now().astimezone().tzinfo
        return local_tz or timezone.utc
    try:
        return _load_timezone(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid MINIO_HELPER_TIMEZONE '{tz_name}'.") from exc


def _render_replace_template(replace: str, env: Dict[str, str]) -> str:
    if "{" not in replace:
        return replace
    local_now = datetime.now(_resolve_local_timezone(env))
    utc_now = datetime.now(timezone.utc)
    tokens = {
        "{timestamp}": local_now.strftime("%Y%m%d-%H%M%S"),
        "{time}": local_now.strftime("%H%M%S"),
        "{date}": local_now.strftime("%Y%m%d"),
        "{date-iso}": local_now.strftime("%Y-%m-%d"),
        "{timestamp-iso}": local_now.strftime("%Y-%m-%dT%H%M%S"),
        "{timestamp-z}": utc_now.strftime("%Y%m%dT%H%M%SZ"),
    }
    for token, value in tokens.items():
        if token in replace:
            replace = replace.replace(token, value)
    return replace


def _apply_rename(rename: Optional[RenameSpec], rel_name: str, env: Dict[str, str]) -> str:
    dir_part, name_part = split_rel_name(rel_name)
    if rename:
        replacement = _render_replace_template(rename.replace, env)
        new_name = rename.apply(name_part, replacement)
    else:
        new_name = name_part
    return join_rel_path(dir_part, new_name)


def _join_os_path(base_dir: str, rel_path: str) -> str:
    parts = rel_path.split("/")
    dest_path = os.path.join(base_dir, *parts)
    ensure_dir(os.path.dirname(dest_path))
    return dest_path


def _resolve_bucket(endpoint: Endpoint, defaults: Defaults, env: Dict[str, str]) -> str:
    if endpoint.bucket:
        return endpoint.bucket
    if defaults.default_bucket:
        return defaults.default_bucket
    env_bucket = env.get("MINIO_BUCKET")
    if env_bucket:
        return env_bucket
    raise ValueError("Bucket must be defined for s3 endpoints.")


def _build_s3_client(env: Dict[str, str]) -> S3Client:
    endpoint = env.get("MINIO_ENDPOINT")
    access_key = env.get("MINIO_ACCESS_KEY")
    secret_key = env.get("MINIO_SECRET_KEY")
    region = env.get("MINIO_REGION")

    if not endpoint:
        raise ValueError("MINIO_ENDPOINT is required.")
    if not access_key or not secret_key:
        raise ValueError("MINIO_ACCESS_KEY and MINIO_SECRET_KEY are required.")

    verify_env = env.get("MINIO_VERIFY")
    verify: Union[bool, str]
    if verify_env is None:
        verify = True
    else:
        verify_env = verify_env.strip().lower()
        if verify_env in {"0", "false", "no"}:
            verify = False
        elif verify_env in {"1", "true", "yes"}:
            verify = True
        else:
            verify = verify_env

    addressing_style = env.get("MINIO_ADDRESSING_STYLE", "path")
    connect_timeout = int(env.get("MINIO_CONNECT_TIMEOUT", "10"))
    read_timeout = int(env.get("MINIO_READ_TIMEOUT", "60"))

    return S3Client(
        endpoint_url=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        verify=verify,
        addressing_style=addressing_style,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    )
