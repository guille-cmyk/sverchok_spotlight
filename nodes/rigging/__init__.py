from . import truss_gen
from . import hang_position

modules = [
    truss_gen,
    hang_position,
]

def register():
    for m in modules:
        m.register()

def unregister():
    for m in reversed(modules):
        m.unregister()
