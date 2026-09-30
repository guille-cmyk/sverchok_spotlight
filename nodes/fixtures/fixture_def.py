# Fixture Profile and Library Definition Node for Sverchok Spotlight
# Specifies photometric, electrical, mechanical, and light generator / emitter specs

import os
import bpy
from bpy.props import FloatProperty, IntProperty, StringProperty, EnumProperty

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode
from ...utils.presets import FIXTURE_PRESETS, PRESET_ENUM_ITEMS
from ...utils.fixture_importer import load_fixture_profile

def on_preset_change(self, context):
    preset = FIXTURE_PRESETS.get(self.preset_choice)
    if preset and self.preset_choice != 'Custom':
        self.fixture_name = preset.get("name", self.preset_choice)
        self.fixture_type = preset.get("type", "Moving Light")
        self.beam_angle = preset.get("beam_angle", 15.0)
        self.field_angle = preset.get("field_angle", 30.0)
        self.candela = preset.get("candela", 100000.0)
        self.weight_kg = preset.get("weight_kg", 15.0)
        self.wattage = preset.get("wattage", 300.0)
        self.dmx_footprint = preset.get("dmx_footprint", 16)
        self.emitter_offset = preset.get("emitter_offset", 0.36)
        self.lens_diameter = preset.get("lens_diameter", 0.15)
    updateNode(self, context)

def on_import_file_change(self, context):
    path = bpy.path.abspath(self.import_filepath.strip())
    if path and os.path.exists(path):
        try:
            prof = load_fixture_profile(path)
            self.preset_choice = 'Custom'
            self.fixture_name = prof.get("name", self.fixture_name)
            self.fixture_type = prof.get("type", self.fixture_type)
            self.beam_angle = prof.get("beam_angle", self.beam_angle)
            self.field_angle = prof.get("field_angle", self.field_angle)
            self.candela = prof.get("candela", self.candela)
            self.weight_kg = prof.get("weight_kg", self.weight_kg)
            self.wattage = prof.get("wattage", self.wattage)
            self.dmx_footprint = prof.get("dmx_footprint", self.dmx_footprint)
            self.emitter_offset = prof.get("emitter_offset", self.emitter_offset)
            self.lens_diameter = prof.get("lens_diameter", self.lens_diameter)
        except Exception as e:
            print("Failed to import profile into FixtureDef:", e)
    updateNode(self, context)

class SvSpotlightFixtureDefNode(SverchCustomTreeNode, bpy.types.Node):
    """Lighting Instrument Specification and Photometric Definition"""
    bl_idname = 'SvSpotlightFixtureDefNode'
    bl_label = 'Spotlight Fixture Def'
    bl_icon = 'LIGHT_SUN'

    preset_choice: EnumProperty(
        name="Preset",
        items=PRESET_ENUM_ITEMS,
        default="Robe Robin MegaPointe",
        update=on_preset_change
    )

    import_filepath: StringProperty(
        name="Import Profile",
        description="Optional: Load fixture from OFL JSON, GDTF, or QLC+ file",
        subtype='FILE_PATH',
        default="",
        update=on_import_file_change
    )

    fixture_name: StringProperty(name="Name", default="Robe Robin MegaPointe", update=updateNode)
    fixture_type: StringProperty(name="Type", default="Spot / Beam", update=updateNode)
    beam_angle: FloatProperty(name="Beam Angle", default=1.8, min=0.1, max=90.0, step=10, update=updateNode)
    field_angle: FloatProperty(name="Field Angle", default=21.0, min=0.1, max=120.0, step=10, update=updateNode)
    candela: FloatProperty(name="Candela (cd)", default=2200000.0, min=1.0, step=10000, update=updateNode)
    weight_kg: FloatProperty(name="Weight (kg)", default=22.0, min=0.1, step=10, update=updateNode)
    wattage: FloatProperty(name="Wattage (W)", default=470.0, min=1.0, step=10, update=updateNode)
    dmx_footprint: IntProperty(name="Footprint", default=39, min=1, max=512, update=updateNode)
    color_label: StringProperty(name="Color/Gel", default="Open White", update=updateNode)
    purpose: StringProperty(name="Purpose", default="Key Light", update=updateNode)

    emitter_offset: FloatProperty(
        name="Emitter Offset (m)",
        description="Distance from mounting clamp to light emitter / front lens (light generator position)",
        default=0.36,
        min=0.01,
        max=3.0,
        step=1,
        update=updateNode
    )

    lens_diameter: FloatProperty(
        name="Lens Diameter (m)",
        description="Diameter of front lens / light emitter aperture",
        default=0.15,
        min=0.01,
        max=1.0,
        step=1,
        update=updateNode
    )

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

    def draw_buttons(self, context, layout):
        layout.prop(self, "preset_choice", text="")
        layout.prop(self, "import_filepath", text="Load")
        box = layout.box()
        box.prop(self, "fixture_name", text="Model")
        box.prop(self, "purpose")
        box.prop(self, "color_label", text="Color")

        col = layout.column(align=True)
        col.prop(self, "beam_angle")
        col.prop(self, "field_angle")
        col.prop(self, "dmx_footprint")
        col.prop(self, "candela")
        col.prop(self, "emitter_offset")
        col.prop(self, "lens_diameter")
        col.prop(self, "weight_kg")
        col.prop(self, "wattage")

    def process(self):
        outputs = self.outputs
        if not any(o.is_linked for o in outputs):
            return

        profile = {
            "name": self.fixture_name,
            "type": self.fixture_type,
            "beam_angle": self.beam_angle,
            "field_angle": self.field_angle,
            "candela": self.candela,
            "weight_kg": self.weight_kg,
            "wattage": self.wattage,
            "dmx_footprint": self.dmx_footprint,
            "color": self.color_label,
            "purpose": self.purpose,
            "emitter_offset": self.emitter_offset,
            "lens_diameter": self.lens_diameter
        }

        outputs['Fixture Profile'].sv_set([[profile]])
        outputs['Beam Angle'].sv_set([[self.beam_angle]])
        outputs['Field Angle'].sv_set([[self.field_angle]])
        outputs['Footprint'].sv_set([[self.dmx_footprint]])
        outputs['Weight (kg)'].sv_set([[self.weight_kg]])
        outputs['Wattage (W)'].sv_set([[self.wattage]])
        outputs['Candela'].sv_set([[self.candela]])
        outputs['Emitter Offset'].sv_set([[self.emitter_offset]])
        outputs['Lens Diameter'].sv_set([[self.lens_diameter]])

classes = [SvSpotlightFixtureDefNode]
register, unregister = bpy.utils.register_classes_factory(classes)
