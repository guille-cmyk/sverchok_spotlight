# Sverchok Spotlight - Live DMX Mapper Node
# Maps parametric fixture values (Pan, Tilt, Dimmer, Color, Strobe) to 512-channel DMX universes

import bpy
from bpy.props import FloatProperty, IntProperty, BoolProperty, FloatVectorProperty, EnumProperty
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode as update_node

def clamp_byte(val):
    """Clamps a numeric value to an integer 0..255."""
    try:
        return max(0, min(255, int(round(float(val)))))
    except Exception:
        return 0

def safe_float(val, default=0.0):
    """Safely converts any value to a float."""
    try:
        if isinstance(val, (list, tuple)):
            return float(val[0]) if len(val) > 0 else default
        return float(val)
    except Exception:
        return default

COLOR_NAMES = {
    'open white': (1.0, 1.0, 1.0),
    'white': (1.0, 1.0, 1.0),
    'red': (1.0, 0.0, 0.0),
    'green': (0.0, 1.0, 0.0),
    'blue': (0.0, 0.0, 1.0),
    'amber': (1.0, 0.75, 0.0),
    'warm white': (1.0, 0.9, 0.7),
    'cool white': (0.9, 0.95, 1.0),
    'cyan': (0.0, 1.0, 1.0),
    'magenta': (1.0, 0.0, 1.0),
    'yellow': (1.0, 1.0, 0.0),
    'orange': (1.0, 0.5, 0.0),
    'uv': (0.3, 0.0, 0.8),
    'purple': (0.5, 0.0, 0.5),
    'pink': (1.0, 0.4, 0.7),
}

def parse_color(val):
    """Converts string names, hex colors, or numeric sequences into (r, g, b) floats in 0..1 range."""
    if isinstance(val, str):
        val_clean = val.strip().lower()
        if val_clean in COLOR_NAMES:
            return COLOR_NAMES[val_clean]
        if val_clean.startswith('#'):
            h = val_clean.lstrip('#')
            if len(h) == 6:
                try:
                    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)
                except ValueError:
                    pass
        if ',' in val_clean:
            try:
                parts = [float(p.strip()) for p in val_clean.split(',')]
                if len(parts) >= 3:
                    scale = 255.0 if any(p > 1.0 for p in parts[:3]) else 1.0
                    return (parts[0] / scale, parts[1] / scale, parts[2] / scale)
            except Exception:
                pass
        return (1.0, 1.0, 1.0)
    elif isinstance(val, (list, tuple)):
        try:
            parts = [float(x) for x in val[:3]]
            while len(parts) < 3:
                parts.append(1.0)
            scale = 255.0 if any(p > 1.0 for p in parts) else 1.0
            return (parts[0] / scale, parts[1] / scale, parts[2] / scale)
        except Exception:
            return (1.0, 1.0, 1.0)
    return (1.0, 1.0, 1.0)

def angle_to_16bit(angle_deg, min_deg=-270.0, max_deg=270.0):
    """Converts an angle in degrees to 16-bit DMX coarse (0..255) and fine (0..255)."""
    angle_deg = safe_float(angle_deg, 0.0)
    span = max_deg - min_deg
    if span <= 0:
        return 0, 0
    norm = (angle_deg - min_deg) / span
    val_16 = max(0, min(65535, int(round(norm * 65535))))
    coarse = (val_16 >> 8) & 0xFF
    fine = val_16 & 0xFF
    return coarse, fine


