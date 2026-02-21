from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
import io
import struct
import zlib
import math

# ── GIF builder (no external libs needed) ─────────────────────────────────────

def lzw_compress(data, min_code_size):
    """Minimal LZW compression for GIF."""
    clear = 1 << min_code_size
    eoi = clear + 1
    code_size = min_code_size + 1
    codes = {(i,): i for i in range(clear)}
    output_bits = []

    def emit(code):
        for i in range(code_size):
            output_bits.append((code >> i) & 1)

    emit(clear)
    buffer = ()
    for byte in data:
        extended = buffer + (byte,)
        if extended in codes:
            buffer = extended
        else:
            emit(codes[buffer])
            codes[extended] = len(codes) + 2
            if len(codes) + 2 > (1 << code_size) and code_size < 12:
                code_size += 1
            buffer = (byte,)
    if buffer:
        emit(codes[buffer])
    emit(eoi)

    # Pack bits into bytes
    result = []
    for i in range(0, len(output_bits), 8):
        byte = 0
        for j, bit in enumerate(output_bits[i:i+8]):
            byte |= bit << j
        result.append(byte)
    return bytes(result)


def pack_sub_blocks(data):
    out = bytearray()
    for i in range(0, len(data), 255):
        chunk = data[i:i+255]
        out.append(len(chunk))
        out.extend(chunk)
    out.append(0)
    return bytes(out)


def make_gif(frames, width, height, palette):
    """
    frames: list of (pixel_index_array, delay_cs)  delay in centiseconds
    palette: list of (r,g,b) tuples, must be power-of-2 length
    """
    n_colors = len(palette)
    color_table_size = int(math.log2(n_colors)) - 1

    out = bytearray()

    # Header
    out += b'GIF89a'
    # Logical screen descriptor
    out += struct.pack('<H', width)
    out += struct.pack('<H', height)
    gct_flag = 1
    color_res = 7
    sort_flag = 0
    packed = (gct_flag << 7) | (color_res << 4) | (sort_flag << 3) | color_table_size
    out += bytes([packed, 0, 0])  # packed, bg color index, pixel aspect ratio
    # Global color table
    for r, g, b in palette:
        out += bytes([r, g, b])

    # Netscape looping extension
    out += bytes([0x21, 0xFF, 0x0B])
    out += b'NETSCAPE2.0'
    out += bytes([3, 1, 0, 0, 0])  # loop forever

    min_code_size = max(2, int(math.log2(n_colors)))

    for pixels, delay_cs in frames:
        # Graphic control extension
        out += bytes([0x21, 0xF9, 0x04])
        out += bytes([0x00, delay_cs & 0xFF, (delay_cs >> 8) & 0xFF, 0, 0])

        # Image descriptor
        out += bytes([0x2C])
        out += struct.pack('<HHHHB', 0, 0, width, height, 0)

        # Image data
        compressed = lzw_compress(pixels, min_code_size)
        out += bytes([min_code_size])
        out += pack_sub_blocks(compressed)

    out += bytes([0x3B])  # Trailer
    return bytes(out)


# ── Drawing helpers ────────────────────────────────────────────────────────────

def draw_rect(pixels, width, x, y, w, h, color_idx):
    for row in range(y, y + h):
        for col in range(x, x + w):
            if 0 <= row < len(pixels) // width and 0 <= col < width:
                pixels[row * width + col] = color_idx


