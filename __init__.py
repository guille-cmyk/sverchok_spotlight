# Sverchok Spotlight - Entertainment Lighting, Rigging & DMX Paperwork Suite
# Parametric Vectorworks Spotlight equivalents for Sverchok & Blender

bl_info = {
    "name": "Sverchok Spotlight",
    "author": "Antigravity",
    "version": (1, 1, 0),
    "blender": (4, 2, 0),
    "location": "Node Editor > Sverchok > Shift+A > Spotlight (or Header Menu)",
    "description": "Parametric Vectorworks Spotlight suite: Rigging, Fixtures, Focus, Photometrics, DMX, Art-Net, grandMA, and MVR exchange.",
    "category": "Node",
}

import importlib
import sys
import bpy
import logging

from . import utils
from . import nodes

logger = logging.getLogger('sverchok.spotlight')

spotlight_menu_config = [
    {"Spotlight": [
        {"Rigging": [
            'SvSpotlightTrussNode',
            'SvSpotlightHangPositionNode',
        ]},
        {"Fixtures": [
            'SvSpotlightFixtureDefNode',
            'SvSpotlightFixtureImportNode',
            'SvSpotlightInstrumentArrayNode',
        ]},
        {"Focus": [
            'SvSpotlightFocusAimNode',
        ]},
        {"Photometrics": [
            'SvSpotlightPhotometricsNode',
            'SvSpotlightBeamMaterialNode',
        ]},
        {"DMX Control": [
            'SvSpotlightDMXPatcherNode',
            'SvSpotlightPixelMapperNode',
            'SvSpotlightLiveDMXMapperNode',
            'SvSpotlightArtNetOutNode',
            'SvSpotlightPaperworkNode',
        ]},
        {"Exchange": [
            'SvSpotlightMVRExportNode',
            'SvSpotlightGrandMANode',
        ]},
    ]}
]


# =========================================================================
# Submenu definitions for direct NODE_MT_add integration
# =========================================================================

def node_add_operator(layout, node_type, label, icon='NONE'):
    """Helper to draw node creation operator button in menus."""
    op = layout.operator("node.add_node", text=label, icon=icon)
    op.type = node_type
    op.use_transform = True
    return op


class SV_MT_SpotlightRiggingMenu(bpy.types.Menu):
    bl_idname = "SV_MT_spotlight_rigging_menu"
    bl_label = "Rigging"

    def draw(self, context):
        layout = self.layout
        node_add_operator(layout, 'SvSpotlightTrussNode', "Truss Generator (Box/Tri/Ladder)", icon='MESH_CYLINDER')
        node_add_operator(layout, 'SvSpotlightHangPositionNode', "Hang Position & Spacing", icon='SNAP_VERTEX')


class SV_MT_SpotlightFixturesMenu(bpy.types.Menu):
    bl_idname = "SV_MT_spotlight_fixtures_menu"
    bl_label = "Fixtures"

    def draw(self, context):
        layout = self.layout
        node_add_operator(layout, 'SvSpotlightFixtureDefNode', "Lighting Instrument Def (Presets)", icon='LIGHT')
        node_add_operator(layout, 'SvSpotlightFixtureImportNode', "Fixture Profile Importer (OFL / GDTF / QLC+)", icon='IMPORT')
        node_add_operator(layout, 'SvSpotlightInstrumentArrayNode', "Instrument Array (3D Geometry)", icon='GROUP')


class SV_MT_SpotlightFocusMenu(bpy.types.Menu):
    bl_idname = "SV_MT_spotlight_focus_menu"
    bl_label = "Focus & Aim"

    def draw(self, context):
        layout = self.layout
        node_add_operator(layout, 'SvSpotlightFocusAimNode', "Focus & Aim Point (Pan/Tilt)", icon='TRACKING')


class SV_MT_SpotlightPhotometricsMenu(bpy.types.Menu):
    bl_idname = "SV_MT_spotlight_photometrics_menu"
    bl_label = "Photometrics"

    def draw(self, context):
        layout = self.layout
        node_add_operator(layout, 'SvSpotlightPhotometricsNode', "Photometric Cone & Footprint", icon='CONE')
        node_add_operator(layout, 'SvSpotlightBeamMaterialNode', "Beam Material & Color Assigner", icon='MATERIAL')


