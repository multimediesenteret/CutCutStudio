"""Children die with the supervisor, however it ends.

An orphaned core would keep port 8080 and the bus ports, and every new core would then fail
to start – a restart loop that looks like a crash. So children are tied to the supervisor:

* Windows: every child is put in a Job Object with ``KILL_ON_JOB_CLOSE``; when the supervisor
  is gone (even killed from Task Manager) Windows closes the job and ends the children.
* Linux: ``PR_SET_PDEATHSIG`` asks the kernel to send SIGTERM to a child whose parent dies.

Both are best effort: if the call fails the child still runs, and that is logged.
"""

from __future__ import annotations

import ctypes
import logging
import signal
import subprocess
import sys
from collections.abc import Callable

log = logging.getLogger(__name__)

_JOB: int | None = None


def linux_preexec() -> Callable[[], None] | None:
    if not sys.platform.startswith("linux"):
        return None

    def preexec() -> None:  # runs in the child between fork and exec
        try:
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            libc.prctl(1, int(signal.SIGTERM), 0, 0, 0)  # PR_SET_PDEATHSIG
        except OSError:
            pass

    return preexec


def bind_to_us(proc: subprocess.Popen[bytes]) -> None:
    """Windows: put ``proc`` in the supervisor's kill-on-close job."""
    if sys.platform != "win32":
        return
    global _JOB
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    k32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)

    class Basic(ctypes.Structure):
        _fields_ = (
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        )

    class Io(ctypes.Structure):
        _fields_ = tuple(
            (n, ctypes.c_uint64)
            for n in ("Reads", "Writes", "Others", "ReadBytes", "WriteBytes", "OtherBytes")
        )

    class Extended(ctypes.Structure):
        _fields_ = (
            ("BasicLimitInformation", Basic),
            ("IoInfo", Io),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        )

    if _JOB is None:
        job = k32.CreateJobObjectW(None, None)
        if not job:
            log.warning("Job Object kunne ikke lages (%s)", ctypes.get_last_error())
            return
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            log.warning("Job Object kunne ikke settes opp (%s)", ctypes.get_last_error())
            return
        _JOB = job
    handle = int(getattr(proc, "_handle", 0))  # the process handle of a Windows Popen
    if not handle or not k32.AssignProcessToJobObject(_JOB, handle):
        log.warning("%s ble ikke bundet til supervisor (%s)", proc.pid, ctypes.get_last_error())