def draw_char(pixels, width, cx, cy, char, color_idx, scale=1):
    """Draw a character using a 5x7 bitmap font."""
    FONT = {
        '0': [0x1F, 0x11, 0x11, 0x11, 0x1F],
        '1': [0x00, 0x12, 0x1F, 0x10, 0x00],
        '2': [0x19, 0x15, 0x15, 0x15, 0x17],
        '3': [0x11, 0x15, 0x15, 0x15, 0x1F],
        '4': [0x07, 0x04, 0x04, 0x04, 0x1F],
        '5': [0x17, 0x15, 0x15, 0x15, 0x1D],
        '6': [0x1F, 0x15, 0x15, 0x15, 0x1D],
        '7': [0x01, 0x01, 0x1D, 0x05, 0x03],
        '8': [0x1F, 0x15, 0x15, 0x15, 0x1F],
        '9': [0x17, 0x15, 0x15, 0x15, 0x1F],
        ':': [0x00, 0x0A, 0x00, 0x0A, 0x00],
        'D': [0x1F, 0x11, 0x11, 0x11, 0x0E],
        'H': [0x1F, 0x04, 0x04, 0x04, 0x1F],
        'M': [0x1F, 0x02, 0x04, 0x02, 0x1F],
        'S': [0x17, 0x15, 0x15, 0x15, 0x1D],
        'd': [0x1F, 0x11, 0x11, 0x11, 0x0E],
        'h': [0x1F, 0x04, 0x04, 0x04, 0x1B],
        'm': [0x1F, 0x02, 0x06, 0x02, 0x1F],
        's': [0x17, 0x15, 0x15, 0x15, 0x1D],
        ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
    }
    if char not in FONT:
        return
    bitmap = FONT[char]
    for row in range(7):
        for col in range(5):
            bit = (bitmap[col] >> (6 - row)) & 1 if row < 7 else 0
            # Use 5-column bitmaps stored as column vectors
            if col < len(bitmap):
                bit = (bitmap[col] >> row) & 1
            if bit:
                for sy in range(scale):
                    for sx in range(scale):
                        px = cx + col * scale + sx
                        py = cy + row * scale + sy
                        if 0 <= py < len(pixels) // width and 0 <= px < width:
                            pixels[py * width + px] = color_idx


def draw_text(pixels, width, x, y, text, color_idx, scale=2):
    char_w = 5 * scale + scale
    for i, ch in enumerate(text):
        draw_char(pixels, width, x + i * char_w, y, ch, color_idx, scale)
    return x + len(text) * char_w


def text_width(text, scale=2):
    return len(text) * (5 * scale + scale)


# ── Frame generation ───────────────────────────────────────────────────────────

# Color palette indices
IDX_BG      = 0
IDX_FG      = 1
IDX_LABEL   = 2
IDX_BOX_BG  = 3
IDX_BOX_BDR = 4
IDX_EXPIRED = 5

def build_palette(bg, fg, label, box_bg, box_bdr, expired):
    palette = [bg, fg, label, box_bg, box_bdr, expired]
    # Pad to 8 entries (next power of 2)
    while len(palette) < 8:
        palette.append((0, 0, 0))
    return palette


