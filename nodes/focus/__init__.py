from . import focus_aim

modules = [
    focus_aim,
]

def register():
    for m in modules:
        m.register()

def unregister():
    for m in reversed(modules):
        m.unregister()
