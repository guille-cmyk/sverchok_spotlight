# Sverchok Spotlight - Beam Material & Color Assigner Node
# Creates and assigns volumetric emission/transparent materials and viewport colors to each light beam

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
    """Converts strings, hex, or numeric tuples to (r, g, b) floats in 0..1 range."""
    if isinstance(val, str):
        v = val.strip().lower()
        if v in COLOR_NAMES:
            return COLOR_NAMES[v]
        if v.startswith('#'):
            h = v.lstrip('#')
            if len(h) == 6:
                try:
                    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)
                except ValueError:
                    pass
        return (1.0, 1.0, 1.0)
    elif isinstance(val, (list, tuple)) and len(val) >= 3:
        try:
            parts = [float(x) for x in val[:3]]
            scale = 255.0 if any(p > 1.0 for p in parts) else 1.0
            return (parts[0] / scale, parts[1] / scale, parts[2] / scale)
        except Exception:
            return (1.0, 1.0, 1.0)
    return (1.0, 1.0, 1.0)


class SvSpotlightBeamMaterialNode(bpy.types.Node, SverchCustomTreeNode):
    """
    Creates and assigns dedicated emissive/transparent materials
    to light beams in the 3D viewport and render engines.
    """
    bl_idname = 'SvSpotlightBeamMaterialNode'
    bl_label = 'Spotlight Beam Material'
    bl_icon = 'MATERIAL'
    sv_icon = 'SV_COLOR_ROUGHNESS'

    material_prefix: StringProperty(
        name="Material Prefix",
        description="Prefix for procedural beam materials (e.g. Spotlight_Beam)",
        default="Spotlight_Beam",
        update=update_node
    )

    emission_strength: FloatProperty(
        name="Emission Strength",
        description="Multiplier for beam glow intensity (volumetric brightness)",
        default=5.0,
        min=0.0,
        max=100.0,
        update=update_node
    )

    beam_alpha: FloatProperty(
        name="Beam Alpha",
        description="Opacity / transparency factor for volumetric atmospheric cone look",
        default=0.25,
        min=0.01,
        max=1.0,
        update=update_node
    )

    color_source: EnumProperty(
        name="Color Source",
        description="Where beam light color is derived from",
        items=[
            ('AUTO', "Auto (Socket / Fixture)", "Use Colors input if linked, else extract from Fixture Instances"),
            ('FIXTURES', "Fixture Instances", "Extract color and dimmer from Fixture Instances metadata"),
            ('COLORS', "Colors Socket", "Strictly use linked Colors socket data"),
            ('GLOBAL', "Global Color", "Override all beams with global RGB color"),
        ],
        default='AUTO',
        update=update_node
    )

    global_color: FloatVectorProperty(
        name="Global Color",
        description="Uniform color applied to all beams when Global mode is active",
        subtype='COLOR',
        size=3,
        default=(1.0, 0.9, 0.7),
        min=0.0,
        max=1.0,
        update=update_node
    )

    auto_create_objects: BoolProperty(
        name="Create Beam Objects",
        description="Automatically create and update 3D beam mesh objects directly in scene collection",
        default=True,
        update=update_node
    )

    collection_name: StringProperty(
        name="Collection",
        description="Scene collection where beam mesh objects are organized",
        default="Spotlight_Beams",
        update=update_node
    )

    last_status: StringProperty(name="Status", default="Ready")

    def sv_init(self, context):
        self.inputs.new('SvVerticesSocket', 'Beam Verts')
        self.inputs.new('SvStringsSocket', 'Beam Polys')
        self.inputs.new('SvColorSocket', 'Colors')
        self.inputs.new('SvDictionarySocket', 'Fixture Instances')
        self.inputs.new('SvObjectSocket', 'Objects')
        self.inputs.new('SvStringsSocket', 'Emission Strength').prop_name = 'emission_strength'
        self.inputs.new('SvStringsSocket', 'Beam Alpha').prop_name = 'beam_alpha'

        self.outputs.new('SvStringsSocket', 'Materials')
        self.outputs.new('SvStringsSocket', 'Material Names')
        self.outputs.new('SvColorSocket', 'Colors (RGB)')
        self.outputs.new('SvObjectSocket', 'Objects')
        self.outputs.new('SvStringsSocket', 'Material Indices')
        self.outputs.new('SvStringsSocket', 'Summary')

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, 'material_prefix', text="Prefix")
        col.prop(self, 'color_source', text="")

        if self.color_source == 'GLOBAL':
            col.prop(self, 'global_color', text="")

        col.prop(self, 'emission_strength', slider=True)
        col.prop(self, 'beam_alpha', slider=True)

        col.separator()
        col.prop(self, 'auto_create_objects')
        if self.auto_create_objects:
            col.prop(self, 'collection_name', text="Collection")

        col.label(text=self.last_status, icon='INFO')

    def get_or_create_collection(self, col_name):
        """Finds or creates a scene collection."""
        if not col_name:
            col_name = "Spotlight_Beams"
        col = bpy.data.collections.get(col_name)
        if col is None:
            col = bpy.data.collections.new(col_name)
            bpy.context.scene.collection.children.link(col)
        elif col.name not in bpy.context.scene.collection.children:
            try:
                bpy.context.scene.collection.children.link(col)
            except Exception:
                pass
        return col

    def build_beam_material(self, mat_name, r, g, b, dimmer, strength, alpha):
        """Constructs or updates an emissive transparent material with viewport colors."""
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(mat_name)

        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Clear and recreate node setup for reliability
        nodes.clear()

        out_node = nodes.new('ShaderNodeOutputMaterial')
        out_node.location = (300, 0)

        add_node = nodes.new('ShaderNodeAddShader')
        add_node.location = (100, 0)

        emit_node = nodes.new('ShaderNodeEmission')
        emit_node.location = (-150, 100)
        emit_color = (clamp(r * dimmer), clamp(g * dimmer), clamp(b * dimmer), 1.0)
        emit_node.inputs['Color'].default_value = emit_color
        emit_node.inputs['Strength'].default_value = max(0.0, float(strength))

        trans_node = nodes.new('ShaderNodeBsdfTransparent')
        trans_node.location = (-150, -100)
        # Transmittance color based on inverse alpha
        trans_node.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)

        links.new(emit_node.outputs['Emission'], add_node.inputs[0])
        links.new(trans_node.outputs['BSDF'], add_node.inputs[1])
        links.new(add_node.outputs['Shader'], out_node.inputs['Surface'])

        # Viewport Display Shading
        mat.diffuse_color = (clamp(r * dimmer), clamp(g * dimmer), clamp(b * dimmer), clamp(alpha))

        # Alpha Transparency settings for Eevee Next (Blender 4.2) and Cycles
        if hasattr(mat, 'surface_render_method'):
            try:
                mat.surface_render_method = 'BLENDED'
            except Exception:
                pass
        if hasattr(mat, 'blend_method'):
            try:
                mat.blend_method = 'BLEND'
            except Exception:
                pass
        if hasattr(mat, 'shadow_method'):
            try:
                mat.shadow_method = 'NONE'
            except Exception:
                pass

        return mat

    def process(self):
        # 1. Collect inputs
        beam_verts = []
        if self.inputs['Beam Verts'].is_linked:
            raw_v = self.inputs['Beam Verts'].sv_get()
            if isinstance(raw_v, list):
                beam_verts = raw_v

        beam_polys = []
        if self.inputs['Beam Polys'].is_linked:
            raw_p = self.inputs['Beam Polys'].sv_get()
            if isinstance(raw_p, list):
                beam_polys = raw_p

        colors_input = []
        if self.inputs['Colors'].is_linked:
            raw_c = self.inputs['Colors'].sv_get()
            if isinstance(raw_c, list):
                for sub in raw_c:
                    if isinstance(sub, list):
                        for c in sub:
                            if isinstance(c, (list, tuple)):
                                colors_input.append(parse_color(c))
                            elif isinstance(c, str):
                                colors_input.append(parse_color(c))
                    elif isinstance(sub, (list, tuple)):
                        colors_input.append(parse_color(sub))
                    elif isinstance(sub, str):
                        colors_input.append(parse_color(sub))

        fixtures = []
        if self.inputs['Fixture Instances'].is_linked:
            raw_f = self.inputs['Fixture Instances'].sv_get()
            if isinstance(raw_f, list):
                for item in raw_f:
                    if isinstance(item, list):
                        fixtures.extend([x for x in item if isinstance(x, dict)])
                    elif isinstance(item, dict):
                        fixtures.append(item)

        input_objs = []
        if self.inputs['Objects'].is_linked:
            raw_obj = self.inputs['Objects'].sv_get()
            if isinstance(raw_obj, list):
                for o_sub in raw_obj:
                    if isinstance(o_sub, list):
                        input_objs.extend([o for o in o_sub if hasattr(o, 'data')])
                    elif hasattr(o_sub, 'data'):
                        input_objs.append(o_sub)

        strength_val = self.emission_strength
        if self.inputs['Emission Strength'].is_linked:
            raw_s = self.inputs['Emission Strength'].sv_get()
            strength_val = safe_float(raw_s[0], self.emission_strength) if raw_s else self.emission_strength

        alpha_val = self.beam_alpha
        if self.inputs['Beam Alpha'].is_linked:
            raw_a = self.inputs['Beam Alpha'].sv_get()
            alpha_val = safe_float(raw_a[0], self.beam_alpha) if raw_a else self.beam_alpha

        # 2. Determine Fixture/Beam Count
        beam_count = max(len(beam_verts), len(fixtures), len(colors_input), len(input_objs))
        if beam_count == 0:
            self.last_status = "No beam geometry, fixtures or colors linked"
            return

        # 3. Resolve Colors and Dimmers per Beam
        resolved_colors = []
        resolved_dimmers = []
        unit_ids = []

        for i in range(beam_count):
            # Fixture metadata
            fix = fixtures[i] if i < len(fixtures) else {}
            u_id = fix.get('unit_number', i + 1)
            unit_ids.append(u_id)

            # Dimmer
            dim = safe_float(fix.get('dimmer', 1.0), 1.0)
            resolved_dimmers.append(dim)

            # Color resolution based on mode
            if self.color_source == 'GLOBAL':
                resolved_colors.append((self.global_color[0], self.global_color[1], self.global_color[2]))
            elif self.color_source == 'COLORS' and i < len(colors_input):
                resolved_colors.append(colors_input[i])
            elif self.color_source == 'FIXTURES' and 'color' in fix:
                resolved_colors.append(parse_color(fix['color']))
            else: # AUTO
                if i < len(colors_input):
                    resolved_colors.append(colors_input[i])
                elif 'color' in fix:
                    resolved_colors.append(parse_color(fix['color']))
                else:
                    resolved_colors.append((1.0, 1.0, 1.0))

        # 4. Generate Materials
        created_materials = []
        created_mat_names = []
        mat_indices = list(range(beam_count))

        for i in range(beam_count):
            u_id = unit_ids[i]
            mat_name = f"{self.material_prefix}_{u_id}"
            r, g, b = resolved_colors[i]
            dim = resolved_dimmers[i]

            mat = self.build_beam_material(
                mat_name=mat_name,
                r=r,
                g=g,
                b=b,
                dimmer=dim,
                strength=strength_val,
                alpha=alpha_val
            )
            created_materials.append(mat)
            created_mat_names.append(mat.name)

        # 5. Assign Materials to Scene Objects
        output_objects = []

        # If explicit input objects provided, assign materials directly
        if input_objs:
            for i, obj in enumerate(input_objs):
                if i < len(created_materials):
                    mat = created_materials[i]
                    if len(obj.data.materials) == 0:
                        obj.data.materials.append(mat)
                    else:
                        obj.data.materials[0] = mat
                    r, g, b = resolved_colors[i]
                    dim = resolved_dimmers[i]
                    obj.color = (clamp(r * dim), clamp(g * dim), clamp(b * dim), clamp(alpha_val))
            output_objects = input_objs

        # If auto_create_objects is enabled and Beam Verts/Polys are linked
        elif self.auto_create_objects and beam_verts and beam_polys:
            collection = self.get_or_create_collection(self.collection_name)

            if len(beam_verts) >= beam_count and len(beam_polys) >= beam_count:
                # Case 1: Separate vertex/polygon lists per fixture
                for i in range(beam_count):
                    v_data = beam_verts[i]
                    p_data = beam_polys[i]
                    u_id = unit_ids[i]
                    obj_name = f"Beam_{u_id}"
                    mesh_name = f"Beam_Mesh_{u_id}"

                    mesh = bpy.data.meshes.get(mesh_name) or bpy.data.meshes.new(mesh_name)
                    mesh.clear_geometry()
                    mesh.from_pydata(v_data, [], p_data)
                    mesh.update()

                    obj = bpy.data.objects.get(obj_name)
                    if obj is None:
                        obj = bpy.data.objects.new(obj_name, mesh)
                        collection.objects.link(obj)
                    else:
                        obj.data = mesh

                    mat = created_materials[i]
                    if len(obj.data.materials) == 0:
                        obj.data.materials.append(mat)
                    else:
                        obj.data.materials[0] = mat

                    r, g, b = resolved_colors[i]
                    dim = resolved_dimmers[i]
                    obj.color = (clamp(r * dim), clamp(g * dim), clamp(b * dim), clamp(alpha_val))
                    output_objects.append(obj)

            elif len(beam_verts) == 1 and beam_count > 1:
                # Case 2: Partitions single combined mesh into individual per-beam objects
                v_all = beam_verts[0]
                p_all = beam_polys[0]
                n_polys = len(p_all)
                chunk_size = n_polys // beam_count if beam_count > 0 else n_polys
                for i in range(beam_count):
                    u_id = unit_ids[i]
                    sub_p = p_all[i * chunk_size : (i + 1) * chunk_size] if chunk_size > 0 else p_all
                    used_indices = sorted(set(idx for poly in sub_p for idx in poly))
                    remap = {old_idx: new_idx for new_idx, old_idx in enumerate(used_indices)}
                    sub_v = [v_all[idx] for idx in used_indices]
                    sub_p_remapped = [[remap[idx] for idx in poly] for poly in sub_p]

                    obj_name = f"Beam_{u_id}"
                    mesh_name = f"Beam_Mesh_{u_id}"
                    mesh = bpy.data.meshes.get(mesh_name) or bpy.data.meshes.new(mesh_name)
                    mesh.clear_geometry()
                    mesh.from_pydata(sub_v, [], sub_p_remapped)
                    mesh.update()

                    obj = bpy.data.objects.get(obj_name)
                    if obj is None:
                        obj = bpy.data.objects.new(obj_name, mesh)
                        collection.objects.link(obj)
                    else:
                        obj.data = mesh

                    mat = created_materials[i]
                    if len(obj.data.materials) == 0:
                        obj.data.materials.append(mat)
                    else:
                        obj.data.materials[0] = mat

                    r, g, b = resolved_colors[i]
                    dim = resolved_dimmers[i]
                    obj.color = (clamp(r * dim), clamp(g * dim), clamp(b * dim), clamp(alpha_val))
                    output_objects.append(obj)

            else:
                for i in range(min(len(beam_verts), len(beam_polys))):
                    v_data = beam_verts[i]
                    p_data = beam_polys[i]
                    u_id = unit_ids[i] if i < len(unit_ids) else i + 1
                    obj_name = f"Beam_{u_id}"
                    mesh_name = f"Beam_Mesh_{u_id}"

                    mesh = bpy.data.meshes.get(mesh_name) or bpy.data.meshes.new(mesh_name)
                    mesh.clear_geometry()
                    mesh.from_pydata(v_data, [], p_data)
                    mesh.update()

                    obj = bpy.data.objects.get(obj_name)
                    if obj is None:
                        obj = bpy.data.objects.new(obj_name, mesh)
                        collection.objects.link(obj)
                    else:
                        obj.data = mesh

                    mat = created_materials[i] if i < len(created_materials) else created_materials[0]
                    if len(obj.data.materials) == 0:
                        obj.data.materials.append(mat)
                    else:
                        obj.data.materials[0] = mat

                    r, g, b = resolved_colors[i] if i < len(resolved_colors) else (1.0, 1.0, 1.0)
                    dim = resolved_dimmers[i] if i < len(resolved_dimmers) else 1.0
                    obj.color = (clamp(r * dim), clamp(g * dim), clamp(b * dim), clamp(alpha_val))
                    output_objects.append(obj)

        self.last_status = f"Assigned {len(created_materials)} beam materials"
        summary_str = f"Created {len(created_materials)} materials ('{self.material_prefix}'), strength={strength_val:.1f}, alpha={alpha_val:.2f}"

        # 6. Set Outputs
        self.outputs['Materials'].sv_set([created_materials])
        self.outputs['Material Names'].sv_set([created_mat_names])
        self.outputs['Colors (RGB)'].sv_set([resolved_colors])
        self.outputs['Objects'].sv_set([output_objects])
        self.outputs['Material Indices'].sv_set([mat_indices])
        self.outputs['Summary'].sv_set([summary_str])


def register():
    bpy.utils.register_class(SvSpotlightBeamMaterialNode)

def unregister():
    bpy.utils.unregister_class(SvSpotlightBeamMaterialNode)
