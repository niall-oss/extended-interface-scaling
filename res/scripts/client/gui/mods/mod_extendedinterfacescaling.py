__version__ = "2.1.0"


def init():
    from gui.extendedinterfacescaling import config
    from gui.extendedinterfacescaling import hooks
    from gui.extendedinterfacescaling.api_detect import detect_scaling_api
    from gui.extendedinterfacescaling.mods_settings import register_mods_settings

    detect_scaling_api()
    config.load()
    hooks.install()
    register_mods_settings()


def fini():
    from gui.extendedinterfacescaling import hooks
    from gui.extendedinterfacescaling.mods_settings import unregister_mods_settings

    unregister_mods_settings()
    hooks.uninstall()
