#!/usr/bin/env python3
"""Build a real request button on the measured inner display of the iPhone Duo GLB."""
from pathlib import Path
import json
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "iPhone duo.glb"
OUTPUT = ROOT / "QAMQOR-iPhone-Duo.glb"
REPORT = ROOT / "qamqor-duo-button-build.json"
TEXTURE_SIZE = (1200, 320)
SCREEN_MATERIAL = "C_StarWhite_Screen_Inner"


def load_font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def make_button_texture() -> Image.Image:
    width, height = TEXTURE_SIZE
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (36, 42, width - 36, height - 28),
        radius=118,
        fill=(0, 70, 170, 90),
    )
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (30, 20, width - 30, height - 42), radius=118, fill=255
    )

    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = gradient.load()
    start = (39, 135, 255)
    end = (5, 91, 205)
    for x in range(width):
        t = x / max(1, width - 1)
        color = tuple(round(start[i] * (1 - t) + end[i] * t) for i in range(3))
        for y in range(height):
            px[x, y] = (*color, 255)
    gradient.putalpha(mask)
    image.alpha_composite(gradient)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (30, 20, width - 30, height - 42),
        radius=118,
        outline=(154, 203, 255, 245),
        width=4,
    )

    highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(highlight).rounded_rectangle(
        (48, 30, width - 48, 118),
        radius=72,
        fill=(255, 255, 255, 42),
    )
    image.alpha_composite(highlight)

    draw = ImageDraw.Draw(image)
    label = "Өтінім беру"
    font = load_font(126)
    bounds = draw.textbbox((0, 0), label, font=font)
    text_w, text_h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    x = (width - text_w) / 2 - bounds[0]
    y = (height - text_h) / 2 - bounds[1] - 4
    draw.text((x, y), label, font=font, fill=(255, 255, 255, 255))
    return image


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Source Duo GLB not found: {SOURCE}")

    scene = trimesh.load(str(SOURCE), force="scene", process=False)
    candidates = []
    for node_name in list(scene.graph.nodes_geometry):
        transform, geometry_name = scene.graph.get(node_name)
        geom = scene.geometry[geometry_name]
        material = getattr(getattr(geom, "visual", None), "material", None)
        material_name = getattr(material, "name", "") if material else ""
        if material_name == SCREEN_MATERIAL:
            world_vertices = trimesh.transform_points(
                np.asarray(geom.vertices, dtype=float), transform
            )
            if len(world_vertices):
                candidates.append((node_name, geometry_name, world_vertices))

    if not candidates:
        raise RuntimeError(
            f"Could not find the inner display material {SCREEN_MATERIAL!r}"
        )

    # This exported model has one large, flat inner screen spanning both halves.
    screen_node, screen_mesh, vertices = max(
        candidates, key=lambda item: len(item[2])
    )
    screen_min = vertices.min(axis=0)
    screen_max = vertices.max(axis=0)
    screen_size = screen_max - screen_min
    screen_width = float(screen_size[0])
    screen_height = float(screen_size[1])
    screen_front_z = float(screen_max[2])

    if screen_width < 0.08 or screen_height < 0.05:
        raise RuntimeError(
            "Measured inner screen bounds are unexpectedly small; refusing to add a misaligned button"
        )
    if float(screen_size[2]) > 0.00002:
        raise RuntimeError(
            f"Inner display is not sufficiently planar (Z thickness {screen_size[2]:.8f} m)"
        )

    # Button is centred across the inner screen, 20% up from its lower edge.
    button_width = screen_width * 0.50
    button_height = screen_width * 0.085
    button_center_x = float((screen_min[0] + screen_max[0]) / 2)
    button_center_y = float(screen_min[1] + screen_height * 0.20)
    button_z = screen_front_z + 0.00020

    half_w, half_h = button_width / 2, button_height / 2
    button_vertices = np.array([
        [button_center_x - half_w, button_center_y - half_h, button_z],
        [button_center_x + half_w, button_center_y - half_h, button_z],
        [button_center_x + half_w, button_center_y + half_h, button_z],
        [button_center_x - half_w, button_center_y + half_h, button_z],
    ], dtype=np.float64)
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    uv = np.array([
        [0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]
    ], dtype=np.float64)

    material = trimesh.visual.material.PBRMaterial(
        name="QAMQOR_Duo_Request_Button_Material",
        baseColorTexture=make_button_texture(),
        metallicFactor=0.0,
        roughnessFactor=0.30,
        alphaMode="OPAQUE",
        doubleSided=False,
    )
    mesh = trimesh.Trimesh(
        vertices=button_vertices,
        faces=faces,
        visual=trimesh.visual.texture.TextureVisuals(uv=uv, material=material),
        process=False,
    )
    scene.add_geometry(
        mesh,
        geom_name="QAMQOR_Duo_Request_Button_Mesh",
        node_name="QAMQOR_Duo_Request_Button",
    )
    OUTPUT.write_bytes(scene.export(file_type="glb"))

    check = trimesh.load(str(OUTPUT), force="scene", process=False)
    button_found = any(
        "QAMQOR_Duo_Request_Button" in str(node)
        or "QAMQOR_Duo_Request_Button" in str(check.graph.get(node)[1])
        for node in list(check.graph.nodes_geometry)
    )
    if not button_found:
        raise RuntimeError("Request button was not found in the exported Duo GLB")

    report = {
        "source": SOURCE.name,
        "output": OUTPUT.name,
        "source_size_bytes": SOURCE.stat().st_size,
        "output_size_bytes": OUTPUT.stat().st_size,
        "screen_material": SCREEN_MATERIAL,
        "screen_node": str(screen_node),
        "screen_mesh": str(screen_mesh),
        "screen_bounds_min": [float(x) for x in screen_min],
        "screen_bounds_max": [float(x) for x in screen_max],
        "screen_width": screen_width,
        "screen_height": screen_height,
        "screen_front_z": screen_front_z,
        "button": {
            "center": [button_center_x, button_center_y, button_z],
            "size": [button_width, button_height],
            "bounds_min": [button_center_x-half_w, button_center_y-half_h, button_z],
            "bounds_max": [button_center_x+half_w, button_center_y+half_h, button_z],
            "normal": [0, 0, 1],
            "physical_glb_mesh": True,
            "texture_size": list(TEXTURE_SIZE),
        },
        "geometry_count_after_export": len(check.geometry),
        "button_mesh_found_after_export": button_found,
        "source_asset_modified": False,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("QAMQOR_DUO_BUTTON_BUILD=" + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
