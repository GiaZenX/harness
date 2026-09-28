"""V2 state-kernel core (HARNESS_V2_SPEC.md Teil II).

One Python core shared by hooks, dashboard generation, scaffold and migration
(spec II.4). Phase 1 modules:

- lock.py     -- cross-process kernel lock (II.4 "Nebenlaeufigkeit & Locking")
- hashing.py  -- canonical subject-manifest hashing (II.2 "Hash-Kanonisierung")
"""
import os as _os
import sys as _sys

# NO IMPORTER CACHES INTO THE INSTALLED PACKAGE, whichever route started it (BUG-0310). Installed,
# this package is `.claude/kernel`, inside the tree `hashing.hook_bundle_hash` measures with nothing
# excluded, and `hashing.BYTECODE_SUFFIXES` says why every route the KIT starts refuses to cache. A
# route the kit does not start -- a project's own test run or script putting `.claude` on its path
# -- cached `__pycache__` there in the field, and every spawn was refused until somebody deleted it
# from outside the session. Set here, the flag holds for every submodule this process imports
# afterwards; it is process-wide, so the importing process caches nothing further either, which
# costs it start-up time and nothing else. ONLY WHERE INSTALLED: in this repo's own tree and in the
# staging, the routes that import the kernel refuse to cache on their own (`hashing.BYTECODE_
# SUFFIXES` names the checks that hold them to it), and a process-wide switch flipped there would
# decide for them -- and would blind the control those checks run.
# WHICHEVER SPELLING of the path the importer used: the directory holding this package is compared
# as a DIRECTORY with `<its parent>/.claude`, not as a name, so `.CLAUDE` on a case-insensitive
# filesystem is the installed package too (the name comparison cached there -- TSK-0156 verify
# round 1, F5). Not recognised: a route that reaches the package through a link under another name.
# `tools/test_stream_c_field.py::test_importing_the_installed_kernel_without_b_writes_no_bytecode_bug_0310`


def _installed_here(package_file):
    holder = _os.path.dirname(_os.path.dirname(_os.path.abspath(package_file)))
    try:
        return _os.path.samefile(holder, _os.path.join(_os.path.dirname(holder), ".claude"))
    except OSError:
        return False


_INSTALLED = _installed_here(__file__)
if _INSTALLED:
    _sys.dont_write_bytecode = True
    # ...AND THE ONE CACHE THE FLAG ARRIVES TOO LATE FOR: this file's own. The loader compiles and
    # caches `__init__` BEFORE running it, so the assignment above cannot prevent that write;
    # removing the cache after the fact is the only place left. Deleting a cache never adds code.
    # `tools/test_stream_c_field.py::test_importing_the_installed_kernel_without_b_writes_no_bytecode_bug_0310`
    # imports an installed copy from a process without `-B` and finds no bytecode under it.
    _cached = globals().get("__cached__")
    if _cached:
        for _remove, _path in ((_os.remove, _cached), (_os.rmdir, _os.path.dirname(_cached))):
            try:
                _remove(_path)        # rmdir removes the cache directory only while it is empty
            except OSError:
                pass
