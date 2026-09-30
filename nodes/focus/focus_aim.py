# Focus Point Targeting and Pan/Tilt Calculation Node for Sverchok Spotlight

import bpy
from bpy.props import FloatProperty, BoolProperty, FloatVectorProperty
from mathutils import Vector, Matrix

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode
from ...utils.lighting_math import calculate_focus_aim

class SvSpotlightFocusAimNode(SverchCustomTreeNode, bpy.types.Node):
    """Calculates Pan/Tilt angles and aims fixtures at 3D stage focus points"""
    bl_idname = 'SvSpotlightFocusAimNode'
    bl_label = 'Spotlight Focus Aim'
    bl_icon = 'EMPTY_AXIS'

    default_focus_target: FloatVectorProperty(
        name="Target XYZ",
        description="Default 3D stage focus target",
        default=(0.0, 0.0, 1.5),
        size=3,
        update=updateNode
    )

    pan_invert: BoolProperty(name="Invert Pan", default=False, update=updateNode)
    tilt_invert: BoolProperty(name="Invert Tilt", default=False, update=updateNode)
    pan_offset: FloatProperty(name="Pan Offset", default=0.0, min=-360.0, max=360.0, step=10, update=updateNode)
    tilt_offset: FloatProperty(name="Tilt Offset", default=0.0, min=-360.0, max=360.0, step=10, update=updateNode)

    def sv_init(self, context):
        self.inputs.new('SvMatrixSocket', "Hang Matrices")
        self.inputs.new('SvVerticesSocket', "Focus Points")

        self.outputs.new('SvMatrixSocket', "Aimed Matrices")
        self.outputs.new('SvStringsSocket', "Pan (deg)")
        self.outputs.new('SvStringsSocket', "Tilt (deg)")
        self.outputs.new('SvStringsSocket', "Throw (m)")
        self.outputs.new('SvVerticesSocket', "Aim Vectors")

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "default_focus_target", text="")
        row = layout.row(align=True)
        row.prop(self, "pan_invert", toggle=True)
        row.prop(self, "tilt_invert", toggle=True)

    def draw_buttons_ext(self, context, layout):
        layout.prop(self, "pan_offset")
        layout.prop(self, "tilt_offset")

    def process(self):
        outputs = self.outputs
        if not any(o.is_linked for o in outputs):
            return

        if 'Hang Matrices' in self.inputs and self.inputs['Hang Matrices'].is_linked:
            raw_m = self.inputs['Hang Matrices'].sv_get(default=[[Matrix.Identity(4)]])[0]
        elif 'Fixture Matrices' in self.inputs and self.inputs['Fixture Matrices'].is_linked:
            raw_m = self.inputs['Fixture Matrices'].sv_get(default=[[Matrix.Identity(4)]])[0]
        elif 'Hang Matrices' in self.inputs:
            raw_m = self.inputs['Hang Matrices'].sv_get(default=[[Matrix.Identity(4)]])[0]
        else:
            raw_m = [Matrix.Identity(4)]

        focus_pts = self.inputs['Focus Points'].sv_get(default=[[]])[0]

        default_target = Vector(self.default_focus_target)

        aimed_matrices = []
        pans = []
        tilts = []
        throws = []
        aim_vectors = []

        for idx, m_raw in enumerate(raw_m):
            if isinstance(m_raw, Matrix):
                M = m_raw
            elif isinstance(m_raw, (list, tuple)):
                if len(m_raw) == 4 and all(isinstance(r, (list, tuple)) for r in m_raw):
                    M = Matrix(m_raw)
                elif len(m_raw) == 3 and not isinstance(m_raw[0], (list, tuple)):
                    M = Matrix.Translation(Vector(m_raw))
                else:
                    try:
                        M = Matrix(m_raw)
                    except Exception:
                        M = Matrix.Identity(4)
            else:
                M = Matrix.Identity(4)

            # Target point: use matching focus point if available, else default
            if focus_pts and len(focus_pts) > 0:
                pt_raw = focus_pts[min(idx, len(focus_pts) - 1)]
                target = Vector(pt_raw)
            else:
                target = default_target

            pan_deg, tilt_deg, throw_dist, M_aimed, aim_dir = calculate_focus_aim(
                M,
                target,
                pan_invert=self.pan_invert,
                tilt_invert=self.tilt_invert,
                pan_offset=self.pan_offset,
                tilt_offset=self.tilt_offset
            )

            aimed_matrices.append(M_aimed)
            pans.append(round(pan_deg, 2))
            tilts.append(round(tilt_deg, 2))
            throws.append(round(throw_dist, 3))
            aim_vectors.append(list(aim_dir))

        outputs['Aimed Matrices'].sv_set([aimed_matrices])
        outputs['Pan (deg)'].sv_set([pans])
        outputs['Tilt (deg)'].sv_set([tilts])
        outputs['Throw (m)'].sv_set([throws])
        outputs['Aim Vectors'].sv_set([aim_vectors])

classes = [SvSpotlightFocusAimNode]
register, unregister = bpy.utils.register_classes_factory(classes)
