#!/usr/bin/env python3
"""Add the closed-state Qamqor screen artwork to the Duo GLB without dropping animations."""
from pathlib import Path
import io
import json
import struct
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "iPhone duo.glb"
LOGO = ROOT / "QamqorPhone.png"
OUTPUT = ROOT / "QAMQOR-iPhone-Duo.glb"
REPORT = ROOT / "qamqor-duo-button-build.json"
MATERIAL_NAME = "C_SW_Screen_Outer"
OUTPUT_MATERIAL_NAME = "QAMQOR_Duo_Closed_Display"
TEXTURE_SIZE = (768, 1120)


def load_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def make_screen_artwork() -> bytes:
    """Create the very short closed-screen state requested: logo + one CTA."""
    width, height = TEXTURE_SIZE
    image = Image.new("RGB", (width, height), (3, 5, 10))
    draw = ImageDraw.Draw(image)

    # Subtle OLED-black vignette.
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (90, 180, width - 90, 800),
        fill=(9, 33, 68, 75),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(95))
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(image)

    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        logo.thumbnail((260, 260), Image.Resampling.LANCZOS)
        # Keep the supplied logo itself; do not redraw or replace it.
        x = (width - logo.width) // 2
        y = 315 + (260 - logo.height) // 2
        image_rgba = image.convert("RGBA")
        image_rgba.alpha_composite(logo, (x, y))
        image = image_rgba.convert("RGB")
        draw = ImageDraw.Draw(image)
    else:
        raise FileNotFoundError(f"QamqorPhone logo not found: {LOGO}")

    # One restrained label beneath the logo.
    brand = "QAMQOR PHONE"
    font_brand = load_font(26)
    box = draw.textbbox((0, 0), brand, font=font_brand)
    draw.text(((width - (box[2]-box[0]))/2, 595), brand, font=font_brand, fill=(199, 214, 236))

    # Single clear, tactile CTA near the lower part of the outer screen.
    button_box = (82, 835, width - 82, 965)
    draw.rounded_rectangle(
        button_box,
        radius=64,
        fill=(17, 112, 225),
        outline=(122, 186, 255),
        width=3,
    )
    font_cta = load_font(39)
    label = "Өтінім беру"
    box = draw.textbbox((0, 0), label, font=font_cta)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    text_x = (width - text_w) / 2 - box[0]
    text_y = (button_box[1] + button_box[3] - text_h) / 2 - box[1] - 2
    draw.text((text_x, text_y), label, font=font_cta, fill=(255, 255, 255))

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def parse_glb(path: Path):
    data = path.read_bytes()
    if len(data) < 20:
        raise RuntimeError("Source GLB is too small")
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total_length != len(data):
        raise RuntimeError("Source must be a valid GLB 2.0 file")
    offset = 12
    document = None
    binary = b""
    while offset + 8 <= total_length:
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode("utf-8").rstrip(" \\0"))
        elif chunk_type == 0x004E4942:
            binary = chunk
    if document is None:
        raise RuntimeError("Source GLB has no JSON chunk")
    return document, binary


