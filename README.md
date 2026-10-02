# Verification grid

Generate a 6x6 grid of two-character codes as a small, black-and-white PNG.
Share the same sheet privately ahead of time, then use its coordinates as a
limited check that another operator has access to that shared information.
This utility creates sheets; it does not authenticate people or track their use.

## Setup

Use Python 3.11 or newer and Pillow 10.2 or newer. Local verification used
Python 3.11.7 and Pillow 10.2.0 on Windows.

Create an isolated environment from the repository directory:

```sh
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` in PowerShell, or
`source .venv/bin/activate` on macOS/Linux, then install the dependency:

```sh
python -m pip install -r requirements.txt
```

## Generate a sheet

```sh
python verification_grid.py --label "W1ABC/P - W2DEF"
```

This prints the path to `verification_grid_<SHEET-ID>.png` in the current
directory. Every invocation generates a fresh grid and a new random sheet ID.
The ID and a UTC creation timestamp appear on the image and in its PNG metadata.
The ID is for coordinating sheet versions, not a secret or an authentication code.

`--label` is required; there is no need to edit the source. Labels may contain
1-80 printable ASCII characters, including callsign slashes. Outer whitespace
is trimmed, long labels wrap, and the label never determines the output path.
The output remains a 1-bit PNG with larger cells and complete outer borders.
The renderer tries DejaVu Sans Mono, then Arial, then Pillow's bundled default font.

Choose an explicit output path when needed (its parent directory must exist):

```sh
python verification_grid.py --label "W1ABC/P - W2DEF" --output pair-sheet.png
python verification_grid.py --help
```

The filename must end in `.png`. Existing files are preserved by default,
including when the randomly selected default filename already exists.
An intentional replacement requires `--force`:

```sh
python verification_grid.py --label "W1ABC/P - W2DEF" --output pair-sheet.png --force
```

Replacement encodes and writes the new sheet to a temporary file before
replacing the old file. A failed encode, write, or replacement leaves the old
file intact; ordinary failed writes remove newly created incomplete files.
Replacements generate new codes: coordinate retirement and redistribution with
everyone holding the old sheet. To give another operator the same sheet, copy
the existing PNG rather than running the generator again.

## Use and limits

Treat the PNG and all printed copies as shared secrets. Keep them in private
storage, share them through a trusted private channel, and keep them out of
version control. Default generated filenames are ignored by Git; custom output
paths are not automatically ignored. The tool does not encrypt files or manage
filesystem permissions.

Before use, agree on the sheet ID, who holds it, when it expires, and how to
mark used cells. Coordinates use column letters A-F and row numbers 1-6.
For example, an operator requests A3 and the other reads its code; a check in
the opposite direction must use a different unused cell. Agree on an unambiguous
way to read letters and digits, especially O/0 and I/1.

After a coordinate is requested, both operators should retire that cell even
if the exchange is interrupted. Keep both copies' used-cell records in sync;
if their state is uncertain, stop and arrange a replacement through the trusted
channel. Retire the whole sheet at the agreed expiry, when exhausted, or whenever
a copy may have been exposed. These are **manual procedures**: the generator
does not enforce one-time use, expiry, failed-attempt limits, or synchronization.

A correct response is limited evidence of access to a shared sheet. It does not
prove personal identity, prevent relaying, or protect a disclosed or reused code.
Anyone holding a copy has the same information. Codes use Python's `secrets`
module, but each two-character code still has only 1,296 possible values. The
two-character format is retained for compatibility and short spoken exchanges;
it is not a strong authentication guarantee. Use an established authentication
method when stronger assurance is required. Changing the random generator alone
does not remove these protocol limitations.

## Python use and tests

Importing the module creates no files or console output. The existing functions
remain available:

```python
from verification_grid import create_verification_grid_image

filename = create_verification_grid_image("W1ABC/P - W2DEF", "pair-sheet.png")
```

`generate_verification_grid()` returns a 7x7 list including headers. The image
function returns the output filename and accepts keyword-only `force=True`
for intentional replacement.

Run the offline regression suite from the repository directory:

```sh
python -m unittest discover -s tests -v
```

Tests cover import behavior, grid shape and randomness API, sheet metadata,
safe saving and failure cleanup, input errors, CLI behavior, and normal/fallback
font layout. They use temporary directories and synthetic sheet data; no radio,
network service, or hardware is needed.
