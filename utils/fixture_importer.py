# Fixture Importer and Parser Engine for Sverchok Spotlight
# Supports:
# 1. Open Fixture Library (OFL) JSON format (*.json)
# 2. General Device Type Format (GDTF) archives (*.gdtf) and XML (*.xml)
# 3. QLC+ Fixture Definition format (*.qxf)
# 4. Generic Lighting Fixture JSON (*.json)

import os
import json
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple

def parse_ofl_json(data: Dict[str, Any], filepath: str = "") -> Dict[str, Any]:
    """Parses Open Fixture Library (OFL) JSON structure into standard profile."""
    name = data.get("name") or os.path.splitext(os.path.basename(filepath))[0]
    short_name = data.get("shortName", name)
    categories = data.get("categories", ["Moving Light"])
    fixture_type = categories[0] if categories else "Moving Light"
    
    physical = data.get("physical", {})
    dims = physical.get("dimensions", [300, 450, 300]) # mm: [w, h, d]
    width_m = (dims[0] if len(dims) > 0 else 300) / 1000.0
    height_m = (dims[1] if len(dims) > 1 else 450) / 1000.0
    depth_m = (dims[2] if len(dims) > 2 else 300) / 1000.0
    
    weight_kg = float(physical.get("weight", 15.0))
    wattage = float(physical.get("power", 300.0))
    
    # Lens and photometrics
    lens = physical.get("lens", {})
    deg_min_max = lens.get("degreesMinMax", [2.0, 20.0])
    if isinstance(deg_min_max, list) and len(deg_min_max) >= 2:
        beam_angle = float(deg_min_max[0])
        field_angle = float(deg_min_max[1])
    elif isinstance(deg_min_max, (int, float)):
        beam_angle = float(deg_min_max)
        field_angle = float(deg_min_max) * 1.5
    else:
        beam_angle = 2.5
        field_angle = 15.0

    if beam_angle <= 0.0:
        beam_angle = 2.0
    if field_angle < beam_angle:
        field_angle = beam_angle * 1.5

    # Bulb & candela
    bulb = physical.get("bulb", {})
    lumens = float(bulb.get("lumens", 10000.0))
    # Approximation of center candela from lumens & beam angle:
    # cd = lumens / (2 * pi * (1 - cos(theta / 2)))
    import math
    half_angle_rad = math.radians(max(beam_angle, 0.5) / 2.0)
    omega = 2.0 * math.pi * (1.0 - math.cos(half_angle_rad))
    calculated_candela = (lumens / max(omega, 0.0001)) if lumens > 0 else 500000.0
    candela = float(physical.get("candela", calculated_candela))
    
    # Focus
    focus = physical.get("focus", {})
    pan_max = float(focus.get("panMax", 540.0))
    tilt_max = float(focus.get("tiltMax", 270.0))
    
    # Emitter offset: distance from base mount to optical center/front lens
    # For moving heads, typical emitter is located at ~70-80% of fixture height
    emitter_offset = round(height_m * 0.76, 3)
    lens_diameter = round(min(width_m, depth_m) * 0.45, 3)
    
    # Parse Modes
    raw_modes = data.get("modes", [])
    modes: List[Dict[str, Any]] = []
    available_channels = data.get("availableChannels", {})
    
    for rm in raw_modes:
        m_name = rm.get("name", "Standard")
        m_short = rm.get("shortName", m_name)
        raw_channels = rm.get("channels", [])
        
        ch_names: List[str] = []
        for ch in raw_channels:
            if ch is None:
                ch_names.append("Reserved / No Function")
            elif isinstance(ch, str):
                ch_names.append(ch)
            elif isinstance(ch, dict):
                ch_names.append(ch.get("insert", "Channel"))
        
        footprint = len(ch_names)
        modes.append({
            "name": m_name,
            "short_name": m_short,
            "footprint": footprint,
            "channels": ch_names
        })
        
    if not modes:
        modes.append({
            "name": "Standard (16ch)",
            "short_name": "16ch",
            "footprint": 16,
            "channels": [f"Channel {i+1}" for i in range(16)]
        })

    # Channel attribute mapping for primary mode
    primary_mode = modes[0]
    channel_map = build_channel_map(primary_mode["channels"], available_channels)

    return {
        "name": name,
        "short_name": short_name,
        "manufacturer": data.get("meta", {}).get("authors", ["Generic"])[0] if data.get("meta", {}).get("authors") else "OFL",
        "type": fixture_type,
        "beam_angle": beam_angle,
        "field_angle": field_angle,
        "candela": candela,
        "lumens": lumens,
        "weight_kg": weight_kg,
        "wattage": wattage,
        "pan_max": pan_max,
        "tilt_max": tilt_max,
        "emitter_offset": emitter_offset,
        "lens_diameter": lens_diameter,
        "dimensions": {"width": width_m, "height": height_m, "depth": depth_m},
        "color": "Open White",
        "purpose": "Key Light",
        "modes": modes,
        "selected_mode": primary_mode["name"],
        "dmx_footprint": primary_mode["footprint"],
        "channels": primary_mode["channels"],
        "channel_map": channel_map,
        "source_format": "Open Fixture Library (OFL)"
    }


