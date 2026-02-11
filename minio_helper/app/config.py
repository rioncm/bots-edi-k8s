import dataclasses
import re
from typing import Any, Dict, List, Optional

import yaml


class ConfigError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class MatchSpec:
    glob: Optional[str] = None
    regex: Optional[str] = None
    _regex: Optional[re.Pattern] = dataclasses.field(default=None, repr=False, compare=False)

    def matches(self, name: str) -> bool:
        if self.glob:
            from fnmatch import fnmatch

            return fnmatch(name, self.glob)
        if self.regex:
            if self._regex is None:
                return False
            return bool(self._regex.search(name))
        return True


@dataclasses.dataclass(frozen=True)
class RenameSpec:
    regex: str
    replace: str
    _regex: re.Pattern = dataclasses.field(repr=False, compare=False)

    def apply(self, name: str, replace: Optional[str] = None) -> str:
        replacement = self.replace if replace is None else replace
        return self._regex.sub(replacement, name)


@dataclasses.dataclass(frozen=True)
class Endpoint:
    type: str
    path: str
    bucket: Optional[str] = None
    match: Optional[MatchSpec] = None
    rename: Optional[RenameSpec] = None


@dataclasses.dataclass(frozen=True)
class Rule:
    name: str
    description: Optional[str]
    src: Endpoint
    dest: Endpoint
    mode: Optional[str]
    retries: Optional[int]
    wait_seconds: Optional[int]
    max_items: Optional[int]


@dataclasses.dataclass(frozen=True)
class Defaults:
    default_bucket: Optional[str] = None
    base_file_path: Optional[str] = None
    mode: str = "move"
    retries: int = 0
    wait_seconds: int = 10
    exit_on_first_failure: bool = True
    max_items: Optional[int] = None


@dataclasses.dataclass(frozen=True)
class Config:
    defaults: Defaults
    rules: List[Rule]


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict) or "config" not in raw:
        raise ConfigError("Config file must contain top-level 'config' mapping.")

    cfg = raw.get("config")
    if not isinstance(cfg, dict):
        raise ConfigError("'config' must be a mapping.")

    defaults = _parse_defaults(cfg.get("defaults"))

    rules: List[Rule] = []
    for name, rule_raw in cfg.items():
        if name == "defaults":
            continue
        rules.append(_parse_rule(name, rule_raw))

    if not rules:
        raise ConfigError("At least one rule must be defined.")

    return Config(defaults=defaults, rules=rules)


def _parse_defaults(raw: Any) -> Defaults:
    if raw is None:
        return Defaults()
    if not isinstance(raw, dict):
        raise ConfigError("defaults must be a mapping.")

    return Defaults(
        default_bucket=_opt_str(raw.get("default_bucket")),
        base_file_path=_opt_str(raw.get("base_file_path")),
        mode=_opt_str(raw.get("mode"), default="move"),
        retries=_opt_int(raw.get("retries"), default=0),
        wait_seconds=_opt_int(raw.get("wait_seconds"), default=10),
        exit_on_first_failure=_opt_bool(raw.get("exit_on_first_failure"), default=True),
        max_items=_opt_int(raw.get("max_items"), default=None),
    )


def _parse_rule(name: str, raw: Any) -> Rule:
    if not isinstance(raw, dict):
        raise ConfigError(f"Rule '{name}' must be a mapping.")

    src = _parse_endpoint(name, raw.get("src"), is_source=True)
    dest = _parse_endpoint(name, raw.get("dest"), is_source=False)

    return Rule(
        name=name,
        description=_opt_str(raw.get("description")),
        src=src,
        dest=dest,
        mode=_opt_str(raw.get("mode")),
        retries=_opt_int(raw.get("retries")),
        wait_seconds=_opt_int(raw.get("wait_seconds")),
        max_items=_opt_int(raw.get("max_items")),
    )


def _parse_endpoint(rule_name: str, raw: Any, is_source: bool) -> Endpoint:
    if not isinstance(raw, dict):
        side = "src" if is_source else "dest"
        raise ConfigError(f"Rule '{rule_name}' must define '{side}'.")

    endpoint_type = _req_str(raw.get("type"), f"Rule '{rule_name}' endpoint 'type' is required.")
    if endpoint_type not in {"file", "s3"}:
        raise ConfigError(
            f"Rule '{rule_name}' endpoint type must be 'file' or 's3'."
        )

    path = _req_str(raw.get("path"), f"Rule '{rule_name}' endpoint 'path' is required.")
    bucket = _opt_str(raw.get("bucket"))

    match = None
    match_raw = raw.get("match")
    if is_source and match_raw is not None:
        if not isinstance(match_raw, dict):
            raise ConfigError(f"Rule '{rule_name}' match must be a mapping.")
        glob = _opt_str(match_raw.get("glob"))
        regex = _opt_str(match_raw.get("regex"))
        if glob and regex:
            raise ConfigError(f"Rule '{rule_name}' match cannot define both glob and regex.")
        match = MatchSpec(glob=glob, regex=regex)
        if match.regex:
            try:
                object.__setattr__(match, "_regex", re.compile(match.regex))
            except re.error as exc:
                raise ConfigError(
                    f"Rule '{rule_name}' match regex is invalid: {exc}"
                ) from exc

    rename = None
    rename_raw = raw.get("rename")
    if not is_source and rename_raw is not None:
        if not isinstance(rename_raw, dict):
            raise ConfigError(f"Rule '{rule_name}' rename must be a mapping.")
        regex = _req_str(rename_raw.get("regex"), f"Rule '{rule_name}' rename regex required.")
        replace = _req_str(
            rename_raw.get("replace"), f"Rule '{rule_name}' rename replace required."
        )
        try:
            compiled = re.compile(regex)
        except re.error as exc:
            raise ConfigError(
                f"Rule '{rule_name}' rename regex is invalid: {exc}"
            ) from exc
        rename = RenameSpec(regex=regex, replace=replace, _regex=compiled)

    return Endpoint(
        type=endpoint_type,
        path=path,
        bucket=bucket,
        match=match,
        rename=rename,
    )


def _req_str(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(message)
    return value.strip()


def _opt_str(value: Any, default: Optional[str] = None) -> Optional[str]:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ConfigError("Expected a string value.")
    value = value.strip()
    return value if value else default


def _opt_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ConfigError("Expected integer value, got boolean.")
    if not isinstance(value, int):
        raise ConfigError("Expected integer value.")
    if value < 0:
        raise ConfigError("Integer values must be >= 0.")
    return value


def _opt_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConfigError("Expected boolean value.")
    return value
