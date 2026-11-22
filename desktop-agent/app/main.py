"""Command-line interface and Windows process lifecycle management for ContextIQ Agent."""
import argparse
import logging
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

# Ensure UTF-8 console output on Windows even with special path characters
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add desktop-agent to path if running directly
agent_root = Path(__file__).resolve().parent.parent
if str(agent_root) not in sys.path:
    sys.path.insert(0, str(agent_root))

from app.agent import DesktopAgent
from app.config import AgentConfig
from app.storage.local_database import LocalDatabase

PID_FILE = agent_root / "agent.pid"


def setup_logging(verbose: bool = False) -> None:
    """Configure structured console logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def is_process_running(pid: int) -> bool:
    """Check if process with PID is currently active."""
    if pid <= 0:
        return False
    if platform.system() == "Windows":
        try:
            # Query tasklist for PID
            output = subprocess.check_output(
                ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return str(pid) in output
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def cmd_run(args: argparse.Namespace) -> None:
    """Run agent in foreground."""
    setup_logging(args.verbose)
    config = AgentConfig()
    agent = DesktopAgent(config=config)
    if args.grant_consent:
        agent.consent_checker.grant_consent()
    agent.run()


def cmd_start(args: argparse.Namespace) -> None:
    """Start agent as a detached background process."""
    setup_logging(args.verbose)
    logger = logging.getLogger("ContextIQ-CLI")

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if is_process_running(pid):
                logger.warning("ContextIQ Desktop Agent is already running with PID %d", pid)
                return
            else:
                logger.info("Found stale PID file; cleaning up.")
                PID_FILE.unlink(missing_ok=True)
        except Exception:
            PID_FILE.unlink(missing_ok=True)

    python_exe = sys.executable
    main_py = str(Path(__file__).resolve())
    cmd = [python_exe, main_py, "run"]
    if args.grant_consent:
        cmd.append("--grant-consent")

    # Launch detached process
    if platform.system() == "Windows":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(
            cmd,
            creationflags=flags,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    PID_FILE.write_text(str(proc.pid))
    logger.info("ContextIQ Desktop Agent started successfully in background (PID: %d)", proc.pid)


def cmd_stop(args: argparse.Namespace) -> None:
    """Gracefully stop running background agent."""
    setup_logging(args.verbose)
    logger = logging.getLogger("ContextIQ-CLI")

    if not PID_FILE.exists():
        logger.info("No active agent PID file found.")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        PID_FILE.unlink(missing_ok=True)
        logger.info("Invalid PID file removed.")
        return

    if not is_process_running(pid):
        logger.info("Process with PID %d is not running. Removing stale PID file.", pid)
        PID_FILE.unlink(missing_ok=True)
        return

    logger.info("Stopping ContextIQ Desktop Agent (PID: %d)...", pid)

    # Attempt graceful termination
    if platform.system() == "Windows":
        # Send terminate signal via taskkill /pid PID
        subprocess.run(["taskkill", "/pid", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        import signal
        os.kill(pid, signal.SIGTERM)

    # Wait for exit
    for _ in range(15):
        if not is_process_running(pid):
            break
        time.sleep(0.5)

    if is_process_running(pid):
        logger.warning("Agent did not terminate gracefully; forcing termination...")
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/f", "/pid", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            import signal
            os.kill(pid, signal.SIGKILL)

    PID_FILE.unlink(missing_ok=True)
    logger.info("ContextIQ Desktop Agent stopped successfully.")


def cmd_status(args: argparse.Namespace) -> None:
    """Check agent operational and buffer status."""
    setup_logging(args.verbose)
    logger = logging.getLogger("ContextIQ-CLI")

    pid_status = "STOPPED"
    pid = None

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if is_process_running(pid):
                pid_status = f"RUNNING (PID: {pid})"
            else:
                pid_status = "STOPPED (Stale PID file)"
        except Exception:
            pid_status = "STOPPED (Corrupt PID file)"

    config = AgentConfig()
    db_path = config.get_absolute_db_path()
    db = LocalDatabase(db_path=db_path)
    stats = db.get_stats()
    db.close()

    print("\n================ ContextIQ Desktop Agent Status ================")
    print(f" Agent Process State   : {pid_status}")
    print(f" Target User ID        : {config.user_id}")
    print(f" Device Hardware ID    : {config.device_id}")
    print(f" Device Computer Name  : {config.device_name}")
    print(f" Backend Endpoint      : {config.backend_url}")
    print(f" Polling Sample Rate   : {config.polling_interval_seconds}s")
    print(f" Idle Threshold        : {config.idle_threshold_seconds}s")
    print(f" Local Database Path   : {db_path}")
    print(f" Total Buffered Events : {stats['total_events']}")
    print(f" Pending Sync Events   : {stats['pending_events']}")
    print(f" Successfully Synced   : {stats['synced_events']}")
    print(f" Failed Sync Events    : {stats['failed_events']}")
    print(f" Buffer Database Size  : {stats['db_size_bytes']} bytes")
    print("================================================================\n")


def cmd_autostart(args: argparse.Namespace) -> None:
    """Manage Windows startup registration requiring explicit user approval."""
    setup_logging(args.verbose)
    logger = logging.getLogger("ContextIQ-CLI")

    if platform.system() != "Windows":
        logger.error("Autostart integration is only supported on Windows.")
        return

    task_name = "ContextIQ_DesktopAgent"
    python_exe = sys.executable
    main_py = str(Path(__file__).resolve())
    agent_cmd = f'"{python_exe}" "{main_py}" run'

    if args.enable:
        if not args.confirm:
            print("\n[!] CAUTION: Windows startup integration requires explicit user authorization.")
            print("    To proceed, re-run with: python main.py autostart --enable --confirm\n")
            return

        # Register with Task Scheduler for interactive logon
        cmd = [
            "schtasks",
            "/create",
            "/tn", task_name,
            "/tr", agent_cmd,
            "/sc", "onlogon",
            "/rl", "limited",
            "/f",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            logger.info("Successfully registered ContextIQ Desktop Agent in Windows Task Scheduler.")
        else:
            logger.error("Failed to register scheduled task: %s", res.stderr)

    elif args.disable:
        cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            logger.info("Successfully removed ContextIQ Desktop Agent from Windows Task Scheduler.")
        else:
            logger.info("Task not found or already deleted.")
    else:
        print("Specify --enable or --disable. Use --help for usage.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ContextIQ Windows Desktop Behavioral Activity Collector")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    run_parser = subparsers.add_parser("run", help="Run agent in foreground")
    run_parser.add_argument("--grant-consent", action="store_true", help="Explicitly grant local telemetry consent")
    run_parser.set_defaults(func=cmd_run)

    # start
    start_parser = subparsers.add_parser("start", help="Start agent in background")
    start_parser.add_argument("--grant-consent", action="store_true", help="Explicitly grant local telemetry consent")
    start_parser.set_defaults(func=cmd_start)

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop background agent")
    stop_parser.set_defaults(func=cmd_stop)

    # status
    status_parser = subparsers.add_parser("status", help="Display agent and buffer status")
    status_parser.set_defaults(func=cmd_status)

    # autostart
    autostart_parser = subparsers.add_parser("autostart", help="Configure Windows startup integration")
    autostart_group = autostart_parser.add_mutually_exclusive_group(required=True)
    autostart_group.add_argument("--enable", action="store_true", help="Enable Windows startup at user login")
    autostart_group.add_argument("--disable", action="store_true", help="Disable Windows startup")
    autostart_parser.add_argument("--confirm", action="store_true", help="Explicit user confirmation for startup change")
    autostart_parser.set_defaults(func=cmd_autostart)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
