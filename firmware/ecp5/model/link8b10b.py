"""8b/10b (IEEE 802.3 clause 36), CRC-16/CCITT-FALSE and frame pack/unpack.

PROPOSED line protocol, firmware/ecp5/README.md sections 3 and 9. This file is
the normative copy of the code tables for the gateware; the RTL tests derive
every expectation from here.

Bit order: a 10-bit code is an int with bit 0 = 'a' (first transmitted) up to
bit 9 = 'j' (last transmitted), i.e. the abcdei fghj order of clause 36.
Running disparity rd is -1 or +1 (the RTL stores 0 for negative, 1 for positive).
"""

# ---------------------------------------------------------------------------
# Tables, strings written in transmit order (a first).  Clause 36 Tables 36-1
# (data) and 36-2 (special codes).  Each 6b entry is (RD- column, RD+ column).
# ---------------------------------------------------------------------------
_T6 = {
    0: ("100111", "011000"), 1: ("011101", "100010"), 2: ("101101", "010010"),
    3: ("110001", "110001"), 4: ("110101", "001010"), 5: ("101001", "101001"),
    6: ("011001", "011001"), 7: ("111000", "000111"), 8: ("111001", "000110"),
    9: ("100101", "100101"), 10: ("010101", "010101"), 11: ("110100", "110100"),
    12: ("001101", "001101"), 13: ("101100", "101100"), 14: ("011100", "011100"),
    15: ("010111", "101000"), 16: ("011011", "100100"), 17: ("100011", "100011"),
    18: ("010011", "010011"), 19: ("110010", "110010"), 20: ("001011", "001011"),
    21: ("101010", "101010"), 22: ("011010", "011010"), 23: ("111010", "000101"),
    24: ("110011", "001100"), 25: ("100110", "100110"), 26: ("010110", "010110"),
    27: ("110110", "001001"), 28: ("001110", "001110"), 29: ("101110", "010001"),
    30: ("011110", "100001"), 31: ("101011", "010100"),
}
_K28_6 = ("001111", "110000")

# 3b/4b data codes (RD- column, RD+ column), RD being the disparity after the 6b block.
_T4 = {
    0: ("1011", "0100"), 1: ("1001", "1001"), 2: ("0101", "0101"),
    3: ("1100", "0011"), 4: ("1101", "0010"), 5: ("1010", "1010"),
    6: ("0110", "0110"), 7: ("1110", "0001"),          # 7 = primary P7
}
_A7 = ("0111", "1000")                                  # alternate A7
_A7_NEG_X = (17, 18, 20)    # A7 used when rd after 6b is negative
_A7_POS_X = (11, 13, 14)    # A7 used when rd after 6b is positive

K_BYTES = (0x1C, 0x3C, 0x5C, 0x7C, 0x9C, 0xBC, 0xDC, 0xFC, 0xF7, 0xFB, 0xFD, 0xFE)

K28_0, K28_1, K28_2, K28_3, K28_4, K28_5, K28_6, K28_7 = (
    0x1C, 0x3C, 0x5C, 0x7C, 0x9C, 0xBC, 0xDC, 0xFC)
K23_7, K27_7, K29_7, K30_7 = 0xF7, 0xFB, 0xFD, 0xFE
D16_2 = 0x50
D0_0 = 0x00


def _bits(s):
    """'abcdei...' string (a first) -> int with a at bit 0."""
    return sum(1 << i for i, c in enumerate(s) if c == "1")


def _ones(s):
    return s.count("1")


def _disp(s):
    return 2 * _ones(s) - len(s)


def is_valid_k(byte):
    return byte in K_BYTES


def _sel(pair, rd):
    return pair[0] if rd < 0 else pair[1]


def encode_strings(byte, is_k, rd):
    """Return (6b string, 4b string, rd_out); raises ValueError on a bad K."""
    if rd not in (-1, 1):
        raise ValueError("rd must be -1 or +1")
    x, y = byte & 0x1F, byte >> 5
    if is_k and byte not in K_BYTES:
        raise ValueError("invalid K code 0x%02X" % byte)
    s6 = _sel(_K28_6 if (is_k and x == 28) else _T6[x], rd)
    rd6 = -rd if _disp(s6) != 0 else rd
    if y == 7 and (is_k or (rd6 < 0 and x in _A7_NEG_X) or (rd6 > 0 and x in _A7_POS_X)):
        s4 = _sel(_A7, rd6)
    else:
        s4 = _sel(_T4[y], rd6)
        if is_k and x == 28 and y in (1, 2, 5, 6) and rd6 < 0:
            s4 = "".join("1" if c == "0" else "0" for c in s4)  # K28 balanced 4b codes swap
    rd_out = -rd6 if _disp(s4) != 0 else rd6
    return s6, s4, rd_out


