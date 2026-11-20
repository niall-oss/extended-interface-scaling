"""Enable/disable, cleanup and screen-change behaviour against the game fakes."""

from conftest import NATIVE_INDEX, NATIVE_SCALE, write_config


def _linkage(game):
    return game.mods_settings.MOD_LINKAGE


def _apply(game, **fields):
    settings = dict(game.api.state["settings"][_linkage(game)])
    settings.update(fields)
    game.api.apply(_linkage(game), settings)


def _labels(template):
    return [
        component["text"]
        for column in ("column1", "column2")
        for component in template[column]
        if component["type"] == "Label"
    ]


def _stored_labels(game):
    return _labels(game.api.state["templates"][_linkage(game)])


def _assert_scale(game, scale):
    assert game.display.app_scale == scale
    assert game.display.glyph_cache_scale == scale
    assert game.display.graphics_scale == scale
    assert game.core.interfaceScale.get() == scale


def _fire_gui_resetters(game):
    for resetter in list(game.gui_resetters):
        resetter()


def _assert_hooks_restored(game):
    for (holder, name), original in game.originals.items():
        assert holder.__dict__[name] is original, name


def test_init_applies_custom_scale(game):
    write_config(1.25, True)

    game.entry.init()

    _assert_scale(game, 1.25)


def test_disabling_restores_native_scale_immediately(game):
    write_config(1.25, True)
    game.entry.init()

    _apply(game, enabled=False)

    _assert_scale(game, NATIVE_SCALE)
    assert game.core.getSetting("interfaceScale") == NATIVE_INDEX


def test_reenabling_applies_custom_scale_again(game):
    write_config(1.25, True)
    game.entry.init()
    _apply(game, enabled=False)

    _apply(game, enabled=True)

    _assert_scale(game, 1.25)


def test_disabled_at_start_leaves_native_scale(game):
    write_config(1.25, False)

    game.entry.init()

    _assert_scale(game, NATIVE_SCALE)


def test_options_menu_change_while_disabled_is_native(game):
    write_config(1.25, False)
    game.entry.init()

    game.core.change_scale_in_options(1)
    _fire_gui_resetters(game)

    _assert_scale(game, 1.0)


def test_reset_button_applies_one(game):
    write_config(1.25, True)
    game.entry.init()

    game.api.click_button(_linkage(game), "scale", None)

    _assert_scale(game, 1.0)


def test_resolution_change_keeps_custom_scale_and_refreshes_panel(game):
    write_config(1.25, True)
    game.entry.init()

    game.display.screen = (2560, 1440)
    game.display.native = (2560, 1440)
    _fire_gui_resetters(game)
    game.bigworld.run_callbacks()

    _assert_scale(game, 1.25)
    labels = _stored_labels(game)
    assert "Resolution: 2560x1440" in labels
    assert "Native: 2560x1440" in labels
    assert "  1.25x -> 2048x1152" in labels


def test_options_menu_change_while_enabled_keeps_custom_scale(game):
    write_config(1.25, True)
    game.entry.init()

    game.core.change_scale_in_options(1)
    game.core.interfaceScale.scaleChanged()

    _assert_scale(game, 1.25)


def test_opening_window_shows_current_resolution(game):
    game.entry.init()
    game.display.screen = (1920, 1080)

    data = game.api.open_window()

    (template,) = [t for t in data if t["linkage"] == _linkage(game)]
    assert "Resolution: 1920x1080" in _labels(template)


def test_fini_removes_every_hook_and_listener(game):
    game.entry.init()
    game.api.open_window()
    game.core.interfaceScale.scaleChanged()
    assert game.bigworld.callbacks

    game.entry.fini()
    game.entry.fini()

    _assert_hooks_restored(game)
    assert list(game.api.onSettingsChanged) == []
    assert list(game.api.onButtonClicked) == []
    assert list(game.api.onWindowOpened) == []
    assert "generateSettingsData" not in vars(game.api)
    assert game.gui_resetters == {game.core.interfaceScale.scaleChanged}
    assert game.bigworld.callbacks == {}


def test_stale_wrapper_passes_through_after_fini(game):
    write_config(1.25, True)
    game.entry.init()
    stale_change_scale = game.Manager.__dict__["changeScale"]
    stale_set_system_value = game.Setting.__dict__["setSystemValue"]

    game.entry.fini()
    stale_set_system_value(game.core.options.getSetting("interfaceScale"), 1)
    stale_change_scale(game.core.interfaceScale, 1)

    _assert_scale(game, 1.0)
    assert game.bigworld.callbacks == {}


def test_fini_leaves_another_mods_wrapper_in_place(game):
    write_config(1.25, True)
    game.entry.init()
    ours = game.Manager.__dict__["changeScale"]

    def theirs(self, index):
        return ours(self, index)

    game.Manager.changeScale = theirs

    game.entry.fini()

    assert game.Manager.__dict__["changeScale"] is theirs
    assert game.notes
    game.core.interfaceScale.changeScale(NATIVE_INDEX)
    assert game.core.interfaceScale.get() == NATIVE_SCALE


def test_reinit_does_not_stack_wrappers_or_listeners(game):
    game.entry.init()
    game.entry.init()
    game.entry.fini()
    game.entry.init()

    assert len(game.api.onSettingsChanged) == 1
    assert len(game.api.onButtonClicked) == 1
    assert len(game.api.onWindowOpened) == 1
    assert game.api.generateSettingsData.__name__ == "wrapped"

    game.entry.fini()

    _assert_hooks_restored(game)
    assert "generateSettingsData" not in vars(game.api)
