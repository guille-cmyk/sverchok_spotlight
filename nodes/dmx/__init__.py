from . import dmx_patcher
from . import paperwork
from . import live_dmx_mapper
from . import artnet_out
from . import pixel_mapper

modules = [
    dmx_patcher,
    paperwork,
    live_dmx_mapper,
    artnet_out,
    pixel_mapper,
]

def register():
    for m in modules:
        m.register()

def unregister():
    for m in reversed(modules):
        m.unregister()
