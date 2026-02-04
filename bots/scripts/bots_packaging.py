"""
Bots packaging lib
"""
import subprocess

from pdm.backend.hooks.version import SCMVersion


def format_version(version: SCMVersion) -> str:
    """Format package version.
    {release}
    {release}.postX.dev{last_commit_date}+g#
    {release}.postX+{last_commit_date}+g#
    """
    print("Version:", version.version)
    print("Branch:", version.branch)
    formated = str(version.version)
    if version.distance:
        print("version.distance:", version.distance)
        formated += f".post{version.distance}"
        formated += "+" if "dev" in formated else ".dev"
        try:
            # Add last commit date: .devYYYYMMDD+g#short
            formated += subprocess.check_output(
                ["git", "log", "-1", "--format=%cd+g%h", "--date=format:%Y%m%d"]
            ).decode().strip()
        except Exception:
            pass
    return formated
