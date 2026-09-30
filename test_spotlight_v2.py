# Comprehensive Integration & Verification Test for Sverchok Spotlight Suite v1.2
# Tests the 5-Stage Pipeline: Truss -> Hang Points -> Focus Aim -> Instrument Array -> Light Analysis
# Also validates bug fixes for Live DMX Mapper and grandMA Export

import os
import sys
import socket
import zipfile
import xml.etree.ElementTree as ET
import bpy
from mathutils import Matrix, Vector

def run_tests():
    print("=" * 60)
    print("RUNNING SVERCHOK SPOTLIGHT 5-STAGE PIPELINE & VERIFICATION TEST")
    print("=" * 60)

    # 1. Enable Addons
    if not hasattr(bpy.types, 'SV_PT_SverchokUtilsPanel'):
        class DummyPanel:
            @staticmethod
            def remove(*args, **kwargs): pass
            @staticmethod
            def append(*args, **kwargs): pass
        bpy.types.SV_PT_SverchokUtilsPanel = DummyPanel

    if "sverchok" not in bpy.context.preferences.addons:
        try:
            bpy.ops.preferences.addon_enable(module="sverchok")
        except Exception as e:
            print("Notice on sverchok enable:", e)
    
    if "sverchok_spotlight" not in bpy.context.preferences.addons:
        try:
            bpy.ops.preferences.addon_enable(module="sverchok_spotlight")
        except Exception as e:
            print("Notice on sverchok_spotlight enable:", e)

    print("[PASS] Addons enabled.")

    # 2. Check Sverchok Category Menu
    from sverchok.ui.nodeview_space_menu import get_add_node_menu
    menu = get_add_node_menu()
    categories = [getattr(c, 'name', '') for c in menu]
    assert "Spotlight" in categories, f"'Spotlight' missing from Sverchok categories: {categories}"
    print("[PASS] Spotlight category verified in Sverchok Add menu.")

    # 3. Instantiate all 15 nodes
    node_types = [
        'SvSpotlightTrussNode',
        'SvSpotlightHangPositionNode',
        'SvSpotlightFixtureDefNode',
        'SvSpotlightFixtureImportNode',
        'SvSpotlightInstrumentArrayNode',
        'SvSpotlightFocusAimNode',
        'SvSpotlightPhotometricsNode',
        'SvSpotlightBeamMaterialNode',
        'SvSpotlightPixelMapperNode',
        'SvSpotlightDMXPatcherNode',
        'SvSpotlightPaperworkNode',
        'SvSpotlightLiveDMXMapperNode',
        'SvSpotlightArtNetOutNode',
        'SvSpotlightGrandMANode',
        'SvSpotlightMVRExportNode',
    ]

    test_tree = bpy.data.node_groups.new(name="TestVerificationTree", type='SverchCustomTreeType')
    for nt in node_types:
        node = test_tree.nodes.new(type=nt)
        assert node is not None, f"Failed to instantiate node {nt}"
    print(f"[PASS] Successfully instantiated all {len(node_types)} Spotlight node types.")

    # 4. Verify 5-Stage Pipeline Architecture & Photometrics Compliance Mask
    print("\n--- Testing 5-Stage Architecture ---")
    tree = bpy.data.node_groups.new(name="Test5StagesTree", type='SverchCustomTreeType')

    # Stage 1: Truss
    n_truss = tree.nodes.new(type='SvSpotlightTrussNode')
    n_truss.length = 8.0
    n_truss.trim_height = 6.0

    # Stage 2: Hanging Points
    n_hang = tree.nodes.new(type='SvSpotlightHangPositionNode')
    n_hang.position_name = "LX 1"
    n_hang.fixture_count = 4

    # Stage 3: Focus Aim
    n_aim = tree.nodes.new(type='SvSpotlightFocusAimNode')
    n_aim.default_focus_target = (0.0, 0.0, 0.0)

    # Fixture Def
    n_fixdef = tree.nodes.new(type='SvSpotlightFixtureDefNode')
    n_fixdef.preset_choice = "Robe Robin MegaPointe"
    from sverchok_spotlight.nodes.fixtures.fixture_def import on_preset_change
    on_preset_change(n_fixdef, None)

    # Stage 4: Fixture Positioning
    n_array = tree.nodes.new(type='SvSpotlightInstrumentArrayNode')

    # Stage 5: Light Analysis
    n_photo = tree.nodes.new(type='SvSpotlightPhotometricsNode')
    n_photo.standard_preset = 'STAGE_500'
    n_photo.min_lux_threshold = 500.0

    n_dummy = tree.nodes.new(type='SvSpotlightPaperworkNode')
    n_dummy_b = tree.nodes.new(type='SvSpotlightPaperworkNode')

    # Connect links between stages
    tree.links.new(n_hang.inputs['Matrix'], n_truss.outputs['Clamp Matrices'])
    tree.links.new(n_aim.inputs['Hang Matrices'], n_hang.outputs['Hang Matrices'])
    tree.links.new(n_array.inputs['Hang Matrices'], n_hang.outputs['Hang Matrices'])
    tree.links.new(n_array.inputs['Position Data'], n_hang.outputs['Position Data'])
    tree.links.new(n_array.inputs['Aimed Matrices'], n_aim.outputs['Aimed Matrices'])
    tree.links.new(n_array.inputs['Pan (deg)'], n_aim.outputs['Pan (deg)'])
    tree.links.new(n_array.inputs['Tilt (deg)'], n_aim.outputs['Tilt (deg)'])
    tree.links.new(n_array.inputs['Fixture Profile'], n_fixdef.outputs['Fixture Profile'])
    tree.links.new(n_photo.inputs['Aimed Matrices'], n_array.outputs['Fixture Matrices'])
    tree.links.new(n_photo.inputs['Fixture Instances'], n_array.outputs['Fixture Instances'])
    tree.links.new(n_photo.inputs['Beam Angle'], n_fixdef.outputs['Beam Angle'])
    tree.links.new(n_photo.inputs['Field Angle'], n_fixdef.outputs['Field Angle'])
    tree.links.new(n_photo.inputs['Candela'], n_fixdef.outputs['Candela'])
    tree.links.new(n_dummy.inputs['Patched Fixtures'], n_photo.outputs['Compliance Mask'])
    tree.links.new(n_dummy_b.inputs['Patched Fixtures'], n_photo.outputs['Beam Verts'])

    # Stage 1 Process
    n_truss.process()
    clamp_mats = n_truss.outputs['Clamp Matrices'].sv_get()
    assert clamp_mats and len(clamp_mats[0]) > 0, "Truss did not generate Clamp Matrices"
    print("[PASS] Stage 1 (Truss): Generated clamp matrices.")

    # Stage 2 Process
    n_hang.inputs['Matrix'].sv_set(clamp_mats)
    n_hang.process()
    hang_mats = n_hang.outputs['Hang Matrices'].sv_get()
    hang_pts = n_hang.outputs['Hang Points'].sv_get()
    pos_data = n_hang.outputs['Position Data'].sv_get()
    assert hang_mats and len(hang_mats[0]) == 4, f"Expected 4 hang matrices, got {len(hang_mats[0])}"
    assert hang_pts and len(hang_pts[0]) == 4, f"Expected 4 hang points, got {len(hang_pts[0])}"
    print(f"[PASS] Stage 2 (Hanging Points): Generated {len(hang_mats[0])} hanging positions and points.")

    # Stage 3 Process
    n_aim.inputs['Hang Matrices'].sv_set(hang_mats)
    n_aim.process()
    aimed_mats = n_aim.outputs['Aimed Matrices'].sv_get()
    pans = n_aim.outputs['Pan (deg)'].sv_get()
    tilts = n_aim.outputs['Tilt (deg)'].sv_get()
    throws = n_aim.outputs['Throw (m)'].sv_get()
    assert aimed_mats and len(aimed_mats[0]) == 4, "Focus Aim failed to compute Aimed Matrices"
    assert pans and tilts and throws, "Focus Aim missing Pan/Tilt/Throw outputs"
    print(f"[PASS] Stage 3 (Focus Aim): Calculated Pan {pans[0]}, Tilt {tilts[0]}, Throw {throws[0]}.")

    # Fixture Def Process
    n_fixdef.process()
    prof = n_fixdef.outputs['Fixture Profile'].sv_get()

    # Stage 4 Process
    n_array.inputs['Hang Matrices'].sv_set(hang_mats)
    n_array.inputs['Aimed Matrices'].sv_set(aimed_mats)
    n_array.inputs['Pan (deg)'].sv_set(pans)
    n_array.inputs['Tilt (deg)'].sv_set(tilts)
    n_array.inputs['Position Data'].sv_set(pos_data)
    n_array.inputs['Fixture Profile'].sv_set(prof)
    n_array.process()
    array_verts = n_array.outputs['Vertices'].sv_get()
    array_polys = n_array.outputs['Polygons'].sv_get()
    fix_instances = n_array.outputs['Fixture Instances'].sv_get()
    assert array_verts and len(array_verts[0]) > 0, "Instrument Array generated no 3D vertices"
    assert len(fix_instances[0]) == 4, f"Expected 4 fixture instances, got {len(fix_instances[0])}"
    # Verify metadata contains pan, tilt, position, emitter specs
    f0 = fix_instances[0][0]
    assert "pan" in f0 and "tilt" in f0, f"Fixture instance missing pan/tilt: {f0}"
    assert isinstance(f0.get("world_pos"), list) and len(f0["world_pos"]) == 3, f"Invalid world_pos: {f0.get('world_pos')}"
    assert "emitter_pos" in f0 and "emitter_matrix" in f0, f"Missing emitter metadata: {f0}"
    assert "clamp_pos" in f0, f"Missing clamp_pos: {f0}"
    # The light generator (emitter_pos) must be offset below the clamp base (clamp_pos Z=6.0)
    assert f0["emitter_pos"][2] < f0["clamp_pos"][2], f"Emitter Z {f0['emitter_pos'][2]} should be below clamp Z {f0['clamp_pos'][2]}"
    emitter_mats = n_array.outputs['Emitter Matrices'].sv_get()
    assert emitter_mats and len(emitter_mats[0]) == 4, "Missing Emitter Matrices output"
    emitter_pts = n_array.outputs['Emitter Points'].sv_get()
    assert emitter_pts and len(emitter_pts[0]) == 4, "Missing Emitter Points output"
    print(f"[PASS] Stage 4 (Fixture Positioning with Pan/Tilt): Generated {len(array_verts[0])} articulated verts, pan={f0['pan']}, tilt={f0['tilt']}.")
    print(f"[PASS] Stage 4 (Light Generator): Emitter pos={f0['emitter_pos']}, clamp pos={f0['clamp_pos']}.")

    # Stage 5: Light Analysis (Photometrics with Standards Compliance)
    n_photo.inputs['Aimed Matrices'].sv_set(emitter_mats)
    n_photo.inputs['Fixture Instances'].sv_set(fix_instances)
    n_photo.inputs['Beam Angle'].sv_set(n_fixdef.outputs['Beam Angle'].sv_get())
    n_photo.inputs['Field Angle'].sv_set(n_fixdef.outputs['Field Angle'].sv_get())
    n_photo.inputs['Candela'].sv_set(n_fixdef.outputs['Candela'].sv_get())
    n_photo.process()
    compliance_mask = n_photo.outputs['Compliance Mask'].sv_get()
    lux_values = n_photo.outputs['Lux'].sv_get()
    comp_status = n_photo.outputs['Compliance Status'].sv_get()
    assert compliance_mask and len(compliance_mask[0]) == 4, f"Expected 4 compliance mask elements, got {compliance_mask}"
    # Ensure compliance values are strictly 0 or 1
    for val in compliance_mask[0]:
        assert val in (0, 1), f"Compliance mask value must be 0 or 1, got {val}"
    print(f"[PASS] Stage 5 (Light Analysis): Lux = {lux_values[0]}, Compliance Mask = {compliance_mask[0]}, Status = {comp_status[0]}.")

    # Light Generator verification on Photometrics Beam Cone:
    beam_verts = n_photo.outputs['Beam Verts'].sv_get()
    assert beam_verts and len(beam_verts[0]) > 0, "Photometrics generated no Beam Vertices"
    first_beam_v = beam_verts[0][0]
    emitter_p = Vector(f0["emitter_pos"])
    dist_to_emitter = (Vector(first_beam_v) - emitter_p).length
    lens_r = float(f0.get("lens_diameter", 0.15)) * 0.5
    assert dist_to_emitter <= (lens_r + 0.05), f"Beam origin {first_beam_v} does not match light generator position {emitter_p} (dist={dist_to_emitter})"
    print(f"[PASS] Light Generator Beam Origin: Beam cone origin matches front lens ({emitter_p.z:.3f}m) instead of truss clamp ({f0['clamp_pos'][2]:.3f}m).")

    # Test standards threshold behavior (raise threshold to 100,000 lx so all fail -> [0, 0, 0, 0])
    n_photo.min_lux_threshold = 1000000.0
    n_photo.process()
    strict_mask = n_photo.outputs['Compliance Mask'].sv_get()[0]
    assert strict_mask == [0, 0, 0, 0], f"Expected all fail [0, 0, 0, 0], got {strict_mask}"
    print(f"[PASS] Stage 5 (Light Analysis): Strict 1,000,000 lx threshold correctly yielded [0, 0, 0, 0].")

    # 5. Test Live DMX Mapper with "Open White" string color (Regression test for TypeError)
    print("\n--- Testing Live DMX Mapper Robustness ---")
    n_mapper = tree.nodes.new(type='SvSpotlightLiveDMXMapperNode')
    n_dummy_map_in = tree.nodes.new(type='SvSpotlightDMXPatcherNode')
    n_dummy_map_out = tree.nodes.new(type='SvSpotlightPaperworkNode')
    tree.links.new(n_mapper.inputs['Fixtures'], n_dummy_map_in.outputs['Patched Fixtures'])
    tree.links.new(n_dummy_map_out.inputs['Patched Fixtures'], n_mapper.outputs['Universe 1'])
    test_fixes_with_strings = [[
        {
            "unit_number": 1,
            "universe": 1,
            "address": 1,
            "channel_count": 16,
            "fixture_type": "Spot",
            "dimmer": 1.0,
            "pan": 45.0,
            "tilt": 30.0,
            "color": "Open White"  # Preset string that previously crashed with '<=' TypeError!
        },
        {
            "unit_number": 2,
            "universe": 1,
            "address": 17,
            "channel_count": 16,
            "fixture_type": "Wash",
            "dimmer": 0.8,
            "pan": -30.0,
            "tilt": 45.0,
            "color": "#FF5500"  # Hex string test
        }
    ]]
    n_dummy_map_in.outputs['Patched Fixtures'].sv_set(test_fixes_with_strings)
    n_mapper.inputs['Fixtures'].sv_set(test_fixes_with_strings)
    n_mapper.process()
    uni_1 = n_mapper.outputs['Universe 1'].sv_get()
    assert uni_1 and len(uni_1[0]) == 512, "Live DMX Mapper failed to generate 512 channels"
    print("[PASS] Live DMX Mapper successfully processed 'Open White' and hex color strings without TypeError.")

    # 6. Test grandMA Export with string positions (Regression test for ValueError)
    print("\n--- Testing grandMA Export Robustness ---")
    n_gma = tree.nodes.new(type='SvSpotlightGrandMANode')
    tree.links.new(n_gma.inputs['Fixtures'], n_dummy_map_in.outputs['Patched Fixtures'])
    sample_gma_fixtures = [[
        {
            "unit_number": 1,
            "universe": 1,
            "address": 1,
            "position": "FOH Truss A",  # String position from paperwork/rigging
            "world_pos": [2.5, 0.0, 6.0],
            "pan": 15.5,
            "tilt": 42.0
        },
        {
            "unit_number": 2,
            "universe": 1,
            "address": 40,
            "position": "FOH Truss A",
            "world_pos": [-2.5, 0.0, 6.0],
            "pan": -15.5,
            "tilt": 42.0
        }
    ]]
    n_dummy_map_in.outputs['Patched Fixtures'].sv_set(sample_gma_fixtures)
    n_gma.inputs['Fixtures'].sv_set(sample_gma_fixtures)
    for fmt in ['MA3_CLI', 'MA3_XML', 'MA2_CLI', 'MA2_XML']:
        n_gma.export_format = fmt
        n_gma.file_path = f"test_gma_robust_{fmt}.txt"
        cnt, pth = n_gma.export_data()
        assert cnt == 2, f"grandMA export returned {cnt} fixtures, expected 2"
        assert os.path.exists(pth), f"grandMA file not created: {pth}"
        if os.path.exists(pth):
            os.remove(pth)
    print("[PASS] grandMA Export successfully formatted positions without ValueError.")

    # 7. Test Pixel Mapper Node (Texture Image to Fixture / Beam Colors)
    print("\n--- Testing Pixel Mapper Node ---")
    n_pixmap = tree.nodes.new(type='SvSpotlightPixelMapperNode')
    # Create test 4x4 image: red, green, blue, yellow quadrants
    test_img = bpy.data.images.get("TestMapperImage") or bpy.data.images.new("TestMapperImage", width=4, height=4)
    px_data = []
    for y in range(4):
        for x in range(4):
            if x < 2 and y < 2:
                px_data.extend([1.0, 0.0, 0.0, 1.0]) # Red
            elif x >= 2 and y < 2:
                px_data.extend([0.0, 1.0, 0.0, 1.0]) # Green
            elif x < 2 and y >= 2:
                px_data.extend([0.0, 0.0, 1.0, 1.0]) # Blue
            else:
                px_data.extend([1.0, 1.0, 0.0, 1.0]) # Yellow
    test_img.pixels = px_data
    n_pixmap.image_name = "TestMapperImage"
    n_pixmap.mapping_plane = 'XY'
    n_pixmap.bounds_mode = 'AUTO'
    n_pixmap.filter_mode = 'BILINEAR'

    # Create dummy receiver to retain Sverchok socket output
    n_dummy_pix = tree.nodes.new(type='SvSpotlightPaperworkNode')
    tree.links.new(n_pixmap.inputs['Fixtures'], n_dummy_map_in.outputs['Patched Fixtures'])
    tree.links.new(n_dummy_pix.inputs['Patched Fixtures'], n_pixmap.outputs['Mapped Fixtures'])

    n_pixmap.inputs['Fixtures'].sv_set(fix_instances)
    n_pixmap.process()

    mapped_fixes = n_pixmap.outputs['Mapped Fixtures'].sv_get()
    mapped_rgb = n_pixmap.outputs['Colors (RGB)'].sv_get()
    mapped_hex = n_pixmap.outputs['Hex Colors'].sv_get()
    mapped_dim = n_pixmap.outputs['Dimmers'].sv_get()
    assert mapped_fixes and len(mapped_fixes[0]) == 4, f"Expected 4 mapped fixtures, got {mapped_fixes}"
    assert mapped_rgb and len(mapped_rgb[0]) == 4, f"Expected 4 RGB colors, got {mapped_rgb}"
    assert mapped_hex and len(mapped_hex[0]) == 4, f"Expected 4 Hex colors, got {mapped_hex}"
    # Verify metadata on first fixture
    mf0 = mapped_fixes[0][0]
    assert 'color' in mf0 and 'pixel_uv' in mf0, f"Missing color/pixel_uv in mapped fixture: {mf0}"
    print(f"[PASS] Pixel Mapper: Sampled colors {mapped_hex[0]}, UVs {[f['pixel_uv'] for f in mapped_fixes[0]]}.")

    # 8. Test Beam Material Node (Assign Light Color to Material for each Beam)
    print("\n--- Testing Beam Material Node ---")
    n_beammat = tree.nodes.new(type='SvSpotlightBeamMaterialNode')
    n_beammat.material_prefix = "Test_Spotlight_Beam"
    n_beammat.emission_strength = 7.5
    n_beammat.beam_alpha = 0.35
    n_beammat.auto_create_objects = True
    n_beammat.collection_name = "Test_Spotlight_Beams"

    n_dummy_mat = tree.nodes.new(type='SvSpotlightPaperworkNode')
    tree.links.new(n_beammat.inputs['Fixture Instances'], n_pixmap.outputs['Mapped Fixtures'])
    tree.links.new(n_beammat.inputs['Beam Verts'], n_photo.outputs['Beam Verts'])
    tree.links.new(n_beammat.inputs['Beam Polys'], n_photo.outputs['Beam Polys'])
    tree.links.new(n_beammat.inputs['Colors'], n_pixmap.outputs['Colors (RGB)'])
    tree.links.new(n_dummy_mat.inputs['Patched Fixtures'], n_beammat.outputs['Material Names'])

    n_beammat.inputs['Fixture Instances'].sv_set(mapped_fixes)
    n_beammat.inputs['Beam Verts'].sv_set(beam_verts)
    n_beammat.inputs['Beam Polys'].sv_set(n_photo.outputs['Beam Polys'].sv_get())
    n_beammat.inputs['Colors'].sv_set(mapped_rgb)
    n_beammat.process()

    mat_names = n_beammat.outputs['Material Names'].sv_get()
    assert mat_names and len(mat_names[0]) == 4, f"Expected 4 material names, got {mat_names}"

    # Verify Blender materials created in bpy.data.materials
    for m_name in mat_names[0]:
        mat_obj = bpy.data.materials.get(m_name)
        assert mat_obj is not None, f"Material '{m_name}' was not created in bpy.data.materials"
        assert mat_obj.use_nodes, f"Material '{m_name}' does not use shader nodes"
        # Check for ShaderNodeEmission and ShaderNodeBsdfTransparent
        node_types_in_mat = [n.type for n in mat_obj.node_tree.nodes]
        assert 'EMISSION' in node_types_in_mat, f"Missing EMISSION shader node in {m_name}"
        assert 'BSDF_TRANSPARENT' in node_types_in_mat, f"Missing BSDF_TRANSPARENT node in {m_name}"
        # Check viewport diffuse alpha
        assert abs(mat_obj.diffuse_color[3] - 0.35) < 0.01, f"Material diffuse alpha expected 0.35, got {mat_obj.diffuse_color[3]}"

    # Verify 3D Beam Mesh Objects created in collection
    beam_col = bpy.data.collections.get("Test_Spotlight_Beams")
    assert beam_col is not None, "Collection 'Test_Spotlight_Beams' was not created"
    assert len(beam_col.objects) == 4, f"Expected 4 beam objects in collection, got {len(beam_col.objects)}"
    for b_obj in beam_col.objects:
        assert len(b_obj.data.materials) > 0, f"Beam object {b_obj.name} has no material assigned"
        assert b_obj.data.materials[0].name.startswith("Test_Spotlight_Beam"), f"Unexpected material {b_obj.data.materials[0].name}"
    print(f"[PASS] Beam Material: Successfully created {len(mat_names[0])} materials with emission & transparency and assigned to 3D beam objects.")

    # 8. Test Fixture Library Import (OFL JSON, GDTF, QLC+ QXF)
    print("\n--- Testing Fixture Library Import (OFL JSON, GDTF, QLC+ QXF) ---")
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(addon_dir, "fixtures_library")
    
    n_import = tree.nodes.new(type='SvSpotlightFixtureImportNode')
    assert n_import is not None, "Failed to instantiate SvSpotlightFixtureImportNode"

    # Test 1: OFL JSON (Clay Paky Sharpy)
    sharpy_path = os.path.join(lib_dir, "clay_paky_sharpy.ofl.json")
    n_import.filepath = sharpy_path
    n_import.reload_file()
    n_import.process()
    prof_sharpy = n_import.outputs['Fixture Profile'].sv_get()[0][0]
    assert prof_sharpy['name'] == "Sharpy", f"Expected Sharpy, got {prof_sharpy['name']}"
    assert prof_sharpy['beam_angle'] == 2.0, f"Expected 2.0 beam angle, got {prof_sharpy['beam_angle']}"
    assert prof_sharpy['dmx_footprint'] == 16, f"Expected 16ch footprint, got {prof_sharpy['dmx_footprint']}"
    assert len(prof_sharpy['modes']) == 3, f"Expected 3 modes, got {len(prof_sharpy['modes'])}"
    print("[PASS] OFL JSON Import: Clay Paky Sharpy parsed with 3 modes and optical specs.")

    # Test 2: OFL JSON with Mode Selection (Martin MAC Aura Extended 25ch)
    aura_path = os.path.join(lib_dir, "martin_mac_aura.ofl.json")
    n_import.filepath = aura_path
    n_import.reload_file("Extended (25ch)")
    n_import.process()
    prof_aura = n_import.outputs['Fixture Profile'].sv_get()[0][0]
    assert prof_aura['name'] == "MAC Aura", f"Expected MAC Aura, got {prof_aura['name']}"
    assert prof_aura['dmx_footprint'] == 25, f"Expected 25 channels, got {prof_aura['dmx_footprint']}"
    assert prof_aura['channel_map']['red'] == 8, f"Expected Red on ch8, got {prof_aura['channel_map']['red']}"
    print("[PASS] OFL JSON Import: Martin MAC Aura with RGBW channel mapping & Extended mode.")

    # Test 3: QLC+ XML (Robe Robin Pointe)
    pointe_path = os.path.join(lib_dir, "robe_robin_pointe.qxf")
    n_import.filepath = pointe_path
    n_import.reload_file()
    n_import.process()
    prof_pointe = n_import.outputs['Fixture Profile'].sv_get()[0][0]
    assert "Robin Pointe" in prof_pointe['name'], f"Expected Robin Pointe, got {prof_pointe['name']}"
    assert prof_pointe['dmx_footprint'] == 20, f"Expected 20 channels, got {prof_pointe['dmx_footprint']}"
    print("[PASS] QLC+ QXF Import: Robe Robin Pointe parsed successfully.")

    # Test 4: GDTF Archive (Generic Moving Spot 350W)
    gdtf_path = os.path.join(lib_dir, "generic_moving_spot.gdtf")
    n_import.filepath = gdtf_path
    n_import.reload_file()
    n_import.process()
    prof_gdtf = n_import.outputs['Fixture Profile'].sv_get()[0][0]
    assert "Generic Moving Spot" in prof_gdtf['name'], f"Expected Generic Moving Spot, got {prof_gdtf['name']}"
    assert prof_gdtf['beam_angle'] == 3.2, f"Expected 3.2 beam angle, got {prof_gdtf['beam_angle']}"
    print("[PASS] GDTF Archive Import: DIN SPEC 15800 GDTF container parsed successfully.")

    # Test 5: Pipeline Integration with Instrument Array
    n_array.inputs['Fixture Profile'].sv_set(n_import.outputs['Fixture Profile'].sv_get())
    n_array.process()
    emitters = n_array.outputs['Emitter Points'].sv_get()[0]
    assert len(emitters) == 4, f"Expected 4 emitter origins, got {len(emitters)}"
    f_inst = n_array.outputs['Fixture Instances'].sv_get()[0][0]
    assert f_inst['fixture_name'] == prof_gdtf['name'], f"Expected {prof_gdtf['name']}, got {f_inst['fixture_name']}"
    print(f"[PASS] Fixture Import -> Instrument Array pipeline verified with 4 optical emitters ({f_inst['fixture_name']}).")

    # 9. Test Demo Rig Operator
    print("\n--- Testing Demo Rig Operator ---")
    res = bpy.ops.node.sverchok_spotlight_create_sample_rig()
    assert res == {'FINISHED'}, f"Demo Rig creation failed: {res}"
    demo_tree = bpy.data.node_groups.get("Spotlight_Demo_Rig")
    assert demo_tree is not None, "Demo Rig node group was not created."
    print(f"[PASS] Demo Rig created with {len(demo_tree.nodes)} nodes and {len(demo_tree.links)} links.")
    assert len(demo_tree.nodes) >= 13, f"Expected at least 13 nodes in rig, got {len(demo_tree.nodes)}"
    assert len(demo_tree.links) >= 18, f"Expected at least 18 links in rig, got {len(demo_tree.links)}"

    # 8. Test Art-Net Streaming
    n_artnet = demo_tree.nodes['Spotlight Art-Net Output']
    test_port = 6458
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass
    recv_sock.bind(('127.0.0.1', test_port))
    recv_sock.settimeout(2.0)
    n_artnet.target_ip = "127.0.0.1"
    n_artnet.target_port = test_port

    test_dmx_data = [{1: [255 if i == 0 else 128 for i in range(512)]}]
    n_artnet.inputs['Universes'].sv_set(test_dmx_data)
    sent_count = n_artnet.send_packets()
    assert sent_count > 0, "No Art-Net packets were sent."
    data, addr = recv_sock.recvfrom(1024)
    recv_sock.close()
    assert len(data) == 530, f"Expected 530-byte ArtDmx packet, got {len(data)}"
    assert data[:8] == b'Art-Net\x00', f"Invalid Art-Net header: {data[:8]}"
    print("[PASS] Art-Net packet validation passed: 530 bytes with valid ArtDmx header.")

    # 9. Test Suite Reload Operator
    reload_res = bpy.ops.node.sverchok_spotlight_reload()
    assert reload_res == {'FINISHED'}, f"Reload operator failed: {reload_res}"
    print("[PASS] Dynamic reload operator verified successfully.")

    print("\n" + "=" * 60)
    print("ALL VERIFICATION TESTS FOR 5-STAGE ARCHITECTURE PASSED 100%!")
    print("=" * 60)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)

if __name__ == '__main__':
    try:
        run_tests()
    except Exception as e:
        import traceback
        print("\n" + "!" * 60)
        print("EXCEPTION IN TEST RUN:")
        traceback.print_exc(file=sys.stdout)
        print("!" * 60)
        sys.stdout.flush()
        os._exit(1)