class SV_MT_SpotlightDMXMenu(bpy.types.Menu):
    bl_idname = "SV_MT_spotlight_dmx_menu"
    bl_label = "DMX & Control"

    def draw(self, context):
        layout = self.layout
        node_add_operator(layout, 'SvSpotlightDMXPatcherNode', "Multi-Universe DMX Patcher", icon='PREFERENCES')
        node_add_operator(layout, 'SvSpotlightPixelMapperNode', "Pixel Mapper (Texture to Color)", icon='IMAGE_RGB')
        node_add_operator(layout, 'SvSpotlightLiveDMXMapperNode', "Live DMX Mapper (512 Channels)", icon='COLOR')
        node_add_operator(layout, 'SvSpotlightArtNetOutNode', "Art-Net UDP Streamer", icon='OUTLINER_OB_LIGHT')
        node_add_operator(layout, 'SvSpotlightPaperworkNode', "DMX Paperwork & Schedules", icon='TEXT')


class SV_MT_SpotlightExchangeMenu(bpy.types.Menu):
    bl_idname = "SV_MT_spotlight_exchange_menu"
    bl_label = "Exchange & Export"

    def draw(self, context):
        layout = self.layout
        node_add_operator(layout, 'SvSpotlightMVRExportNode', "MVR DIN SPEC 15800 Export", icon='PACKAGE')
        node_add_operator(layout, 'SvSpotlightGrandMANode', "grandMA2 / grandMA3 Export", icon='EXPORT')


class SV_MT_SpotlightMainMenu(bpy.types.Menu):
    bl_idname = "SV_MT_spotlight_main_menu"
    bl_label = "Spotlight"

    def draw(self, context):
        layout = self.layout
        layout.menu("SV_MT_spotlight_rigging_menu", icon='MESH_CYLINDER')
        layout.menu("SV_MT_spotlight_fixtures_menu", icon='LIGHT')
        layout.menu("SV_MT_spotlight_focus_menu", icon='TRACKING')
        layout.menu("SV_MT_spotlight_photometrics_menu", icon='CONE')
        layout.separator()
        layout.menu("SV_MT_spotlight_dmx_menu", icon='PREFERENCES')
        layout.menu("SV_MT_spotlight_exchange_menu", icon='PACKAGE')
        layout.separator()
        layout.operator("node.sverchok_spotlight_create_sample_rig", text="Create Demo Spotlight Rig", icon='FILE_NEW')
        layout.operator("node.sverchok_spotlight_reload", text="Reload Spotlight Suite", icon='FILE_REFRESH')


def draw_spotlight_add_menu(self, context):
    """Appended directly into Blender's NODE_MT_add so Shift+A always has Spotlight in Sverchok."""
    if context.space_data and context.space_data.tree_type == 'SverchCustomTreeType':
        self.layout.separator()
        self.layout.menu("SV_MT_spotlight_main_menu", text="Spotlight", icon='LIGHT')


def draw_spotlight_header_menu(self, context):
    """Draws a dedicated Spotlight menu in Node Editor header bar."""
    if context.space_data and context.space_data.tree_type == 'SverchCustomTreeType':
        self.layout.menu("SV_MT_spotlight_main_menu", text="Spotlight", icon='LIGHT')


# =========================================================================
# Operators: Quick Demo Rig & Dynamic Suite Reload
# =========================================================================

