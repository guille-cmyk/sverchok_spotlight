# Trigonometry, photometrics, and procedural geometry helpers for Sverchok Spotlight

import math
from mathutils import Vector, Matrix, Euler

def calculate_focus_aim(fixture_matrix, target_point, pan_invert=False, tilt_invert=False, pan_offset=0.0, tilt_offset=0.0):
    """
    Computes Pan and Tilt angles (degrees), throw distance, and aimed 4x4 matrix
    to point a fixture at target_point.
    
    Theatrical convention:
    - Rest pose (Pan=0, Tilt=0): head hangs straight down (-Z).
    - Tilt increases from 0 to 90 (horizontal) to 180 (pointing up).
    - Pan rotates around the fixture base vertical axis (Z).
    """
    if isinstance(fixture_matrix, (list, tuple)):
        M_fix = Matrix(fixture_matrix)
    else:
        M_fix = fixture_matrix.copy()

    P_fix = M_fix.to_translation()
    target_vec = Vector(target_point)
    V_world = target_vec - P_fix
    throw_distance = V_world.length

    if throw_distance < 1e-5:
        return 0.0, 0.0, 0.0, M_fix, Vector((0, 0, -1))

    # Transform direction into fixture's local coordinate frame
    R_fix = M_fix.to_3x3()
    inv_R_fix = R_fix.inverted()
    V_local = inv_R_fix @ V_world
    u = V_local.normalized()

    # Tilt is angle from -Z axis (0 = pointing straight down)
    cos_tilt = max(-1.0, min(1.0, -u.z))
    tilt_rad = math.acos(cos_tilt)
    tilt_deg = math.degrees(tilt_rad)

    # Pan is azimuth angle in local XY plane (0 = along -Y forward)
    pan_rad = math.atan2(u.x, -u.y)
    pan_deg = math.degrees(pan_rad)

    if pan_invert:
        pan_deg = -pan_deg
    if tilt_invert:
        tilt_deg = -tilt_deg

    pan_deg += pan_offset
    tilt_deg += tilt_offset

    # Reconstruct rotation in local frame: Pan around Z, then Tilt around X
    R_pan = Matrix.Rotation(math.radians(pan_deg), 4, 'Z')
    R_tilt = Matrix.Rotation(math.radians(tilt_deg), 4, 'X')
    R_head = R_pan @ R_tilt

    # Translation to fixture position
    T = Matrix.Translation(P_fix)
    
    # Base fixture rotation without translation
    M_base_rot = M_fix.to_3x3().to_4x4()
    
    # Final aimed matrix
    M_aimed = T @ M_base_rot @ R_head

    aim_dir = (V_world / throw_distance)

    return pan_deg, tilt_deg, throw_distance, M_aimed, aim_dir


