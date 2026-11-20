import json
import sys
import types
from pathlib import Path

import pytest
from fakes import (
    INTERFACE_SCALE,
    Display,
    FakeBigWorld,
    FakeModsSettingsApi,
    FakeMonitorSettings,
    FakeSettingsCore,
    make_scale_classes,
    make_templates_module,
)

CLIENT_SCRIPTS = Path(__file__).resolve().parents[1] / "res" / "scripts" / "client"
MOD_PACKAGES = ("gui.extendedinterfacescaling", "gui.mods")
CONFIG_DIR = Path("mods/configs/ANIALLATOR.extended_interface_scaling")

NATIVE_INDEX = 2
NATIVE_SCALE = 2.0


def _install_game_modules(monkeypatch, game):
    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
        parent, _, child = name.rpartition(".")
        if parent in sys.modules:
            setattr(sys.modules[parent], child, mod)
        return mod

    display = game.display
    module("debug_utils", LOG_NOTE=game.notes.append)
    monkeypatch.setitem(sys.modules, "BigWorld", game.bigworld)
    module("GUI", screenResolution=lambda: display.screen)

    gui = module("gui", g_guiResetters=game.gui_resetters)
    gui.__path__ = [str(CLIENT_SCRIPTS / "gui")]
    module("gui.shared")
    module(
        "gui.shared.event_dispatcher",
        changeAppResolution=lambda w, h, scale: setattr(display, "app_scale", scale),
    )
    module("gui.shared.utils")
    module(
        "gui.shared.utils.graphics",
        onInterfaceScaleChanged=lambda scale: setattr(display, "graphics_scale", scale),
    )
    module(
        "gui.shared.utils.monitor_settings",
        g_monitorSettings=FakeMonitorSettings(display),
    )

    module("helpers")
    module("helpers.dependency", instance=lambda interface: game.core)
    module("skeletons")
    module("skeletons.account_helpers")
    module("skeletons.account_helpers.settings_core", ISettingsCore=object)

    module("account_helpers")
    module("account_helpers.settings_core")
    module(
        "account_helpers.settings_core.settings_constants",
        GRAPHICS=types.SimpleNamespace(INTERFACE_SCALE=INTERFACE_SCALE),
    )
    module(
        "account_helpers.settings_core.interfacescalemanager",
        InterfaceScaleManager=game.Manager,
    )
    module(
        "account_helpers.settings_core.options",
        InterfaceScaleSetting=game.Setting,
    )

    templates = make_templates_module()
    module("gui.modsSettingsApi", g_modsSettingsApi=game.api)
    monkeypatch.setitem(sys.modules, templates.__name__, templates)
    sys.modules["gui.modsSettingsApi"].templates = templates


def _forget_mod_modules():
    for name in list(sys.modules):
        if any(name == pkg or name.startswith(pkg + ".") for pkg in MOD_PACKAGES):
            del sys.modules[name]


def _import_mod_fresh():
    _forget_mod_modules()
    import gui.mods.mod_extendedinterfacescaling as entry
    from gui.extendedinterfacescaling import hooks, mods_settings

    return entry, hooks, mods_settings


def write_config(scale, enabled):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "config.json").write_text(
        json.dumps({"scale": scale, "enabled": enabled})
    )


@pytest.fixture
def game(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    display = Display(screen=(3840, 2160), native=(3840, 2160))
    gui_resetters = set()
    Manager, Setting = make_scale_classes(display, gui_resetters)
    game = types.SimpleNamespace(
        display=display,
        gui_resetters=gui_resetters,
        Manager=Manager,
        Setting=Setting,
        originals={
            (Manager, "changeScale"): Manager.__dict__["changeScale"],
            (Manager, "scaleChanged"): Manager.__dict__["scaleChanged"],
            (Setting, "setSystemValue"): Setting.__dict__["setSystemValue"],
        },
        bigworld=FakeBigWorld(display),
        api=FakeModsSettingsApi(),
        notes=[],
    )
    game.core = FakeSettingsCore(Manager, Setting, NATIVE_INDEX)
    # The client starts the native scale before mods load.
    game.core.change_scale_in_options(NATIVE_INDEX)
    game.core.interfaceScale.init()

    _install_game_modules(monkeypatch, game)
    game.entry, game.hooks, game.mods_settings = _import_mod_fresh()

    yield game
    game.entry.fini()
    _forget_mod_modules()
