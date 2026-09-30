# Sverchok Spotlight Suite

> Parametric Entertainment Lighting, Stage Rigging, Photometric Analysis, and DMX/Art-Net Pipeline for Blender & Sverchok.

[![Blender 4.2+](https://img.shields.io/badge/Blender-4.2+-orange.svg)](https://www.blender.org/)
[![Sverchok](https://img.shields.io/badge/Sverchok-v1.4.0+-blue.svg)](https://github.com/nortikin/sverchok)
[![Tests](https://img.shields.io/badge/Tests-Passing%20(100%25)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)

---

## Overview

The **Sverchok Spotlight Suite** brings professional stage lighting CAD and media server workflows (equivalent to Vectorworks Spotlight, grandMA 3D, and real-time pixel mappers) directly into Blender's node-based visual programming environment.

Built with **15 dedicated custom Sverchok nodes**, the suite eliminates fragile generic script nodes (`SNLite`) and provides a unified parametric pipeline from structural rigging to real-time DMX output.

---

## Pipeline Architecture

```
[Stage 1: Rigging]         SvSpotlightTrussNode (Procedural Box / Tri / Ladder Truss)
        │
[Stage 2: Hanging]         SvSpotlightHangPositionNode (Clamp distribution, spacing, metadata)
        │
[Stage 3: Focus & Aim]     SvSpotlightFocusAimNode (Trigonometric Pan/Tilt calculation & throw)
        │
[Stage 4: Fixtures]        SvSpotlightFixtureDefNode / SvSpotlightFixtureImportNode
        │                  (OFL JSON / GDTF / QLC+ QXF profiles + Instrument Array)
        ▼                  SvSpotlightInstrumentArrayNode (Articulated base/yoke/head, optical emitter ray apex)
        │
[Stage 5: Photometrics]    SvSpotlightPhotometricsNode
        │                  (Standards compliance 0/1 mask, foot-candle/lux & beam frustums)
        │
[Stage 6: Shaders & Media] SvSpotlightBeamMaterialNode + SvSpotlightPixelMapperNode
        │                  (Volumetric emissive shaders, UV texture sampling to RGB)
        │
[Stage 7: DMX & Export]    SvSpotlightDMXPatcherNode ──► SvSpotlightLiveDMXMapperNode
                           ├──► SvSpotlightArtNetOutNode (Real-time UDP 530-byte ArtDmx)
                           ├──► SvSpotlightPaperworkNode (CSV schedules & hookups)
                           ├──► SvSpotlightGrandMANode (grandMA2 / grandMA3 CLI & XML)
                           └──► SvSpotlightMVRExportNode (DIN SPEC 15800 MVR container)
```

---

## Node Inventory

| Category | Node Identifier | Description |
|---|---|---|
| **Rigging** | `SvSpotlightTrussNode` | Procedural parametric box, triangle, and ladder truss chords and diagonal lacing. |
| **Rigging** | `SvSpotlightHangPositionNode` | Calculates clamp hang matrices along truss centerlines with spacing offsets and position labels. |
| **Focus** | `SvSpotlightFocusAimNode` | Computes spherical aim vectors, pan (-180°..180°), tilt (-135°..135°), and throw distances. |
| **Fixtures** | `SvSpotlightFixtureDefNode` | Parametric definitions with industry presets (Clay Paky Sharpy, Robe MegaPointe, Martin MAC Aura, ETC Source Four, etc.). |
| **Fixtures** | `SvSpotlightFixtureImportNode` | Imports Open Fixture Library (OFL `.json`), General Device Type Format (`.gdtf` & `description.xml`), and QLC+ (`.qxf`) definitions with multi-mode channel mapping and optical specs. |
| **Fixtures** | `SvSpotlightInstrumentArrayNode` | Generates 3-part articulated geometry (base, yoke, head) and calculates front-lens emitter origins. |
| **Photometrics** | `SvSpotlightPhotometricsNode` | Inverse-square illuminance calculation with boolean compliance mask (0/1) against standards (Broadcast, Concert, Theatre). |
| **Photometrics** | `SvSpotlightBeamMaterialNode` | Procedural emissive transparent beam shaders and 3D conical beam mesh generation. |
| **DMX & Media** | `SvSpotlightPixelMapperNode` | Bilinear and nearest-neighbor texture sampling to map raster image pixels to fixture beam colors. |
| **DMX & Media** | `SvSpotlightDMXPatcherNode` | Automatic universe (1..512) and address allocation with gap spacing and collision detection. |
| **DMX & Media** | `SvSpotlightLiveDMXMapperNode` | Synthesizes standard 512-channel DMX universe byte arrays from Pan, Tilt, Dimmer, and RGB inputs. |
| **DMX & Media** | `SvSpotlightArtNetOutNode` | Broadcasts live ArtDmx UDP packets (OpCode `0x5000`) over the network on port 6454. |
| **DMX & Media** | `SvSpotlightPaperworkNode` | Generates industry-standard paperwork: Instrument Schedule, Channel Hookup, and Rig Summary CSVs. |
| **Exchange** | `SvSpotlightMVRExportNode` | Exports My Virtual Rig (DIN SPEC 15800) container with `GeneralSceneDescription.xml`. |
| **Exchange** | `SvSpotlightGrandMANode` | Generates grandMA2 and grandMA3 command-line scripts and XML setup macros. |

---

## Fixture Profile Library & Formats

The suite includes direct import capability for professional lighting fixture profiles across all major industry standards:
- **Open Fixture Library (OFL)** (`.json`): Optical beam/field angles, candela, physical dimensions, weight, and multi-mode channel mapping (Pan, Tilt, Dimmer, RGBW, Strobe).
- **General Device Type Format (GDTF)** (`.gdtf` zip container & `description.xml`): Full DIN SPEC 15800 fixture profile definitions, DMX channels, and geometries.
- **QLC+ Fixture Definition** (`.qxf`): XML fixture definitions with pan/tilt physical ranges, channel layouts, and bulb/photometric specs.
- **Generic JSON Profiles**: Custom JSON profiles for architectural and custom entertainment luminaires.

A sample library is included in `fixtures_library/`:
- `clay_paky_sharpy.ofl.json` (Clay Paky Sharpy - 3 modes: Standard 16ch, Vector 20ch, Extended 20ch)
- `martin_mac_aura.ofl.json` (Martin MAC Aura - Standard 14ch & Extended 25ch with full RGBW mapping)
- `robe_robin_pointe.qxf` (Robe Robin Pointe - Mode 1 24ch, Mode 2 16ch, Mode 3 30ch)
- `generic_moving_spot.gdtf` (Generic Moving Spot 350W - DIN SPEC 15800 container with optical lenses & DMX geometry)

---

## Installation

### Automated 1-Click Install (Recommended)

The repository provides automated setup scripts that detect/install **Blender 4.2 LTS**, download and install **Sverchok v1.4.0+**, copy the **Spotlight** suite, and enable both addons in Blender's user preferences:

* **Windows**:
  Double-click `install.bat` or run from PowerShell / Command Prompt:
  ```cmd
  install.bat
  ```

* **Linux & macOS**:
  Make executable and run `install.sh`:
  ```bash
  chmod +x install.sh
  ./install.sh
  ```

---

### Manual Installation

1. Ensure **Blender 4.2+** and **Sverchok 1.4.0+** are installed and enabled.
2. Clone or copy the `sverchok_spotlight` folder into your Blender addons directory:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\4.2\scripts\addons\sverchok_spotlight`
   - **macOS**: `~/Library/Application Support/Blender/4.2/scripts/addons/sverchok_spotlight`
   - **Linux**: `~/.config/blender/4.2/scripts/addons/sverchok_spotlight`
3. In Blender, navigate to **Edit > Preferences > Add-ons**, search for **Sverchok Spotlight Suite**, and check the box to enable.
4. The nodes will appear in the Sverchok Node Editor under the **Spotlight** menu.

---

## Verification & Testing

The repository includes a comprehensive standalone test suite verifying node registration, trigonometric calculations, optical emitter offsets, inverse-square photometrics, and DMX frame serialization:

```bash
python test_spotlight_v2.py
```

---

## Documentation

For full architectural details, mathematical formulas, and node socket specifications, refer to [SPECIFICATIONS.md](SPECIFICATIONS.md).
