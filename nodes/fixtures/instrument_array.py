# Instrument Array and 3D Symbol Instancer Node for Sverchok Spotlight
# Positions fixtures at hanging points and articulates yoke and head using Pan and Tilt
# Aligns beam origin precisely to the light generator / front lens position specified in device specs

import math
import bpy
from bpy.props import FloatProperty, BoolProperty, StringProperty
from mathutils import Vector, Matrix

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode


def create_articulated_symbol_mesh(scale=1.0, pan_deg=0.0, tilt_deg=0.0, emitter_offset=0.36, lens_diameter=0.15):
    """
    Creates procedural 3D moving-light symbol geometry articulated by Pan and Tilt:
    1. Base Box: clamped to truss, stationary at Z=0.
    2. Yoke Arms: rotated around local Z axis by pan_deg.
    3. Head Housing: rotated around trunnion pivot by tilt_deg, then rotated around Z by pan_deg.
       The front lens (light generator) terminates precisely at z = -emitter_offset * scale
       with aperture diameter matching lens_diameter * scale.
    """
    s = scale
    verts = []
    polys = []

    # 1. Base Box (Z: +0.02 to -0.06, X: -0.15 to +0.15, Y: -0.12 to +0.12)
    bx0, bx1 = -0.15 * s, 0.15 * s
    by0, by1 = -0.12 * s, 0.12 * s
    bz0, bz1 = -0.06 * s, 0.02 * s

    base_verts = [
        Vector((bx0, by0, bz0)), Vector((bx1, by0, bz0)), Vector((bx1, by1, bz0)), Vector((bx0, by1, bz0)),  # Bottom 0..3
        Vector((bx0, by0, bz1)), Vector((bx1, by0, bz1)), Vector((bx1, by1, bz1)), Vector((bx0, by1, bz1)),  # Top 4..7
    ]
    base_faces = [
        [0, 1, 2, 3], [7, 6, 5, 4],  # Bottom, top
        [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]  # Sides
    ]

    for v in base_verts:
        verts.append(v)
    polys.extend(base_faces)

    # Rotation transforms
    R_pan = Matrix.Rotation(math.radians(pan_deg), 3, 'Z')
    R_tilt = Matrix.Rotation(math.radians(tilt_deg), 3, 'X')

    # Dimensions based on device specs
    emitter_dist = max(0.1 * s, float(emitter_offset) * s)
    lens_diam = max(0.04 * s, float(lens_diameter) * s)
    pivot_z = -emitter_dist * 0.5  # Trunnion axis in middle of yoke
    pivot = Vector((0.0, 0.0, pivot_z))

    # 2. Yoke Arms (rotated by Pan around fixture vertical axis)
    # Left Arm
    off = len(verts)
    yx0, yx1 = -0.14 * s, -0.11 * s
    yy0, yy1 = -0.04 * s, 0.04 * s
    yz0, yz1 = pivot_z - 0.04 * s, -0.06 * s
    y_verts = [
        Vector((yx0, yy0, yz0)), Vector((yx1, yy0, yz0)), Vector((yx1, yy1, yz0)), Vector((yx0, yy1, yz0)),
        Vector((yx0, yy0, yz1)), Vector((yx1, yy0, yz1)), Vector((yx1, yy1, yz1)), Vector((yx0, yy1, yz1)),
    ]
    for v in y_verts:
        verts.append(R_pan @ v)
    for f in base_faces:
        polys.append([idx + off for idx in f])

    # Right Arm
    off = len(verts)
    yx0, yx1 = 0.11 * s, 0.14 * s
    y_verts = [
        Vector((yx0, yy0, yz0)), Vector((yx1, yy0, yz0)), Vector((yx1, yy1, yz0)), Vector((yx0, yy1, yz0)),
        Vector((yx0, yy0, yz1)), Vector((yx1, yy0, yz1)), Vector((yx1, yy1, yz1)), Vector((yx0, yy1, yz1)),
    ]
    for v in y_verts:
        verts.append(R_pan @ v)
    for f in base_faces:
        polys.append([idx + off for idx in f])

    # 3. Head Housing (pivots at trunnion pivot around X by tilt, then Z by pan)
    off = len(verts)
    segs = 8
    r_top = max(0.04 * s, lens_diam * 0.5 * 1.15)
    r_bot = max(0.03 * s, lens_diam * 0.5)
    z_top = pivot_z + 0.08 * s
    z_bot = -emitter_dist  # Terminate exactly at front lens / light generator!

    head_raw_verts = []
    # Top ring
    for i in range(segs):
        ang = 2.0 * math.pi * i / segs
        head_raw_verts.append(Vector((r_top * math.cos(ang), r_top * math.sin(ang), z_top)))
    # Bottom lens ring (Light Generator Position!)
    for i in range(segs):
        ang = 2.0 * math.pi * i / segs
        head_raw_verts.append(Vector((r_bot * math.cos(ang), r_bot * math.sin(ang), z_bot)))

    for v in head_raw_verts:
        v_tilted = (R_tilt @ (v - pivot)) + pivot
        v_final = R_pan @ v_tilted
        verts.append(v_final)

    # Head side quads
    for i in range(segs):
        i_next = (i + 1) % segs
        v0 = off + i
        v1 = off + i_next
        v2 = off + segs + i_next
        v3 = off + segs + i
        polys.append([v0, v1, v2, v3])

    # Head top and bottom caps (Bottom cap is the front lens!)
    polys.append([off + i for i in range(segs)])
    polys.append([off + segs + ((segs - 1) - i) for i in range(segs)])

    # Derive edges from polygons
    edge_set = set()
    for poly in polys:
        for i in range(len(poly)):
            e = tuple(sorted((poly[i], poly[(i + 1) % len(poly)])))
            edge_set.add(e)
    edges = [list(e) for e in edge_set]

    verts_list = [[v.x, v.y, v.z] for v in verts]
    return verts_list, edges, polys


