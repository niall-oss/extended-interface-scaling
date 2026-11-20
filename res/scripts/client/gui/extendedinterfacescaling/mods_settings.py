from debug_utils import LOG_NOTE

from gui.extendedinterfacescaling.override_utils import override, restore

MOD_LINKAGE = "extended_interface_scaling"
SETTINGS_VERSION = 8

MIN_UI_SCALE = 0.5
MAX_UI_SCALE = 2.0

REFERENCE_SCALES = (0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0)

REFERENCE_TOOLTIP = (
    "{HEADER}Scaling reference{/HEADER}"
    "{BODY}This reference shows what the scaling multiplier will cause "
    "the UI to behave like in terms of resolution. With this mod the "
    "sharpness of the UI will remain as perfect as your native resolution, "
    "despite being \"scaled\" up or down to the reference resolution size.{/BODY}"
)


def _clamp_scale(scale):
    return max(MIN_UI_SCALE, min(MAX_UI_SCALE, float(scale)))


def _parse_scale(value, default=1.0):
    try:
        return _clamp_scale(float(value))
    except (TypeError, ValueError):
        return _clamp_scale(default)


HINT_TOOLTIP = (
    "{HEADER}In-game interface scaling{/HEADER}"
    "{BODY}When this mod is enabled, it controls interface scale. "
    "The in-game Options > Interface Scaling setting is overridden.{/BODY}"
)


def _screen_info():
    from gui.extendedinterfacescaling.display_utils import (
        get_current_screen_size,
        get_native_screen_resolution,
    )

    try:
        from gui.shared.utils.monitor_settings import g_monitorSettings

        monitor = g_monitorSettings.currentMonitor
    except Exception:
        monitor = 0

    screen_width, screen_height = get_current_screen_size()
    native_width, native_height = get_native_screen_resolution(
        monitor, screen_width, screen_height
    )
    aspect = float(screen_width) / float(screen_height) if screen_height else 0.0
    return {
        "screen": "%dx%d" % (screen_width, screen_height),
        "native": "%dx%d" % (int(native_width), int(native_height)),
        "aspect": "%.3f" % aspect,
    }


def _scaling_reference_rows():
    from gui.extendedinterfacescaling.display_utils import get_current_screen_size
    from gui.extendedinterfacescaling.scale_calculator import effective_ui_size

    screen_width, screen_height = get_current_screen_size()

    rows = []
    for scale in REFERENCE_SCALES:
        eff_w, eff_h = effective_ui_size(screen_width, screen_height, scale)
        rows.append(
            {
                "scale": scale,
                "label": "%sx" % scale,
                "width": int(round(eff_w)),
                "height": int(round(eff_h)),
            }
        )
    return rows


_api = None
_settings_data_override = None
_last_cached_screen_size = None
_refresh_callback_id = None


def _get_mods_settings_api():
    try:
        from gui.modsSettingsApi import g_modsSettingsApi
    except ImportError:
        return None
    return g_modsSettingsApi


def _get_gui_resetters():
    try:
        from gui import g_guiResetters
    except ImportError:
        return None
    return g_guiResetters


def refresh_mod_template(force=False):
    global _last_cached_screen_size

    if _api is None:
        return False

    from gui.extendedinterfacescaling.display_utils import get_current_screen_size

    screen_size = get_current_screen_size()
    if MOD_LINKAGE not in _api.state.get("templates", {}):
        return False

    if not force and _last_cached_screen_size == screen_size:
        return False

    _last_cached_screen_size = screen_size
    _api.state["templates"][MOD_LINKAGE] = _build_template()
    _api.saveState()
    return True


def _cancel_template_refresh():
    global _refresh_callback_id

    if _refresh_callback_id is None:
        return

    import BigWorld

    BigWorld.cancelCallback(_refresh_callback_id)
    _refresh_callback_id = None


def schedule_template_refresh():
    global _refresh_callback_id, _last_cached_screen_size

    if _api is None:
        return

    import BigWorld

    _last_cached_screen_size = None
    _cancel_template_refresh()
    _refresh_callback_id = BigWorld.callback(0.0, _deferred_template_refresh)


def _deferred_template_refresh():
    global _refresh_callback_id

    _refresh_callback_id = None
    refresh_mod_template(force=True)


def on_screen_geometry_changed():
    schedule_template_refresh()


def _on_mods_window_opened():
    schedule_template_refresh()


def _on_gui_reset():
    schedule_template_refresh()


