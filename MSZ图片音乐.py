#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSZ 图片音乐 (MSZ Picture Music) v1.0

两种模式：
  模式一  MIDI -> 图片：导入 .mid，自动生成一张“钢琴卷帘图”，
                       整个 MIDI 原文件完整藏进图片里（无损）。
  模式二  图片 -> 播放：导入那张图，自动提取 MIDI 并直接播放音乐。

纯标准库实现：自写 MIDI 解析、PNG 编解码、像素级数据封装、winmm MIDI 输出。
不依赖 mido / Pillow / pygame / numpy，装个 Python 就能跑。
"""

import os
import sys
import json
import zlib
import struct
import math
import time
import threading

APP_NAME = 'MSZ 图片音乐'
APP_VER = '1.0'

# ======================= 版式常量（生成图与播放头共用） =======================
IMG_W = 1440               # 固定宽度，保证播放头刻度稳定
MARGIN_L = 48
MARGIN_R = 48
HEADER_H = 136
FOOTER_H = 88
PITCH_LO = 21              # A0
PITCH_HI = 108             # C8
ROW_H = 7                  # 每个半音的默认像素高度
IMG_MAX_H = 4096

# 深色底 + 琥珀/青绿点缀，不用紫
BG_TOP = (13, 17, 22)
BG_BOT = (24, 31, 37)
ROLL_BG = (16, 20, 25)
ROW_WHITE = (22, 27, 33)
ROW_BLACK = (12, 15, 19)
GRID_BEAT = (30, 37, 44)
GRID_BAR = (44, 54, 63)
TEXT_MAIN = (232, 238, 244)
TEXT_DIM = (128, 142, 156)
ACCENT = (236, 178, 86)
ACCENT2 = (72, 190, 178)

TRACK_COLORS = [
    (64, 196, 182),   # 青绿
    (240, 184, 88),   # 琥珀
    (232, 118, 100),  # 珊瑚
    (96, 168, 232),   # 蓝
    (150, 206, 118),  # 草绿
    (226, 142, 178),  # 玫瑰
]


# ======================= 5x7 点阵字体（只画图内英文标签） =======================
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "01110"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "01110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'E': ("11111", "10000", "11110", "10000", "11110", "10000", "11111"),
    'F': ("11111", "10000", "11110", "10000", "11110", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10101", "10101", "10011", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10110", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10101", "10101", "10101", "01010", "00100"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "01010", "10001"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    '0': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    '3': ("01110", "10001", "00001", "00110", "00001", "10001", "01110"),
    '4': ("00011", "00101", "01001", "11111", "00001", "00010", "00100"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("00110", "01001", "10001", "11111", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "01000", "10000", "10000"),
    '8': ("01110", "10001", "01110", "10001", "01110", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ':': ("00000", "00100", "00000", "00100", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    '-': ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    '/': ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '?': ("01110", "10001", "00001", "00010", "00010", "00000", "01110"),
}


def text_width(s, scale, gap=1):
    if not s:
        return 0
    return (len(s) * 5 + (len(s) - 1) * gap) * scale


def draw_text(pix, W, H, x, y, s, scale, color, gap=1):
    """在 RGB 缓冲上画 5x7 点阵文字，越界自动裁掉。"""
    pen = x
    for ch in s.upper():
        glyph = FONT.get(ch, FONT['?'])
        for ry, row in enumerate(glyph):
            for rx, c in enumerate(row):
                if c != '1':
                    continue
                px = pen + rx * scale
                py = y + ry * scale
                if px < 0 or py < 0 or px + scale > W or py + scale > H:
                    continue
                for dy in range(scale):
                    base = ((py + dy) * W + px) * 3
                    for dx in range(scale):
                        o = base + dx * 3
                        pix[o] = color[0]
                        pix[o + 1] = color[1]
                        pix[o + 2] = color[2]
        pen += (5 + gap) * scale


# ======================= PNG 编码 / 解码（纯标准库） =======================
def _chunk(tag, data):
    return (struct.pack('>I', len(data)) + tag + data +
            struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))


def png_write(path, w, h, pix, extra=()):
    """写 8 位真彩色 PNG；extra 为附加 chunk 列表 [(tag, bytes)]。"""
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    stride = w * 3
    raw = bytearray()
    prev = None
    for y in range(h):
        base = y * stride
        row = bytes(pix[base:base + stride])
        if prev is None:
            raw += b'\x00'
            raw += row
        else:
            raw += b'\x02'          # Up 过滤：逐行差分，梯度背景压得更小
            raw += bytes(((row[i] - prev[i]) & 0xFF) for i in range(stride))
        prev = row
    out = b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', ihdr)
    for tag, data in extra:
        out += _chunk(tag, data)
    out += _chunk(b'IDAT', zlib.compress(bytes(raw), 6))
    out += _chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(out)


def png_read(path):
    """读 PNG，返回 (w, h, rgb_bytearray, chunks)。chunks 为 [(tag, bytes)]。"""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('这不是 PNG 图片。JPG 是有损压缩，会把藏在图里的音乐数据压坏，'
                         '所以本程序只认 PNG。')
    pos = 8
    idat = bytearray()
    ihdr = None
    plte = None
    chunks = []
    while pos + 8 <= len(data):
        ln = int.from_bytes(data[pos:pos + 4], 'big')
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b'IHDR':
            ihdr = body
        elif tag == b'PLTE':
            plte = body
        elif tag == b'IDAT':
            idat += body
        elif tag == b'IEND':
            break
        else:
            chunks.append((tag, body))
    if ihdr is None:
        raise ValueError('PNG 头缺失，文件可能已损坏')
    w, h, depth, ctype, comp, filt, inter = struct.unpack('>IIBBBBB', ihdr[:13])
    if inter:
        raise ValueError('不支持隔行扫描（Adam7）的 PNG，请用普通 PNG')
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if nch is None:
        raise ValueError('不认识的 PNG 颜色类型 ' + str(ctype))
    bits_pp = nch * depth
    bpp = max(1, bits_pp // 8)
    stride = (w * bits_pp + 7) // 8
    raw = zlib.decompress(bytes(idat))
    if len(raw) < h * (stride + 1):
        raise ValueError('PNG 数据不完整')
    recon = bytearray(h * stride)
    p = 0
    prevrow = bytearray(stride)
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prevrow[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prevrow[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prevrow[i]
                c = prevrow[i - bpp] if i >= bpp else 0
                pa = abs(b - c)
                pb = abs(a - c)
                pc = abs(a + b - c - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise ValueError('PNG 行过滤类型异常 ' + str(ft))
        prevrow = line
        recon[y * stride:(y + 1) * stride] = line

    pix = bytearray(w * h * 3)

    def put(i, r, g, b):
        pix[i * 3] = r
        pix[i * 3 + 1] = g
        pix[i * 3 + 2] = b

    if depth == 8:
        if ctype == 2:
            pix[:] = recon
        elif ctype == 6:
            for i in range(w * h):
                s4 = i * 4
                put(i, recon[s4], recon[s4 + 1], recon[s4 + 2])
        elif ctype == 4:
            for i in range(w * h):
                v = recon[i * 2]
                put(i, v, v, v)
        elif ctype == 0:
            for i in range(w * h):
                v = recon[i]
                put(i, v, v, v)
        elif ctype == 3:
            if plte is None:
                raise ValueError('PNG 调色板缺失')
            for i in range(w * h):
                idx = recon[i]
                if idx * 3 + 2 < len(plte):
                    put(i, plte[idx * 3], plte[idx * 3 + 1], plte[idx * 3 + 2])
        return w, h, pix, chunks

    if depth == 16:
        # 16 位：取每个通道的高字节
        for i in range(w * h):
            s16 = i * nch * 2
            if ctype in (2, 6):
                put(i, recon[s16], recon[s16 + 2], recon[s16 + 4])
            else:
                v = recon[s16]
                put(i, v, v, v)
        return w, h, pix, chunks

    # 1/2/4 位：按位拆开（老工具存的调色板图常见）
    maxv = (1 << depth) - 1
    for y in range(h):
        base = y * stride
        for x in range(w):
            bit_off = x * depth
            byte_i = base + (bit_off >> 3)
            shift = 8 - depth - (bit_off & 7)
            v = (recon[byte_i] >> shift) & maxv
            i = y * w + x
            if ctype == 3:
                if plte is not None and v * 3 + 2 < len(plte):
                    put(i, plte[v * 3], plte[v * 3 + 1], plte[v * 3 + 2])
            else:
                g = v * 255 // maxv
                put(i, g, g, g)
    return w, h, pix, chunks


# ======================= 数据封装（LSB 像素藏数据） =======================
PAYLOAD_MAGIC = b'MSZPMv1\0'
CHUNK_META = b'msZm'   # 附加块：曲目信息（PNG 块类型必须恰好 4 个字母）
CHUNK_DATA = b'msZd'   # 附加块：原始 MIDI 字节


def build_payload(midi_bytes):
    return (PAYLOAD_MAGIC + struct.pack('>I', len(midi_bytes)) + midi_bytes +
            struct.pack('>I', zlib.crc32(midi_bytes) & 0xFFFFFFFF))


def payload_capacity(w, h):
    return (w * h * 3) // 8      # 每像素 3 个通道各藏 1 位


def lsb_embed(pix, payload):
    need = len(payload) * 8
    if need > len(pix):
        raise ValueError('图片容量不足，藏不下这首 MIDI')
    off = 0
    for byte in payload:
        for k in range(7, -1, -1):
            pix[off] = (pix[off] & 0xFE) | ((byte >> k) & 1)
            off += 1


def _extract_bytes(pix, start_byte, n):
    out = bytearray()
    for i in range(n):
        base = (start_byte + i) * 8
        b = 0
        for k in range(8):
            b = (b << 1) | (pix[base + k] & 1)
        out.append(b)
    return bytes(out)


def lsb_extract(pix):
    if len(pix) < len(PAYLOAD_MAGIC) * 8:
        return None
    if _extract_bytes(pix, 0, len(PAYLOAD_MAGIC)) != PAYLOAD_MAGIC:
        return None
    n = struct.unpack('>I', _extract_bytes(pix, len(PAYLOAD_MAGIC), 4))[0]
    total = len(PAYLOAD_MAGIC) + 4 + n + 4
    if total * 8 > len(pix) or n > 32 * 1024 * 1024:
        return None
    midi = _extract_bytes(pix, len(PAYLOAD_MAGIC) + 4, n)
    crc = struct.unpack('>I', _extract_bytes(pix, len(PAYLOAD_MAGIC) + 4 + n, 4))[0]
    if crc != (zlib.crc32(midi) & 0xFFFFFFFF):
        return None
    return midi


# ======================= MIDI 解析 =======================
def _vlq(buf, i):
    v = 0
    for _ in range(4):
        b = buf[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return v, i


def _parse_track(body):
    """返回 {'name': str, 'events': [(tick, kind, ch_or_us, note_or_val, vel)]}"""
    name = ''
    events = []
    i = 0
    tick = 0
    status = 0
    n = len(body)
    while i < n:
        delta, i = _vlq(body, i)
        tick += delta
        if i >= n:
            break
        b = body[i]
        if b == 0xFF:
            i += 1
            if i >= n:
                break
            mtype = body[i]
            i += 1
            ln, i = _vlq(body, i)
            payload = body[i:i + ln]
            i += ln
            if mtype == 0x51 and ln >= 3:
                events.append((tick, 'tempo', int.from_bytes(payload[:3], 'big'), 0, 0))
            elif mtype == 0x03:
                try:
                    name = payload.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        name = payload.decode('gbk')
                    except UnicodeDecodeError:
                        name = payload.decode('latin-1', 'ignore')
            continue
        if b in (0xF0, 0xF7):
            i += 1
            ln, i = _vlq(body, i)
            i += ln
            continue
        if b & 0x80:
            status = b
            i += 1
        elif status == 0:
            i += 1
            continue
        hi = status & 0xF0
        ch = status & 0x0F
        if hi in (0x80, 0x90):
            if i + 1 >= n:
                break
            note = body[i]
            vel = body[i + 1]
            i += 2
            if hi == 0x90 and vel > 0:
                events.append((tick, 'on', ch, note, vel))
            else:
                events.append((tick, 'off', ch, note, 0))
        elif hi in (0xA0, 0xB0, 0xE0):
            i += 2
        elif hi in (0xC0, 0xD0):
            if i >= n:
                break
            val = body[i]
            i += 1
            if hi == 0xC0:
                events.append((tick, 'prog', ch, val, 0))
    return {'name': name, 'events': events}


def parse_midi(data):
    if len(data) < 14 or data[:4] != b'MThd':
        raise ValueError('这不是 MIDI 文件（缺少 MThd 头）')
    hlen = int.from_bytes(data[4:8], 'big')
    fmt = int.from_bytes(data[8:10], 'big')
    ntrk = int.from_bytes(data[10:12], 'big')
    div = int.from_bytes(data[12:14], 'big')
    pos = 8 + hlen
    tracks = []
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        clen = int.from_bytes(data[pos + 4:pos + 8], 'big')
        body = data[pos + 8:pos + 8 + clen]
        pos += 8 + clen
        if cid == b'MTrk':
            tracks.append(_parse_track(body))
    if not tracks:
        raise ValueError('MIDI 里没有轨道数据')
    return {'format': fmt, 'ntrk': ntrk, 'division': div, 'tracks': tracks}


def build_performance(mid):
    """把 MIDI 拍成时间轴：音符、总时长、每通道音色。"""
    div = mid['division']
    smpte = bool(div & 0x8000)
    if smpte:
        fps = 256 - (div >> 8)
        tpf = div & 0xFF or 1
        sec_per_tick = 1.0 / float(fps * tpf)

        def sec_at(tick):
            return tick * sec_per_tick
    else:
        tempos = []
        for tr in mid['tracks']:
            for ev in tr['events']:
                if ev[1] == 'tempo':
                    tempos.append((ev[0], ev[2]))
        tempos.sort()
        if not tempos or tempos[0][0] != 0:
            tempos.insert(0, (0, 500000))
        segs = []
        sec = 0.0
        pt = 0
        us = 500000
        for tick, u in tempos:
            if tick < pt:
                continue
            sec += (tick - pt) * us / float(div) / 1e6
            segs.append((tick, sec, u))
            pt = tick
            us = u
        seg_ticks = [s[0] for s in segs]

        def sec_at(tick):
            # 二分找到最后一个起点 <= tick 的段落
            lo, hi = 0, len(segs) - 1
            while lo < hi:
                mid_i = (lo + hi + 1) // 2
                if segs[mid_i][0] <= tick:
                    lo = mid_i
                else:
                    hi = mid_i - 1
            t0, s0, u = segs[lo]
            return s0 + (tick - t0) * u / float(div) / 1e6

    notes = []
    programs = {}
    last_tick = 0
    used_tracks = 0
    for tr in mid['tracks']:
        open_notes = {}
        for ev in tr['events']:
            tick, kind, a, b, c = ev
            last_tick = max(last_tick, tick)
            if kind == 'on':
                open_notes[(a, b)] = (tick, c)
            elif kind == 'off':
                key = (a, b)
                if key in open_notes:
                    t0, vel = open_notes.pop(key)
                    notes.append((sec_at(t0), sec_at(tick), b, vel, a))
            elif kind == 'prog':
                programs.setdefault(a, b)
        if tr['events']:
            if any(ev[1] == 'on' for ev in tr['events']):
                used_tracks += 1
        for (ch, pitch), (t0, vel) in open_notes.items():
            notes.append((sec_at(t0), sec_at(last_tick) + 0.02, pitch, vel, ch))
    notes.sort(key=lambda n: n[0])
    duration = 0.0
    for nt in notes:
        duration = max(duration, nt[1])
    if duration <= 0:
        duration = 1.0
    names = [tr['name'] for tr in mid['tracks'] if tr['name'].strip()]
    beats = (last_tick / float(div)) if (div > 0 and not smpte) else duration * 2.0
    return {
        'notes': notes,
        'duration': duration,
        'beats': beats,
        'programs': programs,
        'names': names,
        'channels': len(set(n[4] for n in notes)),
        'tracks': max(1, used_tracks),
    }


# ======================= 钢琴卷帘图渲染 =======================
BLACK_KEYS = {1, 3, 6, 8, 10}


def _mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def render_image(perf, title, payload, midi_size):
    # 按实际用到的音域裁出画面，别让大半张图空着
    pitches = [n[2] for n in perf['notes']] or [60]
    lo = max(PITCH_LO, min(pitches) - 3)
    hi = min(PITCH_HI, max(pitches) + 3)
    if hi - lo < 32:
        mid = (lo + hi) // 2
        lo = max(PITCH_LO, mid - 16)
        hi = min(PITCH_HI, lo + 32)
    rows = hi - lo + 1
    h = HEADER_H + rows * ROW_H + FOOTER_H
    need_bits = len(payload) * 8
    while h * IMG_W * 3 < need_bits:
        h += 96
        if h > IMG_MAX_H:
            raise ValueError('这首 MIDI 太大（%d 字节），图片装不下，请换短一点的曲子' % midi_size)
    w = IMG_W
    roll_h = h - HEADER_H - FOOTER_H
    row_h = roll_h / float(rows)

    pix = bytearray(w * h * 3)
    # 背景竖向渐变
    for y in range(h):
        col = _mix(BG_TOP, BG_BOT, y / float(h - 1))
        base = y * w * 3
        for x in range(w):
            o = base + x * 3
            pix[o] = col[0]
            pix[o + 1] = col[1]
            pix[o + 2] = col[2]

    # 钢琴键底色（黑白键斑马纹）
    for idx in range(rows):
        pitch = hi - idx
        y0 = HEADER_H + int(idx * row_h)
        y1 = HEADER_H + int((idx + 1) * row_h)
        dark = (pitch % 12) in BLACK_KEYS
        col = ROW_BLACK if dark else ROW_WHITE
        key = (132, 142, 154) if not dark else (34, 40, 48)
        key_w = (MARGIN_L - 22) if not dark else (MARGIN_L - 40)
        for y in range(max(0, y0), min(h, y1)):
            base = y * w * 3
            for x in range(MARGIN_L, w - MARGIN_R):
                o = base + x * 3
                pix[o] = col[0]
                pix[o + 1] = col[1]
                pix[o + 2] = col[2]
            for x in range(12, 12 + key_w):
                o = base + x * 3
                pix[o] = key[0]
                pix[o + 1] = key[1]
                pix[o + 2] = key[2]

    dur = perf['duration'] if perf['duration'] > 0 else 1.0
    plot_w = w - MARGIN_L - MARGIN_R

    def xt(t):
        return MARGIN_L + int(plot_w * min(1.0, t / dur))

    # 小节 / 拍网格
    beats = perf.get('beats', dur * 2.0)
    if beats > 0:
        step_beats = 4 if beats > 64 else (2 if beats > 24 else 1)
        b = 0
        while b <= beats + 0.01:
            x = MARGIN_L + int(plot_w * min(1.0, b / beats))
            strong = abs(b % 4) < 1e-6
            col = GRID_BAR if strong else GRID_BEAT
            for y in range(HEADER_H, h - FOOTER_H):
                o = (y * w + x) * 3
                if 0 <= o < len(pix) - 3:
                    pix[o] = col[0]
                    pix[o + 1] = col[1]
                    pix[o + 2] = col[2]
            b += step_beats

    # 音符条
    for t0, t1, pitch, vel, ch in perf['notes']:
        if pitch < lo or pitch > hi:
            continue
        idx = hi - pitch
        y0 = HEADER_H + int(idx * row_h) + 1
        y1 = HEADER_H + int((idx + 1) * row_h) - 1
        if y1 <= y0:
            y1 = y0 + 1
        x0 = xt(t0)
        x1 = xt(t1)
        if x1 <= x0:
            x1 = x0 + 2
        base_col = TRACK_COLORS[ch % len(TRACK_COLORS)]
        col = _mix(base_col, (255, 255, 255), 0.10 + 0.45 * (vel / 127.0))
        for y in range(max(0, y0), min(h - FOOTER_H, y1)):
            row_base = y * w * 3
            for x in range(max(0, x0), min(w, x1)):
                o = row_base + x * 3
                pix[o] = col[0]
                pix[o + 1] = col[1]
                pix[o + 2] = col[2]

    # 顶部信息区
    for y in range(HEADER_H - 10, HEADER_H):
        base = y * w * 3
        t = (y - (HEADER_H - 10)) / 10.0
        edge = _mix(ACCENT, ACCENT2, t)
        for x in range(w):
            o = base + x * 3
            pix[o] = edge[0]
            pix[o + 1] = edge[1]
            pix[o + 2] = edge[2]

    draw_text(pix, w, h, MARGIN_L, 22, 'MSZ PICTURE MUSIC', 5, TEXT_MAIN)
    draw_text(pix, w, h, MARGIN_L, 66, 'MIDI IS INSIDE THIS IMAGE', 2, ACCENT)
    mm, ss = int(dur // 60), int(dur % 60)
    info = 'NOTES %d   TIME %d:%02d   TRACKS %d' % (
        len(perf['notes']), mm, ss, max(1, perf.get('tracks', 1)))
    draw_text(pix, w, h, MARGIN_L, 92, info, 2, TEXT_DIM)
    right = '%s  V%s' % ('MSZ', APP_VER)
    draw_text(pix, w, h, w - MARGIN_R - text_width(right, 2), 92, right, 2, TEXT_DIM)

    # 底部：把藏进去的字节直接画成条码，看得见数据
    fy = h - FOOTER_H
    strip_h = 34
    nbytes = min(len(payload), w - 2 * MARGIN_L)
    for i in range(nbytes):
        v = payload[i]
        x = MARGIN_L + i
        barh = 2 + int(strip_h * (v / 255.0))
        c = _mix((40, 52, 62), ACCENT2, v / 255.0)
        for y in range(fy + 8 + strip_h - barh, fy + 8 + strip_h):
            o = (y * w + x) * 3
            pix[o] = c[0]
            pix[o + 1] = c[1]
            pix[o + 2] = c[2]
    draw_text(pix, w, h, MARGIN_L, fy + 52,
              'DATA %d BYTES EMBEDDED - KEEP THIS PNG LOSSLESS' % midi_size, 1, TEXT_DIM)
    draw_text(pix, w, h, w - MARGIN_R - text_width('PNG 8BIT RGB', 1), fy + 52,
              'PNG 8BIT RGB', 1, TEXT_DIM)
    return w, h, pix


def meta_dict(perf, title, midi_size, filename):
    return {
        'app': 'MSZ Picture Music',
        'ver': APP_VER,
        'title': title,
        'file': filename,
        'midi_bytes': midi_size,
        'duration': round(perf['duration'], 3),
        'notes': len(perf['notes']),
        'tracks': max(1, perf.get('tracks', 1)),
        'names': perf.get('names', [])[:6],
        'beats': round(perf.get('beats', 0), 2),
        'margin_l': MARGIN_L,
        'margin_r': MARGIN_R,
        'img_w': IMG_W,
        'created': time.strftime('%Y-%m-%d %H:%M:%S'),
    }


def make_picture(midi_path, out_path=None):
    """模式一主体：读 MIDI -> 画图 -> 藏数据 -> 写 PNG。返回 (图片路径, 信息字典)。"""
    with open(midi_path, 'rb') as f:
        raw = f.read()
    mid = parse_midi(raw)
    perf = build_performance(mid)
    payload = build_payload(raw)
    title = os.path.splitext(os.path.basename(midi_path))[0]
    if perf.get('names'):
        title = perf['names'][0].strip() or title
    w, h, pix = render_image(perf, title, payload, len(raw))
    if payload_capacity(w, h) >= 0 and (w * h * 3) >= len(payload) * 8:
        lsb_embed(pix, payload)
    meta = meta_dict(perf, title, len(raw), os.path.basename(midi_path))
    meta['lsb'] = True
    if out_path is None:
        base = os.path.splitext(midi_path)[0] + '_图片.png'
        out_path = base
        k = 2
        while os.path.exists(out_path):
            out_path = os.path.splitext(midi_path)[0] + '_图片(%d).png' % k
            k += 1
    extra = [
        (b'tEXt', b'Software\x00MSZ Picture Music ' + APP_VER.encode()),
        (CHUNK_META, json.dumps(meta, ensure_ascii=False).encode('utf-8')),
        (CHUNK_DATA, raw),
    ]
    png_write(out_path, w, h, pix, extra)
    return out_path, meta


def read_picture(png_path):
    """模式二主体：读图 -> 取 MIDI。返回 (midi_bytes, meta, 来源说明)。"""
    w, h, pix, chunks = png_read(png_path)
    midi = None
    meta = {}
    source = ''
    for tag, body in chunks:
        if tag == CHUNK_DATA and midi is None:
            midi = body
            source = 'PNG 数据块'
        elif tag == CHUNK_META:
            try:
                meta = json.loads(body.decode('utf-8'))
            except Exception:
                meta = {}
    if midi is None:
        lsb = lsb_extract(pix)
        if lsb is not None:
            midi = lsb
            source = '像素隐写'
    if midi is None:
        raise ValueError('这张图里没有音乐数据。\n\n'
                         '要先用「模式一 MIDI → 图片」生成，或者这张图被别的软件重新存过'
                         '（缩放、转 JPG、截图另存都会破坏）。')
    return midi, meta, source

# ======================= 声音输出（Windows 系统 MIDI 合成器） =======================
def _midi_out_open():
    """打开系统 MIDI 输出（MIDI Mapper），失败抛异常。"""
    import ctypes
    winmm = ctypes.WinDLL('winmm')
    handle = ctypes.c_void_p()
    winmm.midiOutOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint,
                                  ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint]
    winmm.midiOutOpen.restype = ctypes.c_uint
    rc = winmm.midiOutOpen(ctypes.byref(handle), ctypes.c_uint(0xFFFFFFFF), 0, 0, 0)
    if rc != 0:
        raise RuntimeError('系统没有可用的 MIDI 输出（错误码 %d）' % rc)
    winmm.midiOutShortMsg.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    winmm.midiOutClose.argtypes = [ctypes.c_void_p]
    return winmm, handle


def _send(winmm, handle, status, d1=0, d2=0):
    import ctypes
    winmm.midiOutShortMsg(handle, ctypes.c_uint(status | (d1 << 8) | (d2 << 16)))


def _sleep_until(t_target):
    while True:
        left = t_target - time.perf_counter()
        if left <= 0:
            return
        if left > 0.004:
            time.sleep(left - 0.003)
        else:
            time.sleep(0.0005)


# ======================= 界面 =======================
UI_BG = '#11151b'
UI_PANEL = '#171d25'
UI_PANEL2 = '#1e2731'
UI_TEXT = '#e8eef4'
UI_DIM = '#8a97a5'
UI_ACC = '#ecb256'
UI_ACC2 = '#48beb2'


class App:
    def __init__(self):
        import tkinter as tk
        self.tk = tk
        self.root = tk.Tk()
        self.root.title('%s  v%s' % (APP_NAME, APP_VER))
        self.root.geometry('1240x820')
        self.root.minsize(980, 660)
        self.root.configure(bg=UI_BG)

        self.mode = 1
        self.pic_path = None
        self.img_ref = None
        self.img_small = None
        self.view = {'sub': 1, 'ox': 0, 'oy': 0}
        self.perf = None
        self.midi_bytes = None
        self.meta = {}
        self.duration = 0.0
        self.stop_flag = None
        self.worker = None
        self.play_start = 0.0
        self.sound_ok = sys.platform.startswith('win')
        self.playhead = None

        self._build()
        self.set_mode(1)

    # ---------- 布局 ----------
    def _build(self):
        tk = self.tk
        head = tk.Frame(self.root, bg=UI_BG)
        head.pack(fill='x', padx=20, pady=(14, 4))

        left = tk.Frame(head, bg=UI_BG)
        left.pack(side='left')
        tk.Label(left, text=APP_NAME, bg=UI_BG, fg=UI_TEXT,
                 font=('Microsoft YaHei UI', 17, 'bold')).pack(anchor='w')
        tk.Label(left, text='MIDI 变成一张图，这张图放回来就是音乐',
                 bg=UI_BG, fg=UI_DIM, font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=(2, 0))

        self.mode_btns = []
        box = tk.Frame(head, bg=UI_BG)
        box.pack(side='right')
        for i, txt in ((1, '  模式一  MIDI → 图片  '), (2, '  模式二  图片 → 播放  ')):
            b = tk.Button(box, text=txt, command=lambda m=i: self.set_mode(m),
                          font=('Microsoft YaHei UI', 10), bd=0, relief='flat',
                          padx=14, pady=8, cursor='hand2', bg=UI_PANEL, fg=UI_DIM,
                          activebackground=UI_ACC, activeforeground='#11151b')
            b.pack(side='left', padx=6)
            self.mode_btns.append(b)

        self.canvas = tk.Canvas(self.root, bg='#0b0e12', highlightthickness=1,
                                highlightbackground='#232c37')
        self.canvas.pack(fill='both', expand=True, padx=20, pady=(10, 8))
        self.canvas.bind('<Configure>', lambda e: self._redraw())

        foot = tk.Frame(self.root, bg=UI_BG)
        foot.pack(fill='x', padx=20, pady=(0, 14))

        self.lbl_info = tk.Label(foot, text='', bg=UI_BG, fg=UI_DIM, anchor='w',
                                 justify='left', wraplength=1180,
                                 font=('Microsoft YaHei UI', 9))
        self.lbl_info.pack(fill='x', pady=(0, 8))

        row = tk.Frame(foot, bg=UI_BG)
        row.pack(fill='x')
        self.btn_import = self._btn(row, '导入文件', self.do_import, primary=True,
                                    font=('Microsoft YaHei UI', 11, 'bold'))
        self.btn_play = self._btn(row, '播放', self.play_music)
        self.btn_stop = self._btn(row, '停止', lambda: self.stop_music())
        self.btn_midi = self._btn(row, '导出 MIDI', self.save_midi)
        self.btn_folder = self._btn(row, '打开所在文件夹', self.open_folder)
        for b in (self.btn_play, self.btn_stop, self.btn_midi, self.btn_folder):
            b.configure(state='disabled')

    def _btn(self, parent, text, cmd, primary=False, font=None):
        tk = self.tk
        b = tk.Button(parent, text=text, command=cmd, bd=0, relief='flat',
                      font=font or ('Microsoft YaHei UI', 10), padx=16, pady=9,
                      cursor='hand2',
                      bg=UI_ACC if primary else UI_PANEL,
                      fg='#11151b' if primary else UI_TEXT,
                      activebackground=UI_ACC2,
                      activeforeground='#11151b',
                      disabledforeground='#4d5a67')
        b.pack(side='left', padx=(0, 8))
        return b

    def status(self, text, color=None):
        self.lbl_info.configure(text=text, fg=color or UI_DIM)

    # ---------- 模式 ----------
    def set_mode(self, m):
        self.mode = m
        self.stop_music(silent=True)
        for i, b in enumerate(self.mode_btns):
            on = (i + 1 == m)
            b.configure(bg=UI_ACC if on else UI_PANEL, fg='#11151b' if on else UI_DIM)
        if m == 1:
            self.btn_import.configure(text='①  导入 MIDI 文件')
            self.status('模式一：选一个 .mid / .midi，程序自动生成钢琴卷帘图，'
                        '整个 MIDI 原文件藏在图片里。生成后也能直接试听。')
        else:
            self.btn_import.configure(text='②  导入图片并自动播放')
            self.status('模式二：选一张由本程序生成的 PNG，程序会把它变成音乐并立即播放。'
                        'JPG 不行 —— 有损压缩会把数据压坏。')

    # ---------- 模式一 ----------
    def do_import(self):
        from tkinter import filedialog, messagebox
        if self.mode == 1:
            path = filedialog.askopenfilename(
                title='选择 MIDI 文件',
                filetypes=[('MIDI 音乐', '*.mid *.midi *.MID *.MIDI'), ('所有文件', '*.*')])
            if not path:
                return
            self.status('正在生成图片…', UI_TEXT)
            self.root.update_idletasks()
            try:
                out, meta = make_picture(path)
            except Exception as e:
                messagebox.showerror('生成失败', str(e))
                self.status('生成失败：%s' % e, '#e87a64')
                return
            self.pic_path = out
            self.meta = meta
            try:
                with open(path, 'rb') as f:
                    raw = f.read()
                mid = parse_midi(raw)
                self.perf = build_performance(mid)
            except Exception:
                self.perf = None
            self._load_image(out)
            kb = os.path.getsize(out) / 1024.0
            self.status('已生成：%s    图片 %.0f KB    曲长 %d:%02d    音符 %d 个\n'
                        '数据已无损写入这张 PNG：切到模式二导入它，就能把它变回音乐。' % (
                            out, kb,
                            int(meta['duration'] // 60), int(meta['duration'] % 60),
                            meta['notes']), UI_ACC2)
            for b in (self.btn_play, self.btn_folder):
                b.configure(state='normal')
            if self.perf:
                self.btn_midi.configure(state='normal')
        else:
            path = filedialog.askopenfilename(
                title='选择图片',
                filetypes=[('PNG 图片', '*.png *.PNG'), ('所有文件', '*.*')])
            if not path:
                return
            self.status('正在从图片里取出音乐…', UI_TEXT)
            self.root.update_idletasks()
            try:
                midi, meta, source = read_picture(path)
                mid = parse_midi(midi)
                perf = build_performance(mid)
            except Exception as e:
                messagebox.showerror('读取失败', str(e))
                self.status('读取失败：%s' % e, '#e87a64')
                return
            self.pic_path = path
            self.midi_bytes = midi
            self.meta = meta
            self.perf = perf
            self._load_image(path)
            title = meta.get('title') or os.path.splitext(os.path.basename(path))[0]
            self.btn_midi.configure(state='normal')
            self.btn_play.configure(state='normal')
            self.btn_folder.configure(state='normal')
            self.status('取到音乐：%s    %d 个音符    %d:%02d    来源：%s    MIDI %d 字节'
                        '\n开始播放。' % (
                            title, len(perf['notes']),
                            int(perf['duration'] // 60), int(perf['duration'] % 60),
                            source, len(midi)), UI_ACC2)
            self.play_music()

    # ---------- 图片显示 ----------
    def _load_image(self, path):
        tk = self.tk
        try:
            self.img_ref = tk.PhotoImage(file=path)
        except Exception as e:
            self.img_ref = None
            self.status('图片预览失败：%s' % e, '#e87a64')
            return
        self._redraw()

    def _redraw(self):
        c = self.canvas
        c.delete('all')
        if self.img_ref is None:
            c.create_text(c.winfo_width() // 2, c.winfo_height() // 2,
                          text='还没有载入内容\n\n模式一：导入 .mid 生成图片\n模式二：导入 PNG 直接播放',
                          fill=UI_DIM, font=('Microsoft YaHei UI', 12), justify='center')
            return
        iw, ih = self.img_ref.width(), self.img_ref.height()
        cw, ch = max(1, c.winfo_width() - 8), max(1, c.winfo_height() - 8)
        sub = max(1, int(math.ceil(iw / float(cw))), int(math.ceil(ih / float(ch))))
        self.img_small = self.img_ref.subsample(sub, sub) if sub > 1 else self.img_ref
        ox = (cw - self.img_small.width()) // 2 + 4
        oy = (ch - self.img_small.height()) // 2 + 4
        self.view = {'sub': sub, 'ox': ox, 'oy': oy}
        c.create_image(ox, oy, image=self.img_small, anchor='nw')
        self.playhead = c.create_line(0, 0, 0, 0, fill=UI_ACC, width=2, state='hidden')

    def _move_playhead(self, t):
        c = self.canvas
        if self.playhead is None or self.img_ref is None or self.duration <= 0:
            return
        if t is None:
            c.itemconfigure(self.playhead, state='hidden')
            return
        sub = self.view['sub']
        x0 = self.view['ox'] + MARGIN_L / float(sub)
        span = (IMG_W - MARGIN_L - MARGIN_R) / float(sub)
        x = x0 + span * min(1.0, t / self.duration)
        y0 = self.view['oy'] + HEADER_H / float(sub)
        y1 = self.view['oy'] + (self.img_ref.height() - FOOTER_H) / float(sub)
        c.coords(self.playhead, x, y0, x, y1)
        c.itemconfigure(self.playhead, state='normal')

    # ---------- 播放 ----------
    def play_music(self):
        if not self.perf:
            return
        self.stop_music(silent=True)
        self.stop_flag = threading.Event()
        self.duration = max(0.2, self.perf['duration'])
        self.play_start = time.perf_counter()
        self.worker = threading.Thread(target=self._player_worker, daemon=True)
        self.worker.start()
        self.btn_play.configure(text='播放中…', state='disabled')
        self.btn_stop.configure(state='normal')
        self._tick()

    def _player_worker(self):
        notes = self.perf['notes']
        programs = self.perf['programs']
        flag = self.stop_flag
        winmm = None
        handle = None
        try:
            winmm, handle = _midi_out_open()
        except Exception:
            self.sound_ok = False
        try:
            msgs = []
            for ch, prog in programs.items():
                msgs.append((0.0, 0xC0 | (ch & 0x0F), prog, 0))
            for ch in range(16):
                msgs.append((0.0, 0xB0 | ch, 7, 100))     # 主音量
            for t0, t1, pitch, vel, ch in notes:
                msgs.append((t0, 0x90 | (ch & 0x0F), pitch, max(1, min(127, vel))))
                msgs.append((t1, 0x80 | (ch & 0x0F), pitch, 0))
            msgs.sort(key=lambda m: m[0])
            t_zero = time.perf_counter()
            for when, st, d1, d2 in msgs:
                if flag.is_set():
                    break
                _sleep_until(t_zero + when)
                if winmm:
                    _send(winmm, handle, st, d1, d2)
            if winmm and not flag.is_set():
                _sleep_until(t_zero + self.duration + 0.02)
        finally:
            if winmm:
                try:
                    for ch in range(16):
                        _send(winmm, handle, 0xB0 | ch, 123, 0)   # 全通道停音
                    winmm.midiOutClose(handle)
                except Exception:
                    pass

    def stop_music(self, silent=False):
        if self.stop_flag:
            self.stop_flag.set()
        self.worker = None
        self.btn_play.configure(text='播放', state='normal' if self.perf else 'disabled')
        self.btn_stop.configure(state='disabled')
        self._move_playhead(None)
        if not silent and not self.sound_ok:
            self.status('已停止。注意：只有 Windows 才有声音输出，当前系统只能看画面。')

    def _tick(self):
        if self.stop_flag is None:
            return
        alive = self.worker is not None and self.worker.is_alive()
        el = time.perf_counter() - self.play_start
        if alive and el < self.duration + 0.5:
            self._move_playhead(el)
            self.root.after(60, self._tick)
        else:
            self.stop_music(silent=True)

    # ---------- 其它按钮 ----------
    def save_midi(self):
        from tkinter import filedialog
        data = self.midi_bytes
        if data is None and self.pic_path:
            try:
                data, _, _ = read_picture(self.pic_path)
            except Exception as e:
                self.status('导出失败：%s' % e, '#e87a64')
                return
        if not data:
            return
        name = os.path.splitext(os.path.basename(self.pic_path or 'music.png'))[0]
        path = filedialog.asksaveasfilename(title='保存 MIDI', defaultextension='.mid',
                                            initialfile=name + '.mid',
                                            filetypes=[('MIDI', '*.mid')])
        if not path:
            return
        with open(path, 'wb') as f:
            f.write(data)
        self.status('MIDI 已导出：%s（%d 字节）' % (path, len(data)), UI_ACC2)

    def open_folder(self):
        if not self.pic_path:
            return
        folder = os.path.dirname(os.path.abspath(self.pic_path))
        try:
            if sys.platform.startswith('win'):
                os.startfile(folder)
            elif sys.platform == 'darwin':
                os.system('open "%s"' % folder)
            else:
                os.system('xdg-open "%s" &' % folder)
        except Exception as e:
            self.status('打开失败：%s' % e, '#e87a64')


def run_gui():
    app = App()
    app.root.mainloop()


# ======================= 自检（无界面） =======================
def _selftest():
    import tempfile
    tmp = tempfile.mkdtemp(prefix='mszpm_')
    # 造一个最小 MIDI：两个轨道，速度 120，含和弦与鼓
    def vlq(v):
        out = [v & 0x7F]
        v >>= 7
        while v:
            out.append((v & 0x7F) | 0x80)
            v >>= 7
        return bytes(reversed(out))

    def track(evts):
        body = b''
        last = 0
        for tick, data in evts:
            body += vlq(tick - last) + data
            last = tick
        body += vlq(0) + b'\xff\x2f\x00'
        return b'MTrk' + len(body).to_bytes(4, 'big') + body

    t0 = [(0, b'\xff\x51\x03\x07\xa1\x20'), (0, b'\xff\x03\x04Titl')]
    mel = []
    for i, p in enumerate((60, 64, 67, 72, 69, 65)):
        mel.append((i * 96, bytes([0x90, p, 100])))
        mel.append((i * 96 + 80, bytes([0x80, p, 0])))
    t1 = [(0, b'\xc0\x00')] + mel
    t2 = [(0, b'\xc0\x02')]
    for i in range(4):
        t2.append((i * 96, bytes([0x90, 36, 90])))
        t2.append((i * 96 + 40, bytes([0x80, 36, 0])))
    smf = (b'MThd' + (6).to_bytes(4, 'big') + (1).to_bytes(2, 'big') +
           (3).to_bytes(2, 'big') + (96).to_bytes(2, 'big') +
           track(t0) + track(t1) + track(t2))
    src = os.path.join(tmp, 'test.mid')
    with open(src, 'wb') as f:
        f.write(smf)

    print('[1] 解析 MIDI')
    mid = parse_midi(smf)
    perf = build_performance(mid)
    print('    notes=%d  duration=%.2fs  format=%d  tracks=%d' %
          (len(perf['notes']), perf['duration'], mid['format'], mid['ntrk']))
    assert len(perf['notes']) == 10, len(perf['notes'])
    assert 2.0 < perf['duration'] < 6.0, perf['duration']

    print('[2] 生成图片')
    out, meta = make_picture(src, os.path.join(tmp, 'out.png'))
    print('    %s  %d bytes  音符=%d  时长=%.2f' %
          (out, os.path.getsize(out), meta['notes'], meta['duration']))

    print('[3] 从 PNG 数据块取回 MIDI')
    back, meta2, source = read_picture(out)
    assert back == smf, '数据块取回内容不一致'
    print('    来源=%s  字节=%d' % (source, len(back)))

    print('[4] 从像素隐写取回 MIDI')
    w, h, pix, chunks = png_read(out)
    lsb = lsb_extract(pix)
    assert lsb == smf, '像素隐写取回内容不一致'
    print('    图片 %dx%d  lsb=%d 字节' % (w, h, len(lsb)))

    print('[5] 取回后重新解析')
    perf2 = build_performance(parse_midi(back))
    assert len(perf2['notes']) == len(perf['notes'])
    print('    notes=%d  duration=%.2f' % (len(perf2['notes']), perf2['duration']))

    print('[6] 空白图片应识别为“没有数据”')
    assert lsb_extract(bytearray(len(pix))) is None

    print('SELFTEST OK ->', tmp)
    return 0


def _cli(argv):
    if not argv:
        return None
    if argv[0] == '--selftest':
        return _selftest()
    if argv[0] in ('--make', '-m') and len(argv) > 1:
        out, meta = make_picture(argv[1], argv[2] if len(argv) > 2 else None)
        print('已生成：%s' % out)
        print('  音符 %d  时长 %d:%02d  轨道 %d  图片 %.0f KB' % (
            meta['notes'], meta['duration'] // 60, meta['duration'] % 60,
            meta['tracks'], os.path.getsize(out) / 1024.0))
        return 0
    if argv[0] in ('--info', '-i') and len(argv) > 1:
        midi, meta, source = read_picture(argv[1])
        perf = build_performance(parse_midi(midi))
        print('曲名：%s' % (meta.get('title') or '（无）'))
        print('来源：%s   MIDI %d 字节' % (source, len(midi)))
        print('音符 %d  时长 %d:%02d  %d 轨' % (
            len(perf['notes']), perf['duration'] // 60, perf['duration'] % 60,
            max(1, perf.get('tracks', 1))))
        return 0
    return None


if __name__ == '__main__':
    rc = _cli(sys.argv[1:])
    if rc is None:
        run_gui()
    else:
        sys.exit(rc)
