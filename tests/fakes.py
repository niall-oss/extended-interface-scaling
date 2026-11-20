"""Stand-ins for the game and ModsSettings API 1.7.1 objects the mod talks to.

Behaviour mirrors the sources pinned in docs/DECOMPILED_REFERENCE.md.
"""

import copy
import itertools
import types

INTERFACE_SCALE = "interfaceScale"


class Event(list):
    """Same semantics as the game's common/Event.py."""

    def __iadd__(self, delegate):
        if delegate not in self:
            self.append(delegate)
        return self

    def __isub__(self, delegate):
        if delegate in self:
            self.remove(delegate)
        return self

    def __call__(self, *args):
        for delegate in self[:]:
            delegate(*args)


class Display:
    """What the client is currently rendering, as set through the game APIs."""

    def __init__(self, screen, native):
        self.screen = screen
        self.native = native
        self.app_scale = None
        self.glyph_cache_scale = None
        self.graphics_scale = None


class FakeBigWorld:
    def __init__(self, display):
        self.display = display
        self.callbacks = {}
        self._ids = itertools.count(1)

    def callback(self, delay, fn):
        callback_id = next(self._ids)
        self.callbacks[callback_id] = fn
        return callback_id

    def cancelCallback(self, callback_id):
        self.callbacks.pop(callback_id, None)

    def run_callbacks(self):
        pending, self.callbacks = self.callbacks, {}
        for fn in pending.values():
            fn()

    def getNativeScreenResolution(self, monitor):
        return self.display.native

    def screenSize(self):
        return self.display.screen


class FakeMonitorSettings:
    currentMonitor = 0

    def __init__(self, display):
        self.display = display

    def isWindowed(self):
        return False

    def isBorderless(self):
        return False

    @property
    def currentVideoMode(self):
        width, height = self.display.screen
        return types.SimpleNamespace(width=width, height=height)

    def setGlyphCache(self, scale):
        self.display.glyph_cache_scale = scale


def make_scale_classes(display, gui_resetters):
    """Fresh copies of the classes the mod overrides, shaped like 2.4.1_EU."""

    class InterfaceScaleManager:
        onScaleChanged = Event()
        onScaleExactlyChanged = Event()

        def __init__(self, settings_core):
            self.proxy = settings_core
            self.__index = None
            self.__scaleValue = None

        def init(self):
            gui_resetters.add(self.scaleChanged)
            self.scaleChanged()

        def get(self):
            return self.__scaleValue

        def scaleChanged(self):
            self.changeScale(self.proxy.getSetting(INTERFACE_SCALE))

        def changeScale(self, index):
            self.__index = index
            previous = self.__scaleValue
            self.__scaleValue = self.getScaleByIndex(index)
            self.onScaleChanged(self.__scaleValue)
            display.graphics_scale = self.__scaleValue
            if previous != self.__scaleValue:
                self.onScaleExactlyChanged(self.__scaleValue)

        def getScaleByIndex(self, index):
            return 2.0 ** (index - 1)

    class InterfaceScaleSetting:
        def __init__(self, settings_core, value):
            self.settings_core = settings_core
            self.__interfaceScale = value

        def get(self):
            return self.__interfaceScale

        def setSystemValue(self, value):
            self.__interfaceScale = value
            scale = self.settings_core.interfaceScale.getScaleByIndex(value)
            display.app_scale = scale
            display.glyph_cache_scale = scale

    return InterfaceScaleManager, InterfaceScaleSetting


class FakeSettingsContainer:
    def __init__(self, settings):
        self.settings = settings

    def getSetting(self, name):
        return self.settings[name]


class FakeSettingsCore:
    def __init__(self, manager_cls, setting_cls, native_index):
        self.options = FakeSettingsContainer(
            {INTERFACE_SCALE: setting_cls(self, native_index)}
        )
        self.interfaceScale = manager_cls(self)

    def getSetting(self, name):
        return self.options.getSetting(name).get()

    def change_scale_in_options(self, index):
        """The Options menu path: InterfaceScaleSetting._set -> setSystemValue."""
        self.options.getSetting(INTERFACE_SCALE).setSystemValue(index)


class FakeModsSettingsApi:
    """The parts of ModsSettings API 1.7.1 (api.py, view.py) the mod relies on."""

    def __init__(self):
        self.state = {"settings": {}, "templates": {}, "storage": {}}
        self.activeMods = set()
        self.onSettingsChanged = Event()
        self.onButtonClicked = Event()
        self.onWindowOpened = Event()
        self.onWindowClosed = Event()

    def saveState(self):
        pass

    def setModTemplate(self, linkage, template, callback, buttonHandler=None):
        self.activeMods.add(linkage)
        current = self.state["templates"].get(linkage)
        if not current or self.compareTemplates(template, current):
            self.state["templates"][linkage] = template
            self.state["settings"][linkage] = self.getSettingsFromTemplate(template)
        self.onSettingsChanged += callback
        if buttonHandler is not None:
            self.onButtonClicked += buttonHandler
        return self.getModSettings(linkage, self.state["templates"][linkage])

    def getModSettings(self, linkage, template):
        current = self.state["templates"].get(linkage)
        if template and current:
            self.activeMods.add(linkage)
            if not self.compareTemplates(template, current):
                return self.state["settings"].get(linkage)
        return None

    def registerCallback(self, linkage, callback, buttonHandler=None):
        self.activeMods.add(linkage)
        self.onSettingsChanged += callback
        if buttonHandler is not None:
            self.onButtonClicked += buttonHandler

    def updateModSettings(self, linkage, newSettings):
        self.state["settings"][linkage] = newSettings
        self.onSettingsChanged(linkage, newSettings)

    def compareTemplates(self, newTemplate, oldTemplate):
        return newTemplate["settingsVersion"] > oldTemplate["settingsVersion"]

    def getSettingsFromTemplate(self, template):
        result = {}
        if "enabled" in template:
            result["enabled"] = template["enabled"]
        for column in ("column1", "column2"):
            for component in template.get(column, []):
                if "varName" in component and "value" in component:
                    result[component["varName"]] = component["value"]
        return result

    def generateSettingsData(self):
        result = []
        for linkage in sorted(self.state["templates"]):
            template = copy.deepcopy(self.state["templates"][linkage])
            settings = self.getModSettings(linkage, template)
            template["linkage"] = linkage
            if "enabled" in template:
                template["enabled"] = settings["enabled"]
            for column in ("column1", "column2"):
                for component in template.get(column, []):
                    if "varName" in component:
                        component["value"] = settings[component["varName"]]
            result.append(template)
        return result

    def open_window(self):
        """view.py: _populate fires onWindowOpened, then Flash requests data."""
        self.onWindowOpened()
        return self.generateSettingsData()

    def apply(self, linkage, settings):
        self.updateModSettings(linkage, settings)

    def click_button(self, linkage, varName, value):
        self.onButtonClicked(linkage, varName, value)


def make_templates_module():
    module = types.ModuleType("gui.modsSettingsApi.templates")
    module.createLabel = lambda text, tooltip="": {"type": "Label", "text": text}
    module.createEmpty = lambda: {"type": "Empty"}
    module.createInput = lambda text, varName, value, **kwargs: {
        "type": "TextInput",
        "text": text,
        "varName": varName,
        "value": value,
    }
    module.createButton = lambda **kwargs: dict(kwargs, type="Button")
    return module
