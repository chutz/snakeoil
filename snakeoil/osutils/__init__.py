# Copyright 2004-2007 Brian Harring <ferringb@gmail.com>
# Copyright 2006 Marien Zwart <marienz@gentoo.org>
# Distributed under the terms of the GNU General Public License v2

"""
os specific utilities, FS access mainly

"""

import os, stat
import fcntl
import errno

__all__ = ['abspath', 'abssymlink', 'ensure_dirs', 'join', 'pjoin',
    'listdir_files', 'listdir_dirs', 'listdir', 'readlines', 'readfile',
    'readdir', 'normpath', 'FsLock', 'GenericFailed',
    'LockException', 'NonExistant']

for val in ("readlines", "readfile"):
    __all__ += list("%s_%s" % (val, mode) for mode in
        ['ascii', 'ascii_strict', 'bytes', 'utf8', 'utf8_strict'])
del val

# No name '_readdir' in module osutils
# pylint: disable-msg=E0611

try:
    from snakeoil.osutils import _readdir as module
except ImportError:
    from snakeoil.osutils import native_readdir as module

# delay this... it's a 1ms hit, and not a lot of the consumers
# force utf8 codepaths yet.
from snakeoil import compatibility
from snakeoil.demandload import demandload
demandload(globals(), "codecs")
from snakeoil.currying import partial, pretty_docs

listdir = module.listdir
listdir_dirs = module.listdir_dirs
listdir_files = module.listdir_files
readdir = module.readdir

del module

def _safe_mkdir(path, mode):
    try:
        os.mkdir(path, mode)
    except OSError, e:
        # if it exists already and is a dir, non issue.
        return e.errno == errno.EEXIST and stat.S_ISDIR(os.stat(path).st_mode)
        os.chmod(path, mode)
    return True

def ensure_dirs(path, gid=-1, uid=-1, mode=0777, minimal=True):
    """
    ensure dirs exist, creating as needed with (optional) gid, uid, and mode.

    be forewarned- if mode is specified to a mode that blocks the euid
    from accessing the dir, this code *will* try to create the dir.
    """

    try:
        st = os.stat(path)
    except OSError:
        base = os.path.sep
        try:
            um = os.umask(0)
            # if the dir perms would lack +wx, we have to force it
            force_temp_perms = ((mode & 0300) != 0300)
            resets = []
            apath = normpath(os.path.abspath(path))
            sticky_parent = False

            for directory in apath.split(os.path.sep):
                base = join(base, directory)
                try:
                    st = os.stat(base)
                    if not stat.S_ISDIR(st.st_mode):
                        return False

                    # if it's a subdir, we need +wx at least
                    if apath != base:
                        if ((st.st_mode & 0300) != 0300):
                            try:
                                os.chmod(base, (st.st_mode | 0300))
                            except OSError:
                                return False
                            resets.append((base, st.st_mode))
                        sticky_parent = (st.st_gid & stat.S_ISGID)

                except OSError:
                    # nothing exists.
                    try:
                        if force_temp_perms:
                            if not _safe_mkdir(base, 0700):
                                return False
                            resets.append((base, mode))
                        else:
                            if not _safe_mkdir(base, mode):
                                return False
                            if base == apath and sticky_parent:
                                resets.append((base, mode))
                            if gid != -1 or uid != -1:
                                os.chown(base, uid, gid)
                    except OSError:
                        return False

            try:
                for base, m in reversed(resets):
                    os.chmod(base, m)
                if uid != -1 or gid != -1:
                    os.chown(base, uid, gid)
            except OSError:
                return False

        finally:
            os.umask(um)
        return True
    else:
        try:
            if ((gid != -1 and gid != st.st_gid) or
                (uid != -1 and uid != st.st_uid)):
                os.chown(path, uid, gid)
            if minimal:
                if mode != (st.st_mode & mode):
                    os.chmod(path, st.st_mode | mode)
            elif mode != (st.st_mode & 07777):
                os.chmod(path, mode)
        except OSError:
            return False
    return True


