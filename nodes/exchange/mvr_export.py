# Sverchok Spotlight - MVR (My Virtual Rig) Exporter Node
# Industry Standard DIN SPEC 15800 Exchange Format for Vectorworks, grandMA3, wysiwyg, Capture

import os
import uuid
import zipfile
import bpy
from mathutils import Matrix
from bpy.props import StringProperty, BoolProperty
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode as update_node


def format_mvr_matrix(mat_4x4):
    """
    Formats a 4x4 matrix into DIN SPEC 15800 MVR 3x4 row notation:
    {m00,m01,m02,tx}{m10,m11,m12,ty}{m20,m21,m22,tz}
    """
    if mat_4x4 is None:
        mat = Matrix.Identity(4)
    elif isinstance(mat_4x4, (list, tuple)):
        try:
            mat = Matrix(mat_4x4)
        except Exception:
            mat = Matrix.Identity(4)
    elif isinstance(mat_4x4, Matrix):
        mat = mat_4x4
    else:
        mat = Matrix.Identity(4)

    r0 = f"{{{mat[0][0]:.4f},{mat[0][1]:.4f},{mat[0][2]:.4f},{mat[0][3]:.4f}}}"
    r1 = f"{{{mat[1][0]:.4f},{mat[1][1]:.4f},{mat[1][2]:.4f},{mat[1][3]:.4f}}}"
    r2 = f"{{{mat[2][0]:.4f},{mat[2][1]:.4f},{mat[2][2]:.4f},{mat[2][3]:.4f}}}"
    return f"{r0}{r1}{r2}"


