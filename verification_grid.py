from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import random
import string

def generate_verification_grid():
    # Generate a 6x6 grid of random two-character alphanumeric codes
    grid = [["".join(random.choices(string.ascii_uppercase + string.digits, k=2)) for _ in range(6)] for _ in range(6)]

    # Add header row and column
    headers = [' '] + [chr(65 + i) for i in range(6)]  # A-F
    grid_with_headers = [headers] + [[str(i+1)] + row for i, row in enumerate(grid)]

    return grid_with_headers

def create_verification_grid_image(custom_name):
    # Generate the verification grid
    verification_grid = generate_verification_grid()

    # Define image properties
    cell_size = 30  # Reduced cell size to make the grid smaller
    header_height = 40  # Reduced header height
    grid_width = len(verification_grid[0]) * cell_size
    grid_height = len(verification_grid) * cell_size + header_height

    # Create a blank image with white background
    img = Image.new('RGB', (grid_width, grid_height), 'white')
    draw = ImageDraw.Draw(img)

    # Load fonts with adjusted sizes
    try:
        font = ImageFont.truetype("arial.ttf", 12)  # Adjusted font size
        title_font = ImageFont.truetype("arial.ttf", 14)  # Adjusted title font size
    except IOError:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    # Draw the title
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title_text = f"Gen: {timestamp}\n{custom_name}"
    draw.text((5, 5), title_text, fill="black", font=title_font)

    # Draw the grid
    for i, row in enumerate(verification_grid):
        for j, cell in enumerate(row):
            x = j * cell_size
            y = i * cell_size + header_height

            # Draw cell border
            draw.rectangle([x, y, x + cell_size, y + cell_size], outline="black", width=1)

            # Center the text in the cell
            bbox = draw.textbbox((0, 0), cell, font=font)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            text_x = x + (cell_size - text_width) // 2
            text_y = y + (cell_size - text_height) // 2
            draw.text((text_x, text_y), cell, fill="black", font=font)

    # Save the image to a file with higher compression
    output_filename = f"verification_grid_{custom_name}.jpg"
    img.save(output_filename, format='JPEG', quality=80, optimize=True)
    return output_filename

# Example usage
custom_name_block = "2-Callsigns-Here"
output_file = create_verification_grid_image(custom_name_block)
print(f"Verification grid saved as: {output_file}")
