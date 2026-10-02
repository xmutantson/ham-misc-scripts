"""Offline regression tests; all generated codes and sheet IDs are synthetic."""

from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageFont

import verification_grid as grid


ROOT = Path(__file__).resolve().parents[1]


class FailingWriter:
    """Simulate a disk error after a partial write, then close the real handle."""

    def __init__(self, stream):
        self.stream = stream
        self.name = stream.name

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def write(self, data):
        self.stream.write(data[:16])
        raise OSError("simulated disk error")


class VerificationGridTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.output = self.directory / "sheet.png"
        self.enterContext(patch.object(grid.secrets, "choice", return_value="A"))
        self.enterContext(patch.object(grid.secrets, "token_hex", return_value="a1b2c3d4e5f6"))

    @contextmanager
    def in_directory(self):
        previous = Path.cwd()
        try:
            os.chdir(self.directory)
            yield
        finally:
            os.chdir(previous)

    def run_python(self, arguments):
        environment = dict(os.environ, PYTHONPATH=str(ROOT))
        return subprocess.run(
            [sys.executable, "-B", *arguments], cwd=self.directory,
            env=environment, capture_output=True, text=True, check=False,
        )

    def test_import_has_no_files_or_console_output(self):
        result = self.run_python(["-c", "import verification_grid"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout + result.stderr, "")
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_grid_has_headers_and_secure_two_character_codes(self):
        with patch.object(grid.secrets, "choice", side_effect=list("A0" * 36)) as choice:
            result = grid.generate_verification_grid()
        self.assertEqual(result[0], [" ", "A", "B", "C", "D", "E", "F"])
        self.assertEqual(len(result), 7)
        for number, row in enumerate(result[1:], 1):
            self.assertEqual(row, [str(number)] + ["A0"] * 6)
        self.assertEqual(choice.call_count, 72)
        self.assertTrue(all(call.args == (grid.ALPHABET,) for call in choice.call_args_list))

    def test_default_filename_metadata_and_printed_id_agree(self):
        with self.in_directory(), patch.object(grid, "_render_grid", wraps=grid._render_grid) as render:
            filename = grid.create_verification_grid_image("W1ABC/P - W2DEF")
        self.assertEqual(filename, "verification_grid_A1B2C3D4E5F6.png")
        with Image.open(self.directory / filename) as image:
            image.load()
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "1")
            self.assertEqual(image.info["Sheet ID"], "A1B2C3D4E5F6")
            self.assertEqual(render.call_args.args[2], image.info["Sheet ID"])
            self.assertEqual(image.info["Label"], "W1ABC/P - W2DEF")
            self.assertEqual(render.call_args.args[3], image.info["Generated UTC"])
            self.assertTrue(image.info["Generated UTC"].endswith(" UTC"))

    def test_default_collision_preserves_existing_sheet(self):
        with self.in_directory():
            filename = Path(grid.create_verification_grid_image("Pair one"))
            original = filename.read_bytes()
            with self.assertRaises(FileExistsError):
                grid.create_verification_grid_image("Pair two")
            self.assertEqual(filename.read_bytes(), original)

    def test_explicit_path_refuses_overwrite_and_force_replaces(self):
        self.output.write_bytes(b"existing sheet")
        with self.assertRaises(FileExistsError):
            grid.create_verification_grid_image("Pair", self.output)
        self.assertEqual(self.output.read_bytes(), b"existing sheet")
        grid.create_verification_grid_image("Replacement", self.output, force=True)
        with Image.open(self.output) as image:
            self.assertEqual(image.info["Label"], "Replacement")
        self.assertEqual(list(self.directory.iterdir()), [self.output])

    def test_invalid_labels_and_extensions_create_nothing(self):
        for label in ("", "   ", "W" * 81, "Pair\nOther", "caf\u00e9"):
            with self.subTest(label=repr(label)), self.assertRaises(ValueError):
                grid.create_verification_grid_image(label, self.output)
        with self.assertRaises(ValueError):
            grid.create_verification_grid_image("Pair", self.directory / "sheet.jpg")
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_missing_parent_creates_nothing(self):
        for force in (False, True):
            with self.subTest(force=force), self.assertRaises(FileNotFoundError):
                grid.create_verification_grid_image("Pair", self.directory / "missing" / "sheet.png", force=force)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_encoding_failure_preserves_destination(self):
        self.output.write_bytes(b"existing sheet")
        for force in (False, True):
            with self.subTest(force=force), patch.object(Image.Image, "save", side_effect=OSError("encode failed")):
                with self.assertRaises(OSError):
                    grid.create_verification_grid_image("Pair", self.output, force=force)
            self.assertEqual(self.output.read_bytes(), b"existing sheet")
        self.assertEqual(list(self.directory.iterdir()), [self.output])

    def test_partial_new_write_is_removed(self):
        real_open = Path.open

        def failing_open(path, mode="r", *args, **kwargs):
            stream = real_open(path, mode, *args, **kwargs)
            return FailingWriter(stream) if mode == "xb" else stream

        with patch.object(Path, "open", failing_open), self.assertRaises(OSError):
            grid.create_verification_grid_image("Pair", self.output)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_failed_force_write_preserves_destination_and_cleans_temp(self):
        self.output.write_bytes(b"existing sheet")
        real_temporary_file = tempfile.NamedTemporaryFile

        def failing_temporary_file(*args, **kwargs):
            return FailingWriter(real_temporary_file(*args, **kwargs))

        with patch.object(tempfile, "NamedTemporaryFile", failing_temporary_file), self.assertRaises(OSError):
            grid.create_verification_grid_image("Pair", self.output, force=True)
        self.assertEqual(self.output.read_bytes(), b"existing sheet")
        self.assertEqual(list(self.directory.iterdir()), [self.output])

    def test_failed_replace_preserves_destination_and_cleans_temp(self):
        self.output.write_bytes(b"existing sheet")
        with patch.object(grid.os, "replace", side_effect=OSError("replace failed")), self.assertRaises(OSError):
            grid.create_verification_grid_image("Pair", self.output, force=True)
        self.assertEqual(self.output.read_bytes(), b"existing sheet")
        self.assertEqual(list(self.directory.iterdir()), [self.output])

    def test_normal_and_fallback_rendering_keep_borders_and_wrap_long_label(self):
        real_truetype = ImageFont.truetype

        def missing_named_fonts(font, *args, **kwargs):
            if isinstance(font, str):
                raise OSError("font unavailable")
            return real_truetype(font, *args, **kwargs)

        for fallback in (False, True):
            with self.subTest(fallback=fallback), patch.object(
                ImageFont, "truetype", missing_named_fonts if fallback else real_truetype,
            ):
                font = grid._load_font(16)
                lines = grid._wrap_text("W" * 80, font, 336)
                self.assertGreater(len(lines), 1)
                self.assertEqual("".join(lines), "W" * 80)
                self.assertTrue(all(font.getbbox(line)[2] - font.getbbox(line)[0] <= 336 for line in lines))
                grid.create_verification_grid_image("W" * 80, self.output, force=True)
                with Image.open(self.output) as image:
                    image.load()
                    left, right = 12, image.width - 13
                    bottom = image.height - 13
                    top = bottom - 336
                    for x in range(left, right + 1):
                        self.assertEqual(image.getpixel((x, top)), 0)
                        self.assertEqual(image.getpixel((x, bottom)), 0)
                    for y in range(top, bottom + 1):
                        self.assertEqual(image.getpixel((left, y)), 0)
                        self.assertEqual(image.getpixel((right, y)), 0)

    def test_cli_help_and_errors_are_clear_and_have_no_side_effects(self):
        cases = [
            (["--help"], 0),
            ([], 2),
            (["--label", "Pair", "--output", "sheet.jpg"], 2),
            (["--label", "Pair", "--output", "missing/sheet.png"], 2),
        ]
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                script = (
                    "import verification_grid as grid; "
                    "grid.secrets.choice = lambda alphabet: 'A'; "
                    "grid.secrets.token_hex = lambda size: 'a1b2c3d4e5f6'; "
                    "raise SystemExit(grid.main())"
                )
                result = self.run_python(["-c", script, *arguments])
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(list(self.directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