def encode(byte, is_k, rd):
    """Encode one symbol -> (code10, rd_out)."""
    s6, s4, rd_out = encode_strings(byte, is_k, rd)
    return _bits(s6 + s4), rd_out


def encode_stream(symbols, rd=-1):
    out = []
    for byte, is_k in symbols:
        code, rd = encode(byte, is_k, rd)
        out.append(code)
    return out


# Reverse map: code10 -> {(byte, is_k): set of start rd for which the encoder emits it}
def _build_reverse():
    rev = {}
    for is_k, byte in [(False, b) for b in range(256)] + [(True, b) for b in K_BYTES]:
        for rd in (-1, 1):
            code, _ = encode(byte, is_k, rd)
            ent = rev.setdefault(code, {"sym": (byte, is_k), "rds": set()})
            assert ent["sym"] == (byte, is_k), "code word shared by two symbols"
            ent["rds"].add(rd)
    return rev


_REV = _build_reverse()
VALID_CODES = frozenset(_REV)


def _popdisp(code):
    return 2 * bin(code).count("1") - 10


def decode(code10, rd):
    """Decode one 10-bit code word.

    rd is -1, +1, or None (disparity unknown: the first symbol after reset
    resync, see below).  Returns (byte, is_k, rd_out, code_err, disp_err).

    code_err: word is not a code word the encoder can emit; byte = 0,
      is_k = False, rd_out = None (disparity must be resynchronised).
    disp_err: valid word whose required start disparity differs from rd; the
      byte is still decoded.
    rd_out (valid word): sign of the word's disparity if non-zero; otherwise,
      if only one start disparity is legal for the word, that one; otherwise
      rd unchanged (possibly None).  With rd None no disp_err is reported.
    """
    ent = _REV.get(code10 & 0x3FF)
    if ent is None:
        return 0, False, None, True, False
    byte, is_k = ent["sym"]
    rds = ent["rds"]
    d = _popdisp(code10)
    if d != 0:
        rd_out = 1 if d > 0 else -1
    elif len(rds) == 1:
        rd_out = next(iter(rds))
    else:
        rd_out = rd
    disp_err = rd is not None and rd not in rds
    return byte, is_k, rd_out, False, disp_err


def symbols_to_bits(codes):
    """List of 10-bit codes -> list of bits, 'a' first."""
    return [(c >> i) & 1 for c in codes for i in range(10)]


# ---------------------------------------------------------------------------
# CRC-16/CCITT-FALSE
# ---------------------------------------------------------------------------
def crc16_ccitt_false(data, crc=0xFFFF):
    for b in bytes(data):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


# ---------------------------------------------------------------------------
# PRBS-15 (x^15 + x^14 + 1), Fibonacci, LSB-first bytes: matches rtl/prbs.v
# ---------------------------------------------------------------------------
def prbs15_bytes(seed, n):
    """n bytes; first generated bit is data[0].  A zero seed loads 0x7FFF."""
    s = (seed & 0x7FFF) or 0x7FFF
    out = []
    for _ in range(n):
        v = 0
        for i in range(8):
            fb = ((s >> 14) ^ (s >> 13)) & 1
            s = ((s << 1) | fb) & 0x7FFF
            v |= fb << i
        out.append(v)
    return out


# ---------------------------------------------------------------------------
# Frames (README section 3)
# ---------------------------------------------------------------------------
def idle_pair():
    """/I2/-style idle ordered set: K28.5 then D16.2."""
    return [(K28_5, True), (D16_2, False)]


def pack_frame(seq, ftype, payload):
    payload = bytes(payload)
    if not 1 <= len(payload) <= 256:
        raise ValueError("payload must be 1..256 bytes")
    body = bytes([seq & 0xFF, (seq >> 8) & 0xFF, ftype & 0xFF, len(payload) - 1]) + payload
    crc = crc16_ccitt_false(body)
    body += bytes([crc & 0xFF, crc >> 8])
    return [(K27_7, True)] + [(b, False) for b in body] + [(K29_7, True)]


