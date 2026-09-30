from . import fixture_def
from . import fixture_import
from . import instrument_array

modules = [
    fixture_def,
    fixture_import,
    instrument_array,
]

def register():
    for m in modules:
        m.register()

def unregister():
    for m in reversed(modules):
        m.unregister()
