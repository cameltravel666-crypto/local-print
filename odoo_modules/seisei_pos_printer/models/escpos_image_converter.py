# -*- coding: utf-8 -*-
"""
ESC/POS Image Converter

Converts images (e.g., rendered POS receipts) to ESC/POS raster commands
for thermal receipt printers.
"""

import base64
import io
import logging

_logger = logging.getLogger(__name__)

# Paper width in pixels (assuming 8 dots per mm)
PAPER_WIDTH_PIXELS = {
    '58mm': 384,  # 48mm printable area * 8 dots/mm
    '80mm': 576,  # 72mm printable area * 8 dots/mm
}


def convert_image_to_escpos(image_base64, paper_width='80mm', auto_cut=True, 
                             cut_mode='partial', feed_lines=3, protocol='escpos'):
    """
    Convert a base64 encoded image to ESC/POS raster commands.
    
    Args:
        image_base64: Base64 encoded image (JPEG/PNG)
        paper_width: Paper width ('58mm' or '80mm')
        auto_cut: Whether to add cut command
        cut_mode: 'full' or 'partial' cut
        feed_lines: Lines to feed before cutting
        protocol: 'escpos' or 'star'
        
    Returns:
        bytes: ESC/POS command sequence
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        _logger.error("PIL/Pillow not available, cannot convert image")
        return b''
    
    try:
        # Decode base64 image
        image_data = base64.b64decode(image_base64)
        im = Image.open(io.BytesIO(image_data))
        
        # Get target width
        target_width = PAPER_WIDTH_PIXELS.get(paper_width, 576)
        
        # Resize image to fit paper width while maintaining aspect ratio
        if im.width != target_width:
            ratio = target_width / im.width
            new_height = int(im.height * ratio)
            im = im.resize((target_width, new_height), Image.LANCZOS)
        
        # Convert to grayscale then to black and white
        im = im.convert("L")
        im = ImageOps.invert(im)
        im = im.convert("1")
        
        # Generate raster commands
        if protocol == 'star':
            raster_data = _format_star_raster(im)
        else:
            raster_data = _format_escpos_raster(im)
        
        # Add feed and cut commands
        commands = raster_data
        
        if feed_lines > 0:
            # ESC d n - Feed n lines
            commands += b'\x1b\x64' + bytes([feed_lines])
        
        if auto_cut:
            if cut_mode == 'full':
                # GS V m - Full cut
                commands += b'\x1d\x56\x00'
            else:
                # GS V m - Partial cut
                commands += b'\x1d\x56\x01'
        
        return commands
        
    except Exception as e:
        _logger.error("Error converting image to ESC/POS: %s", str(e))
        return b''


def _format_escpos_raster(im):
    """
    Format image as ESC/POS raster data using GS v 0 command.
    
    Args:
        im: PIL Image in mode '1' (black and white)
        
    Returns:
        bytes: Raster command data
    """
    width = int((im.width + 7) / 8)  # Width in bytes
    max_slice_height = 255
    
    raster_data = b''
    dots = im.tobytes()
    
    while len(dots):
        im_slice = dots[:width * max_slice_height]
        slice_height = int(len(im_slice) / width)
        
        # GS v 0 m xL xH yL yH d1...dk
        raster_send = b'\x1d\x76\x30\x00'
        raster_data += raster_send
        raster_data += width.to_bytes(2, 'little')
        raster_data += slice_height.to_bytes(2, 'little')
        raster_data += im_slice
        
        dots = dots[width * max_slice_height:]
    
    return raster_data


def _format_star_raster(im):
    """
    Format image as Star raster data.
    
    Args:
        im: PIL Image in mode '1' (black and white)
        
    Returns:
        bytes: Raster command data
    """
    width = int((im.width + 7) / 8)
    
    raster_init = b'\x1b\x2a\x72\x41'  # ESC * r A - Enter raster mode
    raster_page_length = b'\x1b\x2a\x72\x50\x30\x00'  # ESC * r P 0 NUL
    raster_send = b'\x62'  # b - Raster line
    raster_close = b'\x1b\x2a\x72\x42'  # ESC * r B - Exit raster mode
    
    raster_data = b''
    dots = im.tobytes()
    
    while len(dots):
        raster_data += raster_send + width.to_bytes(2, 'little') + dots[:width]
        dots = dots[width:]
    
    return raster_init + raster_page_length + raster_data + raster_close


def _format_escpos_column_image(im, high_density_vertical=True, 
                                 high_density_horizontal=True, scale=100):
    """
    Format image using ESC * bit image column mode.
    For older printers that don't support GS v 0.
    
    Args:
        im: PIL Image in mode '1' (black and white)
        high_density_vertical: Use high density vertically
        high_density_horizontal: Use high density horizontally
        scale: Scale percentage
        
    Returns:
        bytes: Bit image command data
    """
    from PIL import Image
    
    # Scale if needed
    if scale != 100:
        scale_ratio = scale / 100
        new_width = int(im.width * scale_ratio)
        new_height = int(im.height * scale_ratio)
        im = im.resize((new_width, new_height), Image.LANCZOS)
    
    # ESC * prints column by column, so transpose the image
    im = im.transpose(Image.ROTATE_270).transpose(Image.FLIP_LEFT_RIGHT)
    
    ESC = b'\x1b'
    density_byte = (1 if high_density_horizontal else 0) + \
                   (32 if high_density_vertical else 0)
    nL = im.height & 0xFF
    nH = (im.height >> 8) & 0xFF
    HEADER = ESC + b'*' + bytes([density_byte, nL, nH])
    
    line_height = 24 if high_density_vertical else 8
    
    raster_data = ESC + b'3\x10'  # Adjust line-feed size
    
    for column in _extract_columns(im, line_height):
        raster_data += HEADER + column + b'\n'
    
    raster_data += ESC + b'2'  # Reset line-feed size
    
    return raster_data


def _extract_columns(im, line_height):
    """
    Extract columns from an image for ESC * command.
    
    Args:
        im: PIL Image
        line_height: Height of each column slice
        
    Yields:
        bytes: Column data
    """
    from PIL import Image
    
    width_pixels, height_pixels = im.size
    
    for left in range(0, width_pixels, line_height):
        box = (left, 0, left + line_height, height_pixels)
        im_chunk = im.transform(
            (line_height, height_pixels),
            Image.EXTENT,
            box
        )
        yield im_chunk.tobytes()
