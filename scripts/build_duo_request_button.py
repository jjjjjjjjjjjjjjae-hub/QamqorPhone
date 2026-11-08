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
    """Bake a compact lock screen and its physical request CTA into the folded Duo display."""
    width, height = TEXTURE_SIZE
    image = Image.new("RGB", (width, height), (2, 5, 10))

    # Restrained OLED glow, keeping most of the screen near true black.
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (95, 140, width - 95, 760),
        fill=(8, 47, 96, 88),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(92))
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(image)

    # Subtle system status indicators along the top edge.
    font_status = load_font(20)
    draw.text((48, 46), "QAMQOR", font=font_status, fill=(220, 232, 248))
    # Cellular bars.
    for i, bar_h in enumerate((10, 15, 20, 25)):
        x = 570 + i * 12
        draw.rounded_rectangle(
            (x, 68 - bar_h, x + 7, 68),
            radius=3,
            fill=(238, 245, 255),
        )
    # Wi-Fi arcs and a compact battery glyph.
    draw.arc((632, 36, 672, 74), 218, 322, fill=(238, 245, 255), width=4)
    draw.arc((640, 45, 664, 69), 218, 322, fill=(238, 245, 255), width=4)
    draw.ellipse((650, 64, 655, 69), fill=(238, 245, 255))
    draw.rounded_rectangle((684, 43, 733, 68), radius=6, outline=(238, 245, 255), width=3)
    draw.rounded_rectangle((735, 50, 740, 61), radius=2, fill=(238, 245, 255))
    draw.rounded_rectangle((689, 48, 724, 63), radius=3, fill=(65, 205, 117))

    # iPhone-style lock-screen clock and a short service label.
    date = "ТЕЛЕФОН ЖӨНДЕУ ҚЫЗМЕТІ"
    font_date = load_font(25)
    date_box = draw.textbbox((0, 0), date, font=font_date)
    draw.text(((width - (date_box[2] - date_box[0])) / 2, 145),
              date, font=font_date, fill=(208, 222, 242))

    font_time = load_font(154)
    time_label = "9:41"
    time_box = draw.textbbox((0, 0), time_label, font=font_time)
    time_w = time_box[2] - time_box[0]
    draw.text(((width - time_w) / 2 - time_box[0], 205 - time_box[1]),
              time_label, font=font_time, fill=(250, 252, 255))

    # Use the actual uploaded QamqorPhone logo in the lock screen.
    if not LOGO.exists():
        raise FileNotFoundError(f"QamqorPhone logo not found: {LOGO}")
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((172, 172), Image.Resampling.LANCZOS)
    logo_x = (width - logo.width) // 2
    logo_y = 475 + (172 - logo.height) // 2
    image_rgba = image.convert("RGBA")
    image_rgba.alpha_composite(logo, (logo_x, logo_y))
    image = image_rgba.convert("RGB")
    draw = ImageDraw.Draw(image)

    brand = "QAMQOR PHONE"
    font_brand = load_font(30)
    brand_box = draw.textbbox((0, 0), brand, font=font_brand)
    brand_w = brand_box[2] - brand_box[0]
    draw.text(((width - brand_w) / 2 - brand_box[0], 665 - brand_box[1]),
              brand, font=font_brand, fill=(219, 231, 248))

    # The button stays at the same UV location as the existing 3D hitbox.
    button_box = (82, 835, width - 82, 965)
    draw.rounded_rectangle(
        button_box,
        radius=64,
        fill=(17, 112, 225),
        outline=(132, 194, 255),
        width=4,
    )
    font_cta = load_font(42)
    label = "Өтінім беру"
    box = draw.textbbox((0, 0), label, font=font_cta)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    text_x = (width - text_w) / 2 - box[0]
    text_y = (button_box[1] + button_box[3] - text_h) / 2 - box[1] - 2
    draw.text((text_x, text_y), label, font=font_cta, fill=(255, 255, 255))

    # A familiar bottom home indicator.
    draw.rounded_rectangle((292, 1050, 476, 1058), radius=5, fill=(238, 242, 250))

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
        "lock_screen_artwork": True,
        "lock_screen_time": "9:41",
        "physical_request_button_box_px": [82, 835, width - 82, 965],
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
