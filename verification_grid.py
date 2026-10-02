"""Create a printable, pre-shared verification grid. Importing has no side effects."""

import argparse
from datetime import datetime, timezone
from io import BytesIO
import os
from pathlib import Path
import secrets
import string
import tempfile

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo


ALPHABET = string.ascii_uppercase + string.digits
GRID_SIZE = 6
CELL_SIZE = 48
MARGIN = 12


def generate_verification_grid():
    """Return six rows of two-character codes, with A-F and 1-6 headers."""
    headers = [" "] + list(string.ascii_uppercase[:GRID_SIZE])
    rows = [
        [str(row + 1)]
        + ["".join(secrets.choice(ALPHABET) for _ in range(2))
           for _ in range(GRID_SIZE)]
        for row in range(GRID_SIZE)
    ]
    return [headers] + rows


def _load_font(size):
    for name in ("DejaVuSansMono.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def _wrap_text(text, font, width):
    """Wrap even unbroken labels using actual glyph bounds."""
    lines = []
    line = ""
    for character in text:
        candidate = line + character
        left, _, right, _ = font.getbbox(candidate)
        if line and right - left > width:
            lines.append(line)
            line = character
        else:
            line = candidate
    return lines + [line]


def _render_grid(grid, label, sheet_id, generated_at):
    cell_font = _load_font(20)
    title_font = _load_font(16)
    grid_span = (GRID_SIZE + 1) * CELL_SIZE
    heading = ["Verification grid", f"Sheet: {sheet_id}", generated_at]
    heading += _wrap_text(label, title_font, grid_span)
    boxes = [title_font.getbbox(line) for line in heading]
    header_height = sum(bottom - top + 8 for _, top, _, bottom in boxes)
    grid_top = MARGIN + header_height
    image = Image.new("1", (grid_span + 1 + 2 * MARGIN,
                            grid_top + grid_span + 1 + MARGIN), 1)
    draw = ImageDraw.Draw(image)
    y = MARGIN
    for line, (left, top, _, bottom) in zip(heading, boxes):
        draw.text((MARGIN - left, y - top), line, fill=0, font=title_font)
        y += bottom - top + 8

    for i, row in enumerate(grid):
        for j, cell in enumerate(row):
            x = MARGIN + j * CELL_SIZE
            y = grid_top + i * CELL_SIZE
            draw.rectangle((x, y, x + CELL_SIZE, y + CELL_SIZE), outline=0)
            left, top, right, bottom = draw.textbbox((0, 0), cell, font=cell_font)
            text_x = x + (CELL_SIZE - (right - left)) // 2 - left
            text_y = y + (CELL_SIZE - (bottom - top)) // 2 - top
            draw.text((text_x, text_y), cell, fill=0, font=cell_font)
    return image


def _save_png(image, output_path, metadata, force):
    # Finish encoding before touching the destination, including on --force.
    with BytesIO() as buffer:
        image.save(buffer, format="PNG", optimize=True, pnginfo=metadata)
        data = buffer.getvalue()

    if not force:
        # Exclusive creation is the existence check: no check-then-open race.
        stream = output_path.open("xb")
        try:
            with stream:
                stream.write(data)
        except BaseException:
            output_path.unlink(missing_ok=True)
            raise
        return

    # A same-directory temporary file makes replacement atomic on the same disk.
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(data)
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def create_verification_grid_image(custom_name, output_path=None, *, force=False):
    """Save a new sheet and return its filename; replacement requires force=True.

    The human-readable label never forms part of the filesystem path. The random
    sheet ID appears in the image, PNG metadata and the default filename.
    """
    label = custom_name.strip()
    if not label or len(label) > 80 or any(not 32 <= ord(c) <= 126 for c in label):
        raise ValueError("label must contain 1-80 printable ASCII characters")
    sheet_id = secrets.token_hex(6).upper()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    output_path = Path(output_path) if output_path is not None else Path(
        f"verification_grid_{sheet_id}.png"
    )
    if output_path.suffix.lower() != ".png":
        raise ValueError("output filename must end in .png")

    image = _render_grid(generate_verification_grid(), label, sheet_id, generated_at)
    metadata = PngInfo()
    metadata.add_text("Sheet ID", sheet_id)
    metadata.add_text("Label", label)
    metadata.add_text("Generated UTC", generated_at)
    try:
        _save_png(image, output_path, metadata, force)
    finally:
        image.close()
    return str(output_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a pre-shared verification grid PNG.")
    parser.add_argument("--label", required=True, help="operator names/callsigns (1-80 ASCII characters)")
    parser.add_argument("--output", type=Path, help="PNG path; default includes a new sheet ID")
    parser.add_argument("--force", action="store_true", help="replace the selected output file")
    args = parser.parse_args(argv)
    try:
        output_file = create_verification_grid_image(args.label, args.output, force=args.force)
    except FileExistsError:
        parser.exit(2, "error: output already exists; choose another path or use --force\n")
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Verification grid saved as: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
