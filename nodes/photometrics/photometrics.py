# Photometric Beam Cone, Floor Footprint Projection, and Lighting Standard Analysis Node
# Evaluates illuminance against entertainment and architectural standards (0 = not enough, 1 = enough)
# Originates light beam precisely from the light generator / front lens position specified in device specs

import math
import bpy
from bpy.props import FloatProperty, IntProperty, BoolProperty, EnumProperty
from mathutils import Vector, Matrix

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode
from ...utils.lighting_math import generate_cone_mesh, calculate_floor_footprint, calculate_photometrics


def on_standard_change(self, context):
    presets = {
        'STAGE_500': 500.0,
        'BROADCAST_1000': 1000.0,
        'CONCERT_750': 750.0,
        'MUSEUM_300': 300.0,
        'WORK_200': 200.0,
    }
    if self.standard_preset in presets:
        self.min_lux_threshold = presets[self.standard_preset]
    updateNode(self, context)


class SvSpotlightPhotometricsNode(SverchCustomTreeNode, bpy.types.Node):
    """Calculates 3D beam cones, floor footprint ellipses, and lighting standard compliance"""
    bl_idname = 'SvSpotlightPhotometricsNode'
    bl_label = 'Spotlight Photometrics'
    bl_icon = 'OUTLINER_OB_LIGHT'

    standard_preset: EnumProperty(
        name="Standard",
        description="Lighting Illuminance Standard for stage/studio analysis",
        items=[
            ('STAGE_500', 'Theatrical Stage (500 lx - EN 12464)', 'Standard theatre / stage drama performance level'),
            ('BROADCAST_1000', 'Broadcast / TV (1000 lx)', 'High-definition television broadcast & camera standard'),
            ('CONCERT_750', 'Concert / High-Impact (750 lx)', 'High-energy live music and touring standard'),
            ('MUSEUM_300', 'Museum / Gallery (300 lx)', 'Art exhibition / gallery / museum lighting standard'),
            ('WORK_200', 'Worklight / Rehearsal (200 lx)', 'Rehearsal, backstage, and worklight minimum'),
            ('CUSTOM', 'Custom Threshold', 'User-defined minimum illuminance threshold'),
        ],
        default='STAGE_500',
        update=on_standard_change
    )

    min_lux_threshold: FloatProperty(
        name="Min Lux",
        description="Minimum Lux required by lighting standard (compliant if >= threshold)",
        default=500.0,
        min=0.0,
        step=50,
        update=updateNode
    )

    beam_angle: FloatProperty(name="Beam Angle", default=15.0, min=0.1, max=120.0, step=10, update=updateNode)
    field_angle: FloatProperty(name="Field Angle", default=30.0, min=0.1, max=160.0, step=10, update=updateNode)
    candela: FloatProperty(name="Candela (cd)", default=100000.0, min=1.0, step=10000, update=updateNode)
    floor_z: FloatProperty(name="Floor Z (m)", default=0.0, step=10, update=updateNode)
    max_cone_length: FloatProperty(name="Max Distance", default=15.0, min=0.5, step=50, update=updateNode)
    segments: IntProperty(name="Segments", default=24, min=8, max=64, update=updateNode)

    show_beam: BoolProperty(name="Beam Cone (50%)", default=True, update=updateNode)
    show_field: BoolProperty(name="Field Cone (10%)", default=False, update=updateNode)
    use_lens_aperture: BoolProperty(
        name="Lens Aperture",
        description="Start beam cone from front lens aperture diameter matching device specs",
        default=True,
        update=updateNode
    )

    def sv_init(self, context):
        self.inputs.new('SvMatrixSocket', "Aimed Matrices")
        self.inputs.new('SvDictionarySocket', "Fixture Instances")
        self.inputs.new('SvStringsSocket', "Min Lux").prop_name = 'min_lux_threshold'
        self.inputs.new('SvStringsSocket', "Beam Angle").prop_name = 'beam_angle'
        self.inputs.new('SvStringsSocket', "Field Angle").prop_name = 'field_angle'
        self.inputs.new('SvStringsSocket', "Candela").prop_name = 'candela'
        self.inputs.new('SvStringsSocket', "Floor Z").prop_name = 'floor_z'

        self.outputs.new('SvStringsSocket', "Compliance Mask")
        self.outputs.new('SvStringsSocket', "Compliance Status")
        self.outputs.new('SvStringsSocket', "Lux")
        self.outputs.new('SvStringsSocket', "Footprint Size")
        self.outputs.new('SvVerticesSocket', "Beam Verts")
        self.outputs.new('SvStringsSocket', "Beam Polys")
        self.outputs.new('SvVerticesSocket', "Field Verts")
        self.outputs.new('SvStringsSocket', "Field Polys")
        self.outputs.new('SvVerticesSocket', "Footprint Verts")
        self.outputs.new('SvStringsSocket', "Footprint Edges")

    def draw_buttons(self, context, layout):
        layout.prop(self, "standard_preset", text="")
        layout.prop(self, "min_lux_threshold")
        col = layout.column(align=True)
        col.prop(self, "show_beam", toggle=True)
        col.prop(self, "show_field", toggle=True)
        col.prop(self, "use_lens_aperture", toggle=True)
        layout.prop(self, "floor_z")
        layout.prop(self, "max_cone_length")

    def process(self):
        outputs = self.outputs
        if not any(o.is_linked for o in outputs):
            return

        # 1. Resolve fixture metadata and input matrices
        fixture_dicts = []
        if 'Fixture Instances' in self.inputs and self.inputs['Fixture Instances'].is_linked:
            f_in = self.inputs['Fixture Instances'].sv_get(default=[[]])[0]
            if isinstance(f_in, list):
                fixture_dicts = [x for x in f_in if isinstance(x, dict)]

        matrices = []
        if 'Aimed Matrices' in self.inputs and self.inputs['Aimed Matrices'].is_linked:
            matrices = self.inputs['Aimed Matrices'].sv_get(default=[[Matrix.Identity(4)]])[0]
        elif fixture_dicts:
            for fix in fixture_dicts:
                m = fix.get('emitter_matrix') or fix.get('aimed_matrix') or fix.get('matrix') or fix.get('hang_matrix')
                if m:
                    matrices.append(Matrix(m) if not isinstance(m, Matrix) else m)
                else:
                    matrices.append(Matrix.Identity(4))
        else:
            matrices = [Matrix.Identity(4)]

        # 2. Threshold & parameters
        if 'Min Lux' in self.inputs and self.inputs['Min Lux'].is_linked:
            m_lux_in = self.inputs['Min Lux'].sv_get(default=[[self.min_lux_threshold]])[0]
            current_threshold = float(m_lux_in[0]) if m_lux_in else self.min_lux_threshold
        else:
            current_threshold = self.min_lux_threshold

        beam_angles = self.inputs['Beam Angle'].sv_get(default=[[self.beam_angle]])[0]
        field_angles = self.inputs['Field Angle'].sv_get(default=[[self.field_angle]])[0]
        candelas = self.inputs['Candela'].sv_get(default=[[self.candela]])[0]
        floor_zs = self.inputs['Floor Z'].sv_get(default=[[self.floor_z]])[0]

        default_b_ang = float(beam_angles[0]) if beam_angles else self.beam_angle
        default_f_ang = float(field_angles[0]) if field_angles else self.field_angle
        default_cd = float(candelas[0]) if candelas else self.candela
        fz = float(floor_zs[0]) if floor_zs else self.floor_z

        beam_verts_all = []
        beam_polys_all = []
        field_verts_all = []
        field_polys_all = []
        footprint_verts_all = []
        footprint_edges_all = []

        lux_values = []
        compliance_mask = []
        footprint_sizes = []

        b_vert_offset = 0
        f_vert_offset = 0
        fp_vert_offset = 0

        for idx, m_raw in enumerate(matrices):
            M = Matrix(m_raw) if not isinstance(m_raw, Matrix) else m_raw
            fix_dict = fixture_dicts[idx] if idx < len(fixture_dicts) else {}

            # Ensure beam origin is at the light generator (emitter)
            # If fixture dictionary provides an explicit emitter_matrix, use it
            if fix_dict.get('emitter_matrix'):
                M = Matrix(fix_dict['emitter_matrix'])
            elif fix_dict.get('emitter_offset'):
                # If matrix was at base clamp, translate along aim direction to light generator
                emitter_d = float(fix_dict['emitter_offset'])
                aim_d = (M.to_3x3() @ Vector((0, 0, -1))).normalized()
                clamp_p = M.to_translation()
                emitter_p = clamp_p + aim_d * emitter_d
                M = Matrix.Translation(emitter_p) @ M.to_3x3().to_4x4()

            pos = M.to_translation()
            aim_dir = (M.to_3x3() @ Vector((0, 0, -1))).normalized()

            # Determine fixture photometric parameters
            b_ang = float(fix_dict.get('beam_angle', default_b_ang))
            f_ang = float(fix_dict.get('field_angle', default_f_ang))
            cd = float(fix_dict.get('candela', default_cd))
            lens_diam = float(fix_dict.get('lens_diameter', 0.15))
            lens_r = (lens_diam * 0.5) if self.use_lens_aperture else 0.0

            # 1. Floor footprint & throw calculation (measured from light generator)
            if aim_dir.z < -1e-4 and pos.z > fz:
                throw_dist = (fz - pos.z) / aim_dir.z
                cos_incidence = -aim_dir.z  # Dot product with floor normal (0, 0, 1)
            else:
                throw_dist = self.max_cone_length
                cos_incidence = 1.0

            lux, _ = calculate_photometrics(cd, throw_dist, cos_incidence)
            lux_values.append(round(lux, 1))

            # Light Analysis: boolean array (0 = not enough, 1 = compliant with standard)
            is_enough = 1 if lux >= current_threshold else 0
            compliance_mask.append(is_enough)

            fp_v, fp_e, fp_w, fp_l = calculate_floor_footprint(pos, M, b_ang, floor_z=fz, segments=self.segments)
            footprint_sizes.append(f"{round(fp_w, 2)}m x {round(fp_l, 2)}m")

            if fp_v:
                for v in fp_v:
                    footprint_verts_all.append(v)
                for e in fp_e:
                    footprint_edges_all.append([e[0] + fp_vert_offset, e[1] + fp_vert_offset])
                fp_vert_offset += len(fp_v)

            actual_cone_len = min(self.max_cone_length, max(0.5, throw_dist))

            # 2. Beam cone (50%) originating at the light generator
            if self.show_beam:
                scaled_b_v, _, b_polys_local = generate_cone_mesh(actual_cone_len, b_ang, self.segments, lens_radius=lens_r)
                for v in scaled_b_v:
                    wv = M @ Vector(v)
                    beam_verts_all.append([wv.x, wv.y, wv.z])
                for p in b_polys_local:
                    beam_polys_all.append([p_idx + b_vert_offset for p_idx in p])
                b_vert_offset += len(scaled_b_v)

            # 3. Field cone (10%) originating at the light generator
            if self.show_field:
                scaled_f_v, _, f_polys_local = generate_cone_mesh(actual_cone_len, f_ang, self.segments, lens_radius=lens_r)
                for v in scaled_f_v:
                    wv = M @ Vector(v)
                    field_verts_all.append([wv.x, wv.y, wv.z])
                for p in f_polys_local:
                    field_polys_all.append([p_idx + f_vert_offset for p_idx in p])
                f_vert_offset += len(scaled_f_v)

        pass_count = sum(compliance_mask)
        total_count = len(compliance_mask)
        status_str = f"{pass_count}/{total_count} Pass (>= {int(current_threshold)} lx)"

        outputs['Compliance Mask'].sv_set([compliance_mask])
        outputs['Compliance Status'].sv_set([status_str])
        outputs['Lux'].sv_set([lux_values])
        outputs['Footprint Size'].sv_set([footprint_sizes])
        outputs['Beam Verts'].sv_set([beam_verts_all])
        outputs['Beam Polys'].sv_set([beam_polys_all])
        outputs['Field Verts'].sv_set([field_verts_all])
        outputs['Field Polys'].sv_set([field_polys_all])
        outputs['Footprint Verts'].sv_set([footprint_verts_all])
        outputs['Footprint Edges'].sv_set([footprint_edges_all])


classes = [SvSpotlightPhotometricsNode]
register, unregister = bpy.utils.register_classes_factory(classes)
