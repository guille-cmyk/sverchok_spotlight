# DMX Universe and Address Patching Node for Sverchok Spotlight

import bpy
from bpy.props import IntProperty, BoolProperty

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode

class SvSpotlightDMXPatcherNode(SverchCustomTreeNode, bpy.types.Node):
    """Auto-patches fixtures across DMX universes with overflow and conflict checks"""
    bl_idname = 'SvSpotlightDMXPatcherNode'
    bl_label = 'Spotlight DMX Patcher'
    bl_icon = 'PREFERENCES'

    start_universe: IntProperty(name="Start Uni", default=1, min=1, max=256, update=updateNode)
    start_address: IntProperty(name="Start Addr", default=1, min=1, max=512, update=updateNode)
    channel_start: IntProperty(name="Start Ch", default=1, min=1, update=updateNode)
    address_gap: IntProperty(name="Gap", default=0, min=0, max=128, update=updateNode)
    auto_next_universe: BoolProperty(name="Wrap Universe (>512)", default=True, update=updateNode)

    def sv_init(self, context):
        self.inputs.new('SvDictionarySocket', "Fixtures")
        self.inputs.new('SvStringsSocket', "Start Universe").prop_name = 'start_universe'
        self.inputs.new('SvStringsSocket', "Start Address").prop_name = 'start_address'

        self.outputs.new('SvDictionarySocket', "Patched Fixtures")
        self.outputs.new('SvStringsSocket', "Patch Table")
        self.outputs.new('SvStringsSocket', "Universe Summary")
        self.outputs.new('SvStringsSocket', "Warnings")

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "start_universe")
        col.prop(self, "start_address")
        col.prop(self, "channel_start")
        col.prop(self, "address_gap")
        col.prop(self, "auto_next_universe")

    def process(self):
        outputs = self.outputs
        if not any(o.is_linked for o in outputs):
            return

        fixtures_in = self.inputs['Fixtures'].sv_get(default=[[]])[0]
        uni_in = self.inputs['Start Universe'].sv_get(default=[[self.start_universe]])[0]
        addr_in = self.inputs['Start Address'].sv_get(default=[[self.start_address]])[0]

        curr_uni = uni_in[0] if uni_in else self.start_universe
        curr_addr = addr_in[0] if addr_in else self.start_address
        curr_ch = self.channel_start

        patched_fixtures = []
        patch_table_rows = []
        warnings = []
        universe_usage = {}

        for fix in fixtures_in:
            if not isinstance(fix, dict):
                continue

            fix_copy = dict(fix)
            footprint = max(1, int(fix_copy.get("dmx_footprint", 1)))

            # Check 512 universe capacity limit
            if curr_addr + footprint - 1 > 512:
                if self.auto_next_universe:
                    curr_uni += 1
                    curr_addr = 1
                else:
                    msg = f"OVERFLOW: Fixture '{fix_copy.get('unit_id', 'Unknown')}' exceeds Universe {curr_uni} (End: {curr_addr + footprint - 1})"
                    warnings.append(msg)

            end_addr = curr_addr + footprint - 1
            fix_copy["channel"] = curr_ch
            fix_copy["universe"] = curr_uni
            fix_copy["address"] = curr_addr
            fix_copy["address_end"] = end_addr
            fix_copy["dmx_patch_str"] = f"U{curr_uni}:{curr_addr:03d}-{end_addr:03d}"

            # Track universe footprint usage
            if curr_uni not in universe_usage:
                universe_usage[curr_uni] = 0
            universe_usage[curr_uni] += footprint

            summary_row = f"Ch {curr_ch:03d} | U{curr_uni}:{curr_addr:03d} ({footprint:02d}ch) | {fix_copy.get('fixture_name', 'Fixture')} | {fix_copy.get('position', 'LX')}-{fix_copy.get('unit_number', '?')}"
            patch_table_rows.append(summary_row)
            patched_fixtures.append(fix_copy)

            curr_addr = end_addr + 1 + self.address_gap
            curr_ch += 1

        uni_summary_list = []
        for u, used in sorted(universe_usage.items()):
            pct = round((used / 512.0) * 100.0, 1)
            uni_summary_list.append(f"Universe {u}: {used}/512 channels used ({pct}%)")

        outputs['Patched Fixtures'].sv_set([patched_fixtures])
        outputs['Patch Table'].sv_set([patch_table_rows])
        outputs['Universe Summary'].sv_set([uni_summary_list])
        outputs['Warnings'].sv_set([warnings if warnings else ["No patch conflicts detected."]])

classes = [SvSpotlightDMXPatcherNode]
register, unregister = bpy.utils.register_classes_factory(classes)