class SvSpotlightLiveDMXMapperNode(bpy.types.Node, SverchCustomTreeNode):
    """
    Triggers/maps fixture parameters (Pan, Tilt, Dimmer, RGB, Strobe)
    into 512-channel DMX universe byte arrays ready for Art-Net transmission.
    """
    bl_idname = 'SvSpotlightLiveDMXMapperNode'
    bl_label = 'Spotlight Live DMX Mapper'
    bl_icon = 'LIGHT'
    sv_icon = 'SV_COLOR_ROUGHNESS'

    master_dimmer: FloatProperty(
        name="Master Dimmer",
        description="Global dimmer multiplier (0.0 to 1.0)",
        default=1.0,
        min=0.0,
        max=1.0,
        update=update_node
    )

    strobe_val: IntProperty(
        name="Strobe",
        description="Global strobe value (0 = open, 1-255 = strobe)",
        default=0,
        min=0,
        max=255,
        update=update_node
    )

    override_color: BoolProperty(
        name="Color Override",
        description="Override fixture colors with global color",
        default=False,
        update=update_node
    )

    global_color: FloatVectorProperty(
        name="Global RGB",
        description="Global RGB color override",
        subtype='COLOR',
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        update=update_node
    )

    def sv_init(self, context):
        self.inputs.new('SvStringsSocket', 'Fixtures')
        self.inputs.new('SvStringsSocket', 'Master Dimmer').prop_name = 'master_dimmer'
        self.inputs.new('SvStringsSocket', 'Strobe').prop_name = 'strobe_val'
        self.inputs.new('SvColorSocket', 'Global Color').prop_name = 'global_color'

        self.outputs.new('SvStringsSocket', 'Universes')
        self.outputs.new('SvStringsSocket', 'Universe 1')
        self.outputs.new('SvStringsSocket', 'DMX Matrix')
        self.outputs.new('SvStringsSocket', 'Summary')

    def draw_buttons(self, context, layout):
        layout.prop(self, 'master_dimmer', slider=True)
        layout.prop(self, 'override_color')
        if self.override_color:
            layout.prop(self, 'global_color', text="")
        layout.prop(self, 'strobe_val')

    def process(self):
        try:
            fixtures_input = self.inputs['Fixtures'].sv_get()
        except Exception:
            return

        if not fixtures_input:
            return

        # Flatten in case of nested Sverchok socket structures
        fixture_list = []
        if isinstance(fixtures_input, list):
            for item in fixtures_input:
                if isinstance(item, list):
                    fixture_list.extend([x for x in item if isinstance(x, dict)])
                elif isinstance(item, dict):
                    fixture_list.append(item)

        master_dim = self.inputs['Master Dimmer'].sv_get()[0] if self.inputs['Master Dimmer'].is_linked else self.master_dimmer
        strobe_ctrl = self.inputs['Strobe'].sv_get()[0] if self.inputs['Strobe'].is_linked else self.strobe_val
        if isinstance(master_dim, list):
            master_dim = master_dim[0]
        if isinstance(strobe_ctrl, list):
            strobe_ctrl = strobe_ctrl[0]

        # Allocate 512 channels for all universes encountered (default 1 to 4)
        universes = {}
        for u in range(1, 5):
            universes[u] = [0] * 512

        mapped_count = 0
        for fix in fixture_list:
            u_id = int(safe_float(fix.get('universe', 1), 1))
            addr = int(safe_float(fix.get('address', 1), 1))  # 1-based (1..512)
            if u_id not in universes:
                universes[u_id] = [0] * 512

            ch_count = int(safe_float(fix.get('channel_count', 1), 1))
            ftype = str(fix.get('fixture_type', 'Profile')).lower()

            # Base values
            dim = safe_float(fix.get('dimmer', 1.0), 1.0) * safe_float(master_dim, 1.0)
            dim_byte = clamp_byte(dim * 255.0 if dim <= 1.0 else dim)

            pan = safe_float(fix.get('pan', 0.0), 0.0)
            tilt = safe_float(fix.get('tilt', 0.0), 0.0)
            pan_c, pan_f = angle_to_16bit(pan, -270.0, 270.0)
            tilt_c, tilt_f = angle_to_16bit(tilt, -135.0, 135.0)

            if self.override_color:
                r_byte = clamp_byte(self.global_color[0] * 255.0)
                g_byte = clamp_byte(self.global_color[1] * 255.0)
                b_byte = clamp_byte(self.global_color[2] * 255.0)
            else:
                col = fix.get('color', (1.0, 1.0, 1.0))
                r_f, g_f, b_f = parse_color(col)
                r_byte = clamp_byte(r_f * 255.0)
                g_byte = clamp_byte(g_f * 255.0)
                b_byte = clamp_byte(b_f * 255.0)

            strobe_byte = clamp_byte(safe_float(strobe_ctrl, 0))

            # Map based on standard fixture profiles
            ch_data = [0] * ch_count
            if ch_count == 1:
                # Conventional Dimmer
                ch_data[0] = dim_byte
            elif 'wash' in ftype or 'aura' in ftype:
                # LED Wash Profile (Pan, PanFine, Tilt, TiltFine, Dimmer, Shutter, R, G, B, W)
                assignments = [pan_c, pan_f, tilt_c, tilt_f, dim_byte, strobe_byte, r_byte, g_byte, b_byte, 255]
                for idx, v in enumerate(assignments):
                    if idx < ch_count:
                        ch_data[idx] = v
            elif 'batten' in ftype or 'par' in ftype:
                # LED RGBW Par / Batten (Dimmer, R, G, B, Strobe)
                assignments = [dim_byte, r_byte, g_byte, b_byte, strobe_byte]
                for idx, v in enumerate(assignments):
                    if idx < ch_count:
                        ch_data[idx] = v
            else:
                # Standard Moving Light / Spot / Profile (Pan, PanFine, Tilt, TiltFine, Dimmer, Shutter, R, G, B, Zoom)
                assignments = [pan_c, pan_f, tilt_c, tilt_f, dim_byte, strobe_byte, r_byte, g_byte, b_byte, 128]
                for idx, v in enumerate(assignments):
                    if idx < ch_count:
                        ch_data[idx] = v

            # Write into universe array (converting 1-based address to 0-based index)
            start_idx = max(0, addr - 1)
            for c_offset, byte_val in enumerate(ch_data):
                slot = start_idx + c_offset
                if slot < 512:
                    universes[u_id][slot] = byte_val

            mapped_count += 1

        # Prepare outputs
        uni_matrix = [universes[k] for k in sorted(universes.keys())]
        uni_1 = universes.get(1, [0] * 512)
        summary_str = f"Mapped {mapped_count} fixtures across {len(universes)} universes (Master: {int(master_dim*100)}%)"

        self.outputs['Universes'].sv_set([universes])
        self.outputs['Universe 1'].sv_set([uni_1])
        self.outputs['DMX Matrix'].sv_set(uni_matrix)
        self.outputs['Summary'].sv_set([summary_str])


def register():
    bpy.utils.register_class(SvSpotlightLiveDMXMapperNode)

def unregister():
    bpy.utils.unregister_class(SvSpotlightLiveDMXMapperNode)
