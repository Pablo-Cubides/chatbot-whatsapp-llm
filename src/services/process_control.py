"""Process-control helpers shared by admin routers/endpoints."""

from contextlib import suppress
from typing import Iterable

from src.services.audit_system import audit_manager

try:
    import psutil
except ImportError:  # pragma: no cover - runtime optional dependency
    psutil = None


def lm_port() -> int:
    """Return configured LM Studio port with safe default."""
    import os

    try:
        return int(os.environ.get("LM_STUDIO_PORT", "1234"))
    except Exception:
        return 1234


def _log_process_kill(
    action: str,
    *,
    killed: list[int],
    details: dict[str, object],
    username: str,
    role: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Record process-kill operation in audit trail."""
    audit_manager.log_action(
        username=username,
        role=role,
        action=action,
        resource="process-control",
        details={**details, "killed_pids": killed, "killed_count": len(killed)},
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
    )


def kill_processes(
    matchers: Iterable[str],
    *,
    username: str = "system",
    role: str = "system",
    reason: str = "unspecified",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> list[int]:
    """Terminate processes whose name/cmdline contains any matcher."""
    killed: list[int] = []
    if psutil is None:
        _log_process_kill(
            "PROCESS_KILL",
            killed=[],
            details={"matchers": list(matchers), "reason": reason, "psutil_available": False},
            username=username,
            role=role,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return killed

    matcher_list = [m.lower() for m in matchers]
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            cmdline = " ".join(proc.info.get("cmdline") or []).lower()
            if any(m in name or m in cmdline for m in matcher_list):
                proc.terminate()
                killed.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    with suppress(Exception):
        psutil.wait_procs([psutil.Process(pid) for pid in killed if psutil.pid_exists(pid)], timeout=2)

    for pid in list(killed):
        with suppress(Exception):
            if psutil.pid_exists(pid):
                psutil.Process(pid).kill()

    _log_process_kill(
        "PROCESS_KILL",
        killed=killed,
        details={"matchers": list(matchers), "reason": reason, "psutil_available": True},
        username=username,
        role=role,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return killed


def kill_processes_except_current(
    matchers: Iterable[str],
    exclude_pid: int,
    *,
    username: str = "system",
    role: str = "system",
    reason: str = "unspecified",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> list[int]:
    """Terminate matched processes except the excluded PID."""
    killed: list[int] = []
    if psutil is None:
        _log_process_kill(
            "PROCESS_KILL_EXCEPT_CURRENT",
            killed=[],
            details={
                "matchers": list(matchers),
                "exclude_pid": exclude_pid,
                "reason": reason,
                "psutil_available": False,
            },
            username=username,
            role=role,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return killed

    matcher_list = [m.lower() for m in matchers]
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["pid"] == exclude_pid:
                continue
            name = (proc.info.get("name") or "").lower()
            cmdline = " ".join(proc.info.get("cmdline") or []).lower()
            if any(m in name or m in cmdline for m in matcher_list):
                proc.terminate()
                killed.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    with suppress(Exception):
        psutil.wait_procs([psutil.Process(pid) for pid in killed if psutil.pid_exists(pid)], timeout=2)

    for pid in list(killed):
        with suppress(Exception):
            if psutil.pid_exists(pid):
                psutil.Process(pid).kill()

    _log_process_kill(
        "PROCESS_KILL_EXCEPT_CURRENT",
        killed=killed,
        details={
            "matchers": list(matchers),
            "exclude_pid": exclude_pid,
            "reason": reason,
            "psutil_available": True,
        },
        username=username,
        role=role,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return killed


def kill_by_port(
    port: int,
    *,
    username: str = "system",
    role: str = "system",
    reason: str = "unspecified",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> list[int]:
    """Kill processes listening on a given TCP port (best-effort)."""
    killed: list[int] = []
    if psutil is None:
        _log_process_kill(
            "PROCESS_KILL_BY_PORT",
            killed=[],
            details={"port": port, "reason": reason, "psutil_available": False},
            username=username,
            role=role,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return killed

    try:
        for proc in psutil.process_iter(["pid", "name", "connections"]):
            try:
                conns = proc.connections(kind="inet") if hasattr(proc, "connections") else []
                for conn in conns:
                    with suppress(Exception):
                        if conn.laddr and getattr(conn.laddr, "port", None) == port:
                            proc.terminate()
                            killed.append(proc.pid)
                            break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        with suppress(Exception):
            psutil.wait_procs([psutil.Process(pid) for pid in killed if psutil.pid_exists(pid)], timeout=2)

        for pid in list(killed):
            with suppress(Exception):
                if psutil.pid_exists(pid):
                    psutil.Process(pid).kill()
    except Exception:
        pass

    deduped = list(set(killed))
    _log_process_kill(
        "PROCESS_KILL_BY_PORT",
        killed=deduped,
        details={"port": port, "reason": reason, "psutil_available": True},
        username=username,
        role=role,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return deduped
