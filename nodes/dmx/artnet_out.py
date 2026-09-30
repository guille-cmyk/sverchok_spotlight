# Sverchok Spotlight - Art-Net Output Node
# Streams real-time DMX512 data over UDP using standard Art-Net 4 protocol

import socket
import struct
import time
import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode as update_node

# Art-Net Protocol Constants
ARTNET_HEADER = b'Art-Net\x00'
ARTNET_OP_OUTPUT = 0x5000  # Little-endian 0x00, 0x50
ARTNET_PROT_VER = 14       # Version 14


def build_artdmx_packet(universe_15bit, dmx_data, sequence=0):
    """
    Constructs an 18-byte ArtDmx header followed by 512 bytes of DMX data (total 530 bytes).
    Reference: Art-Net 4 Protocol Specification (Artistic Licence)
    """
    # Clamp data to 512 bytes (0..255)
    data_bytes = bytearray(512)
    for i in range(min(512, len(dmx_data))):
        v = dmx_data[i]
        data_bytes[i] = max(0, min(255, int(v)))

    # ArtDmx header:
    # 0..7:   "Art-Net\0"
    # 8..9:   OpCode (0x5000, OpOutput / OpDmx, little-endian)
    # 10..11: ProtVer (14, big-endian)
    # 12:     Sequence (0..255)
    # 13:     Physical (0)
    # 14:     SubUni (Sub-Net [7:4] and Universe [3:0])
    # 15:     Net (Top 7 bits of 15-bit address)
    # 16..17: Length (512, big-endian)
    sub_uni = universe_15bit & 0xFF
    net = (universe_15bit >> 8) & 0x7F
    length = 512

    header = struct.pack(
        '<8sHHBBBBH',
        ARTNET_HEADER,
        ARTNET_OP_OUTPUT,
        (ARTNET_PROT_VER << 8), # big-endian packing via byte shift or standard struct
        sequence & 0xFF,
        0,                      # physical
        sub_uni,
        net,
        (length >> 8) | ((length & 0xFF) << 8)  # 512 as big-endian 0x0200
    )
    return header + data_bytes


class SV_OT_SpotlightArtNetSendOnce(bpy.types.Operator):
    """Sends a single Art-Net DMX frame immediately"""
    bl_idname = "node.sv_spotlight_artnet_send_once"
    bl_label = "Send DMX Frame"
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

            count = node.send_packets()
            self.report({'INFO'}, f"Art-Net: Sent {count} universes to {node.target_ip}:{node.target_port}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Art-Net send failed: {e}")
            return {'CANCELLED'}