def create_fixture_symbol_mesh(scale=1.0):
    """Fallback rest pose symbol mesh."""
    return create_articulated_symbol_mesh(scale=scale, pan_deg=0.0, tilt_deg=0.0)


class SvSpotlightInstrumentArrayNode(SverchCustomTreeNode, bpy.types.Node):
    """Generates 3D fixture symbols oriented by calculated Pan/Tilt and bundles records"""
    bl_idname = 'SvSpotlightInstrumentArrayNode'
    bl_label = 'Spotlight Instrument Array'
    bl_icon = 'LIGHT_HEMI'

    symbol_scale: FloatProperty(name="Scale", default=1.0, min=0.1, max=5.0, step=10, update=updateNode)
    default_purpose: StringProperty(name="Purpose", default="Spot", update=updateNode)

    def sv_init(self, context):
        self.inputs.new('SvMatrixSocket', "Hang Matrices")
        self.inputs.new('SvMatrixSocket', "Aimed Matrices")
        self.inputs.new('SvStringsSocket', "Pan (deg)")
        self.inputs.new('SvStringsSocket', "Tilt (deg)")
        self.inputs.new('SvDictionarySocket', "Fixture Profile")
        self.inputs.new('SvDictionarySocket', "Position Data")

        self.outputs.new('SvVerticesSocket', "Vertices")
        self.outputs.new('SvStringsSocket', "Edges")
        self.outputs.new('SvStringsSocket', "Polygons")
        self.outputs.new('SvDictionarySocket', "Fixture Instances")
        self.outputs.new('SvMatrixSocket', "Fixture Matrices")
        self.outputs.new('SvMatrixSocket', "Emitter Matrices")
        self.outputs.new('SvVerticesSocket', "Emitter Points")
        self.outputs.new('SvStringsSocket', "Pan (deg)")
        self.outputs.new('SvStringsSocket', "Tilt (deg)")

    def draw_buttons(self, context, layout):
        layout.prop(self, "symbol_scale")
        layout.prop(self, "default_purpose")

    def process(self):
        outputs = self.outputs

        hang_matrices = [Matrix.Identity(4)]
        if 'Hang Matrices' in self.inputs:
            try:
                hang_matrices = self.inputs['Hang Matrices'].sv_get(default=[[Matrix.Identity(4)]])[0]
            except Exception:
                pass

        aimed_in = []
        if 'Aimed Matrices' in self.inputs:
            try:
                aimed_in = self.inputs['Aimed Matrices'].sv_get(default=[[]])[0]
            except Exception:
                pass

        pans_in = []
        if 'Pan (deg)' in self.inputs:
            try:
                pans_in = self.inputs['Pan (deg)'].sv_get(default=[[]])[0]
            except Exception:
                pass

        tilts_in = []
        if 'Tilt (deg)' in self.inputs:
            try:
                tilts_in = self.inputs['Tilt (deg)'].sv_get(default=[[]])[0]
            except Exception:
                pass

        profiles = [{}]
        if 'Fixture Profile' in self.inputs:
            try:
                profiles = self.inputs['Fixture Profile'].sv_get(default=[[{}]])[0]
            except Exception:
                pass

        pos_data = []
        if 'Position Data' in self.inputs:
            try:
                pos_data = self.inputs['Position Data'].sv_get(default=[[]])[0]
            except Exception:
                pass

        profile = profiles[0] if profiles else {}

        # Light Generator / Emitter Specs
        emitter_offset_spec = float(profile.get("emitter_offset", 0.36))
        lens_diameter_spec = float(profile.get("lens_diameter", 0.15))
        emitter_dist = emitter_offset_spec * self.symbol_scale
        lens_diam = lens_diameter_spec * self.symbol_scale

        all_verts = []
        all_edges = []
        all_polys = []
        fixture_instances = []
        emitter_matrices = []
        emitter_points = []
        pans_out = []
        tilts_out = []

        vert_offset = 0

        for idx, m_raw in enumerate(hang_matrices):
            M_hang = Matrix(m_raw) if not isinstance(m_raw, Matrix) else m_raw

            # Pan & Tilt determination
            pan_val = 0.0
            tilt_val = 0.0

            if pans_in and idx < len(pans_in):
                try:
                    pan_val = float(pans_in[idx])
                except (ValueError, TypeError):
                    pan_val = 0.0

            if tilts_in and idx < len(tilts_in):
                try:
                    tilt_val = float(tilts_in[idx])
                except (ValueError, TypeError):
                    tilt_val = 0.0

            # If Aimed Matrix is linked directly without explicit pan/tilt sockets
            if aimed_in and idx < len(aimed_in) and not pans_in and not tilts_in:
                aim_raw = aimed_in[idx]
                M_aim = Matrix(aim_raw) if not isinstance(aim_raw, Matrix) else aim_raw
                try:
                    R_local = M_hang.to_3x3().inverted() @ M_aim.to_3x3()
                    u = (R_local @ Vector((0, 0, -1))).normalized()
                    tilt_val = math.degrees(math.acos(max(-1.0, min(1.0, -u.z))))
                    pan_val = math.degrees(math.atan2(u.x, -u.y))
                except Exception:
                    pass

            pans_out.append(round(pan_val, 2))
            tilts_out.append(round(tilt_val, 2))

            # Rotation transforms
            R_pan = Matrix.Rotation(math.radians(pan_val), 3, 'Z')
            R_tilt = Matrix.Rotation(math.radians(tilt_val), 3, 'X')
            pivot = Vector((0.0, 0.0, -emitter_dist * 0.5))

            # -----------------------------------------------------------------
            # Light Generator (Emitter / Front Lens) 3D Position & Matrix
            # -----------------------------------------------------------------
            # In fixture rest pose, emitter is at (0, 0, -emitter_dist)
            emitter_rest = Vector((0.0, 0.0, -emitter_dist))
            emitter_tilted = (R_tilt @ (emitter_rest - pivot)) + pivot
            emitter_articulated = R_pan @ emitter_tilted
            P_emitter_world = M_hang @ emitter_articulated

            # Aimed rotation of the head housing
            R_head_world = M_hang.to_3x3() @ R_pan @ R_tilt
            M_emitter_world = Matrix.Translation(P_emitter_world) @ R_head_world.to_4x4()

            emitter_matrices.append(M_emitter_world)
            emitter_points.append([P_emitter_world.x, P_emitter_world.y, P_emitter_world.z])

            # Metadata resolution
            p_info = pos_data[idx] if idx < len(pos_data) else {}
            pos_name = p_info.get("position", "LX")
            unit_num = p_info.get("unit_number", str(idx + 1))
            clamp_pos = list(M_hang.to_translation())

            record = {
                "unit_id": f"{pos_name}-{unit_num}",
                "unit_number": unit_num,
                "position": pos_name,
                "position_name": pos_name,
                "hang_position": pos_name,
                "world_pos": [P_emitter_world.x, P_emitter_world.y, P_emitter_world.z],
                "coords": [P_emitter_world.x, P_emitter_world.y, P_emitter_world.z],
                "clamp_pos": clamp_pos,
                "emitter_pos": [P_emitter_world.x, P_emitter_world.y, P_emitter_world.z],
                "lens_pos": [P_emitter_world.x, P_emitter_world.y, P_emitter_world.z],
                "emitter_matrix": [list(row) for row in M_emitter_world],
                "aimed_matrix": [list(row) for row in M_emitter_world],
                "matrix": [list(row) for row in M_emitter_world],
                "hang_matrix": [list(row) for row in M_hang],
                "fixture_name": profile.get("name", "Generic Spot"),
                "fixture_type": profile.get("type", "Spot"),
                "beam_angle": float(profile.get("beam_angle", 15.0)),
                "field_angle": float(profile.get("field_angle", 30.0)),
                "candela": float(profile.get("candela", 100000.0)),
                "weight_kg": float(profile.get("weight_kg", 15.0)),
                "wattage": float(profile.get("wattage", 300.0)),
                "dmx_footprint": int(profile.get("dmx_footprint", 16)),
                "color": profile.get("color", "Open White"),
                "purpose": profile.get("purpose", self.default_purpose),
                "pan": round(pan_val, 2),
                "tilt": round(tilt_val, 2),
                "emitter_offset": round(emitter_dist, 3),
                "lens_diameter": round(lens_diam, 3),
            }
            fixture_instances.append(record)

            # Generate articulated symbol mesh terminating exactly at emitter_dist
            sym_v, sym_e, sym_p = create_articulated_symbol_mesh(
                scale=self.symbol_scale,
                pan_deg=pan_val,
                tilt_deg=tilt_val,
                emitter_offset=emitter_offset_spec,
                lens_diameter=lens_diameter_spec
            )

            # Transform symbol into world space at hanging position
            for v in sym_v:
                wv = M_hang @ Vector(v)
                all_verts.append([wv.x, wv.y, wv.z])

            for e in sym_e:
                all_edges.append([e[0] + vert_offset, e[1] + vert_offset])

            for p in sym_p:
                all_polys.append([i + vert_offset for i in p])

            vert_offset += len(sym_v)

        outputs['Vertices'].sv_set([all_verts])
        outputs['Edges'].sv_set([all_edges])
        outputs['Polygons'].sv_set([all_polys])
        outputs['Fixture Instances'].sv_set([fixture_instances])
        # Fixture Matrices & Emitter Matrices output the exact Light Generator matrix
        outputs['Fixture Matrices'].sv_set([emitter_matrices])
        outputs['Emitter Matrices'].sv_set([emitter_matrices])
        outputs['Emitter Points'].sv_set([emitter_points])
        outputs['Pan (deg)'].sv_set([pans_out])
        outputs['Tilt (deg)'].sv_set([tilts_out])


classes = [SvSpotlightInstrumentArrayNode]
register, unregister = bpy.utils.register_classes_factory(classes)
