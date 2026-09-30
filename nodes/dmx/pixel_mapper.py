# Sverchok Spotlight - Pixel Mapper Node
# Maps texture image pixels to fixture/beam light colors based on spatial coordinates or UVs

import os
import math
import bpy
from bpy.props import StringProperty, EnumProperty, FloatProperty, BoolProperty, FloatVectorProperty
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode as update_node

def safe_float(v, default=0.0):
    try:
        if isinstance(v, (list, tuple)):
            return float(v[0]) if len(v) > 0 else default
        return float(v)
    except Exception:
        return default

def clamp(v, min_v=0.0, max_v=1.0):
    return max(min_v, min(max_v, float(v)))

def rgb_to_hex(r, g, b):
    cr = max(0, min(255, int(round(r * 255.0))))
    cg = max(0, min(255, int(round(g * 255.0))))
    cb = max(0, min(255, int(round(b * 255.0))))
    return f"#{cr:02X}{cg:02X}{cb:02X}"

def rgb_to_luminance(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def sample_image_nearest(img, u, v):
    """Samples (R, G, B, A) at normalized (u, v) using nearest-neighbor."""
    w, h = img.size[0], img.size[1]
    if w <= 0 or h <= 0:
        return (1.0, 1.0, 1.0, 1.0)
    px = max(0, min(w - 1, int(round(u * (w - 1)))))
    py = max(0, min(h - 1, int(round(v * (h - 1)))))
    idx = (py * w + px) * 4
    try:
        pixels = img.pixels
        return (float(pixels[idx]), float(pixels[idx+1]), float(pixels[idx+2]), float(pixels[idx+3]))
    except Exception:
        return (1.0, 1.0, 1.0, 1.0)

def sample_image_bilinear(img, u, v):
    """Samples (R, G, B, A) at normalized (u, v) using bilinear interpolation."""
    w, h = img.size[0], img.size[1]
    if w <= 0 or h <= 0:
        return (1.0, 1.0, 1.0, 1.0)

    # Subpixel coordinates in [0, w-1] and [0, h-1]
    x = u * (w - 1)
    y = v * (h - 1)
    x0 = int(math.floor(x))
    x1 = min(w - 1, x0 + 1)
    y0 = int(math.floor(y))
    y1 = min(h - 1, y0 + 1)

    fx = x - x0
    fy = y - y0
    w00 = (1.0 - fx) * (1.0 - fy)
    w10 = fx * (1.0 - fy)
    w01 = (1.0 - fx) * fy
    w11 = fx * fy

    try:
        pixels = img.pixels
        i00 = (y0 * w + x0) * 4
        i10 = (y0 * w + x1) * 4
        i01 = (y1 * w + x0) * 4
        i11 = (y1 * w + x1) * 4

        r = w00 * pixels[i00] + w10 * pixels[i10] + w01 * pixels[i01] + w11 * pixels[i11]
        g = w00 * pixels[i00+1] + w10 * pixels[i10+1] + w01 * pixels[i01+1] + w11 * pixels[i11+1]
        b = w00 * pixels[i00+2] + w10 * pixels[i10+2] + w01 * pixels[i01+2] + w11 * pixels[i11+2]
        a = w00 * pixels[i00+3] + w10 * pixels[i10+3] + w01 * pixels[i01+3] + w11 * pixels[i11+3]
        return (clamp(r), clamp(g), clamp(b), clamp(a))
    except Exception:
        return sample_image_nearest(img, u, v)


class SvSpotlightPixelMapperNode(bpy.types.Node, SverchCustomTreeNode):
    """
    Maps texture image file pixels to beam / fixture light colors
    based on 2D/3D physical spatial positions or explicit UV coordinates.
    """
    bl_idname = 'SvSpotlightPixelMapperNode'
    bl_label = 'Spotlight Pixel Mapper'
    bl_icon = 'IMAGE_RGB'
    sv_icon = 'SV_COLOR_MIX'

    image_path: StringProperty(
        name="Image Path",
        description="Path to texture image file (.png, .jpg, .exr, .hdr, etc.)",
        subtype='FILE_PATH',
        default="",
        update=update_node
    )

    image_name: StringProperty(
        name="Blender Image",
        description="Name of existing Blender Image datablock",
        default="",
        update=update_node
    )

    mapping_plane: EnumProperty(
        name="Plane",
        description="Planar projection plane for fixture coordinates",
        items=[
            ('XY', "Top/Plan (XY)", "Map coordinates in top-down XY stage plane (X=Left/Right, Y=Depth)"),
            ('XZ', "Front/Elevation (XZ)", "Map coordinates in front elevation XZ plane (X=Left/Right, Z=Trim)"),
            ('YZ', "Side (YZ)", "Map coordinates in side elevation YZ plane (Y=Depth, Z=Trim)"),
            ('UV', "Explicit UV", "Direct normalized UV coordinates from input socket"),
        ],
        default='XY',
        update=update_node
    )

    bounds_mode: EnumProperty(
        name="Bounds",
        description="How coordinates are scaled into 0..1 image UV space",
        items=[
            ('AUTO', "Auto Fit", "Automatically fit to bounding box of all connected fixtures"),
            ('CUSTOM', "Manual Bounds", "Use user-specified stage coordinate boundaries (meters)"),
        ],
        default='AUTO',
        update=update_node
    )

    min_u_bound: FloatProperty(
        name="Min U (m)",
        description="Minimum stage coordinate mapped to left image edge",
        default=-6.0,
        update=update_node
    )

    max_u_bound: FloatProperty(
        name="Max U (m)",
        description="Maximum stage coordinate mapped to right image edge",
        default=6.0,
        update=update_node
    )

    min_v_bound: FloatProperty(
        name="Min V (m)",
        description="Minimum stage coordinate mapped to bottom image edge",
        default=-4.0,
        update=update_node
    )

    max_v_bound: FloatProperty(
        name="Max V (m)",
        description="Maximum stage coordinate mapped to top image edge",
        default=4.0,
        update=update_node
    )

    padding: FloatProperty(
        name="Padding",
        description="Normalized margin padding around auto-bounds (0.0 to 0.4)",
        default=0.05,
        min=0.0,
        max=0.4,
        update=update_node
    )

    flip_x: BoolProperty(
        name="Flip X",
        description="Invert horizontal sampling axis",
        default=False,
        update=update_node
    )

    flip_y: BoolProperty(
        name="Flip Y",
        description="Invert vertical sampling axis",
        default=False,
        update=update_node
    )

    master_dimmer: FloatProperty(
        name="Master Dimmer",
        description="Global dimmer multiplier applied to sampled light colors",
        default=1.0,
        min=0.0,
        max=1.0,
        update=update_node
    )

    filter_mode: EnumProperty(
        name="Filter",
        description="Pixel sampling filtering mode",
        items=[
            ('BILINEAR', "Bilinear", "Smooth subpixel interpolation between adjacent pixels"),
            ('NEAREST', "Nearest", "Fast nearest pixel lookup"),
        ],
        default='BILINEAR',
        update=update_node
    )

    last_status: StringProperty(name="Status", default="Ready")

    def sv_init(self, context):
        self.inputs.new('SvDictionarySocket', 'Fixtures')
        self.inputs.new('SvVerticesSocket', 'Points')
        self.inputs.new('SvStringsSocket', 'Image Path').prop_name = 'image_path'
        self.inputs.new('SvVerticesSocket', 'UVs')
        self.inputs.new('SvStringsSocket', 'Master Dimmer').prop_name = 'master_dimmer'

        self.outputs.new('SvDictionarySocket', 'Mapped Fixtures')
        self.outputs.new('SvColorSocket', 'Colors (RGB)')
        self.outputs.new('SvColorSocket', 'Colors (RGBA)')
        self.outputs.new('SvStringsSocket', 'Hex Colors')
        self.outputs.new('SvStringsSocket', 'Dimmers')
        self.outputs.new('SvVerticesSocket', 'UV Coordinates')
        self.outputs.new('SvStringsSocket', 'Summary')

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, 'image_path')
        col.prop_search(self, 'image_name', bpy.data, 'images', text="Blender Image")

        row = col.row(align=True)
        row.prop(self, 'mapping_plane', text="")
        row.prop(self, 'bounds_mode', text="")

        if self.bounds_mode == 'CUSTOM':
            box = col.box()
            r1 = box.row(align=True)
            r1.prop(self, 'min_u_bound', text="Min U")
            r1.prop(self, 'max_u_bound', text="Max U")
            r2 = box.row(align=True)
            r2.prop(self, 'min_v_bound', text="Min V")
            r2.prop(self, 'max_v_bound', text="Max V")
        else:
            col.prop(self, 'padding', slider=True)

        row2 = col.row(align=True)
        row2.prop(self, 'flip_x', toggle=True)
        row2.prop(self, 'flip_y', toggle=True)
        row2.prop(self, 'filter_mode', text="")

        col.prop(self, 'master_dimmer', slider=True)
        col.label(text=self.last_status, icon='INFO')

    def get_image(self, override_path=None):
        """Loads or retrieves the Blender Image datablock."""
        path = override_path if override_path else self.image_path
        if path:
            resolved = bpy.path.abspath(path)
            if os.path.isfile(resolved):
                try:
                    img = bpy.data.images.load(resolved, check_existing=True)
                    return img
                except Exception as e:
                    self.last_status = f"Load error: {e}"

        # Check existing datablock
        if self.image_name and self.image_name in bpy.data.images:
            return bpy.data.images[self.image_name]

        return None

    def process(self):
        # 1. Collect inputs
        fixtures = []
        if self.inputs['Fixtures'].is_linked:
            raw_fixes = self.inputs['Fixtures'].sv_get()
            if isinstance(raw_fixes, list):
                for item in raw_fixes:
                    if isinstance(item, list):
                        fixtures.extend([x for x in item if isinstance(x, dict)])
                    elif isinstance(item, dict):
                        fixtures.append(item)

        points = []
        if self.inputs['Points'].is_linked:
            raw_pts = self.inputs['Points'].sv_get()
            if isinstance(raw_pts, list):
                for p_sub in raw_pts:
                    if isinstance(p_sub, list):
                        for p in p_sub:
                            if isinstance(p, (list, tuple)) and len(p) >= 2:
                                points.append(p)
                    elif isinstance(p_sub, (list, tuple)) and len(p_sub) >= 2:
                        points.append(p_sub)

        explicit_uvs = []
        if self.inputs['UVs'].is_linked:
            raw_uv = self.inputs['UVs'].sv_get()
            if isinstance(raw_uv, list):
                for uv_sub in raw_uv:
                    if isinstance(uv_sub, list):
                        for uv in uv_sub:
                            if isinstance(uv, (list, tuple)) and len(uv) >= 2:
                                explicit_uvs.append((safe_float(uv[0]), safe_float(uv[1])))
                    elif isinstance(uv_sub, (list, tuple)) and len(uv_sub) >= 2:
                        explicit_uvs.append((safe_float(uv_sub[0]), safe_float(uv_sub[1])))

        path_override = None
        if self.inputs['Image Path'].is_linked:
            raw_path = self.inputs['Image Path'].sv_get()
            if raw_path and isinstance(raw_path[0], (list, tuple)):
                path_override = str(raw_path[0][0])
            elif raw_path:
                path_override = str(raw_path[0])

        dimmer_val = self.master_dimmer
        if self.inputs['Master Dimmer'].is_linked:
            raw_dim = self.inputs['Master Dimmer'].sv_get()
            dimmer_val = safe_float(raw_dim[0], self.master_dimmer) if raw_dim else self.master_dimmer

        # 2. Extract coordinates per fixture or point
        items_count = max(len(fixtures), len(points), len(explicit_uvs))
        if items_count == 0:
            self.last_status = "No fixtures or points linked"
            return

        coords = []
        for i in range(items_count):
            if i < len(explicit_uvs) and self.mapping_plane == 'UV':
                coords.append((explicit_uvs[i][0], explicit_uvs[i][1], 0.0))
            elif i < len(fixtures):
                fix = fixtures[i]
                # Check for 3D coordinates in order of priority
                pos = fix.get('world_pos') or fix.get('clamp_pos') or fix.get('emitter_pos') or fix.get('location')
                if isinstance(pos, (list, tuple)) and len(pos) >= 3:
                    coords.append((safe_float(pos[0]), safe_float(pos[1]), safe_float(pos[2])))
                else:
                    coords.append((0.0, 0.0, 0.0))
            elif i < len(points):
                p = points[i]
                coords.append((safe_float(p[0]), safe_float(p[1]), safe_float(p[2]) if len(p) > 2 else 0.0))
            else:
                coords.append((0.0, 0.0, 0.0))

        # 3. Project to Planar UV coordinates
        raw_u_vals = []
        raw_v_vals = []
        for (x, y, z) in coords:
            if self.mapping_plane == 'XY':
                raw_u_vals.append(x)
                raw_v_vals.append(y)
            elif self.mapping_plane == 'XZ':
                raw_u_vals.append(x)
                raw_v_vals.append(z)
            elif self.mapping_plane == 'YZ':
                raw_u_vals.append(y)
                raw_v_vals.append(z)
            else: # UV
                raw_u_vals.append(x)
                raw_v_vals.append(y)

        # 4. Determine Bounds for Normalization
        if self.bounds_mode == 'AUTO' and self.mapping_plane != 'UV':
            min_u = min(raw_u_vals) if raw_u_vals else -1.0
            max_u = max(raw_u_vals) if raw_u_vals else 1.0
            min_v = min(raw_v_vals) if raw_v_vals else -1.0
            max_v = max(raw_v_vals) if raw_v_vals else 1.0

            span_u = max_u - min_u
            span_v = max_v - min_v

            pad_u = max(0.01, span_u * self.padding) if span_u > 0.001 else 0.5
            pad_v = max(0.01, span_v * self.padding) if span_v > 0.001 else 0.5

            b_min_u = min_u - pad_u
            b_max_u = max_u + pad_u
            b_min_v = min_v - pad_v
            b_max_v = max_v + pad_v
        elif self.bounds_mode == 'CUSTOM' and self.mapping_plane != 'UV':
            b_min_u = self.min_u_bound
            b_max_u = self.max_u_bound
            b_min_v = self.min_v_bound
            b_max_v = self.max_v_bound
        else: # UV mode
            b_min_u, b_max_u = 0.0, 1.0
            b_min_v, b_max_v = 0.0, 1.0

        span_u = max(1e-6, b_max_u - b_min_u)
        span_v = max(1e-6, b_max_v - b_min_v)

        # 5. Compute Normalized UVs
        uv_pairs = []
        for ru, rv in zip(raw_u_vals, raw_v_vals):
            u_norm = clamp((ru - b_min_u) / span_u)
            v_norm = clamp((rv - b_min_v) / span_v)

            if self.flip_x:
                u_norm = 1.0 - u_norm
            if self.flip_y:
                v_norm = 1.0 - v_norm

            uv_pairs.append((u_norm, v_norm))

        # 6. Sample Image Pixels
        img = self.get_image(path_override)
        sampled_rgb = []
        sampled_rgba = []
        sampled_hex = []
        sampled_dimmers = []
        mapped_fixtures = []

        if img is not None and img.size[0] > 0 and img.size[1] > 0:
            sampler = sample_image_bilinear if self.filter_mode == 'BILINEAR' else sample_image_nearest
            img_info = f"{img.name} ({img.size[0]}x{img.size[1]})"
            self.last_status = f"Mapped {len(uv_pairs)} from {img_info}"

            for idx, (u, v) in enumerate(uv_pairs):
                r, g, b, a = sampler(img, u, v)

                # Apply Master Dimmer
                r_eff = r * dimmer_val
                g_eff = g * dimmer_val
                b_eff = b * dimmer_val
                lum = rgb_to_luminance(r_eff, g_eff, b_eff)

                sampled_rgb.append([round(r_eff, 4), round(g_eff, 4), round(b_eff, 4)])
                sampled_rgba.append([round(r_eff, 4), round(g_eff, 4), round(b_eff, 4), round(a, 4)])
                sampled_hex.append(rgb_to_hex(r_eff, g_eff, b_eff))
                sampled_dimmers.append(round(lum, 4))

                if idx < len(fixtures):
                    new_fix = dict(fixtures[idx])
                    new_fix['color'] = (round(r_eff, 4), round(g_eff, 4), round(b_eff, 4))
                    new_fix['color_rgba'] = (round(r_eff, 4), round(g_eff, 4), round(b_eff, 4), round(a, 4))
                    new_fix['color_hex'] = rgb_to_hex(r_eff, g_eff, b_eff)
                    new_fix['dimmer'] = round(lum, 4)
                    new_fix['pixel_uv'] = (round(u, 4), round(v, 4))
                    mapped_fixtures.append(new_fix)
        else:
            # Fallback procedural color spectrum when no image is loaded
            self.last_status = "No image loaded (using rainbow fallback)"
            for idx, (u, v) in enumerate(uv_pairs):
                hue = u
                # HSL to RGB conversion for fallback
                r = clamp(abs(hue * 6.0 - 3.0) - 1.0)
                g = clamp(2.0 - abs(hue * 6.0 - 2.0))
                b = clamp(2.0 - abs(hue * 6.0 - 4.0))

                r_eff = r * dimmer_val
                g_eff = g * dimmer_val
                b_eff = b * dimmer_val
                lum = rgb_to_luminance(r_eff, g_eff, b_eff)

                sampled_rgb.append([round(r_eff, 4), round(g_eff, 4), round(b_eff, 4)])
                sampled_rgba.append([round(r_eff, 4), round(g_eff, 4), round(b_eff, 4), 1.0])
                sampled_hex.append(rgb_to_hex(r_eff, g_eff, b_eff))
                sampled_dimmers.append(round(lum, 4))

                if idx < len(fixtures):
                    new_fix = dict(fixtures[idx])
                    new_fix['color'] = (round(r_eff, 4), round(g_eff, 4), round(b_eff, 4))
                    new_fix['color_rgba'] = (round(r_eff, 4), round(g_eff, 4), round(b_eff, 4), 1.0)
                    new_fix['color_hex'] = rgb_to_hex(r_eff, g_eff, b_eff)
                    new_fix['dimmer'] = round(lum, 4)
                    new_fix['pixel_uv'] = (round(u, 4), round(v, 4))
                    mapped_fixtures.append(new_fix)

        out_uvs = [[u, v, 0.0] for (u, v) in uv_pairs]
        summary_str = f"Pixel mapped {len(uv_pairs)} fixtures/points on {self.mapping_plane} ({self.last_status})"

        self.outputs['Mapped Fixtures'].sv_set([mapped_fixtures])
        self.outputs['Colors (RGB)'].sv_set([sampled_rgb])
        self.outputs['Colors (RGBA)'].sv_set([sampled_rgba])
        self.outputs['Hex Colors'].sv_set([sampled_hex])
        self.outputs['Dimmers'].sv_set([sampled_dimmers])
        self.outputs['UV Coordinates'].sv_set([out_uvs])
        self.outputs['Summary'].sv_set([summary_str])


def register():
    bpy.utils.register_class(SvSpotlightPixelMapperNode)

def unregister():
    bpy.utils.unregister_class(SvSpotlightPixelMapperNode)