def abssymlink(symlink):
    """
    Read a symlink, resolving if it is relative, returning the absolute.
    If the path doesn't exist, OSError is thrown.

    @param symlink: filepath to resolve
    @return: resolve path.
    """
    mylink = os.readlink(symlink)
    if mylink[0] != '/':
        mydir = os.path.dirname(symlink)
        mylink = mydir+"/"+mylink
    return os.path.normpath(mylink)


def abspath(path):
    """
    resolve a path absolutely, including symlink resolving.
    Throws OSError if the path doesn't exist

    Note that if it's a symlink and the target doesn't exist, it'll still
    return the target.

    @param path: filepath to resolve.
    @return: resolve path
    """
    path = os.path.abspath(path)
    try:
        return abssymlink(path)
    except OSError, e:
        if e.errno == errno.EINVAL:
            return path
        raise


def native_normpath(mypath):
    """
    normalize path- //usr/bin becomes /usr/bin
    """
    newpath = os.path.normpath(mypath)
    if newpath.startswith('//'):
        return newpath[1:]
    return newpath

native_join = os.path.join

def _internal_native_readfile(mode, mypath, none_on_missing=False, encoding=None,
    strict=compatibility.is_py3k):
    """
    read a file, returning the contents

    @param mypath: fs path for the file to read
    @param none_on_missing: whether to return None if the file is missing,
        else through the exception
    """
    try:
        if encoding and strict:
            # we special case this- codecs.open is about 2x slower,
            # thus if py3k, use the native one (which supports encoding directly)
            if compatibility.is_py3k:
                return open(mypath, mode, encoding=encoding).read()
            return codecs.open(mypath, mode, encoding=encoding).read()
        return open(mypath, mode).read()
    except IOError, oe:
        if none_on_missing and oe.errno == errno.ENOENT:
            return None
        raise

def _mk_pretty_derived_func(func, name_base, name, *args, **kwds):
    if name:
        name = '_' + name
    return pretty_docs(partial(_internal_native_readfile, *args, **kwds),
        name='%s%s' % (name_base, name))

_mk_readfile = partial(_mk_pretty_derived_func, _internal_native_readfile,
    'readfile')

native_readfile_ascii = _mk_readfile('ascii', 'rt')
native_readfile = native_readfile_ascii
native_readfile_ascii_strict = _mk_readfile('ascii_strict', 'r',
    encoding='ascii', strict=True)
native_readfile_bytes = _mk_readfile('bytes', 'rb')
native_readfile_utf8 = _mk_readfile('utf8', 'r',
    encoding='utf8', strict=True)


class readlines_iter(object):
    __slots__ = ("iterable", "mtime")
    def __init__(self, iterable, mtime):
        self.iterable = iterable
        self.mtime = mtime

    def __iter__(self):
        return self.iterable


def native_readlines(mode, mypath, strip_newlines=True, swallow_missing=False,
    none_on_missing=False, encoding=None, strict=compatibility.is_py3k):
    """
    read a file, yielding each line

    @param mypath: fs path for the file to read
    @param strip_newlines: strip trailing newlines?
    @param swallow_missing: throw an IOError if missing, or swallow it?
    @param none_on_missing: if the file is missing, return None, else
        if the file is missing return an empty iterable
    """
    try:
        if encoding and strict:
            # we special case this- codecs.open is about 2x slower,
            # thus if py3k, use the native one (which supports encoding directly)
            if compatibility.is_py3k:
                f = open(mypath, mode, encoding=encoding)
            else:
                f = codecs.open(mypath, mode, encoding=encoding)
        else:
            f = open(mypath, mode)
    except IOError, ie:
        if ie.errno != errno.ENOENT or not swallow_missing:
            raise
        if none_on_missing:
            return None
        return readlines_iter(iter([]), None)

    if not strip_newlines:
        return readlines_iter(f, os.fstat(f.fileno()).st_mtime)

    return readlines_iter((x.strip("\n") for x in f),
        os.fstat(f.fileno()).st_mtime)


_mk_readlines = partial(_mk_pretty_derived_func, native_readlines,
    'readlines')

try:
    from snakeoil.osutils._posix import normpath, join, readfile, readlines
    readfile_ascii = readfile
    readlines_ascii = readlines
