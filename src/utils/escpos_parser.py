# -*- coding: utf-8 -*-
"""
Seisei Print Agent - ESC/POS Parser
Parses ESC/POS commands and extracts raster images

Developed by Seisei
"""

import struct
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ESCPOSImage:
    """Represents a raster image from ESC/POS data"""
    width: int  # Width in pixels
    height: int  # Height in pixels
    data: bytes  # Raw bitmap data
    offset: int  # Position in original data


class ESCPOSParser:
    """
    Parser for ESC/POS thermal printer commands

    Supports:
    - Text extraction
    - Raster image extraction (GS v 0)
    - Basic command recognition
    """

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.images: List[ESCPOSImage] = []
        self.text_content: List[str] = []

    def parse(self) -> Tuple[str, List[ESCPOSImage]]:
        """
        Parse ESC/POS data

        Returns:
            Tuple of (extracted_text, list_of_images)
        """
        self.pos = 0
        self.images = []
        self.text_content = []
        current_line = ""

        while self.pos < len(self.data):
            byte = self.data[self.pos]

            # ESC commands (0x1B)
            if byte == 0x1B:
                if current_line:
                    self.text_content.append(current_line)
                    current_line = ""
                self._parse_esc_command()
                continue

            # GS commands (0x1D)
            elif byte == 0x1D:
                if current_line:
                    self.text_content.append(current_line)
                    current_line = ""
                self._parse_gs_command()
                continue

            # Line feed
            elif byte == 0x0A:
                self.text_content.append(current_line)
                current_line = ""
                self.pos += 1
                continue

            # Carriage return
            elif byte == 0x0D:
                self.pos += 1
                continue

            # Printable ASCII
            elif 0x20 <= byte <= 0x7E:
                current_line += chr(byte)
                self.pos += 1
                continue

            # UTF-8 multi-byte sequences (Chinese characters)
            elif byte >= 0xC0:
                char, length = self._decode_utf8()
                if char:
                    current_line += char
                continue

            # Other control characters
            else:
                self.pos += 1
                continue

        if current_line:
            self.text_content.append(current_line)

        return "\n".join(self.text_content), self.images

    def _decode_utf8(self) -> Tuple[Optional[str], int]:
        """Decode UTF-8 character at current position"""
        try:
            byte = self.data[self.pos]

            # 2-byte sequence
            if 0xC0 <= byte <= 0xDF:
                if self.pos + 2 <= len(self.data):
                    char = self.data[self.pos:self.pos+2].decode('utf-8', errors='ignore')
                    self.pos += 2
                    return char, 2

            # 3-byte sequence (most Chinese characters)
            elif 0xE0 <= byte <= 0xEF:
                if self.pos + 3 <= len(self.data):
                    char = self.data[self.pos:self.pos+3].decode('utf-8', errors='ignore')
                    self.pos += 3
                    return char, 3

            # 4-byte sequence
            elif 0xF0 <= byte <= 0xF7:
                if self.pos + 4 <= len(self.data):
                    char = self.data[self.pos:self.pos+4].decode('utf-8', errors='ignore')
                    self.pos += 4
                    return char, 4

        except Exception:
            pass

        self.pos += 1
        return None, 1

    def _parse_esc_command(self):
        """Parse ESC command"""
        if self.pos + 1 >= len(self.data):
            self.pos += 1
            return

        cmd = self.data[self.pos + 1]

        # ESC @ - Initialize printer
        if cmd == ord('@'):
            self.pos += 2

        # ESC a n - Select justification
        elif cmd == ord('a'):
            self.pos += 3

        # ESC ! n - Select print mode
        elif cmd == ord('!'):
            self.pos += 3

        # ESC d n - Print and feed n lines
        elif cmd == ord('d'):
            if self.pos + 2 < len(self.data):
                n = self.data[self.pos + 2]
                self.text_content.extend([""] * n)
            self.pos += 3

        # ESC J n - Print and feed n dots
        elif cmd == ord('J'):
            self.pos += 3

        # ESC 2 - Select default line spacing
        elif cmd == ord('2'):
            self.pos += 2

        # ESC 3 n - Set line spacing
        elif cmd == ord('3'):
            self.pos += 3

        # ESC M n - Select character font
        elif cmd == ord('M'):
            self.pos += 3

        # ESC E n - Turn emphasized mode on/off
        elif cmd == ord('E'):
            self.pos += 3

        # ESC - n - Turn underline mode on/off
        elif cmd == ord('-'):
            self.pos += 3

        # ESC G n - Turn double-strike mode on/off
        elif cmd == ord('G'):
            self.pos += 3

        # ESC { n - Turn upside-down mode on/off
        elif cmd == ord('{'):
            self.pos += 3

        # ESC R n - Select international character set
        elif cmd == ord('R'):
            self.pos += 3

        # ESC t n - Select character code table
        elif cmd == ord('t'):
            self.pos += 3

        # ESC p - Generate pulse
        elif cmd == ord('p'):
            self.pos += 5

        # ESC c 5 n - Enable/disable panel buttons
        elif cmd == ord('c'):
            self.pos += 4

        # Unknown - skip 2 bytes
        else:
            self.pos += 2

    def _parse_gs_command(self):
        """Parse GS command"""
        if self.pos + 1 >= len(self.data):
            self.pos += 1
            return

        cmd = self.data[self.pos + 1]

        # GS v 0 - Print raster bit image
        if cmd == ord('v'):
            self._parse_raster_image()

        # GS V - Select cut mode and cut paper
        elif cmd == ord('V'):
            if self.pos + 2 < len(self.data):
                m = self.data[self.pos + 2]
                if m in [0, 1, 48, 49]:
                    self.pos += 3
                elif m in [65, 66, 97, 98]:
                    self.pos += 4
                else:
                    self.pos += 3
            else:
                self.pos += 3

        # GS ! n - Select character size
        elif cmd == ord('!'):
            self.pos += 3

        # GS B n - Turn white/black reverse print mode
        elif cmd == ord('B'):
            self.pos += 3

        # GS L - Set left margin
        elif cmd == ord('L'):
            self.pos += 4

        # GS W - Set print area width
        elif cmd == ord('W'):
            self.pos += 4

        # GS k - Print barcode
        elif cmd == ord('k'):
            self._skip_barcode()

        # GS ( L - Graphics commands
        elif cmd == ord('('):
            self._skip_graphics_command()

        # GS * - Define downloaded bit image
        elif cmd == ord('*'):
            self._skip_define_image()

        # Unknown - skip 2 bytes
        else:
            self.pos += 2

    def _parse_raster_image(self):
        """Parse GS v 0 raster image command"""
        # Check for GS v 0 (1D 76 30) or GS v (1D 76)
        if self.pos + 2 >= len(self.data):
            self.pos += 2
            return

        offset = self.pos

        # Check if it's GS v 0 (three-byte command) or GS v (two-byte)
        if self.data[self.pos + 2] == 0x30 or self.data[self.pos + 2] == ord('0'):
            # GS v 0 format: 1D 76 30 m xL xH yL yH d1...dk
            if self.pos + 8 > len(self.data):
                self.pos += 3
                return

            m = self.data[self.pos + 3]
            xL = self.data[self.pos + 4]
            xH = self.data[self.pos + 5]
            yL = self.data[self.pos + 6]
            yH = self.data[self.pos + 7]
            header_size = 8
        else:
            # GS v format: 1D 76 m xL xH yL yH d1...dk
            if self.pos + 7 > len(self.data):
                self.pos += 2
                return

            m = self.data[self.pos + 2]
            xL = self.data[self.pos + 3]
            xH = self.data[self.pos + 4]
            yL = self.data[self.pos + 5]
            yH = self.data[self.pos + 6]
            header_size = 7

        # Width in bytes, height in dots
        width_bytes = xL + xH * 256
        height_dots = yL + yH * 256

        # Sanity check
        if width_bytes <= 0 or width_bytes > 1000 or height_dots <= 0 or height_dots > 10000:
            logger.warning(f"Invalid image dimensions: {width_bytes}x{height_dots} at pos {self.pos}")
            self.pos += header_size
            return

        # Width in pixels (8 bits per byte)
        width_pixels = width_bytes * 8

        # Image data size
        data_size = width_bytes * height_dots

        if self.pos + header_size + data_size > len(self.data):
            # Use available data
            available = len(self.data) - self.pos - header_size
            if available > 0:
                logger.info(f"Raster image using available data: {available} of {data_size} bytes")
                data_size = available
            else:
                logger.warning(f"Raster image data truncated at pos {self.pos}")
                self.pos += header_size
                return

        image_data = self.data[self.pos + header_size:self.pos + header_size + data_size]

        image = ESCPOSImage(
            width=width_pixels,
            height=height_dots,
            data=image_data,
            offset=offset
        )
        self.images.append(image)

        logger.info(f"Found raster image: {width_pixels}x{height_dots} pixels at offset {offset}")

        self.pos += header_size + data_size

    def _skip_barcode(self):
        """Skip barcode command"""
        if self.pos + 3 >= len(self.data):
            self.pos += 2
            return

        m = self.data[self.pos + 2]

        if 0 <= m <= 6:
            # Format 1: data ends with NUL
            self.pos += 3
            while self.pos < len(self.data) and self.data[self.pos] != 0:
                self.pos += 1
            self.pos += 1
        elif 65 <= m <= 73:
            # Format 2: length specified
            if self.pos + 3 < len(self.data):
                n = self.data[self.pos + 3]
                self.pos += 4 + n
            else:
                self.pos += 3
        else:
            self.pos += 3

    def _skip_graphics_command(self):
        """Skip GS ( L graphics command"""
        if self.pos + 5 >= len(self.data):
            self.pos += 2
            return

        # GS ( L pL pH m fn ...
        pL = self.data[self.pos + 2]
        pH = self.data[self.pos + 3]
        param_size = pL + pH * 256

        self.pos += 4 + param_size

    def _skip_define_image(self):
        """Skip GS * define image command"""
        if self.pos + 4 >= len(self.data):
            self.pos += 2
            return

        x = self.data[self.pos + 2]
        y = self.data[self.pos + 3]
        data_size = x * y * 8

        self.pos += 4 + data_size


