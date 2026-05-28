#-----------------------------------------------------------------------------
# Copyright (c) 2024, PyInstaller Development Team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#
# SPDX-License-Identifier: Apache-2.0
#-----------------------------------------------------------------------------

# Override the `findlibs.find()` function with custom implementation that checks whether the original implementation
# resolves the copy of a library that is bundled with the frozen application. If the original implementation fails to
# resolve the shared library or resolves a system copy, explicitly check if a copy exists in the top-level application
# directory and if it does, return it instead. This aims to mitigate issues with older versions of `findlibs` (< 0.1.0)
# that failed to pick up bundled copy from top-level application directory due to hard-coded search paths.
def _pyi_rthook():
    import sys
    import os
    import pathlib

    # findlibs v0.1.0 broke compatibility with python < 3.10; due to incompatible typing annotation, attempting to
    # import the package raises `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`. Gracefully
    # handle this situation by making this run-time hook no-op, in order to avoid crashing the frozen program even
    # if it would never end up importing/using `findlibs`.
    try:
        import findlibs
    except TypeError:
        return

    _orig_find = getattr(findlibs, 'find', None)
    if _orig_find is None:
        return

    def _pyi_find(lib_name, *args, **kwargs):
        # Try resolving with the original implementation. If resolved, check that a bundled copy was resolved.
        orig_lib = _orig_find(lib_name, *args, **kwargs)
        if orig_lib is not None:
            application_dir = pathlib.Path(sys._MEIPASS).resolve()
            lib_path = pathlib.Path(orig_lib).resolve()
            if application_dir in lib_path.parents:
                return orig_lib

        # Look for a copy in top-level application directory.
        extension = findlibs.EXTENSIONS.get(sys.platform, ".so")
        fullname = os.path.join(sys._MEIPASS, f"lib{lib_name}{extension}")
        if os.path.isfile(fullname):
            return fullname

        # As a last resort, return the result of original resolution attempt.
        return orig_lib

    findlibs.find = _pyi_find


_pyi_rthook()
del _pyi_rthook
