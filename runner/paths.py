from pathlib import PurePosixPath, PureWindowsPath


def host_to_openclaw(host_path: str, host_root: str, container_root: str) -> str:
    """Translate a host path under host_root to its mirror under container_root.

    Accepts both forward-slash and backslash host paths; returns POSIX form.
    Raises ValueError if host_path is not under host_root.
    """
    host_path_p = PureWindowsPath(host_path)
    host_root_p = PureWindowsPath(host_root)

    try:
        rel = host_path_p.relative_to(host_root_p)
    except ValueError as e:
        raise ValueError(
            f"host_path={host_path!r} is not under host_root={host_root!r}"
        ) from e

    rel_posix = PurePosixPath(*rel.parts)
    return str(PurePosixPath(container_root) / rel_posix)
