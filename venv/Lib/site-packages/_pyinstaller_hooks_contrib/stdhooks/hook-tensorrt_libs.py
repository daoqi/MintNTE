# ------------------------------------------------------------------
# Copyright (c) 2026 PyInstaller Development Team.
#
# This file is distributed under the terms of the GNU General Public
# License (version 2.0 or later).
#
# The full license is available in LICENSE, distributed with
# this software.
#
# SPDX-License-Identifier: GPL-2.0-or-later
# ------------------------------------------------------------------

from PyInstaller.utils.hooks import PY_DYLIB_PATTERNS, collect_dynamic_libs
from PyInstaller.compat import is_linux

_search_patterns = list(PY_DYLIB_PATTERNS)
if is_linux:
    _search_patterns.append("*.so.*")

binaries = collect_dynamic_libs("tensorrt_libs", search_patterns=_search_patterns)