def raster_to_png(image: ESCPOSImage) -> bytes:
    """
    Convert ESC/POS raster image to PNG

    Args:
        image: ESCPOSImage object

    Returns:
        PNG image data as bytes
    """
    try:
        from PIL import Image
        import io

        # Create image from bitmap data
        # ESC/POS uses 1 bit per pixel, MSB first
        img = Image.new('1', (image.width, image.height), 1)  # White background
        pixels = img.load()

        byte_idx = 0
        for y in range(image.height):
            for x_byte in range(image.width // 8):
                if byte_idx < len(image.data):
                    byte = image.data[byte_idx]
                    for bit in range(8):
                        x = x_byte * 8 + bit
                        # MSB first, 1 = black, 0 = white (inverted for PIL)
                        pixel = (byte >> (7 - bit)) & 1
                        if x < image.width:
                            pixels[x, y] = 1 - pixel  # Invert: 1->0 (black), 0->1 (white)
                    byte_idx += 1

        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    except ImportError:
        logger.warning("PIL not available, cannot convert to PNG")
        return b''


def raster_to_pdf(images: List[ESCPOSImage], output_path: str) -> bool:
    """
    Convert ESC/POS raster images to PDF

    Args:
        images: List of ESCPOSImage objects
        output_path: Output PDF file path

    Returns:
        True if successful
    """
    try:
        from PIL import Image
        import io

        if not images:
            return False

        pil_images = []

        for img in images:
            # Create PIL image
            pil_img = Image.new('1', (img.width, img.height), 1)
            pixels = pil_img.load()

            byte_idx = 0
            for y in range(img.height):
                for x_byte in range(img.width // 8):
                    if byte_idx < len(img.data):
                        byte = img.data[byte_idx]
                        for bit in range(8):
                            x = x_byte * 8 + bit
                            pixel = (byte >> (7 - bit)) & 1
                            if x < img.width:
                                pixels[x, y] = 1 - pixel
                        byte_idx += 1

            # Convert to RGB for PDF
            pil_img = pil_img.convert('RGB')
            pil_images.append(pil_img)

        if pil_images:
            # Save as PDF (first image, append rest)
            pil_images[0].save(
                output_path,
                'PDF',
                save_all=True,
                append_images=pil_images[1:] if len(pil_images) > 1 else []
            )
            return True

    except ImportError:
        logger.warning("PIL not available, cannot create PDF")
    except Exception as e:
        logger.error(f"Error creating PDF: {e}")

    return False


def parse_escpos(data: bytes) -> Tuple[str, List[ESCPOSImage]]:
    """
    Convenience function to parse ESC/POS data

    Args:
        data: Raw ESC/POS data

    Returns:
        Tuple of (text_content, images)
    """
    parser = ESCPOSParser(data)
    return parser.parse()