def parse_qlc_qxf(root: ET.Element, filepath: str = "") -> Dict[str, Any]:
    """Parses QLC+ Fixture Definition XML (.qxf) into standard profile."""
    # Strip or support namespace
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
        
    manufacturer = root.findtext(f"{ns}Manufacturer") or "Generic"
    model = root.findtext(f"{ns}Model") or os.path.splitext(os.path.basename(filepath))[0]
    name = f"{manufacturer} {model}".strip()
    fixture_type = root.findtext(f"{ns}Type") or "Moving Head"
    
    physical_el = root.find(f"{ns}Physical")
    width_m = 0.3
    height_m = 0.45
    depth_m = 0.3
    weight_kg = 15.0
    wattage = 300.0
    beam_angle = 2.0
    field_angle = 15.0
    pan_max = 540.0
    tilt_max = 270.0
    
    if physical_el is not None:
        dim_el = physical_el.find(f"{ns}Dimensions")
        if dim_el is not None:
            width_m = float(dim_el.get("Width", 300)) / 1000.0
            height_m = float(dim_el.get("Height", 450)) / 1000.0
            depth_m = float(dim_el.get("Depth", 300)) / 1000.0
            weight_kg = float(dim_el.get("Weight", 15.0))
            
        tech_el = physical_el.find(f"{ns}Technical")
        if tech_el is not None:
            wattage = float(tech_el.get("PowerConsumption", 300.0))
            
        lens_el = physical_el.find(f"{ns}Lens")
        if lens_el is not None:
            beam_angle = float(lens_el.get("DegreesMin", 2.0))
            field_angle = float(lens_el.get("DegreesMax", 15.0))
            
        focus_el = physical_el.find(f"{ns}Focus")
        if focus_el is not None:
            pan_max = float(focus_el.get("PanMax", 540.0))
            tilt_max = float(focus_el.get("TiltMax", 270.0))

    if beam_angle <= 0.0:
        beam_angle = 2.0
    if field_angle < beam_angle:
        field_angle = beam_angle * 1.5

    # Parse Modes
    modes: List[Dict[str, Any]] = []
    for mode_el in root.findall(f"{ns}Mode"):
        m_name = mode_el.get("Name", "Standard")
        ch_list = [ch_el.text for ch_el in mode_el.findall(f"{ns}Channel") if ch_el.text]
        modes.append({
            "name": m_name,
            "short_name": m_name,
            "footprint": len(ch_list),
            "channels": ch_list
        })
        
    if not modes:
        # Fallback to all root channels
        all_channels = [ch.get("Name", f"Channel {i+1}") for i, ch in enumerate(root.findall(f"{ns}Channel"))]
        modes.append({
            "name": "Standard",
            "short_name": "Standard",
            "footprint": len(all_channels) or 16,
            "channels": all_channels or [f"Channel {i+1}" for i in range(16)]
        })

    primary_mode = modes[0]
    emitter_offset = round(height_m * 0.76, 3)
    lens_diameter = round(min(width_m, depth_m) * 0.45, 3)
    channel_map = build_channel_map(primary_mode["channels"], {})

    return {
        "name": name,
        "short_name": model,
        "manufacturer": manufacturer,
        "type": fixture_type,
        "beam_angle": beam_angle,
        "field_angle": field_angle,
        "candela": 500000.0,
        "lumens": 12000.0,
        "weight_kg": weight_kg,
        "wattage": wattage,
        "pan_max": pan_max,
        "tilt_max": tilt_max,
        "emitter_offset": emitter_offset,
        "lens_diameter": lens_diameter,
        "dimensions": {"width": width_m, "height": height_m, "depth": depth_m},
        "color": "Open White",
        "purpose": "Key Light",
        "modes": modes,
        "selected_mode": primary_mode["name"],
        "dmx_footprint": primary_mode["footprint"],
        "channels": primary_mode["channels"],
        "channel_map": channel_map,
        "source_format": "QLC+ Fixture Definition (.qxf)"
    }


