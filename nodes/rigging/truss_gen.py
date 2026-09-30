# Parametric Truss Generator Node for Sverchok Spotlight

import math
import bpy
from bpy.props import FloatProperty, IntProperty, EnumProperty
from mathutils import Vector, Matrix

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode

class SvSpotlightTrussNode(SverchCustomTreeNode, bpy.types.Node):
    """Parametric Truss Generator (Box, Triangle, Ladder)"""
    bl_idname = 'SvSpotlightTrussNode'
    bl_label = 'Spotlight Truss'
    bl_icon = 'GRID'

    truss_type: EnumProperty(
        name="Type",
        items=[
            ('BOX', 'Box Truss (F34)', '4 Chords square/rectangular truss'),
            ('TRIANGLE_APEX_UP', 'Triangle Apex Up', '3 Chords triangle truss apex up'),
            ('TRIANGLE_APEX_DOWN', 'Triangle Apex Down', '3 Chords triangle truss apex down'),
            ('LADDER', 'Ladder Truss', '2 Chords flat ladder truss')
        ],
        default='BOX',
        update=updateNode
    )

    lacing_style: EnumProperty(
        name="Lacing",
        items=[
            ('ZIGZAG', 'Zig-Zag', 'Alternating diagonal bracing'),
            ('CROSS', 'Cross (X)', 'Double cross bracing')
        ],
        default='ZIGZAG',
        update=updateNode
    )

    truss_length: FloatProperty(name="Length", default=3.0, min=0.2, step=10, update=updateNode)
    truss_width: FloatProperty(name="Width", default=0.29, min=0.05, step=1, update=updateNode)
    truss_height: FloatProperty(name="Height", default=0.29, min=0.05, step=1, update=updateNode)
    bay_length: FloatProperty(name="Bay Length", default=0.5, min=0.1, step=5, update=updateNode)
    clamp_count: IntProperty(name="Clamp Count", default=4, min=1, max=100, update=updateNode)
    trim_height: FloatProperty(name="Trim Height", default=6.0, step=10, description="Truss elevation above stage floor (Z)", update=updateNode)

    def sv_init(self, context):
        self.inputs.new('SvStringsSocket', "Length").prop_name = 'truss_length'
        self.inputs.new('SvStringsSocket', "Width").prop_name = 'truss_width'
        self.inputs.new('SvStringsSocket', "Height").prop_name = 'truss_height'
        self.inputs.new('SvMatrixSocket', "Matrix")

        self.outputs.new('SvVerticesSocket', "Vertices")
        self.outputs.new('SvStringsSocket', "Edges")
        self.outputs.new('SvStringsSocket', "Polygons")
        self.outputs.new('SvVerticesSocket', "Bottom Chords")
        self.outputs.new('SvMatrixSocket', "Clamp Matrices")

    def draw_buttons(self, context, layout):
        layout.prop(self, "truss_type", text="")
        layout.prop(self, "lacing_style", text="")
        layout.prop(self, "trim_height")
        layout.prop(self, "clamp_count")

    def _generate_box_truss(self, L, W, H, bay_len, clamp_cnt):
        num_bays = max(1, int(round(L / bay_len)))
        dx = L / num_bays
        half_w = W / 2.0
        half_h = H / 2.0

        # Define 4 chord profiles at each bay boundary:
        # 0: bottom-left (-Y, -Z), 1: bottom-right (+Y, -Z)
        # 2: top-right (+Y, +Z),   3: top-left (-Y, +Z)
        profiles = [
            (-half_w, -half_h),
            (+half_w, -half_h),
            (+half_w, +half_h),
            (-half_w, +half_h),
        ]

        verts = []
        edges = []

        # Generate chord vertices along length X (from -L/2 to +L/2)
        start_x = -L / 2.0
        for b in range(num_bays + 1):
            x = start_x + b * dx
            for py, pz in profiles:
                verts.append([x, py, pz])

        # Longitudinal chord edges
        for b in range(num_bays):
            idx_b = b * 4
            idx_next = (b + 1) * 4
            for c in range(4):
                edges.append([idx_b + c, idx_next + c])

        # Cross frames at bay boundaries and lacing
        for b in range(num_bays + 1):
            idx = b * 4
            edges.append([idx + 0, idx + 1])
            edges.append([idx + 1, idx + 2])
            edges.append([idx + 2, idx + 3])
            edges.append([idx + 3, idx + 0])

        # Diagonal lacing for each face: 4 faces (bottom, right, top, left)
        face_chords = [
            (0, 1), # Bottom
            (1, 2), # Right
            (2, 3), # Top
            (3, 0)  # Left
        ]

        for b in range(num_bays):
            i0 = b * 4
            i1 = (b + 1) * 4
            for c_a, c_b in face_chords:
                v_bl = i0 + c_a
                v_br = i0 + c_b
                v_tl = i1 + c_a
                v_tr = i1 + c_b

                if self.lacing_style == 'CROSS':
                    edges.append([v_bl, v_tr])
                    edges.append([v_br, v_tl])
                else:  # ZIGZAG
                    if b % 2 == 0:
                        edges.append([v_bl, v_tr])
                    else:
                        edges.append([v_br, v_tl])

        # Extract bottom chords centerline
        bottom_chords = [
            [start_x, -half_w, -half_h], [start_x + L, -half_w, -half_h],
            [start_x, +half_w, -half_h], [start_x + L, +half_w, -half_h]
        ]

        # Generate clamp matrices along bottom center (Y=0, Z=-half_h)
        clamp_matrices = []
        if clamp_cnt > 0:
            step = L / (clamp_cnt + 1) if clamp_cnt > 1 else L / 2.0
            for k in range(clamp_cnt):
                cx = start_x + (step * (k + 1) if clamp_cnt > 1 else L / 2.0)
                # Matrix located at clamp position with Z pointing down for fixture mounting
                clamp_mat = Matrix.Translation(Vector((cx, 0.0, -half_h)))
                clamp_matrices.append(clamp_mat)

        return verts, edges, [], bottom_chords, clamp_matrices

    def _generate_triangle_truss(self, L, W, H, bay_len, clamp_cnt, apex_up=True):
        num_bays = max(1, int(round(L / bay_len)))
        dx = L / num_bays
        half_w = W / 2.0
        start_x = -L / 2.0

        if apex_up:
            profiles = [
                (-half_w, -H / 2.0), # Bottom-left
                (+half_w, -H / 2.0), # Bottom-right
                (0.0, +H / 2.0)      # Top Apex
            ]
            face_chords = [(0, 1), (1, 2), (2, 0)]
            clamp_z = -H / 2.0
        else:
            profiles = [
                (-half_w, +H / 2.0), # Top-left
                (+half_w, +H / 2.0), # Top-right
                (0.0, -H / 2.0)      # Bottom Apex
            ]
            face_chords = [(0, 1), (1, 2), (2, 0)]
            clamp_z = -H / 2.0

        verts = []
        edges = []
        for b in range(num_bays + 1):
            x = start_x + b * dx
            for py, pz in profiles:
                verts.append([x, py, pz])

        for b in range(num_bays):
            i0 = b * 3
            i1 = (b + 1) * 3
            for c in range(3):
                edges.append([i0 + c, i1 + c])

        for b in range(num_bays + 1):
            i0 = b * 3
            edges.append([i0 + 0, i0 + 1])
            edges.append([i0 + 1, i0 + 2])
            edges.append([i0 + 2, i0 + 0])

        for b in range(num_bays):
            i0 = b * 3
            i1 = (b + 1) * 3
            for c_a, c_b in face_chords:
                v_bl = i0 + c_a
                v_br = i0 + c_b
                v_tl = i1 + c_a
                v_tr = i1 + c_b
                if self.lacing_style == 'CROSS':
                    edges.append([v_bl, v_tr])
                    edges.append([v_br, v_tl])
                else:
                    if b % 2 == 0:
                        edges.append([v_bl, v_tr])
                    else:
                        edges.append([v_br, v_tl])

        clamp_matrices = []
        if clamp_cnt > 0:
            step = L / (clamp_cnt + 1) if clamp_cnt > 1 else L / 2.0
            for k in range(clamp_cnt):
                cx = start_x + (step * (k + 1) if clamp_cnt > 1 else L / 2.0)
                clamp_mat = Matrix.Translation(Vector((cx, 0.0, clamp_z)))
                clamp_matrices.append(clamp_mat)

        return verts, edges, [], verts[:3], clamp_matrices

    def process(self):
        outputs = self.outputs
        if not any(o.is_linked for o in outputs):
            return

        lengths = self.inputs['Length'].sv_get(default=[[self.truss_length]])[0]
        widths = self.inputs['Width'].sv_get(default=[[self.truss_width]])[0]
        heights = self.inputs['Height'].sv_get(default=[[self.truss_height]])[0]
        if self.inputs['Matrix'].is_linked:
            matrices = self.inputs['Matrix'].sv_get(default=[[Matrix.Identity(4)]])[0]
            base_mat = Matrix(matrices[0]) if matrices else Matrix.Identity(4)
        else:
            base_mat = Matrix.Translation(Vector((0.0, 0.0, self.trim_height)))

        L = lengths[0] if lengths else self.truss_length
        W = widths[0] if widths else self.truss_width
        H = heights[0] if heights else self.truss_height

        if self.truss_type == 'BOX':
            verts, edges, polys, b_chords, clamps = self._generate_box_truss(L, W, H, self.bay_length, self.clamp_count)
        elif self.truss_type == 'TRIANGLE_APEX_UP':
            verts, edges, polys, b_chords, clamps = self._generate_triangle_truss(L, W, H, self.bay_length, self.clamp_count, apex_up=True)
        elif self.truss_type == 'TRIANGLE_APEX_DOWN':
            verts, edges, polys, b_chords, clamps = self._generate_triangle_truss(L, W, H, self.bay_length, self.clamp_count, apex_up=False)
        else:  # LADDER
            verts, edges, polys, b_chords, clamps = self._generate_box_truss(L, W, 0.05, self.bay_length, self.clamp_count)

        # Transform vertices and clamps by base_mat
        world_verts = [(base_mat @ Vector(v))[:] for v in verts]
        world_chords = [(base_mat @ Vector(v))[:] for v in b_chords]
        world_clamps = [base_mat @ m for m in clamps]

        outputs['Vertices'].sv_set([world_verts])
        outputs['Edges'].sv_set([edges])
        outputs['Polygons'].sv_set([polys])
        outputs['Bottom Chords'].sv_set([world_chords])
        outputs['Clamp Matrices'].sv_set([world_clamps])

classes = [SvSpotlightTrussNode]
register, unregister = bpy.utils.register_classes_factory(classes)
