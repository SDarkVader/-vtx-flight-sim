"""Merge separately authored A10-C parts into the A10-B visual, without editing B.

Run from repo root:
  blender -b --python tools/phantom/build_a10c_parts_blend.py
  python tools/phantom/build_a10c_visual.py --replace-exhaust

Inputs: public/assets/phantom-a10b-visual.glb and assets/derived/phantom-a10c-parts.glb
Output: public/assets/phantom-a10c-visual.glb
The parts' editable master lives at assets/derived/phantom-a10c-parts.blend.
This tool changes visual data only; it does not change aircraft physics.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "public/assets/phantom-a10b-visual.glb"
PARTS = ROOT / "assets/derived/phantom-a10c-parts.glb"
OUTPUT = ROOT / "public/assets/phantom-a10c-visual.glb"
OPTIONAL_EXTENSIONS = {
    "KHR_lights_punctual",
    "KHR_materials_clearcoat",
    "KHR_materials_emissive_strength",
}
LEGACY_EXHAUST = {
    "POWER_L_CERAMIC_EXHAUST_LINER",
    "POWER_L_ORANGE_EXHAUST_RIM",
    "POWER_L_REAR_THRUST_NOZZLE",
    "POWER_R_CERAMIC_EXHAUST_LINER",
    "POWER_R_ORANGE_EXHAUST_RIM",
    "POWER_R_REAR_THRUST_NOZZLE",
}

def unpack(path: Path):
    raw = path.read_bytes()
    assert len(raw) >= 28, f"Truncated GLB: {path}"
    assert struct.unpack_from("<4sII", raw, 0) == (b"glTF", 2, len(raw)), path
    data, binary, pos = None, None, 12
    while pos < len(raw):
        size, kind = struct.unpack_from("<I4s", raw, pos)
        pos += 8
        chunk = raw[pos:pos + size]
        pos += size
        if kind == b"JSON":
            data = json.loads(chunk)
        elif kind == b"BIN\x00":
            binary = chunk
        else:
            raise ValueError(f"Unhandled chunk {kind}")
    assert pos == len(raw) and data is not None and binary is not None
    assert len(data.get("buffers", [])) == 1
    assert "uri" not in data["buffers"][0]
    assert len(binary) >= data["buffers"][0]["byteLength"]
    return data, binary

def pack(path: Path, data, binary: bytes):
    data["buffers"][0]["byteLength"] = len(binary)
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    raw = (struct.pack("<4sII", b"glTF", 2, 28 + len(js) + len(binary))
           + struct.pack("<I4s", len(js), b"JSON") + js
           + struct.pack("<I4s", len(binary), b"BIN\x00") + binary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)

def remove_optional_extensions(node):
    if isinstance(node, dict):
        exts = node.get("extensions")
        if isinstance(exts, dict):
            for name in OPTIONAL_EXTENSIONS:
                exts.pop(name, None)
            if not exts:
                node.pop("extensions")
        for value in list(node.values()):
            remove_optional_extensions(value)
    elif isinstance(node, list):
        for value in node:
            remove_optional_extensions(value)

def merge(base, base_bin, parts, parts_bin, replace_exhaust):
    if set(base.get("extensionsRequired", [])) & OPTIONAL_EXTENSIONS:
        raise ValueError("Cannot strip a required base extension")
    if parts.get("extensionsRequired"):
        raise ValueError("Parts file requires unsupported extensions")
    for key in ("skins", "animations", "cameras"):
        if parts.get(key):
            raise ValueError(f"Part input unexpectedly contains {key}")
    out = copy.deepcopy(base)
    frag = copy.deepcopy(parts)
    offsets = {k: len(out.get(k, [])) for k in (
        "samplers", "images", "textures", "materials",
        "meshes", "accessors", "bufferViews", "nodes"
    )}
    pad = -len(base_bin) % 4
    binary_offset = len(base_bin) + pad
    for v in frag.get("bufferViews", []):
        v["buffer"] = 0
        v["byteOffset"] = v.get("byteOffset", 0) + binary_offset
    for a in frag.get("accessors", []):
        if "sparse" in a:
            raise ValueError("Sparse accessors not supported")
        if "bufferView" in a:
            a["bufferView"] += offsets["bufferViews"]
    for i in frag.get("images", []):
        if "uri" in i:
            raise ValueError("External images not supported")
        if "bufferView" in i:
            i["bufferView"] += offsets["bufferViews"]
    for t in frag.get("textures", []):
        if "source" in t:
            t["source"] += offsets["images"]
        if "sampler" in t:
            t["sampler"] += offsets["samplers"]
    for material in frag.get("materials", []):
        texture_slots = [
            (material.get("pbrMetallicRoughness", {}), "baseColorTexture"),
            (material.get("pbrMetallicRoughness", {}), "metallicRoughnessTexture"),
            (material, "normalTexture"),
            (material, "occlusionTexture"),
            (material, "emissiveTexture"),
        ]
        for owner, key in texture_slots:
            if key in owner:
                owner[key]["index"] += offsets["textures"]
    for mesh in frag.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if "indices" in primitive:
                primitive["indices"] += offsets["accessors"]
            if "material" in primitive:
                primitive["material"] += offsets["materials"]
            for name, i in list(primitive.get("attributes", {}).items()):
                primitive["attributes"][name] = i + offsets["accessors"]
            for morph in primitive.get("targets", []):
                for name, i in list(morph.items()):
                    morph[name] = i + offsets["accessors"]
    for node in frag.get("nodes", []):
        if "mesh" in node:
            node["mesh"] += offsets["meshes"]
        if "children" in node:
            node["children"] = [i + offsets["nodes"] for i in node["children"]]
        if "camera" in node or "skin" in node:
            raise ValueError("Unexpected camera/skin in parts")
        name = node.get("name", "")
        extras = node.setdefault("extras", {})
        if name.startswith("A10C_JOINT_NOSE_LIFT_"):
            extras.update(
                joint_type="slide", axis_parent=[0, 0, -1],
                stroke_m=0.2, visual_only=True,
                phantom_joint="nose_lift_" + name.rsplit("_", 1)[-1]
            )
        if name.startswith("A10C_TJ150_") and name.endswith("_MOUNT"):
            extras.update(
                physical_engine="PBS_TJ150_envelope",
                geometry_validation="provisional",
                nominal_thrust_n=1500,
                nominal_length_m=.636,
                nominal_diameter_m=.272
            )
    for key in offsets:
        out.setdefault(key, []).extend(frag.get(key, []))
    # Attach the parts to the existing B airframe; don't replace the joint tree.
    originals = out["nodes"][:offsets["nodes"]]
    roots = frag["scenes"][frag.get("scene", 0)]["nodes"]
    airframes = [n for n in originals if n.get("name") == "airframe"]
    if len(roots) != 1 or len(airframes) != 1:
        raise ValueError("Expected one parts root and one original airframe")
    airframes[0].setdefault("children", []).append(roots[0] + offsets["nodes"])
    suppressed = []
    if replace_exhaust:
        for node in originals:
            name = node.get("name", "")
            if name in LEGACY_EXHAUST or name.startswith("VTX_VISUAL_BOOSTER_"):
                if "mesh" in node:
                    node.pop("mesh")
                    suppressed.append(name)
    for key in ("extensionsUsed", "extensionsRequired"):
        out[key] = list(dict.fromkeys(out.get(key, []) + frag.get(key, [])))
        out[key] = [x for x in out[key] if x not in OPTIONAL_EXTENSIONS]
        if not out[key]:
            out.pop(key)
    remove_optional_extensions(out)
    meta = out.setdefault("asset", {}).setdefault("extras", {})
    meta.update(
        vtx_variant="phantom-a10c",
        derived_from="phantom-a10b-visual.glb",
        base_variant_config_sha256="3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01",
        overlay_name="takeoff_stance_v1",
        proposals=["P7: four TJ150-class turbojets", "nose lift 0.20m"],
        design_note="Visual-only provisional placement: mounting, geometry and animation require verification",
        removed_legacy_exhaust_meshes=suppressed,
    )
    return out, base_bin + b"\0" * pad + parts_bin, suppressed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--parts", type=Path, default=PARTS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--replace-exhaust", action="store_true")
    args = parser.parse_args()

    before_sha = hashlib.sha256(args.base.read_bytes()).hexdigest()
    base, base_bin = unpack(args.base)
    parts, parts_bin = unpack(args.parts)
    original_nodes = copy.deepcopy(base["nodes"])
    merged, merged_bin, suppressed = merge(
        base, base_bin, parts, parts_bin, args.replace_exhaust
    )
    pack(args.output, merged, merged_bin)
    result, result_bin = unpack(args.output)

    assert result_bin.startswith(base_bin), "Base geometry binary was changed"
    assert len(result["nodes"]) == len(original_nodes) + len(parts["nodes"])
    for a, b in zip(original_nodes, result["nodes"][:len(original_nodes)]):
        for field in ("name", "translation", "rotation", "scale", "matrix", "extras"):
            assert a.get(field) == b.get(field), (a.get("name"), field)
        if a.get("name") != "airframe":
            assert a.get("children") == b.get("children"), a.get("name")
        assert a.get("mesh") == b.get("mesh") or b.get("name") in suppressed
    names = [n.get("name", "") for n in result["nodes"]]
    assert len(names) == len(set(names)), "Duplicate node name"
    assert sum(x.startswith("A10C_TJ150_") and x.endswith("_MOUNT") for x in names) == 4
    assert sum(x.startswith("A10C_JOINT_NOSE_LIFT_") for x in names) == 2
    assert hashlib.sha256(args.base.read_bytes()).hexdigest() == before_sha
    print(f"BASE_UNCHANGED sha256={before_sha} nodes={len(original_nodes)}")
    print(f"OUTPUT {args.output} nodes={len(result['nodes'])} meshes={len(result.get('meshes', []))}")
    print(f"ADDED {len(parts['nodes'])} nodes; suppressed {len(suppressed)} legacy C-only meshes")

if __name__ == "__main__":
    main()
