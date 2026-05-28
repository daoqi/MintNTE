# ------------------------------------------------------------------
# Copyright (c) 2024 PyInstaller Development Team.
#
# This file is distributed under the terms of the GNU General Public
# License (version 2.0 or later).
#
# The full license is available in LICENSE, distributed with
# this software.
#
# SPDX-License-Identifier: GPL-2.0-or-later
# ------------------------------------------------------------------

from PyInstaller.utils.hooks import collect_data_files, is_module_satisfies

# This was required with langchain < 1.0.0; in contemporary versions, the package does not contain any data files,
# so this should be effectively a no-op.
datas = collect_data_files('langchain')

# In langchain 1.2.1 the import logic for optional add-on packages was refactored, and direct imports in conditional
# blocks were replaced with dictionary-based look-up; see https://github.com/langchain-ai/langchain/pull/32813
# So now we need to use that same dictionary to explicitly collect the optional packages that happen to be installed
# in the build environment.
if is_module_satisfies('langchain >= 1.2.1'):
    from PyInstaller import isolated

    @isolated.decorate
    def get_optional_packages(var_name):
        packages = set()

        try:
            import langchain.chat_models.base
            providers = getattr(langchain.chat_models.base, var_name)
            packages.update(package_name for package_name, *_ in providers.values())
        except Exception:
            pass

        try:
            import langchain.embeddings.base
            providers = getattr(langchain.embeddings.base, var_name)
            packages.update(package_name for package_name, *_ in providers.values())
        except Exception:
            pass

        return sorted(packages)

    # langchain 1.2.10 renamed the `_SUPPORTED_PROVIDERS` into `_BUILTIN_PROVIDERS`.
    if is_module_satisfies('langchain >= 1.2.10'):
        var_name = '_BUILTIN_PROVIDERS'
    else:
        var_name = '_SUPPORTED_PROVIDERS'

    hiddenimports = get_optional_packages(var_name)
    warn_on_missing_hiddenimports = False
