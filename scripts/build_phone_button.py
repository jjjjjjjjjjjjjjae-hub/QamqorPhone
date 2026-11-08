#!/usr/bin/env python3
"""Add a real, textured 3D request-button plane to the iPhone GLB."""

from pathlib import Path
import json
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "iPhone 18 pro max.glb"
OUTPUT = ROOT / "QAMQOR-iPhone-18-Pro-Max.glb"
TEXTURE_SIZE = (1200, 320)


def load_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def build_button_texture() -> Image.Image:
    width, height = TEXTURE_SIZE
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # Subtle soft shadow and a blue glass-like pill with antialiased edges.
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (38, 42, width - 38, height - 30),
        radius=116,
        fill=(0, 20, 55, 105),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    image.alpha_composite(shadow)

    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    pill_box = (30, 20, width - 30, height - 42)
    mask_draw.rounded_rectangle(pill_box, radius=116, fill=255)

    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = gradient.load()
    left = (32, 151, 255)
    right = (0, 91, 205)
    for x in range(width):
        t = x / max(1, width - 1)
        color = tuple(round(left[i] * (1 - t) + right[i] * t) for i in range(3))
        for y in range(height):
            px[x, y] = (*color, 255)
    gradient.putalpha(mask)
    image.alpha_composite(gradient)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        pill_box,
        radius=116,
        outline=(205, 235, 255, 210),
        width=5,
    )

    # Gentle highlight across the upper edge.
    highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight)
    hd.rounded_rectangle(
        (48, 32, width - 48, 118),
        radius=74,
        fill=(255, 255, 255, 28),
    )
    image.alpha_composite(highlight)

    draw = ImageDraw.Draw(image)
    label = "Өтінім беру"
    font = load_font(104)
    bounds = draw.textbbox((0, 0), label, font=font, stroke_width=0)
    text_w, text_h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    x = (width - text_w) / 2 - bounds[0]
    y = (height - text_h) / 2 - bounds[1] - 5
    draw.text((x, y), label, font=font, fill=(255, 255, 255, 255))

    return image


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Source GLB not found: {SOURCE}")

    scene = trimesh.load(str(SOURCE), force="scene", process=False)
    screen_candidates = []

    for node_name in list(scene.graph.nodes_geometry):
        transform, geometry_name = scene.graph.get(node_name)
        geom = scene.geometry[geometry_name]
        material = getattr(getattr(geom, "visual", None), "material", None)
        material_name = getattr(material, "name", "") if material else ""
        if material_name == "COLOUR_Blue_Screen":
            vertices = trimesh.transform_points(np.asarray(geom.vertices), transform)
            if len(vertices):
                screen_candidates.append((node_name, vertices))

    if not screen_candidates:
        raise RuntimeError("Could not locate COLOUR_Blue_Screen mesh in source GLB")

    # Use the exact measured screen mesh bounds rather than guessed phone coordinates.
    _, screen_vertices = max(screen_candidates, key=lambda item: len(item[1]))
    screen_min = screen_vertices.min(axis=0)
    screen_max = screen_vertices.max(axis=0)
    screen_width = float(screen_max[0] - screen_min[0])
    screen_height = float(screen_max[1] - screen_min[1])
    screen_front_z = float(screen_max[2])

    # Place a small physical plane in front of the display glass.
    button_width = screen_width * 0.72
    button_height = screen_width * 0.18
    button_center_x = float((screen_min[0] + screen_max[0]) / 2)
    button_center_y = float(screen_min[1] + screen_height * 0.34)
    button_z = screen_front_z + 0.00018

    half_w = button_width / 2
    half_h = button_height / 2
    vertices = np.array([
        [button_center_x - half_w, button_center_y - half_h, button_z],
        [button_center_x + half_w, button_center_y - half_h, button_z],
        [button_center_x + half_w, button_center_y + half_h, button_z],
        [button_center_x - half_w, button_center_y + half_h, button_z],
    ], dtype=np.float64)

    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)

    # GLTF UV origin is top-left. Keep the text upright on the front glass.
    uv = np.array([
        [0.0, 1.0],
        [1.0, 1.0],
        [1.0, 0.0],
        [0.0, 0.0],
    ], dtype=np.float64)

    texture = build_button_texture()
    material = trimesh.visual.material.PBRMaterial(
        name="QAMQOR_Request_Button_Material",
        baseColorTexture=texture,
        metallicFactor=0.0,
        roughnessFactor=0.34,
        alphaMode="BLEND",
        doubleSided=False,
    )
    visual = trimesh.visual.texture.TextureVisuals(uv=uv, material=material)
    button_mesh = trimesh.Trimesh(
        vertices=vertices,
        faces=faces,
        visual=visual,
        process=False,
    )

    scene.add_geometry(
        button_mesh,
        geom_name="QAMQOR_Request_Button_Mesh",
        node_name="QAMQOR_Request_Button",
    )

    glb_bytes = scene.export(file_type="glb")
    OUTPUT.write_bytes(glb_bytes)

    # Re-open the exported asset and validate the 3D button is present.
    check = trimesh.load(str(OUTPUT), force="scene", process=False)
    found = False
    for node_name in list(check.graph.nodes_geometry):
        _, geometry_name = check.graph.get(node_name)
        if "QAMQOR_Request_Button" in str(node_name) or "QAMQOR_Request_Button" in str(geometry_name):
            found = True
            break
    if not found:
        raise RuntimeError("Exported GLB does not contain the QAMQOR button mesh")

    report = {
        "source": SOURCE.name,
        "output": OUTPUT.name,
        "output_size_bytes": OUTPUT.stat().st_size,
        "screen_bounds_min": screen_min.tolist(),
        "screen_bounds_max": screen_max.tolist(),
        "screen_width": screen_width,
        "screen_height": screen_height,
        "screen_front_z": screen_front_z,
        "button": {
            "center": [button_center_x, button_center_y, button_z],
            "size": [button_width, button_height],
            "normal": [0, 0, 1],
            "physical_glb_mesh": True,
            "texture_size": list(TEXTURE_SIZE),
        },
        "mesh_count_after_export": len(check.geometry),
        "button_mesh_found_after_export": found,
    }
    (ROOT / "qamqor-3d-button-build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    from PIL import ImageFilter
    main()
