from account_helpers.settings_core.interfacescalemanager import InterfaceScaleManager
from account_helpers.settings_core.options import InterfaceScaleSetting
from gui.extendedinterfacescaling import config
from gui.extendedinterfacescaling.override_utils import override, restore
from gui.extendedinterfacescaling.scale_applier import apply_scale, is_applying

_overrides = []


def _is_installed():
    return bool(_overrides)


def _should_pass_through():
    # The game keeps bound references to these methods (g_guiResetters,
    # connection events), so a wrapper can still run after uninstall().
    return not _is_installed() or is_applying() or not config.is_enabled()


def _patched_change_scale(original, self, arg):
    if _should_pass_through():
        return original(self, arg)
    apply_scale(config.get_scale())


def _patched_scale_changed(original, self):
    original(self)
    if not _is_installed():
        return
    try:
        from gui.extendedinterfacescaling.mods_settings import on_screen_geometry_changed

        on_screen_geometry_changed()
    except ImportError:
        pass
    if _should_pass_through():
        return
    apply_scale(config.get_scale())


def _patched_set_system_value(original, self, value):
    original(self, value)
    if _should_pass_through():
        return
    apply_scale(config.get_scale())


def install():
    if _is_installed():
        return

    _overrides.extend(
        [
            override(InterfaceScaleManager, "changeScale", _patched_change_scale),
            override(InterfaceScaleManager, "scaleChanged", _patched_scale_changed),
            override(
                InterfaceScaleSetting, "setSystemValue", _patched_set_system_value
            ),
        ]
    )

    if config.is_enabled():
        apply_scale(config.get_scale())


def uninstall():
    while _overrides:
        restore(_overrides.pop())
