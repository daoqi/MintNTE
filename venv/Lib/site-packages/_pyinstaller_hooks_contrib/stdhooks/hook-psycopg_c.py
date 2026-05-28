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

# The `psycopg_c._uuid` module is imported from the `psycopg_c._psycopg` binary extension when working with
# data of UUID data type.
hiddenimports = ['psycopg_c._uuid']