def parse_gdtf(xml_content: str, filepath: str = "") -> Dict[str, Any]:
    """Parses GDTF description.xml into standard profile."""
    root = ET.fromstring(xml_content)
    fixture_type_el = root.find(".//FixtureType") or root
    
    name = fixture_type_el.get("Name") or fixture_type_el.get("LongName") or os.path.splitext(os.path.basename(filepath))[0]
    manufacturer = fixture_type_el.get("Manufacturer") or "GDTF Fixture"
    
    # Physical descriptions
    weight_kg = 18.0
    wattage = 350.0
    prop_el = root.find(".//Properties")
    if prop_el is not None:
        weight_el = prop_el.find("Weight")
        if weight_el is not None and "Value" in weight_el.attrib:
            try: weight_kg = float(weight_el.get("Value"))
            except ValueError: pass
        pwr_el = prop_el.find("PowerConsumption")
        if pwr_el is not None and "Value" in pwr_el.attrib:
            try: wattage = float(pwr_el.get("Value"))
            except ValueError: pass

    # Beam angles from Geometries / Beam
    beam_angle = 3.0
    field_angle = 18.0
    beam_el = root.find(".//Beam")
    if beam_el is not None:
        try:
            if "BeamAngle" in beam_el.attrib:
                beam_angle = float(beam_el.get("BeamAngle"))
            if "FieldAngle" in beam_el.attrib:
                field_angle = float(beam_el.get("FieldAngle"))
        except ValueError:
            pass

    # Modes
    modes: List[Dict[str, Any]] = []
    dmx_modes = root.findall(".//DMXMode")
    for dm in dmx_modes:
        m_name = dm.get("Name", "Standard")
        channels: List[str] = []
        for ch in dm.findall(".//DMXChannel"):
            logical = ch.find("LogicalChannel")
            attr = logical.get("Attribute") if logical is not None else ch.get("Geometry", "Channel")
            channels.append(attr)
        modes.append({
            "name": m_name,
            "short_name": m_name,
            "footprint": len(channels),
            "channels": channels
        })
        
    if not modes:
        modes.append({
            "name": "Standard (16ch)",
            "short_name": "Standard",
            "footprint": 16,
            "channels": [f"Ch {i+1}" for i in range(16)]
        })

    primary_mode = modes[0]
    channel_map = build_channel_map(primary_mode["channels"], {})

    return {
        "name": f"{manufacturer} {name}".strip(),
        "short_name": name,
        "manufacturer": manufacturer,
        "type": "Moving Light (GDTF)",
        "beam_angle": beam_angle,
        "field_angle": field_angle,
        "candela": 650000.0,
        "lumens": 14000.0,
        "weight_kg": weight_kg,
        "wattage": wattage,
        "pan_max": 540.0,
        "tilt_max": 270.0,
        "emitter_offset": 0.38,
        "lens_diameter": 0.16,
        "dimensions": {"width": 0.35, "height": 0.50, "depth": 0.35},
        "color": "Open White",
        "purpose": "Spot / Beam",
        "modes": modes,
        "selected_mode": primary_mode["name"],
        "dmx_footprint": primary_mode["footprint"],
        "channels": primary_mode["channels"],
        "channel_map": channel_map,
        "source_format": "General Device Type Format (GDTF)"
    }