def _generate_settings_data_with_fresh_template(original):
    # The window reads templates here, after onWindowOpened, so the deferred
    # refresh would arrive too late for the first paint.
    refresh_mod_template(force=True)
    return original()


def _build_template():
    from gui.modsSettingsApi import templates
    from gui.extendedinterfacescaling import config

    info = _screen_info()
    reference_rows = _scaling_reference_rows()
    current_scale = config.get_scale()

    reset_button = templates.createButton(
        width=70, height=23, text="1.0x", offsetTop=0, offsetLeft=8
    )

    column1 = [
        templates.createLabel(
            "When enabled, this mod controls interface scale.",
            tooltip=HINT_TOOLTIP,
        ),
        templates.createEmpty(),
        templates.createInput(
            "UI scale",
            "scale",
            str(current_scale),
            tooltip=(
                HINT_TOOLTIP
                + "{BODY}Enter a value between %.1f and %.1f (e.g. 1.22).{/BODY}"
                % (MIN_UI_SCALE, MAX_UI_SCALE)
            ),
            button=reset_button,
            width=80,
        ),
        templates.createEmpty(),
        templates.createLabel("Scaling reference", tooltip=REFERENCE_TOOLTIP),
    ]

    for item in reference_rows:
        column1.append(
            templates.createLabel(
                "  %s -> %dx%d"
                % (item["label"], item["width"], item["height"])
            )
        )

    return {
        "modDisplayName": "Extended Interface Scaling",
        "settingsVersion": SETTINGS_VERSION,
        "enabled": config.is_enabled(),
        "column1": column1,
        "column2": [
            templates.createLabel("Resolution: %s" % info["screen"]),
            templates.createLabel("Native: %s" % info["native"]),
            templates.createLabel("Aspect: %s" % info["aspect"]),
            templates.createEmpty(),
            templates.createLabel(
                "Changes apply when you click Apply in the settings window."
            ),
        ],
    }


def _apply_settings(settings):
    from gui.extendedinterfacescaling import config
    from gui.extendedinterfacescaling.scale_applier import (
        apply_scale,
        restore_native_scale,
    )

    settings = dict(settings)

    scale = _parse_scale(settings.get("scale", config.get_scale()))
    enabled = bool(settings.get("enabled", config.is_enabled()))
    was_enabled = config.is_enabled()

    config.apply_values(scale=scale, enabled=enabled)

    if enabled:
        apply_scale(scale)
    elif was_enabled:
        restore_native_scale()


def _on_settings_changed(linkage, settings):
    if linkage != MOD_LINKAGE:
        return
    _apply_settings(settings)


def _on_button_clicked(linkage, varName, value):
    if linkage != MOD_LINKAGE or varName != "scale" or _api is None:
        return

    saved = _api.getModSettings(MOD_LINKAGE, _build_template())
    if not saved:
        return

    saved["scale"] = "1.0"
    _api.updateModSettings(MOD_LINKAGE, saved)


def register_mods_settings():
    global _api, _settings_data_override

    if _api is not None:
        return True

    api = _get_mods_settings_api()
    if api is None:
        LOG_NOTE(
            "ModsSettings API not installed. Configure scale via "
            "mods/configs/ANIALLATOR.extended_interface_scaling/config.json"
        )
        return False

    _api = api
    template = _build_template()
    saved = api.getModSettings(MOD_LINKAGE, template)

    if saved:
        api.registerCallback(MOD_LINKAGE, _on_settings_changed, _on_button_clicked)
        _apply_settings(saved)
    else:
        settings = api.setModTemplate(
            MOD_LINKAGE, template, _on_settings_changed, _on_button_clicked
        )
        if settings:
            _apply_settings(settings)

    api.onWindowOpened += _on_mods_window_opened
    _settings_data_override = override(
        api, "generateSettingsData", _generate_settings_data_with_fresh_template
    )

    gui_resetters = _get_gui_resetters()
    if gui_resetters is not None:
        gui_resetters.add(_on_gui_reset)
    return True


def unregister_mods_settings():
    global _api, _settings_data_override, _last_cached_screen_size

    _cancel_template_refresh()
    if _api is None:
        return

    # ModsSettings API has no unregister call; these mirror registerCallback.
    _api.onSettingsChanged -= _on_settings_changed
    _api.onButtonClicked -= _on_button_clicked
    _api.onWindowOpened -= _on_mods_window_opened
    restore(_settings_data_override)

    gui_resetters = _get_gui_resetters()
    if gui_resetters is not None:
        gui_resetters.discard(_on_gui_reset)

    _api = None
    _settings_data_override = None
    _last_cached_screen_size = None