class SV_OT_SpotlightMVRExport(bpy.types.Operator):
    """Exports MVR (My Virtual Rig) zip archive for grandMA3 and Vectorworks"""
    bl_idname = "node.sv_spotlight_mvr_export"
    bl_label = "Export MVR Rig"
    bl_options = {'REGISTER', 'UNDO'}

    node_name: StringProperty(name="Node Name", default="")
    tree_name: StringProperty(name="Tree Name", default="")

    def execute(self, context):
        try:
            tree = bpy.data.node_groups.get(self.tree_name)
            if not tree:
                self.report({'WARNING'}, f"Node tree '{self.tree_name}' not found.")
                return {'CANCELLED'}
            node = tree.nodes.get(self.node_name)
            if not node:
                self.report({'WARNING'}, f"Node '{self.node_name}' not found.")
                return {'CANCELLED'}

            count, path = node.export_mvr()
            self.report({'INFO'}, f"MVR: Exported {count} fixtures to {path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"MVR export failed: {e}")
            return {'CANCELLED'}


class SvSpotlightMVRExportNode(bpy.types.Node, SverchCustomTreeNode):
    """
    Exports parametric fixtures and trusses to standard DIN SPEC 15800 MVR (.mvr) format,
    seamlessly interoperable with Vectorworks Spotlight, grandMA3, and Capture.
    """
    bl_idname = 'SvSpotlightMVRExportNode'
    bl_label = 'Spotlight MVR Export'
    bl_icon = 'PACKAGE'
    sv_icon = 'SV_COLOR_ROUGHNESS'

    file_path: StringProperty(
        name="MVR File Path",
        description="Path to save .mvr archive (e.g. //rig.mvr)",
        default="//spotlight_rig.mvr",
        subtype='FILE_PATH',
        update=update_node
    )

    layer_name: StringProperty(
        name="Layer Name",
        description="Name of lighting layer in MVR scene",
        default="Spotlight Rig",
        update=update_node
    )

    create_blender_text: BoolProperty(
        name="Blender XML Text",
        description="Also store GeneralSceneDescription.xml in Blender text editor",
        default=True,
        update=update_node
    )

    last_status: StringProperty(
        name="Status",
        default="Ready"
    )

    def sv_init(self, context):
        self.inputs.new('SvStringsSocket', 'Fixtures')
        self.inputs.new('SvStringsSocket', 'Trusses')
        self.inputs.new('SvStringsSocket', 'File Path').prop_name = 'file_path'

        self.outputs.new('SvStringsSocket', 'XML Text')
        self.outputs.new('SvStringsSocket', 'MVR Path')
        self.outputs.new('SvStringsSocket', 'Status')

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, 'file_path')
        col.prop(self, 'layer_name')
        col.prop(self, 'create_blender_text')

        op = col.operator('node.sv_spotlight_mvr_export', text="Export .mvr Archive", icon='EXPORT')
        op.node_name = self.name
        op.tree_name = self.id_data.name if self.id_data else ""

        col.label(text=self.last_status, icon='INFO')

    def build_mvr_xml(self, fixtures, trusses=None):
        """Builds GeneralSceneDescription.xml compliant with DIN SPEC 15800."""
        layer_uuid = str(uuid.uuid4())
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<GeneralSceneDescription verMajor="1" verMinor="6" xmlns="http://schemas.mvr.org/mvr/1.6">',
            '  <UserDataProvider name="Sverchok Spotlight" version="1.0" />',
            '  <Scene>',
            '    <Layers>',
            f'      <Layer name="{self.layer_name}" uuid="{layer_uuid}">',
        ]

        # Export Fixtures
        for idx, fix in enumerate(fixtures):
            fix_uuid = str(uuid.uuid4())
            name = fix.get('name', f"Fixture {idx+1}")
            fid = fix.get('unit_number', idx + 1)
            u = fix.get('universe', 1)
            a = fix.get('address', 1)
            ftype = fix.get('fixture_type', 'Spot')
            gdtf_spec = f"{ftype.replace(' ', '_')}.gdtf"

            mat = fix.get('aimed_matrix') or fix.get('matrix') or fix.get('hang_matrix') or Matrix.Identity(4)
            mat_str = format_mvr_matrix(mat)

            lines.append(f'        <Fixture name="{name}" uuid="{fix_uuid}" fid="{fid}" cid="{fid}">')
            lines.append(f'          <Matrix>{mat_str}</Matrix>')
            lines.append(f'          <GDTFSpec>{gdtf_spec}</GDTFSpec>')
            lines.append('          <GDTFMode>Default</GDTFMode>')
            lines.append('          <Addresses>')
            lines.append('            <Address>')
            lines.append('              <Break>1</Break>')
            lines.append(f'              <Universe>{u}</Universe>')
            lines.append(f'              <Address>{a}</Address>')
            lines.append('            </Address>')
            lines.append('          </Addresses>')
            lines.append('        </Fixture>')

        # Export Trusses (if any)
        if trusses:
            for t_idx, truss in enumerate(trusses):
                t_uuid = str(uuid.uuid4())
                t_name = truss.get('name', f"Truss {t_idx+1}") if isinstance(truss, dict) else f"Truss {t_idx+1}"
                t_mat = truss.get('matrix', Matrix.Identity(4)) if isinstance(truss, dict) else truss
                t_mat_str = format_mvr_matrix(t_mat)

                lines.append(f'        <Truss name="{t_name}" uuid="{t_uuid}">')
                lines.append(f'          <Matrix>{t_mat_str}</Matrix>')
                lines.append('        </Truss>')

        lines.extend([
            '      </Layer>',
            '    </Layers>',
            '  </Scene>',
            '</GeneralSceneDescription>'
        ])

        return "\n".join(lines)

    def export_mvr(self):
        """Constructs and writes the .mvr zip file containing GeneralSceneDescription.xml."""
        if not self.inputs['Fixtures'].is_linked:
            self.last_status = "No fixtures linked"
            return 0, ""

        raw_in = self.inputs['Fixtures'].sv_get()
        fixtures = []
        if isinstance(raw_in, list):
            for item in raw_in:
                if isinstance(item, list):
                    fixtures.extend([x for x in item if isinstance(x, dict)])
                elif isinstance(item, dict):
                    fixtures.append(item)

        if not fixtures:
            self.last_status = "No fixture dictionaries found"
            return 0, ""

        trusses = []
        if self.inputs['Trusses'].is_linked:
            raw_t = self.inputs['Trusses'].sv_get()
            if isinstance(raw_t, list):
                for item in raw_t:
                    if isinstance(item, list):
                        trusses.extend(item)
                    else:
                        trusses.append(item)

        xml_data = self.build_mvr_xml(fixtures, trusses)

        if self.create_blender_text:
            txt_block = bpy.data.texts.get("GeneralSceneDescription.xml") or bpy.data.texts.new("GeneralSceneDescription.xml")
            txt_block.clear()
            txt_block.write(xml_data)

        resolved_path = bpy.path.abspath(self.file_path)
        if not resolved_path.lower().endswith('.mvr'):
            resolved_path += '.mvr'

        try:
            os.makedirs(os.path.dirname(os.path.abspath(resolved_path)), exist_ok=True)
            with zipfile.ZipFile(resolved_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr('GeneralSceneDescription.xml', xml_data)
            self.last_status = f"Exported {len(fixtures)} fixtures to MVR"
        except Exception as err:
            self.last_status = f"MVR write error: {err}"

        return len(fixtures), resolved_path

    def process(self):
        if not self.inputs['Fixtures'].is_linked:
            return

        raw_in = self.inputs['Fixtures'].sv_get()
        fixtures = []
        if isinstance(raw_in, list):
            for item in raw_in:
                if isinstance(item, list):
                    fixtures.extend([x for x in item if isinstance(x, dict)])
                elif isinstance(item, dict):
                    fixtures.append(item)

        if not fixtures:
            return

        trusses = []
        if self.inputs['Trusses'].is_linked:
            raw_t = self.inputs['Trusses'].sv_get()
            if isinstance(raw_t, list):
                for item in raw_t:
                    if isinstance(item, list):
                        trusses.extend(item)
                    else:
                        trusses.append(item)

        xml_data = self.build_mvr_xml(fixtures, trusses)
        resolved_path = bpy.path.abspath(self.file_path)

        self.outputs['XML Text'].sv_set([xml_data])
        self.outputs['MVR Path'].sv_set([resolved_path])
        self.outputs['Status'].sv_set([self.last_status])


def register():
    bpy.utils.register_class(SV_OT_SpotlightMVRExport)
    bpy.utils.register_class(SvSpotlightMVRExportNode)

def unregister():
    bpy.utils.unregister_class(SvSpotlightMVRExportNode)
    bpy.utils.unregister_class(SV_OT_SpotlightMVRExport)