except ImportError:
    normpath = native_normpath
    join = native_join
    readfile_ascii = native_readfile_ascii
    readfile = native_readfile
    readlines_ascii = _mk_readlines('ascii', 'r',
        encoding='ascii')
    readlines = readlines_ascii

readlines_bytes = _mk_readlines('bytes', 'rb')
readlines_ascii_strict = _mk_readlines('ascii_strict', 'r',
    encoding='ascii', strict=True)
readlines_utf8 = _mk_readlines('utf8', 'r', encoding='utf8')
readlines_utf8_strict = _mk_readlines('utf8_strict', 'r',
    encoding='utf8', strict=True)

readfile_ascii_strict = native_readfile_ascii_strict
readfile_bytes = native_readfile_bytes
readfile_utf8 = native_readfile_utf8

# convenience.  importing join into a namespace is ugly, pjoin less so
pjoin = join

class LockException(Exception):
    """Base lock exception class"""
    def __init__(self, path, reason):
        Exception.__init__(self, path, reason)
        self.path, self.reason = path, reason

class NonExistant(LockException):
    """Missing file/dir exception"""
    def __init__(self, path, reason=None):
        LockException.__init__(self, path, reason)
    def __str__(self):
        return (
            "Lock action for '%s' failed due to not being a valid dir/file %s"
            % (self.path, self.reason))

class GenericFailed(LockException):
    """The fallback lock exception class.

    Covers perms, IOError's, and general whackyness.
    """
    def __str__(self):
        return "Lock action for '%s' failed due to '%s'" % (
            self.path, self.reason)


# should the fd be left open indefinitely?
# IMO, it shouldn't, but opening/closing everytime around is expensive


class FsLock(object):

    """
    fnctl based locks
    """

    __slots__ = ("path", "fd", "create")
    def __init__(self, path, create=False):
        """
        @param path: fs path for the lock
        @param create: controls whether the file will be created
            if the file doesn't exist.
            If true, the base dir must exist, and it will create a file.
            If you want to lock via a dir, you have to ensure it exists
            (create doesn't suffice).
        @raise NonExistant: if no file/dir exists for that path,
            and cannot be created
        """
        self.path = path
        self.fd = None
        self.create = create
        if not create:
            if not os.path.exists(path):
                raise NonExistant(path)

    def _acquire_fd(self):
        if self.create:
            try:
                self.fd = os.open(self.path, os.R_OK|os.O_CREAT)
            except OSError, oe:
                raise GenericFailed(self.path, oe)
        else:
            try:
                self.fd = os.open(self.path, os.R_OK)
            except OSError, oe:
                raise NonExistant(self.path, oe)

    def _enact_change(self, flags, blocking):
        if self.fd is None:
            self._acquire_fd()
        # we do it this way, due to the fact try/except is a bit of a hit
        if not blocking:
            try:
                fcntl.flock(self.fd, flags|fcntl.LOCK_NB)
            except IOError, ie:
                if ie.errno == errno.EAGAIN:
                    return False
                raise GenericFailed(self.path, ie)
        else:
            fcntl.flock(self.fd, flags)
        return True

    def acquire_write_lock(self, blocking=True):
        """
        Acquire an exclusive lock

        Note if you have a read lock, it implicitly upgrades atomically

        @param blocking: if enabled, don't return until we have the lock
        @return: True if lock is acquired, False if not.
        """
        return self._enact_change(fcntl.LOCK_EX, blocking)

    def acquire_read_lock(self, blocking=True):
        """
        Acquire a shared lock

        Note if you have a write lock, it implicitly downgrades atomically

        @param blocking: if enabled, don't return until we have the lock
        @return: True if lock is acquired, False if not.
        """
        return self._enact_change(fcntl.LOCK_SH, blocking)

    def release_write_lock(self):
        """Release an write/exclusive lock if held"""
        self._enact_change(fcntl.LOCK_UN, False)

    def release_read_lock(self):
        """Release an shared/read lock if held"""
        self._enact_change(fcntl.LOCK_UN, False)

    def __del__(self):
        # alright, it's 5:45am, yes this is weird code.
        try:
            if self.fd is not None:
                self.release_read_lock()
        finally:
            if self.fd is not None:
                os.close(self.fd)