class SV_OT_SpotlightCreateSampleRig(bpy.types.Operator):
    """Creates a complete Sverchok Spotlight Rig node tree with one click"""
    bl_idname = "node.sverchok_spotlight_create_sample_rig"
    bl_label = "Create Spotlight Demo Rig"
    bl_options = {'REGISTER'}

    def execute(self, context):
        tree_name = "Spotlight_Demo_Rig"
        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            tree = bpy.data.node_groups.new(name=tree_name, type='SverchCustomTreeType')

        # Clear existing nodes in tree
        tree.nodes.clear()

        # 1. Stage 1: Truss Node
        n_truss = tree.nodes.new(type='SvSpotlightTrussNode')
        n_truss.location = (-1050, 200)
        n_truss.length = 10.0
        n_truss.trim_height = 6.0

        # 2. Stage 2: Hanging Points (Hang Position Node)
        n_hang = tree.nodes.new(type='SvSpotlightHangPositionNode')
        n_hang.location = (-800, 200)
        n_hang.position_name = "FOH Truss A"
        n_hang.fixture_count = 6

        # 3. Stage 3: Focus Aim Node (calculates Pan/Tilt & Aimed Matrices directly from hang points)
        n_aim = tree.nodes.new(type='SvSpotlightFocusAimNode')
        n_aim.location = (-550, 200)
        n_aim.default_focus_target = (0.0, 0.0, 0.0)

        # Fixture Profile Specification
        n_fixdef = tree.nodes.new(type='SvSpotlightFixtureDefNode')
        n_fixdef.location = (-550, -100)
        n_fixdef.preset_choice = "Robe Robin MegaPointe"
        from .nodes.fixtures.fixture_def import on_preset_change
        on_preset_change(n_fixdef, None)

        # 4. Stage 4: Fixture Positioning with Pan/Tilt (Instrument Array Node)
        n_array = tree.nodes.new(type='SvSpotlightInstrumentArrayNode')
        n_array.location = (-280, 150)

        # 5. Stage 5: Light Analysis (Photometrics Node with Standards Compliance 0/1 array)
        n_photo = tree.nodes.new(type='SvSpotlightPhotometricsNode')
        n_photo.location = (20, 300)
        n_photo.standard_preset = 'STAGE_500'
        n_photo.min_lux_threshold = 500.0

        # 6. DMX Patcher Node
        n_patch = tree.nodes.new(type='SvSpotlightDMXPatcherNode')
        n_patch.location = (20, -50)

        # 7. Live DMX Mapper Node
        n_mapper = tree.nodes.new(type='SvSpotlightLiveDMXMapperNode')
        n_mapper.location = (280, 150)

        # 8. Art-Net UDP Streamer Node
        n_artnet = tree.nodes.new(type='SvSpotlightArtNetOutNode')
        n_artnet.location = (540, 250)

        # 9. Paperwork Schedules Node
        n_paper = tree.nodes.new(type='SvSpotlightPaperworkNode')
        n_paper.location = (280, -150)

        # 10. MVR Export Node
        n_mvr = tree.nodes.new(type='SvSpotlightMVRExportNode')
        n_mvr.location = (540, 50)

        # 11. grandMA Export Node
        n_gma = tree.nodes.new(type='SvSpotlightGrandMANode')
        n_gma.location = (540, -120)

        # 12. Pixel Mapper Node (texture image to fixture colors)
        n_pixmap = tree.nodes.new(type='SvSpotlightPixelMapperNode')
        n_pixmap.location = (20, -260)

        # 13. Beam Material Node (assigns light color to material for each beam)
        n_beammat = tree.nodes.new(type='SvSpotlightBeamMaterialNode')
        n_beammat.location = (280, 420)

        # Connect Sockets (input_socket, output_socket)
        try:
            # Stage 1 (Truss) -> Stage 2 (Hanging Points)
            tree.links.new(n_hang.inputs['Matrix'], n_truss.outputs['Clamp Matrices'])

            # Stage 2 (Hanging Points) -> Stage 3 (Focus Aim)
            tree.links.new(n_aim.inputs['Hang Matrices'], n_hang.outputs['Hang Matrices'])

            # Stage 2 & 3 -> Stage 4 (Fixture Positioning with Pan/Tilt)
            tree.links.new(n_array.inputs['Hang Matrices'], n_hang.outputs['Hang Matrices'])
            tree.links.new(n_array.inputs['Position Data'], n_hang.outputs['Position Data'])
            tree.links.new(n_array.inputs['Aimed Matrices'], n_aim.outputs['Aimed Matrices'])
            tree.links.new(n_array.inputs['Pan (deg)'], n_aim.outputs['Pan (deg)'])
            tree.links.new(n_array.inputs['Tilt (deg)'], n_aim.outputs['Tilt (deg)'])
            tree.links.new(n_array.inputs['Fixture Profile'], n_fixdef.outputs['Fixture Profile'])

            # Stage 4 -> Stage 5 (Light Analysis / Photometrics)
            tree.links.new(n_photo.inputs['Aimed Matrices'], n_array.outputs['Fixture Matrices'])
            tree.links.new(n_photo.inputs['Fixture Instances'], n_array.outputs['Fixture Instances'])
            tree.links.new(n_photo.inputs['Beam Angle'], n_fixdef.outputs['Beam Angle'])
            tree.links.new(n_photo.inputs['Field Angle'], n_fixdef.outputs['Field Angle'])
            tree.links.new(n_photo.inputs['Candela'], n_fixdef.outputs['Candela'])

            # Stage 4 -> Pixel Mapper (map texture pixels to fixture light colors)
            tree.links.new(n_pixmap.inputs['Fixtures'], n_array.outputs['Fixture Instances'])

            # Stage 5 & Pixel Mapper -> Beam Material Assigner
            tree.links.new(n_beammat.inputs['Beam Verts'], n_photo.outputs['Beam Verts'])
            tree.links.new(n_beammat.inputs['Beam Polys'], n_photo.outputs['Beam Polys'])
            tree.links.new(n_beammat.inputs['Colors'], n_pixmap.outputs['Colors (RGB)'])
            tree.links.new(n_beammat.inputs['Fixture Instances'], n_pixmap.outputs['Mapped Fixtures'])

            # Pixel Mapped Fixtures -> DMX Patcher
            tree.links.new(n_patch.inputs['Fixtures'], n_pixmap.outputs['Mapped Fixtures'])

            # DMX Patcher -> Controls, Paperwork & Exchange
            tree.links.new(n_mapper.inputs['Fixtures'], n_patch.outputs['Patched Fixtures'])
            tree.links.new(n_paper.inputs['Patched Fixtures'], n_patch.outputs['Patched Fixtures'])
            tree.links.new(n_mvr.inputs['Fixtures'], n_patch.outputs['Patched Fixtures'])
            tree.links.new(n_gma.inputs['Fixtures'], n_patch.outputs['Patched Fixtures'])

            # Live DMX Mapper -> Art-Net Streamer
            tree.links.new(n_artnet.inputs['Universes'], n_mapper.outputs['Universes'])

            # Optional 3D Viewport Viewer Draw nodes
            for v_type in ['SvViewerDrawMk4', 'SvViewerDraw', 'ViewerNode2']:
                if hasattr(bpy.types, v_type):
                    # 1. 3D Fixture Symbols
                    n_view = tree.nodes.new(type=v_type)
                    n_view.location = (-280, 480)
                    v_in = n_view.inputs.get('vertices') or n_view.inputs.get('Vertices')
                    p_in = n_view.inputs.get('data') or n_view.inputs.get('polygons') or n_view.inputs.get('Polygons')
                    if v_in:
                        tree.links.new(v_in, n_array.outputs['Vertices'])
                    if p_in:
                        tree.links.new(p_in, n_array.outputs['Polygons'])

                    # 2. Photometric Beam Cones originating at Light Generator / Front Lens
                    n_cone_view = tree.nodes.new(type=v_type)
                    n_cone_view.location = (20, 560)
                    cv_in = n_cone_view.inputs.get('vertices') or n_cone_view.inputs.get('Vertices')
                    cp_in = n_cone_view.inputs.get('data') or n_cone_view.inputs.get('polygons') or n_cone_view.inputs.get('Polygons')
                    if cv_in:
                        tree.links.new(cv_in, n_photo.outputs['Beam Verts'])
                    if cp_in:
                        tree.links.new(cp_in, n_photo.outputs['Beam Polys'])
                    break
        except Exception as e:
            logger.warning("Auto-linking warning: %s", e)

        # Set tree active in current node editor if possible
        try:
            if context and getattr(context, 'space_data', None) and hasattr(context.space_data, 'node_tree'):
                context.space_data.node_tree = tree
        except Exception:
            pass

        try:
            self.report({'INFO'}, f"Spotlight Demo Rig created in node tree '{tree_name}'")
        except Exception:
            pass
        return {'FINISHED'}


