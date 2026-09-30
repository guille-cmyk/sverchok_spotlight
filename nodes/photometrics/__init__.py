from . import photometrics
from . import beam_material

modules = [
    photometrics,
    beam_material,
]

def register():
    for m in modules:
        m.register()

def unregister():
    for m in reversed(modules):
        m.unregister()