def unpack_frame(symbols):
    """-> (seq, ftype, payload); raises ValueError on any violation."""
    symbols = list(symbols)
    if len(symbols) < 1 + 4 + 1 + 2 + 1:
        raise ValueError("frame too short")
    if symbols[0] != (K27_7, True):
        raise ValueError("missing /S/")
    if symbols[-1] != (K29_7, True):
        raise ValueError("missing /T/")
    inner = symbols[1:-1]
    if any(k for _, k in inner):
        raise ValueError("control symbol inside frame")
    body = bytes(b for b, _ in inner)
    n = body[3] + 1
    if len(body) != 4 + n + 2:
        raise ValueError("length mismatch")
    crc = body[-2] | (body[-1] << 8)
    if crc16_ccitt_false(body[:-2]) != crc:
        raise ValueError("crc mismatch")
    return body[0] | (body[1] << 8), body[2], body[4:4 + n]


# ---------------------------------------------------------------------------
# Self check:  python3 -m model.link8b10b
# ---------------------------------------------------------------------------
def _runs(bits):
    best = cur = 0
    prev = None
    for b in bits:
        cur = cur + 1 if b == prev else 1
        prev = b
        best = max(best, cur)
    return best


def _selfcheck():
    import random
    syms = [(b, False) for b in range(256)] + [(b, True) for b in K_BYTES]
    # well-known words (clause 36 / common references), transmit order strings
    known = {
        (K28_5, True, -1): "0011111010", (K28_5, True, 1): "1100000101",
        (K27_7, True, -1): "1101101000", (K29_7, True, -1): "1011101000",
        (D16_2, False, -1): "0110110101", (D16_2, False, 1): "1001000101",
        (K28_1, True, -1): "0011111001", (K28_1, True, 1): "1100000110",
        (0x00, False, -1): "1001110100", (0xFF, False, -1): "1010110001",
    }
    for (b, k, rd), s in known.items():
        code, _ = encode(b, k, rd)
        assert code == _bits(s), (hex(b), k, rd, s)
    for rd in (-1, 1):
        for b, k in syms:
            code, rd_out = encode(b, k, rd)
            assert 0 <= code < 1024
            d = _popdisp(code)
            assert d in (-2, 0, 2), (b, k, rd, d)
            # disparity bookkeeping: a +2 word must start at rd- and end rd+
            assert rd_out == (rd if d == 0 else (1 if d > 0 else -1))
            if d != 0:
                assert (d > 0) == (rd < 0)
            b2, k2, rd2, ce, de = decode(code, rd)
            assert (b2, k2, ce, de) == (b, k, False, False), (b, k, rd)
            assert rd2 == rd_out
    # exactly the encoder words decode without error
    n_valid = 0
    for w in range(1024):
        _, _, _, ce, _ = decode(w, -1)
        if not ce:
            n_valid += 1
            assert w in VALID_CODES
        else:
            assert w not in VALID_CODES
    # 268 symbols; every symbol has 1 or 2 distinct words
    assert n_valid == len(VALID_CODES)
    # run length <= 5 for random legal streams and for idle
    stream = encode_stream(idle_pair() * 50)
    assert _runs(symbols_to_bits(stream)) <= 5
    rng = random.Random(1)
    rd = -1
    rb = []
    for _ in range(20000):
        b, k = rng.choice(syms)
        code, rd = encode(b, k, rd)
        rb.append(code)
    assert _runs(symbols_to_bits(rb)) <= 5
    # idle leaves rd negative and K28.5 is always the same word
    rd = -1
    for _ in range(10):
        c, rd = encode(K28_5, True, rd)
        assert c == _bits("0011111010")
        c, rd = encode(D16_2, False, rd)
        assert rd == -1
    assert crc16_ccitt_false(b"123456789") == 0x29B1
    p = bytes(rng.randrange(256) for _ in range(256))
    fr = pack_frame(0xBEEF, 0x10, p)
    assert unpack_frame(fr) == (0xBEEF, 0x10, p)
    assert len(pack_frame(0, 0, b"\0")) == 1 + 4 + 1 + 2 + 1
    try:
        bad = list(fr)
        bad[5] = ((bad[5][0] ^ 1), False)
        unpack_frame(bad)
        raise AssertionError("bad crc accepted")
    except ValueError:
        pass
    print("link8b10b self-check OK: %d symbols, %d valid code words" % (len(syms), n_valid))


if __name__ == "__main__":
    _selfcheck()
