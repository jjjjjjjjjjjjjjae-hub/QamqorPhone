#!/usr/bin/env python3
"""Inspect the uploaded iPhone Duo GLB without changing the source asset."""
from pathlib import Path
import json
import re
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "iPhone duo.glb"
OUTPUT = ROOT / "qamqor-duo-model-report.json"
KEYWORDS = re.compile(r"screen|display|glass|touch|fold|hinge|inner|outer|front|panel|oled|amoled", re.I)

def material_name(geom):
    material = getattr(getattr(geom, "visual", None), "material", None)
    return getattr(material, "name", None) if material else None

def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    scene = trimesh.load(str(SOURCE), force="scene", process=False)
    geometries = []
    all_vertices = []
    candidates = []
    movable = []

    for node_name in list(scene.graph.nodes_geometry):
        transform, geometry_name = scene.graph.get(node_name)
        geom = scene.geometry[geometry_name]
        local = np.asarray(geom.vertices, dtype=float)
        world = trimesh.transform_points(local, transform)
        if not len(world):
            continue
        lo, hi = world.min(axis=0), world.max(axis=0)
        size = hi - lo
        material = material_name(geom)
        row = {
            "node": str(node_name),
            "mesh": str(geometry_name),
            "material": material,
            "vertices": int(len(local)),
            "faces": int(len(getattr(geom, "faces", []))),
            "bounds_min": [float(x) for x in lo],
            "bounds_max": [float(x) for x in hi],
            "size": [float(x) for x in size],
            "center": [float(x) for x in ((lo + hi) / 2)],
            "matrix_world": np.asarray(transform, dtype=float).round(8).tolist(),
        }
        geometries.append(row)
        all_vertices.append(world)
        label = " ".join([str(node_name), str(geometry_name), str(material or "")])
        if KEYWORDS.search(label):
            candidates.append(row)
        if re.search(r"hinge|fold|left|right|inner|outer|display|screen", label, re.I):
            movable.append(row)

    if not geometries:
        raise RuntimeError("GLB loaded but no geometry nodes were found")
    vertices = np.vstack(all_vertices)
    lo, hi = vertices.min(axis=0), vertices.max(axis=0)
    report = {
        "source": SOURCE.name,
        "source_size_bytes": SOURCE.stat().st_size,
        "geometry_count": len(scene.geometry),
        "node_count": len(geometries),
        "scene_bounds_min": [float(x) for x in lo],
        "scene_bounds_max": [float(x) for x in hi],
        "scene_size": [float(x) for x in (hi - lo)],
        "scene_center": [float(x) for x in ((lo + hi) / 2)],
        "geometry": geometries,
        "screen_display_glass_candidates": sorted(
            candidates, key=lambda x: x["vertices"], reverse=True
        ),
        "hinge_fold_panel_candidates": sorted(
            movable, key=lambda x: x["vertices"], reverse=True
        ),
        "notes": [
            "Bounds are transformed GLB model-space coordinates, not CSS pixels.",
            "No screen or hinge coordinates are assumed; inspect the candidate meshes before using them.",
            "The original iPhone duo.glb file is read only and is not modified."
        ]
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "source": report["source"],
        "size_bytes": report["source_size_bytes"],
        "geometry_count": report["geometry_count"],
        "scene_size": report["scene_size"],
        "candidate_count": len(candidates),
        "candidates": [{
            "node": x["node"], "mesh": x["mesh"], "material": x["material"],
            "vertices": x["vertices"], "size": x["size"]
        } for x in candidates[:30]],
        "hinge_candidates": [{
            "node": x["node"], "mesh": x["mesh"], "material": x["material"],
            "vertices": x["vertices"], "size": x["size"]
        } for x in movable[:30]]
    }
    print("QAMQOR_DUO_SUMMARY=" + json.dumps(summary, ensure_ascii=False))
    print("REPORT=" + str(OUTPUT))

if __name__ == "__main__":
    main()