def make_frame(seconds_left, width=320, height=90,
               bg=(30, 30, 30), fg=(255, 255, 255),
               label=(180, 180, 180), box_bg=(50, 50, 50),
               box_bdr=(255, 80, 80), expired=(255, 80, 80)):

    palette = build_palette(bg, fg, label, box_bg, box_bdr, expired)
    pixels = bytearray([IDX_BG] * (width * height))

    if seconds_left <= 0:
        # Expired frame
        msg = "OFFER EXPIRED"
        tw = text_width(msg, scale=2)
        tx = (width - tw) // 2
        ty = (height - 14) // 2
        draw_text(pixels, width, tx, ty, msg, IDX_EXPIRED, scale=2)
        return bytes(pixels), palette

    days    = seconds_left // 86400
    hours   = (seconds_left % 86400) // 3600
    minutes = (seconds_left % 3600) // 60
    secs    = seconds_left % 60

    units = [
        (f"{days:02d}",  "DAYS"),
        (f"{hours:02d}", "HRS"),
        (f"{minutes:02d}", "MIN"),
        (f"{secs:02d}",  "SEC"),
    ]

    box_w = 68
    box_h = 70
    gap   = 8
    total_w = 4 * box_w + 3 * gap
    start_x = (width - total_w) // 2
    start_y = (height - box_h) // 2

    for i, (num, lbl) in enumerate(units):
        bx = start_x + i * (box_w + gap)
        by = start_y

        # Box background
        draw_rect(pixels, width, bx, by, box_w, box_h, IDX_BOX_BG)
        # Border (2px)
        for t in range(2):
            draw_rect(pixels, width, bx + t, by + t, box_w - 2*t, 1, IDX_BOX_BDR)
            draw_rect(pixels, width, bx + t, by + box_h - 1 - t, box_w - 2*t, 1, IDX_BOX_BDR)
            draw_rect(pixels, width, bx + t, by + t, 1, box_h - 2*t, IDX_BOX_BDR)
            draw_rect(pixels, width, bx + box_w - 1 - t, by + t, 1, box_h - 2*t, IDX_BOX_BDR)

        # Number (scale=3 → each char ~18px wide)
        nw = text_width(num, scale=3)
        nx = bx + (box_w - nw) // 2
        draw_text(pixels, width, nx, by + 8, num, IDX_FG, scale=3)

        # Label
        lw = text_width(lbl, scale=1)
        lx = bx + (box_w - lw) // 2
        draw_text(pixels, width, lx, by + box_h - 16, lbl, IDX_LABEL, scale=1)

    return bytes(pixels), palette


# ── Request handler ────────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # --- Parse end date ---
        end_str = params.get('end', [None])[0]
        if not end_str:
            self.send_error(400, "Missing ?end= parameter (ISO format e.g. 2026-03-01T18:00:00)")
            return

        try:
            end_dt = datetime.fromisoformat(end_str)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            self.send_error(400, "Invalid date format. Use ISO 8601 e.g. 2026-03-01T18:00:00+05:30")
            return

        # --- Parse colors ---
        def hex_to_rgb(h, default):
            try:
                h = h.lstrip('#')
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            except:
                return default

        bg      = hex_to_rgb(params.get('bg',  ['1e1e1e'])[0], (30, 30, 30))
        fg      = hex_to_rgb(params.get('fg',  ['ffffff'])[0], (255, 255, 255))
        label   = hex_to_rgb(params.get('label', ['b4b4b4'])[0], (180, 180, 180))
        box_bg  = hex_to_rgb(params.get('box',  ['323232'])[0], (50, 50, 50))
        accent  = hex_to_rgb(params.get('accent', ['ff5050'])[0], (255, 80, 80))

        # --- Recipient timezone offset ---
        # Pass ?tz=+05:30 or ?tz=-05:00 or ?tz=330 (minutes)
        tz_param = params.get('tz', ['0'])[0]
        offset_minutes = 0
        try:
            if ':' in tz_param:
                sign = -1 if tz_param.startswith('-') else 1
                parts = tz_param.lstrip('+-').split(':')
                offset_minutes = sign * (int(parts[0]) * 60 + int(parts[1]))
            else:
                offset_minutes = int(tz_param)
        except:
            offset_minutes = 0

        from datetime import timedelta
        recipient_tz = timezone(timedelta(minutes=offset_minutes))
        now = datetime.now(tz=recipient_tz)
        end_local = end_dt.astimezone(recipient_tz)
        seconds_left = max(0, int((end_local - now).total_seconds()))

        # --- Build animated GIF (animate last 60s smoothly, else just show current) ---
        W, H = 320, 90

        # Generate frames: show current second + animate for 1 second
        frames = []
        for tick in range(10):  # 10 frames per second display
            s = max(0, seconds_left - (tick // 10))
            pix, pal = make_frame(s, W, H, bg, fg, label, box_bg, accent, accent)
            frames.append((pix, 10))  # 10 centiseconds = 0.1s

        gif_data = make_gif(frames, W, H, pal)

        self.send_response(200)
        self.send_header('Content-Type', 'image/gif')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.end_headers()
        self.wfile.write(gif_data)

    def log_message(self, format, *args):
        pass
