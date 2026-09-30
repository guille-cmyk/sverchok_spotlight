# Hanging Position and Fixture Distribution Node for Sverchok Spotlight

import math
import bpy
from bpy.props import FloatProperty, IntProperty, StringProperty, EnumProperty
from mathutils import Vector, Matrix

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode

class SvSpotlightHangPositionNode(SverchCustomTreeNode, bpy.types.Node):
    """Defines a Hanging Position and calculates fixture clamp distribution"""
    bl_idname = 'SvSpotlightHangPositionNode'
    bl_label = 'Spotlight Hang Position'
    bl_icon = 'OUTLINER_DATA_CURVE'

    position_name: StringProperty(name="Position", default="LX 1", update=updateNode)
    unit_start: IntProperty(name="Start Unit", default=1, min=1, update=updateNode)
    unit_prefix: StringProperty(name="Prefix", default="", update=updateNode)
    fixture_count: IntProperty(name="Fixtures", default=6, min=1, max=128, update=updateNode)
    rail_length: FloatProperty(name="Length", default=8.0, min=0.5, step=50, update=updateNode)
    margin: FloatProperty(name="End Margin", default=0.5, min=0.0, step=10, update=updateNode)

    orientation: EnumProperty(
        name="Hang Style",
        items=[
            ('UNDERHUNG', 'Underhung (-Z)', 'Hanging below pipe/truss'),
            ('TOPHUNG', 'Top-hung (+Z)', 'Mounted on top of truss'),
            ('SIDEHUNG_L', 'Side-hung Left (-Y)', 'Mounted on stage left face'),
            ('SIDEHUNG_R', 'Side-hung Right (+Y)', 'Mounted on stage right face')
        ],
        default='UNDERHUNG',
        update=updateNode
    )

    distribution_mode: EnumProperty(
        name="Distribution",
        items=[
            ('EQUIDISTANT', 'Equidistant', 'Evenly spread across span'),
            ('FIXED_SPACING', 'Fixed Spacing', 'Fixed distance between fixtures')
        ],
        default='EQUIDISTANT',
        update=updateNode
    )
    spacing: FloatProperty(name="Spacing", default=1.2, min=0.1, step=10, update=updateNode)
    trim_height: FloatProperty(name="Trim Height", default=6.0, step=10, description="Hanging elevation above stage floor (Z)", update=updateNode)

    def sv_init(self, context):
        self.inputs.new('SvMatrixSocket', "Matrix")
        self.inputs.new('SvStringsSocket', "Length").prop_name = 'rail_length'
        self.inputs.new('SvStringsSocket', "Count").prop_name = 'fixture_count'

        self.outputs.new('SvMatrixSocket', "Hang Matrices")
        self.outputs.new('SvVerticesSocket', "Hang Points")
        self.outputs.new('SvDictionarySocket', "Position Data")
        self.outputs.new('SvVerticesSocket', "Rail Vertices")
        self.outputs.new('SvStringsSocket', "Rail Edges")

    def draw_buttons(self, context, layout):
        layout.prop(self, "position_name", text="Name")
        layout.prop(self, "orientation", text="")
        layout.prop(self, "distribution_mode", text="")
        layout.prop(self, "trim_height")
        if self.distribution_mode == 'FIXED_SPACING':
            layout.prop(self, "spacing")
        else:
            layout.prop(self, "margin")
        layout.prop(self, "unit_start")

    def process(self):
        outputs = self.outputs
        if not any(o.is_linked for o in outputs):
            return

        if self.inputs['Matrix'].is_linked:
            matrices = self.inputs['Matrix'].sv_get(default=[[Matrix.Identity(4)]])[0]
            base_mat = Matrix(matrices[0]) if matrices else Matrix.Identity(4)
        else:
            base_mat = Matrix.Translation(Vector((0.0, 0.0, self.trim_height)))

        lengths = self.inputs['Length'].sv_get(default=[[self.rail_length]])[0]
        counts = self.inputs['Count'].sv_get(default=[[self.fixture_count]])[0]

        L = lengths[0] if lengths else self.rail_length
        N = max(1, int(counts[0])) if counts else self.fixture_count

        half_l = L / 2.0
        start_x = -half_l
        end_x = half_l

        # Compute clamp positions along local X
        positions_x = []
        if self.distribution_mode == 'EQUIDISTANT':
            usable_len = max(0.1, L - 2.0 * self.margin)
            if N == 1:
                positions_x.append(0.0)
            else:
                step = usable_len / (N - 1)
                for i in range(N):
                    positions_x.append(start_x + self.margin + i * step)
        else:
            total_span = (N - 1) * self.spacing
            start_offset = -total_span / 2.0
            for i in range(N):
                positions_x.append(start_offset + i * self.spacing)

        # Orientation rotation matrix
        if self.orientation == 'UNDERHUNG':
            rot_hang = Matrix.Identity(4) # Standard rest pose (down)
        elif self.orientation == 'TOPHUNG':
            rot_hang = Matrix.Rotation(math.pi, 4, 'X')
        elif self.orientation == 'SIDEHUNG_L':
            rot_hang = Matrix.Rotation(-math.pi / 2.0, 4, 'X')
        else:  # SIDEHUNG_R
            rot_hang = Matrix.Rotation(math.pi / 2.0, 4, 'X')

        hang_matrices = []
        meta_data = []

        for i, px in enumerate(positions_x):
            unit_num = self.unit_start + i
            unit_id = f"{self.unit_prefix}{unit_num}" if self.unit_prefix else str(unit_num)
            
            local_mat = Matrix.Translation(Vector((px, 0.0, 0.0))) @ rot_hang
            world_mat = base_mat @ local_mat
            hang_matrices.append(world_mat)

            meta_data.append({
                "position": self.position_name,
                "unit_number": unit_id,
                "unit_index": unit_num,
                "orientation": self.orientation,
                "local_x": px
            })

        # Rail geometry (centerline)
        rail_verts = [
            (base_mat @ Vector((start_x, 0.0, 0.0)))[:],
            (base_mat @ Vector((end_x, 0.0, 0.0)))[:]
        ]
        rail_edges = [[0, 1]]

        hang_points = [list(m.to_translation()) for m in hang_matrices]

        outputs['Hang Matrices'].sv_set([hang_matrices])
        outputs['Hang Points'].sv_set([hang_points])
        outputs['Position Data'].sv_set([meta_data])
        outputs['Rail Vertices'].sv_set([rail_verts])
        outputs['Rail Edges'].sv_set([rail_edges])

classes = [SvSpotlightHangPositionNode]
register, unregister = bpy.utils.register_classes_factory(classes)
