# Decompiled reference

The mod is written against these sources. Update the pins when a new game patch or ModsSettings API release ships.

| Source | Pinned version |
|---|---|
| Game client | [StranikS-Scan/WorldOfTanks-Decompiled `2.4.1_EU`](https://github.com/StranikS-Scan/WorldOfTanks-Decompiled/tree/2.4.1_EU) (live client v2.4.1.1 EU) |
| ModsSettings API | [izeberg/modssettingsapi 1.7.1](https://github.com/izeberg/modssettingsapi) |

Game paths are under `source/res/scripts/`; ModsSettings paths are under `sources/scripts/client/gui/modsSettingsApi/`. Lesta clients are detected at runtime (`api_detect.py`) but have no pinned source.

## Game behaviour the mod relies on

- **Scale manager**: `client/account_helpers/settings_core/InterfaceScaleManager.py`. `scaleChanged()` reads `GRAPHICS.INTERFACE_SCALE` and calls `self.changeScale(index)`, which sets `__scaleValue` and raises `onScaleChanged`, `graphics.onInterfaceScaleChanged` and `onScaleExactlyChanged`. The mod overrides `changeScale` and `scaleChanged`.
- **Bound references**: `InterfaceScaleManager.init()` adds the bound `self.scaleChanged` to `g_guiResetters` and to `connectionMgr.onConnected`/`onDisconnected`. Those references outlive a restore of the class attribute, so every mod wrapper passes straight through once the hooks are uninstalled.
- **Options setting**: `InterfaceScaleSetting.setSystemValue(value)` in `client/account_helpers/settings_core/options.py` calls `event_dispatcher.changeAppResolution(width, height, scale)` and `g_monitorSettings.setGlyphCache(scale)`. The mod overrides it, and calls it with the stored value to restore the native scale when disabled.
- **Settings access**: `SettingsCore.getSetting(name)` returns `options.getSetting(name).get()`; `SettingsCore.options` and `SettingsCore.interfaceScale` are public properties (`client/account_helpers/settings_core/settingscore.py`). The key is `GRAPHICS.INTERFACE_SCALE` (`interfaceScale`) in `settings_constants.py`.
- **GUI resetters**: `client/gui/__init__.py` defines `g_guiResetters = set()`. It is called after resolution, window mode and monitor changes; the mod adds `_on_gui_reset` and removes it with `discard`.
- **Events**: `common/Event.py` `Event.__iadd__` ignores a handler that is already added and `__isub__` ignores one that never was, so unsubscribing is always safe.

## ModsSettings API behaviour the mod relies on

- `api.py` `setModTemplate`/`registerCallback` do `onSettingsChanged += callback` and `onButtonClicked += buttonHandler`. There is no unregister call, so the mod removes both with `-=`.
- `compareTemplates` replaces a stored template only when `settingsVersion` increases, so the mod rewrites `state['templates'][linkage]` itself to show the current resolution.
- `view.py` `_populate` fires `onWindowOpened`, then Flash calls `requestModsData`, which calls `api.generateSettingsData()`. The mod wraps that method on the instance to rebuild its template first, and deletes the instance attribute on unload.

## Updating for a new patch

1. Find the new branch: `git ls-remote --heads https://github.com/StranikS-Scan/WorldOfTanks-Decompiled.git`.
2. Re-check the files above for renamed methods, changed `setSystemValue`/`changeScale` bodies or changed registrations.
3. Check the installed ModsSettings API version against the latest release and re-read `api.py` and `view.py`.
4. Update `tests/fakes.py` if any of this behaviour changed, then the pins in this file.