class SV_OT_SpotlightReload(bpy.types.Operator):
    """Reloads all Sverchok Spotlight modules and updates node registry"""
    bl_idname = "node.sverchok_spotlight_reload"
    bl_label = "Reload Spotlight Nodes"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            reload_all_modules()
            try:
                self.report({'INFO'}, "Sverchok Spotlight Suite reloaded successfully.")
            except Exception:
                pass
            return {'FINISHED'}
        except Exception as err:
            try:
                self.report({'ERROR'}, f"Failed to reload Spotlight: {err}")
            except Exception:
                pass
            return {'CANCELLED'}


def reload_all_modules():
    """Reloads all Python submodules of sverchok_spotlight."""
    unregister()

    # Reload utility modules
    importlib.reload(utils.lighting_math)
    importlib.reload(utils.presets)
    importlib.reload(utils)

    # Reload rigging
    from .nodes.rigging import truss_gen, hang_position
    importlib.reload(truss_gen)
    importlib.reload(hang_position)
    from .nodes import rigging
    importlib.reload(rigging)

    # Reload fixtures
    from .nodes.fixtures import fixture_def, fixture_import, instrument_array
    importlib.reload(fixture_def)
    importlib.reload(fixture_import)
    importlib.reload(instrument_array)
    from .nodes import fixtures
    importlib.reload(fixtures)

    # Reload focus
    from .nodes.focus import focus_aim
    importlib.reload(focus_aim)
    from .nodes import focus
    importlib.reload(focus)

    # Reload photometrics
    from .nodes.photometrics import photometrics
    importlib.reload(photometrics)
    from .nodes import photometrics as pm_pkg
    importlib.reload(pm_pkg)

    # Reload dmx
    from .nodes.dmx import dmx_patcher, paperwork, live_dmx_mapper, artnet_out
    importlib.reload(dmx_patcher)
    importlib.reload(paperwork)
    importlib.reload(live_dmx_mapper)
    importlib.reload(artnet_out)
    from .nodes import dmx
    importlib.reload(dmx)

    # Reload exchange
    from .nodes.exchange import grandma_export, mvr_export
    importlib.reload(grandma_export)
    importlib.reload(mvr_export)
    from .nodes import exchange
    importlib.reload(exchange)

    # Reload nodes root
    importlib.reload(nodes)

    register()
    print("Sverchok Spotlight modules fully reloaded.")


