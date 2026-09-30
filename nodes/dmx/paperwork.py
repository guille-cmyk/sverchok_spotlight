# Paperwork, Instrument Schedule, Channel Hookup, and CSV Export Node for Sverchok Spotlight

import os
import csv
import bpy
from bpy.props import StringProperty, EnumProperty
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode

PAPERWORK_CACHE = {}

class SV_OT_SpotlightExportPaperwork(bpy.types.Operator):
    """Exports the generated lighting paperwork to a CSV file or Blender Text datablock"""
    bl_idname = "node.spotlight_export_paperwork"
    bl_label = "Export CSV"
    bl_options = {'REGISTER', 'UNDO'}

    node_name: StringProperty(default="")
    tree_name: StringProperty(default="")

    def execute(self, context):
        cache = PAPERWORK_CACHE.get(self.node_name)
        if not cache or not cache.get("rows"):
            self.report({'WARNING'}, "No paperwork data available to export")
            return {'CANCELLED'}

        report_type = cache.get("report_type", "INSTRUMENT_SCHEDULE")
        cached_text = cache.get("text", "")
        cached_rows = cache.get("rows", [])
        export_path = cache.get("export_path", "")

        # 1. Create or update Blender Text datablock
        text_name = f"{report_type.replace(' ', '_')}.txt"
        text_block = bpy.data.texts.get(text_name) or bpy.data.texts.new(text_name)
        text_block.clear()
        text_block.write(cached_text)

        # 2. If export path is defined, write CSV file
        out_path = bpy.path.abspath(export_path) if export_path else ""
        if out_path:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
                with open(out_path, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for row in cached_rows:
                        writer.writerow(row)
                self.report({'INFO'}, f"Exported {len(cached_rows)} rows to {out_path} and Text '{text_name}'")
            except Exception as e:
                self.report({'ERROR'}, f"Failed to write CSV: {e}")
                return {'CANCELLED'}
        else:
            self.report({'INFO'}, f"Saved paperwork to Blender Text Editor as '{text_name}'")

        return {'FINISHED'}


class SvSpotlightPaperworkNode(SverchCustomTreeNode, bpy.types.Node):
    """Generates Vectorworks-style Instrument Schedule, Channel Hookup, and Rig Summaries"""
    bl_idname = 'SvSpotlightPaperworkNode'
    bl_label = 'Spotlight Paperwork'
    bl_icon = 'TEXT'

    report_type: EnumProperty(
        name="Report",
        items=[
            ('INSTRUMENT_SCHEDULE', 'Instrument Schedule', 'Grouped by Position and Unit Number'),
            ('CHANNEL_HOOKUP', 'Channel Hookup', 'Sorted strictly by DMX Channel'),
            ('RIG_SUMMARY', 'Weight & Power Summary', 'Totals per position and whole rig')
        ],
        default='INSTRUMENT_SCHEDULE',
        update=updateNode
    )

    export_path: StringProperty(
        name="CSV Path",
        subtype='FILE_PATH',
        default="//lighting_schedule.csv",
        update=updateNode
    )

    # In-memory storage for operator export
    cached_text: str = ""
    cached_rows: list = []

    def sv_init(self, context):
        self.inputs.new('SvDictionarySocket', "Patched Fixtures")

        self.outputs.new('SvStringsSocket', "Report Text")
        self.outputs.new('SvStringsSocket', "Total Weight (kg)")
        self.outputs.new('SvStringsSocket', "Total Power (kW)")
        self.outputs.new('SvStringsSocket', "Current 230V (A)")
        self.outputs.new('SvStringsSocket', "Current 120V (A)")

    def draw_buttons(self, context, layout):
        layout.prop(self, "report_type", text="")
        layout.prop(self, "export_path", text="CSV")

        op = layout.operator("node.spotlight_export_paperwork", text="Export CSV / Text", icon='EXPORT')
        op.node_name = self.name
        op.tree_name = self.id_data.name if self.id_data else ""

    def process(self):
        outputs = self.outputs

        fixtures = self.inputs['Patched Fixtures'].sv_get(default=[[]])[0]
        if not fixtures:
            outputs['Report Text'].sv_set([["No fixture data connected."]])
            return

        total_weight = sum(float(f.get("weight_kg", 0.0)) for f in fixtures)
        total_power_w = sum(float(f.get("wattage", 0.0)) for f in fixtures)
        total_power_kw = round(total_power_w / 1000.0, 2)
        amps_230 = round(total_power_w / 230.0, 1)
        amps_120 = round(total_power_w / 120.0, 1)

        headers = []
        rows = []

        if self.report_type == 'INSTRUMENT_SCHEDULE':
            headers = ["Position", "Unit #", "Fixture Type", "Channel", "DMX Patch", "Purpose", "Color", "Weight (kg)", "Wattage (W)"]
            sorted_fixes = sorted(fixtures, key=lambda f: (f.get("position", ""), str(f.get("unit_number", ""))))
            for f in sorted_fixes:
                rows.append([
                    f.get("position", "-"),
                    str(f.get("unit_number", "-")),
                    f.get("fixture_name", "-"),
                    str(f.get("channel", "-")),
                    f.get("dmx_patch_str", f"U{f.get('universe', 1)}:{f.get('address', 1)}"),
                    f.get("purpose", "-"),
                    f.get("color", "-"),
                    str(f.get("weight_kg", "-")),
                    str(f.get("wattage", "-"))
                ])

        elif self.report_type == 'CHANNEL_HOOKUP':
            headers = ["Channel", "DMX Patch", "Fixture Type", "Position", "Unit #", "Purpose", "Color", "Footprint"]
            sorted_fixes = sorted(fixtures, key=lambda f: int(f.get("channel", 9999)))
            for f in sorted_fixes:
                rows.append([
                    str(f.get("channel", "-")),
                    f.get("dmx_patch_str", f"U{f.get('universe', 1)}:{f.get('address', 1)}"),
                    f.get("fixture_name", "-"),
                    f.get("position", "-"),
                    str(f.get("unit_number", "-")),
                    f.get("purpose", "-"),
                    f.get("color", "-"),
                    str(f.get("dmx_footprint", "-"))
                ])

        else:  # RIG_SUMMARY
            headers = ["Position", "Fixture Count", "Weight (kg)", "Power (W)", "Amps @ 230V"]
            by_pos = {}
            for f in fixtures:
                p = f.get("position", "Unassigned")
                if p not in by_pos:
                    by_pos[p] = {"count": 0, "weight": 0.0, "power": 0.0}
                by_pos[p]["count"] += 1
                by_pos[p]["weight"] += float(f.get("weight_kg", 0.0))
                by_pos[p]["power"] += float(f.get("wattage", 0.0))

            for pos, data in sorted(by_pos.items()):
                rows.append([
                    pos,
                    str(data["count"]),
                    f"{data['weight']:.1f}",
                    f"{data['power']:.0f}",
                    f"{data['power'] / 230.0:.1f} A"
                ])
            rows.append(["--- TOTAL RIG ---", str(len(fixtures)), f"{total_weight:.1f} kg", f"{total_power_kw:.2f} kW", f"{amps_230:.1f} A"])

        # Format ASCII table
        col_widths = [len(h) for h in headers]
        for r in rows:
            for i, val in enumerate(r):
                col_widths[i] = max(col_widths[i], len(str(val)))

        def fmt_row(vals):
            return " | ".join(str(v).ljust(col_widths[i]) for i, v in enumerate(vals))

        line_sep = "-+-".join("-" * w for w in col_widths)
        text_lines = [
            f"=== SPOTLIGHT {self.report_type.replace('_', ' ')} ===",
            fmt_row(headers),
            line_sep
        ]
        for r in rows:
            text_lines.append(fmt_row(r))

        self.cached_text = "\n".join(text_lines)
        self.cached_rows = [headers] + rows

        PAPERWORK_CACHE[self.name] = {
            "text": self.cached_text,
            "rows": self.cached_rows,
            "report_type": self.report_type,
            "export_path": self.export_path,
        }

        outputs['Report Text'].sv_set([text_lines])
        outputs['Total Weight (kg)'].sv_set([[round(total_weight, 1)]])
        outputs['Total Power (kW)'].sv_set([[total_power_kw]])
        outputs['Current 230V (A)'].sv_set([[amps_230]])
        outputs['Current 120V (A)'].sv_set([[amps_120]])

classes = [
    SV_OT_SpotlightExportPaperwork,
    SvSpotlightPaperworkNode
]
register, unregister = bpy.utils.register_classes_factory(classes)