def generate_cone_mesh(length, angle_deg, segments=24, lens_radius=0.0):
    """
    Generates procedural cone mesh vertices, edges, and polygons along local -Z.
    Origin is at Z=0 (the light generator position).
    If lens_radius > 0: starts with a lens aperture ring at Z=0 and expands to Z=-length.
    If lens_radius == 0: apex is at (0, 0, 0) at the light generator position.
    """
    half_angle = math.radians(max(0.1, angle_deg) / 2.0)
    tan_half = math.tan(half_angle)
    r_base = max(0.01, lens_radius + length * tan_half)

    verts = []
    edges = []
    polys = []

    if lens_radius > 1e-4:
        # Frustum: top lens ring at Z=0
        for i in range(segments):
            theta = 2.0 * math.pi * i / segments
            x = lens_radius * math.cos(theta)
            y = lens_radius * math.sin(theta)
            verts.append([x, y, 0.0])

        # Bottom base ring at Z=-length
        for i in range(segments):
            theta = 2.0 * math.pi * i / segments
            x = r_base * math.cos(theta)
            y = r_base * math.sin(theta)
            verts.append([x, y, -length])

        # Side quads connecting top lens ring to bottom ring
        for i in range(segments):
            i_next = (i + 1) % segments
            v_top_curr = i
            v_top_next = i_next
            v_bot_next = segments + i_next
            v_bot_curr = segments + i

            polys.append([v_top_curr, v_top_next, v_bot_next, v_bot_curr])
            edges.append([v_top_curr, v_top_next])
            edges.append([v_top_curr, v_bot_curr])
            edges.append([v_bot_curr, v_bot_next])

        # Top lens cap
        polys.append([i for i in range(segments)])
        # Bottom cap
        center_idx = len(verts)
        verts.append([0.0, 0.0, -length])
        for i in range(segments):
            curr_idx = segments + i
            next_idx = segments + ((i + 1) % segments)
            polys.append([center_idx, next_idx, curr_idx])
    else:
        # Conical apex at (0, 0, 0)
        verts = [[0.0, 0.0, 0.0]]
        for i in range(segments):
            theta = 2.0 * math.pi * i / segments
            x = r_base * math.cos(theta)
            y = r_base * math.sin(theta)
            verts.append([x, y, -length])

        for i in range(segments):
            curr_idx = 1 + i
            next_idx = 1 + ((i + 1) % segments)
            polys.append([0, curr_idx, next_idx])
            edges.append([0, curr_idx])
            edges.append([curr_idx, next_idx])

        center_idx = len(verts)
        verts.append([0.0, 0.0, -length])
        for i in range(segments):
            curr_idx = 1 + i
            next_idx = 1 + ((i + 1) % segments)
            polys.append([center_idx, next_idx, curr_idx])

    return verts, edges, polys


def calculate_floor_footprint(fixture_pos, aimed_matrix, angle_deg, floor_z=0.0, segments=32, max_dist=50.0):
    """
    Projects a light cone onto the horizontal stage floor plane (Z = floor_z).
    Returns footprint polygon vertices, edges, and (width, length) dimensions.
    """
    P_fix = Vector(fixture_pos)
    half_angle = math.radians(max(0.1, angle_deg) / 2.0)
    
    # If fixture is already at or below floor level, no floor footprint
    if P_fix.z <= floor_z:
        return [], [], 0.0, 0.0

    R_aim = Matrix(aimed_matrix).to_3x3()

    footprint_verts = []
    cos_half = math.cos(half_angle)
    sin_half = math.sin(half_angle)

    valid = True
    for i in range(segments):
        theta = 2.0 * math.pi * i / segments
        # Local cone boundary ray
        dir_local = Vector((
            sin_half * math.cos(theta),
            sin_half * math.sin(theta),
            -cos_half
        ))
        dir_world = (R_aim @ dir_local).normalized()

        if dir_world.z >= -1e-4:
            # Ray is pointing horizontal or up, footprint is open/infinite
            valid = False
            break

        t = (floor_z - P_fix.z) / dir_world.z
        if t <= 0 or t > max_dist:
            valid = False
            break

        hit_p = P_fix + t * dir_world
        footprint_verts.append([hit_p.x, hit_p.y, floor_z])

    if not valid or len(footprint_verts) < 3:
        return [], [], 0.0, 0.0

    edges = []
    n = len(footprint_verts)
    for i in range(n):
        edges.append([i, (i + 1) % n])

    # Calculate major and minor diameter of the footprint
    xs = [p[0] for p in footprint_verts]
    ys = [p[1] for p in footprint_verts]
    width = max(xs) - min(xs)
    length = max(ys) - min(ys)

    return footprint_verts, edges, width, length


def calculate_photometrics(candela, throw_dist, cos_incidence=1.0):
    """
    Calculates illuminance (Lux) using inverse square law.
    """
    d = max(0.1, throw_dist)
    cos_factor = max(0.0, min(1.0, cos_incidence))
    lux = (candela / (d * d)) * cos_factor
    foot_candles = lux * 0.092903
    return lux, foot_candles