# =========================================================================
# Registration
# =========================================================================

ui_classes = [
    SV_MT_SpotlightRiggingMenu,
    SV_MT_SpotlightFixturesMenu,
    SV_MT_SpotlightFocusMenu,
    SV_MT_SpotlightPhotometricsMenu,
    SV_MT_SpotlightDMXMenu,
    SV_MT_SpotlightExchangeMenu,
    SV_MT_SpotlightMainMenu,
    SV_OT_SpotlightCreateSampleRig,
    SV_OT_SpotlightReload,
]


def register():
    # 1. Register node classes
    nodes.register()

    # 2. Register UI menus and operators
    for cls in ui_classes:
        bpy.utils.register_class(cls)

    # 3. Append to Blender's standard Node Add menu and Header
    if not bpy.app.background:
        bpy.types.NODE_MT_add.append(draw_spotlight_add_menu)
        bpy.types.NODE_HT_header.append(draw_spotlight_header_menu)

    # 4. Register into Sverchok's custom category menu system
    try:
        from sverchok.ui import nodeview_space_menu as sm
        menu = sm.get_add_node_menu()
        if menu:
            categories = [getattr(c, 'name', '') for c in menu]
            if "Spotlight" not in categories:
                menu.append_from_config(spotlight_menu_config)
                menu.register()
    except Exception as e:
        logger.warning("Sverchok category menu registration deferred: %s", e)

    print("Sverchok Spotlight Suite registered successfully.")


def unregister():
    # 1. Remove from Sverchok's custom category menu
    try:
        from sverchok.ui import nodeview_space_menu as sm
        menu = sm.get_add_node_menu()
        if menu and hasattr(menu, 'menu_cls') and hasattr(menu.menu_cls, 'draw_data'):
            for elem in list(menu.menu_cls.draw_data):
                if getattr(elem, 'name', None) == 'Spotlight':
                    if hasattr(elem, 'unregister'):
                        try:
                            elem.unregister()
                        except Exception:
                            pass
                    try:
                        menu.menu_cls.draw_data.remove(elem)
                    except Exception:
                        pass
    except Exception as e:
        logger.warning("Could not cleanly remove Sverchok Spotlight menu: %s", e)

    # 2. Remove header and add menu callbacks
    try:
        bpy.types.NODE_MT_add.remove(draw_spotlight_add_menu)
    except Exception:
        pass
    try:
        bpy.types.NODE_HT_header.remove(draw_spotlight_header_menu)
    except Exception:
        pass

    # 3. Unregister UI classes
    for cls in reversed(ui_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    # 4. Unregister nodes
    try:
        nodes.unregister()
    except Exception:
        pass
    print("Sverchok Spotlight Suite unregistered.")


if __name__ == "__main__":
    register()