class SvSpotlightArtNetOutNode(bpy.types.Node, SverchCustomTreeNode):
    """
    Streams Art-Net DMX packets over UDP to lighting consoles (grandMA onPC, Chamsys, ETC),
    visualizers (Capture, Wysiwyg), and Art-Net DMX nodes.
    """
    bl_idname = 'SvSpotlightArtNetOutNode'
    bl_label = 'Spotlight Art-Net Output'
    bl_icon = 'OUTLINER_OB_LIGHT'
    sv_icon = 'SV_COLOR_ROUGHNESS'

    target_ip: StringProperty(
        name="Target IP",
        description="Destination IP address (e.g. 127.0.0.1 for local grandMA onPC, 255.255.255.255 for broadcast)",
        default="127.0.0.1",
        update=update_node
    )

    target_port: IntProperty(
        name="UDP Port",
        description="Standard Art-Net UDP Port is 6454",
        default=6454,
        min=1024,
        max=65535,
        update=update_node
    )

    active_stream: BoolProperty(
        name="Enable Live Stream",
        description="Stream packets over network whenever tree updates",
        default=False,
        update=update_node
    )

    universe_offset: IntProperty(
        name="Universe Offset",
        description="Offset added to universe numbers (0-based in Art-Net)",
        default=0,
        min=0,
        max=128,
        update=update_node
    )

    sequence_num: IntProperty(
        name="Sequence",
        default=0
    )

    packets_sent_total: IntProperty(
        name="Total Sent",
        default=0
    )

    last_status: StringProperty(
        name="Status",
        default="Idle"
    )

    def sv_init(self, context):
        self.inputs.new('SvStringsSocket', 'Universes')
        self.inputs.new('SvStringsSocket', 'Target IP').prop_name = 'target_ip'
        self.inputs.new('SvStringsSocket', 'Active').prop_name = 'active_stream'

        self.outputs.new('SvStringsSocket', 'Status')
        self.outputs.new('SvStringsSocket', 'Packets Sent')

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, 'target_ip')
        col.prop(self, 'target_port')
        col.prop(self, 'universe_offset')
        col.prop(self, 'active_stream', toggle=True)

        op = col.operator('node.sv_spotlight_artnet_send_once', text="Send Single Frame", icon='PLAY')
        op.node_name = self.name
        op.tree_name = self.id_data.name if self.id_data else ""

        col.label(text=self.last_status, icon='INFO')

    def extract_universe_data(self):
        """Extracts universe dictionary {u_id: [512 ints]} from input socket."""
        if not self.inputs['Universes'].is_linked:
            return {}

        raw_in = self.inputs['Universes'].sv_get()
        if not raw_in:
            return {}

        # Can be [{1: [...], 2: [...]}] or [[512], [512]]
        if isinstance(raw_in, list) and len(raw_in) > 0:
            first = raw_in[0]
            if isinstance(first, dict):
                return first
            elif isinstance(first, list):
                # Check if first is list of 512 ints or list of universes
                if len(first) > 0 and isinstance(first[0], (int, float)):
                    return {1: first}
                elif len(first) > 0 and isinstance(first[0], list):
                    return {i + 1: u for i, u in enumerate(first)}
            elif isinstance(raw_in, dict):
                return raw_in
        return {}

    def send_packets(self):
        """Sends ArtDmx UDP packets for each universe."""
        uni_data = self.extract_universe_data()
        if not uni_data:
            self.last_status = "No DMX data linked"
            return 0

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Enable broadcast if destination ends with .255 or is 255.255.255.255
            if self.target_ip.endswith('.255') or self.target_ip == '255.255.255.255':
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            count = 0
            for u_num, channels in uni_data.items():
                artnet_uni = max(0, int(u_num) - 1 + self.universe_offset)
                self.sequence_num = (self.sequence_num + 1) % 256
                packet = build_artdmx_packet(artnet_uni, channels, self.sequence_num)
                sock.sendto(packet, (self.target_ip, self.target_port))
                count += 1
                self.packets_sent_total += 1

            self.last_status = f"Sent {count} universes ({count * 512} ch) -> {self.target_ip}:{self.target_port}"
            return count
        except Exception as err:
            self.last_status = f"Socket error: {err}"
            return 0
        finally:
            sock.close()

    def process(self):
        if self.inputs['Target IP'].is_linked:
            ip_val = self.inputs['Target IP'].sv_get()
            if ip_val and isinstance(ip_val[0], str):
                self.target_ip = ip_val[0]

        is_active = self.active_stream
        if self.inputs['Active'].is_linked:
            act_val = self.inputs['Active'].sv_get()
            if act_val:
                is_active = bool(act_val[0])

        if is_active:
            self.send_packets()

        self.outputs['Status'].sv_set([self.last_status])
        self.outputs['Packets Sent'].sv_set([self.packets_sent_total])


def register():
    bpy.utils.register_class(SV_OT_SpotlightArtNetSendOnce)
    bpy.utils.register_class(SvSpotlightArtNetOutNode)

def unregister():
    bpy.utils.unregister_class(SvSpotlightArtNetOutNode)
    bpy.utils.unregister_class(SV_OT_SpotlightArtNetSendOnce)
