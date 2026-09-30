# Fixture Profile Import Node for Sverchok Spotlight
# Imports Open Fixture Library (OFL) JSON, GDTF (.gdtf), QLC+ (.qxf), and Generic JSON files

import os
import bpy
from bpy.props import StringProperty, EnumProperty, FloatProperty, IntProperty, BoolProperty

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode
from ...utils.fixture_importer import load_fixture_profile

def get_sample_library_path():
    """Returns absolute path to bundled fixtures_library directory."""
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(addon_dir, "fixtures_library")

def on_file_path_changed(self, context):
    self.reload_file()
    updateNode(self, context)

def on_mode_index_changed(self, context):
    if hasattr(self, "_cached_profile") and self._cached_profile:
        modes = self._cached_profile.get("modes", [])
        if 0 <= self.mode_index < len(modes):
            target_mode = modes[self.mode_index]["name"]
            self.selected_mode = target_mode
            self.reload_file(target_mode)
    updateNode(self, context)


class SvSpotlightFixtureImportNode(SverchCustomTreeNode, bpy.types.Node):
    """Imports lighting fixture profiles from Open Fixture Library (OFL JSON), GDTF, or QLC+ XML"""
    bl_idname = 'SvSpotlightFixtureImportNode'
    bl_label = 'Spotlight Fixture Import'
    bl_icon = 'IMPORT'

    filepath: StringProperty(
        name="Profile File",
        description="Path to Open Fixture Library (.json), GDTF (.gdtf / .xml), or QLC+ (.qxf) file",
        subtype='FILE_PATH',
        default="",
        update=on_file_path_changed
    )

    selected_mode: StringProperty(
        name="Active Mode",
        description="Currently selected DMX personality / channel mode",
        default="Standard",
        update=updateNode
    )

    mode_index: IntProperty(
        name="Mode Index",
        description="Index of selected mode in fixture modes list",
        default=0,
        min=0,
        update=on_mode_index_changed
    )

    color_label: StringProperty(name="Color/Gel", default="Open White", update=updateNode)
    purpose: StringProperty(name="Purpose", default="Key Light", update=updateNode)

    # Cached inspection properties for UI display
    fixture_display_name: StringProperty(name="Fixture", default="No File Loaded")
    format_label: StringProperty(name="Format", default="None")
    total_modes_count: IntProperty(name="Modes Count", default=0)

    def sv_init(self, context):
        self.outputs.new('SvDictionarySocket', "Fixture Profile")
        self.outputs.new('SvStringsSocket', "Beam Angle")
        self.outputs.new('SvStringsSocket', "Field Angle")
        self.outputs.new('SvStringsSocket', "Footprint")
        self.outputs.new('SvStringsSocket', "Weight (kg)")
        self.outputs.new('SvStringsSocket', "Wattage (W)")
        self.outputs.new('SvStringsSocket', "Candela")
        self.outputs.new('SvStringsSocket', "Emitter Offset")
        self.outputs.new('SvStringsSocket', "Lens Diameter")
        self.outputs.new('SvStringsSocket', "Channels")
        self.outputs.new('SvStringsSocket', "Modes List")
        self.outputs.new('SvDictionarySocket', "Channel Map")

    def reload_file(self, target_mode=None):
        clean_path = bpy.path.abspath(self.filepath.strip())
        if not clean_path or not os.path.exists(clean_path):
            # Check relative to bundled sample library
            lib_dir = get_sample_library_path()
            candidate = os.path.join(lib_dir, os.path.basename(self.filepath.strip()))
            if os.path.exists(candidate):
                clean_path = candidate

        if clean_path and os.path.exists(clean_path):
            try:
                mode_to_use = target_mode or (self.selected_mode if self.selected_mode != "Standard" else None)
                prof = load_fixture_profile(clean_path, mode_name=mode_to_use)
                self._cached_profile = prof
                self.fixture_display_name = prof.get("name", "Unknown Fixture")
                self.format_label = prof.get("source_format", "Unknown Format")
                modes = prof.get("modes", [])
                self.total_modes_count = len(modes)
                self.selected_mode = prof.get("selected_mode", "Standard")
            except Exception as e:
                self.fixture_display_name = f"Error: {e}"
                self._cached_profile = None

    def draw_buttons(self, context, layout):
        layout.prop(self, "filepath", text="")
        
        box = layout.box()
        if hasattr(self, "_cached_profile") and self._cached_profile:
            p = self._cached_profile
            box.label(text=f"Model: {p.get('name', 'Unknown')}", icon='LIGHT')
            box.label(text=f"Format: {p.get('source_format', 'Unknown')}", icon='FILE')
            
            # Mode switcher
            modes = p.get("modes", [])
            if len(modes) > 1:
                row = box.row(align=True)
                row.prop(self, "mode_index", text=f"Mode ({self.mode_index+1}/{len(modes)})")
                row.label(text=p.get("selected_mode", ""))
            else:
                box.label(text=f"Mode: {p.get('selected_mode', 'Standard')} ({p.get('dmx_footprint', 16)}ch)")

            col = box.column(align=True)
            col.label(text=f"Beam: {p.get('beam_angle', 0.0)}° | Field: {p.get('field_angle', 0.0)}°")
            col.label(text=f"Weight: {p.get('weight_kg', 0.0)} kg | Power: {p.get('wattage', 0.0)} W")
            col.label(text=f"Emitter Offset: {p.get('emitter_offset', 0.35)} m")

            # Quick channel mapping indicator
            cmap = p.get("channel_map", {})
            mapped_attrs = []
            if cmap.get("pan", -1) != -1: mapped_attrs.append(f"Pan: ch{cmap['pan']}")
            if cmap.get("tilt", -1) != -1: mapped_attrs.append(f"Tilt: ch{cmap['tilt']}")
            if cmap.get("dimmer", -1) != -1: mapped_attrs.append(f"Dim: ch{cmap['dimmer']}")
            if mapped_attrs:
                box.label(text=" | ".join(mapped_attrs), icon='DRIVER')
        else:
            box.label(text="Select OFL JSON, GDTF, or QLC+ file", icon='INFO')
            if self.filepath:
                box.label(text=self.fixture_display_name, icon='ERROR')

        col2 = layout.column(align=True)
        col2.prop(self, "color_label", text="Color")
        col2.prop(self, "purpose", text="Purpose")

    def process(self):
        outputs = self.outputs

        clean_path = bpy.path.abspath(self.filepath.strip())
        if not hasattr(self, "_cached_profile") or self._cached_profile is None:
            self.reload_file()

        if hasattr(self, "_cached_profile") and self._cached_profile:
            profile = dict(self._cached_profile)
        else:
            # Fallback default profile
            profile = {
                "name": "Generic Spotlight",
                "type": "Moving Light",
                "beam_angle": 15.0,
                "field_angle": 30.0,
                "candela": 100000.0,
                "weight_kg": 15.0,
                "wattage": 300.0,
                "dmx_footprint": 16,
                "color": self.color_label,
                "purpose": self.purpose,
                "emitter_offset": 0.36,
                "lens_diameter": 0.15,
                "channels": [f"Channel {i+1}" for i in range(16)],
                "modes": [{"name": "Standard", "footprint": 16, "channels": [f"Ch {i+1}" for i in range(16)]}],
                "channel_map": {"pan": 1, "pan_fine": 2, "tilt": 3, "tilt_fine": 4, "dimmer": 5}
            }

        profile["color"] = self.color_label
        profile["purpose"] = self.purpose

        outputs['Fixture Profile'].sv_set([[profile]])
        outputs['Beam Angle'].sv_set([[profile.get('beam_angle', 15.0)]])
        outputs['Field Angle'].sv_set([[profile.get('field_angle', 30.0)]])
        outputs['Footprint'].sv_set([[profile.get('dmx_footprint', 16)]])
        outputs['Weight (kg)'].sv_set([[profile.get('weight_kg', 15.0)]])
        outputs['Wattage (W)'].sv_set([[profile.get('wattage', 300.0)]])
        outputs['Candela'].sv_set([[profile.get('candela', 100000.0)]])
        outputs['Emitter Offset'].sv_set([[profile.get('emitter_offset', 0.36)]])
        outputs['Lens Diameter'].sv_set([[profile.get('lens_diameter', 0.15)]])
        outputs['Channels'].sv_set([[profile.get('channels', [])]])
        outputs['Modes List'].sv_set([[[m['name'] for m in profile.get('modes', [])]]])
        outputs['Channel Map'].sv_set([[profile.get('channel_map', {})]])


classes = [SvSpotlightFixtureImportNode]
register, unregister = bpy.utils.register_classes_factory(classes)
