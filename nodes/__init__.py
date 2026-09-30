from . import rigging
from . import fixtures
from . import focus
from . import photometrics
from . import dmx
from . import exchange

subpackages = [
    rigging,
    fixtures,
    focus,
    photometrics,
    dmx,
    exchange,
]

def register():
    for pkg in subpackages:
        pkg.register()

def unregister():
    for pkg in reversed(subpackages):
        pkg.unregister()