def pack_glb(document, binary: bytes) -> bytes:
    json_bytes = json.dumps(
        document, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    json_bytes += b" " * ((-len(json_bytes)) % 4)
    binary += b"\\0" * ((-len(binary)) % 4)
    json_chunk = struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
    bin_chunk = struct.pack("<II", len(binary), 0x004E4942) + binary
    total = 12 + len(json_chunk) + len(bin_chunk)
    return struct.pack("<4sII", b"glTF", 2, total) + json_chunk + bin_chunk


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    document, binary = parse_glb(SOURCE)

    animations_before = json.loads(json.dumps(document.get("animations", [])))
    materials = document.setdefault("materials", [])
    matches = [
        i for i, material in enumerate(materials)
        if material.get("name") == MATERIAL_NAME
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {MATERIAL_NAME!r} material, found {len(matches)}"
        )
    material_index = matches[0]

    # Ensure the external display material is actually referenced by a mesh primitive
    # with UV coordinates. No model-space coordinates or animation channels are changed.
    mesh_indices = []
    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        for primitive in mesh.get("primitives", []):
            if primitive.get("material") == material_index:
                if "TEXCOORD_0" not in primitive.get("attributes", {}):
                    raise RuntimeError(
                        f"Outer screen mesh {mesh_index} has no TEXCOORD_0"
                    )
                mesh_indices.append(mesh_index)
                break
    if not mesh_indices:
        raise RuntimeError("No mesh primitive uses the external screen material")

    png_bytes = make_screen_artwork()
    buffers = document.setdefault("buffers", [])
    if len(buffers) != 1:
        raise RuntimeError("Expected one embedded GLB buffer")
    buffer_length = int(buffers[0].get("byteLength", 0))
    if buffer_length > len(binary):
        raise RuntimeError("GLB buffer length exceeds the binary chunk")
    binary = binary[:buffer_length]
    binary += b"\\0" * ((-len(binary)) % 4)
    image_offset = len(binary)
    binary += png_bytes
    binary += b"\\0" * ((-len(binary)) % 4)
    buffers[0]["byteLength"] = image_offset + len(png_bytes)

    buffer_views = document.setdefault("bufferViews", [])
    image_view_index = len(buffer_views)
    buffer_views.append({
        "buffer": 0,
        "byteOffset": image_offset,
        "byteLength": len(png_bytes),
        "name": "QAMQOR_Duo_Closed_Screen_Image",
    })

    images = document.setdefault("images", [])
    image_index = len(images)
    images.append({
        "bufferView": image_view_index,
        "mimeType": "image/png",
        "name": "QAMQOR_Duo_Closed_Screen",
    })

    samplers = document.setdefault("samplers", [])
    sampler_index = len(samplers)
    samplers.append({
        "magFilter": 9729,
        "minFilter": 9729,
        "wrapS": 33071,
        "wrapT": 33071,
    })

    textures = document.setdefault("textures", [])
    texture_index = len(textures)
    textures.append({
        "sampler": sampler_index,
        "source": image_index,
        "name": "QAMQOR_Duo_Closed_Screen_Texture",
    })

    material = materials[material_index]
    material["name"] = OUTPUT_MATERIAL_NAME
    pbr = material.setdefault("pbrMetallicRoughness", {})
    pbr["baseColorFactor"] = [1, 1, 1, 1]
    pbr["baseColorTexture"] = {"index": texture_index, "texCoord": 0}
    pbr["metallicFactor"] = 0.0
    pbr["roughnessFactor"] = 0.75
    material["emissiveFactor"] = [0.72, 0.72, 0.72]
    material["emissiveTexture"] = {"index": texture_index, "texCoord": 0}
    material["alphaMode"] = "OPAQUE"

    # Preserve every source animation clip and every channel byte-for-byte in JSON.
    if document.get("animations", []) != animations_before:
        raise RuntimeError("Animation data unexpectedly changed while patching the screen")
    output_bytes = pack_glb(document, binary)
    OUTPUT.write_bytes(output_bytes)

    # Re-open the newly packed GLB and verify its clip is still present.
    check_document, _ = parse_glb(OUTPUT)
    animations_after = check_document.get("animations", [])
    if animations_after != animations_before:
        raise RuntimeError("Output GLB lost or changed source animations")
    output_material = next(
        (m for m in check_document.get("materials", [])
         if m.get("name") == OUTPUT_MATERIAL_NAME),
        None,
    )
    if not output_material:
        raise RuntimeError("Output GLB does not contain the Qamqor external-screen material")

    report = {
        "source": SOURCE.name,
        "output": OUTPUT.name,
        "source_size_bytes": SOURCE.stat().st_size,
        "output_size_bytes": OUTPUT.stat().st_size,
        "closed_screen_material_source": MATERIAL_NAME,
        "closed_screen_material_output": OUTPUT_MATERIAL_NAME,
        "screen_mesh_indices": mesh_indices,
        "texture_size": list(TEXTURE_SIZE),
        "texture_bytes": len(png_bytes),
        "animations_preserved": True,
        "animations_count": len(animations_after),
        "animations": [
            {"name": a.get("name"), "channels": len(a.get("channels", []))}
            for a in animations_after
        ],
        "source_asset_modified": False,
    }
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("QAMQOR_DUO_BUILD=" + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