def build_channel_map(channels: List[str], available_channels: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes channel names to locate Pan, Tilt, Dimmer, and RGB channels."""
    ch_map = {
        "pan": -1,
        "pan_fine": -1,
        "tilt": -1,
        "tilt_fine": -1,
        "dimmer": -1,
        "red": -1,
        "green": -1,
        "blue": -1,
        "white": -1,
        "strobe": -1
    }
    
    for idx, ch_name in enumerate(channels):
        c_lower = ch_name.lower().strip()
        ch_num = idx + 1 # 1-based index
        
        if "pan fine" in c_lower or "pan 16" in c_lower or "pan msb" in c_lower:
            ch_map["pan_fine"] = ch_num
        elif "pan" in c_lower and ch_map["pan"] == -1:
            ch_map["pan"] = ch_num
            
        elif "tilt fine" in c_lower or "tilt 16" in c_lower or "tilt msb" in c_lower:
            ch_map["tilt_fine"] = ch_num
        elif "tilt" in c_lower and ch_map["tilt"] == -1:
            ch_map["tilt"] = ch_num
            
        elif ("dimmer" in c_lower or "intensity" in c_lower) and ch_map["dimmer"] == -1:
            ch_map["dimmer"] = ch_num
            
        elif "red" in c_lower and ch_map["red"] == -1:
            ch_map["red"] = ch_num
        elif "green" in c_lower and ch_map["green"] == -1:
            ch_map["green"] = ch_num
        elif "blue" in c_lower and ch_map["blue"] == -1:
            ch_map["blue"] = ch_num
        elif "white" in c_lower and ch_map["white"] == -1:
            ch_map["white"] = ch_num
        elif ("strobe" in c_lower or "shutter" in c_lower) and ch_map["strobe"] == -1:
            ch_map["strobe"] = ch_num

    return ch_map


def load_fixture_profile(filepath: str, mode_name: Optional[str] = None) -> Dict[str, Any]:
    """Unified entry point to parse OFL JSON, GDTF, QLC+ QXF, or Generic JSON."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Fixture profile file not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    # 1. GDTF Archive (.gdtf)
    if ext == ".gdtf" or zipfile.is_zipfile(filepath):
        try:
            with zipfile.ZipFile(filepath, "r") as z:
                # Look for description.xml
                desc_name = next((n for n in z.namelist() if n.lower().endswith("description.xml")), None)
                if desc_name:
                    xml_str = z.read(desc_name).decode("utf-8")
                    profile = parse_gdtf(xml_str, filepath)
                else:
                    raise ValueError("No description.xml found in GDTF archive.")
        except Exception as e:
            raise ValueError(f"Failed to parse GDTF archive '{filepath}': {e}")

    # 2. QLC+ Fixture (.qxf) or XML
    elif ext == ".qxf" or ext == ".xml":
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            if root.tag.endswith("FixtureDefinition") or "FixtureDefinition" in root.tag or root.find("Manufacturer") is not None:
                profile = parse_qlc_qxf(root, filepath)
            elif root.tag.endswith("GDTF") or "FixtureType" in root.tag:
                profile = parse_gdtf(open(filepath, "r", encoding="utf-8").read(), filepath)
            else:
                profile = parse_qlc_qxf(root, filepath)
        except Exception as e:
            raise ValueError(f"Failed to parse XML/QXF fixture definition '{filepath}': {e}")

    # 3. JSON (OFL or Generic)
    elif ext == ".json":
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "categories" in data or "availableChannels" in data or "modes" in data or "physical" in data:
                profile = parse_ofl_json(data, filepath)
            else:
                # Generic JSON format
                profile = {
                    "name": data.get("name", "Generic Fixture"),
                    "short_name": data.get("short_name", "Fixture"),
                    "manufacturer": data.get("manufacturer", "Generic"),
                    "type": data.get("type", "Moving Light"),
                    "beam_angle": float(data.get("beam_angle", 15.0)),
                    "field_angle": float(data.get("field_angle", 30.0)),
                    "candela": float(data.get("candela", 100000.0)),
                    "lumens": float(data.get("lumens", 8000.0)),
                    "weight_kg": float(data.get("weight_kg", 15.0)),
                    "wattage": float(data.get("wattage", 300.0)),
                    "pan_max": float(data.get("pan_max", 540.0)),
                    "tilt_max": float(data.get("tilt_max", 270.0)),
                    "emitter_offset": float(data.get("emitter_offset", 0.35)),
                    "lens_diameter": float(data.get("lens_diameter", 0.15)),
                    "dimensions": data.get("dimensions", {"width": 0.3, "height": 0.45, "depth": 0.3}),
                    "color": data.get("color", "Open White"),
                    "purpose": data.get("purpose", "Key Light"),
                    "modes": data.get("modes", [{"name": "Standard", "short_name": "Standard", "footprint": 16, "channels": [f"Ch {i+1}" for i in range(16)]}]),
                    "selected_mode": "Standard",
                    "dmx_footprint": int(data.get("dmx_footprint", 16)),
                    "channels": data.get("channels", [f"Ch {i+1}" for i in range(16)]),
                    "channel_map": data.get("channel_map", {}),
                    "source_format": "Generic JSON"
                }
        except Exception as e:
            raise ValueError(f"Failed to parse JSON fixture profile '{filepath}': {e}")
    else:
        raise ValueError(f"Unsupported fixture profile format '{ext}'. Supported: .json (OFL), .gdtf, .qxf, .xml")

    # If specific mode requested, switch active mode
    if mode_name and profile.get("modes"):
        matching_mode = next((m for m in profile["modes"] if m["name"].lower() == mode_name.lower() or m["short_name"].lower() == mode_name.lower()), None)
        if matching_mode:
            profile["selected_mode"] = matching_mode["name"]
            profile["dmx_footprint"] = matching_mode["footprint"]
            profile["channels"] = matching_mode["channels"]
            profile["channel_map"] = build_channel_map(matching_mode["channels"], {})

    return profile
