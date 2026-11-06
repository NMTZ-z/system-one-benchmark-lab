"""Read-only Darwin process identity without executing the setuid /bin/ps."""
import ctypes
import errno
import os


class _BSDInfo(ctypes.Structure):
    # SDK sys/proc_info.h: proc_bsdinfo / PROC_PIDTBSDINFO.
    _fields_ = [(name, ctypes.c_uint32) for name in (
        'flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid', 'rgid', 'svuid', 'svgid', 'reserved')]
    _fields_ += [('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)]
    _fields_ += [(name, ctypes.c_uint32) for name in ('nfiles', 'pgid', 'jobc', 'tdev', 'tpgid')]
    _fields_ += [('nice', ctypes.c_int32), ('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]


_lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
_lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
_lib.proc_pidinfo.restype = ctypes.c_int
_lib.proc_listpids.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_int]
_lib.proc_listpids.restype = ctypes.c_int


def identity(pid: int) -> dict | None:
    if type(pid) is not int or pid <= 1:
        raise ValueError('positive owned process ID required')
    data = _BSDInfo()
    ctypes.set_errno(0)
    count = _lib.proc_pidinfo(pid, 3, 0, ctypes.byref(data), ctypes.sizeof(data))
    number = ctypes.get_errno()
    if count == 0 and number == errno.ESRCH:
        return None
    if count != ctypes.sizeof(data) or data.pid != pid or data.start_usec >= 1_000_000:
        raise OSError(number or errno.EIO, 'kernel process identity unavailable')
    return {'pid': data.pid, 'pgid': data.pgid, 'uid': data.uid,
            'start': f'darwin:{data.start_sec}:{data.start_usec}', 'zombie': data.status == 5}


def group_members(pgid: int) -> list[int]:
    if type(pgid) is not int or pgid <= 1:
        raise ValueError('positive owned process group required')
    # A bounded full buffer is an uncertain result, never proof of an empty group.
    values = (ctypes.c_int * 4096)()
    ctypes.set_errno(0)
    size = _lib.proc_listpids(2, pgid, ctypes.byref(values), ctypes.sizeof(values))
    number = ctypes.get_errno()
    if number or size < 0 or size >= ctypes.sizeof(values) or size % ctypes.sizeof(ctypes.c_int):
        raise OSError(number or errno.EOVERFLOW, 'kernel process group enumeration unavailable')
    members = []
    for pid in values[:size // ctypes.sizeof(ctypes.c_int)]:
        if pid <= 1:
            continue
        item = identity(pid)
        if item is not None and item['pgid'] == pgid and not item['zombie']:
            members.append(pid)
    return members
