"""Lee y escribe el marcado legible por maquina que pide el articulo 50(2).

PROCEDENCIA: escrito para el arnes de medicion `art50-survival` y traido aqui
sin cambiar su logica. Lo que cambia es el papel: alli medía plataformas, aqui
decide un control sobre los ficheros del cliente.

POR QUE ESTE MODULO NO USA NINGUNA BIBLIOTECA
----------------------------------------------
Las alternativas eran `exiftool` (cadena Perl), `c2pa-python` (extension Rust
mas una lista de confianza) y Pillow. Las tres se rechazan para el camino de
MEDICION, y por la misma razon por la que existe el control: una cifra que
nadie puede regenerar es una cifra que nadie puede comprobar.

  exiftool     correcto y exhaustivo, pero ata el resultado a cual de sus ~25
               versiones anuales instalo el lector, y normaliza lo que lee, con
               lo que "la propiedad esta presente" pasaria a ser "exiftool la
               reconocio", que es otra afirmacion.
  c2pa-python  VALIDA, y validar necesita una lista de confianza, que es una
               politica y no un hecho sobre los bytes. Este modulo no publica
               decisiones de politica.
  Pillow       sirve para dibujar, pero su lector de JPEG descarta APP11, que
               es justo el segmento donde vive un manifiesto C2PA.

Asi que el camino de medicion no tiene ni una dependencia de tercero: es
`struct`, `zlib` y `re` sobre los dos contenedores que cubre este estudio.
Pillow solo lo importa el arnes de durabilidad. El coste aceptado y publicado:
este modulo responde PRESENCIA, jamas VALIDEZ. Un manifiesto C2PA se reporta
`present_unverified` y nunca como valido.
"""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

XMP_JPEG_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_XMP_KEYWORD = b"XML:com.adobe.xmp"
PNG_C2PA_CHUNK = b"caBX"

# The IPTC newscode this study writes and looks for. Article 50(2) names no
# format at all, so the choice of vocabulary is ours; this is the one the
# C2PA soft binding and the IPTC extension both point at for synthetic media.
TRAINED_ALGORITHMIC_MEDIA = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
)

_IPTC_PREFIX = "http://cv.iptc.org/newscodes/digitalsourcetype/"

DIGITAL_SOURCE_TYPES = frozenset({
    _IPTC_PREFIX + name
    for name in (
        # The three that mean "a model made this", which is what Article 50(2)
        # is about. `trainedAlgorithmicMedia` is the one we write.
        "trainedAlgorithmicMedia",
        "compositeSynthetic",
        "algorithmicMedia",
        # The rest of the IPTC vocabulary. They are legitimate values that mean
        # the file is NOT synthetic, and reading one is a perfectly good
        # outcome: it says the channel marked the file and said something else.
        # Leaving them out would have turned "correctly marked as a photograph"
        # into "unrecognised value", which is a different and wrong answer.
        "digitalCapture",
        "negativeFilm",
        "positiveFilm",
        "print",
        "minorHumanEdits",
        "compositeCapture",
        "compositeWithTrainedAlgorithmicMedia",
        "algorithmicallyEnhanced",
        "digitalArt",
        "virtualRecording",
        "dataDrivenMedia",
        "softwareImage",
    )
})
"""The IPTC DigitalSourceType newscodes this reader recognises.

WHY THIS LIST EXISTS
---------------------
`has_marking` used to be `digital_source_type is not None`, so ANY non-null
value counted as a marking. An external audit wrote

    DigitalSourceType="potato"

and the tool reported that machine-readable marking was present. So did
`http://malo/inventado`, and a four-hundred character run of `x`.

That is a false OBSERVATION, which is worse than a false conclusion: every
layer above it -- sufficiency, the dossier, the panel -- is built on the idea
that what the observation layer reports was actually read off the bytes. A
control that is satisfied by typing a word into a file is not a control.

The list is closed on purpose. Accepting "anything under the IPTC prefix" would
have been almost as bad: the whole point of a controlled vocabulary is that the
values are enumerated, and a reader that accepts unseen ones is not reading a
controlled vocabulary.
"""

SYNTHETIC_SOURCE_TYPES = frozenset({
    _IPTC_PREFIX + name
    for name in ("trainedAlgorithmicMedia", "compositeSynthetic", "algorithmicMedia")
})
"""The subset that actually means a model produced the content.

Kept apart from `DIGITAL_SOURCE_TYPES` because they answer different questions.
"Is this file marked?" and "does the marking say it is synthetic?" are not the
same question, and the second is the one Article 50(2) asks.
"""


# Matches both the attribute form and the element form, under any prefix.
# Written permissively on purpose: a channel that rewrites XMP into a
# different but equivalent serialisation has NOT destroyed the marking, and
# a reader that counted that as a loss would be measuring its own parser.
_DST_ATTR = re.compile(rb"[\w-]*:?DigitalSourceType\s*=\s*[\"']([^\"']+)[\"']")
_DST_ELEM = re.compile(
    rb"<[\w-]*:?DigitalSourceType[^>]*>\s*(?:<[^>]+>\s*)*?([^<\s][^<]*)", re.S
)

SOF_MARKERS = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
STANDALONE_MARKERS = {0xD8, 0xD9, 0x01} | set(range(0xD0, 0xD8))


@dataclass
class FileFacts:
    """Everything this harness is willing to assert about one file's bytes."""

    path: str
    readable: bool
    container: str | None = None          # "png" | "jpeg" | None
    sha256: str | None = None
    bytes_len: int | None = None
    width: int | None = None
    height: int | None = None
    xmp_packets: int = 0
    digital_source_type: str | None = None
    c2pa: str = "absent"                  # "absent" | "present_unverified"
    notes: list[str] = field(default_factory=list)

    @property
    def marking(self) -> str:
        """Three answers, not two, because there are three things that can be true.

            "absent"        no DigitalSourceType was found in any XMP packet.
            "unrecognised"  one was found and it is not in the IPTC vocabulary.
            "present"       one was found and it is a recognised newscode.

        The middle state is the one that was missing, and its absence is what
        let `DigitalSourceType="potato"` be reported as machine-readable
        marking. It must not collapse into either neighbour: folding it into
        "present" asserts a marking that nobody can interpret, and folding it
        into "absent" hides that somebody wrote something there -- which is a
        finding in itself, and usually means a pipeline is writing the field
        wrong rather than not writing it.
        """
        if self.digital_source_type is None:
            return "absent"
        if self.digital_source_type in DIGITAL_SOURCE_TYPES:
            return "present"
        return "unrecognised"

    @property
    def says_synthetic(self) -> bool:
        """Whether the marking says a model produced this. Not the same question.

        A file correctly marked `digitalCapture` IS marked, and it is not
        synthetic. Answering both with one boolean forced a choice between two
        different truths.
        """
        return self.digital_source_type in SYNTHETIC_SOURCE_TYPES

    @property
    def has_marking(self) -> bool:
        """Kept for the callers that only ask "is there a readable marking?".

        Now anchored to the recognised vocabulary, which is the whole fix: it
        used to be `is not None`.
        """
        return self.marking == "present"


def _iter_png_chunks(data: bytes):
    off = len(PNG_SIGNATURE)
    while off + 8 <= len(data):
        (length,) = struct.unpack(">I", data[off : off + 4])
        ctype = data[off + 4 : off + 8]
        start = off + 8
        end = start + length
        if end > len(data):
            return
        yield ctype, data[start:end]
        off = end + 4


def _iter_jpeg_segments(data: bytes):
    off = 2
    while off + 1 < len(data):
        if data[off] != 0xFF:
            off += 1
            continue
        marker = data[off + 1]
        if marker in STANDALONE_MARKERS or marker == 0xFF:
            off += 2
            continue
        if off + 4 > len(data):
            return
        (length,) = struct.unpack(">H", data[off + 2 : off + 4])
        payload = data[off + 4 : off + 2 + length]
        yield marker, payload
        if marker == 0xDA:      # SOS: entropy coded data follows, stop here
            return
        off += 2 + length


def _png_itxt_payload(chunk: bytes) -> tuple[bytes, bytes] | None:
    try:
        keyword, rest = chunk.split(b"\x00", 1)
    except ValueError:
        return None
    if len(rest) < 2:
        return None
    compression_flag = rest[0]
    rest = rest[2:]
    try:
        _lang, rest = rest.split(b"\x00", 1)
        _translated, text = rest.split(b"\x00", 1)
    except ValueError:
        return None
    if compression_flag:
        import zlib

        try:
            text = zlib.decompress(text)
        except zlib.error:
            return None
    return keyword, text


def _png_text_payload(ctype: bytes, chunk: bytes) -> tuple[bytes, bytes] | None:
    """The payload of a `tEXt` or `zTXt` chunk, as (keyword, text).

    WHY THIS EXISTS: the branch that used to handle these chunks was

        elif ctype in (b"tEXt", b"zTXt") and b"xmp" in ctype.lower():
            pass

    and it never ran. It tested for `xmp` inside the CHUNK TYPE -- `tEXt` does
    not contain `xmp` -- rather than inside the keyword, and even if it had
    matched it did nothing.

    So a file whose XMP lives in a `tEXt` chunk read as UNMARKED. The PNG
    standard puts XMP in `iTXt`, and that is what this harness writes, but some
    tools write it to `tEXt`, and a reader that reports absence when the truth
    is "I did not look there" is the exact failure this module exists to avoid.

    `tEXt` is `keyword\0text`. `zTXt` is `keyword\0method\0deflate(text)`.
    """
    try:
        keyword, rest = chunk.split(b"\x00", 1)
    except ValueError:
        return None
    if ctype == b"tEXt":
        return keyword, rest
    # zTXt: one byte of compression method, then the compressed text.
    if not rest:
        return None
    if rest[0] != 0:
        return None          # only deflate is defined; anything else is unread
    import zlib

    try:
        return keyword, zlib.decompress(rest[1:])
    except zlib.error:
        return None


def _extract_digital_source_type(packets: list[bytes]) -> str | None:
    for packet in packets:
        for pattern in (_DST_ATTR, _DST_ELEM):
            match = pattern.search(packet)
            if match:
                return match.group(1).decode("utf-8", "replace").strip()
    return None


def read_facts(path: str | Path) -> FileFacts:
    """Inspect one file and report only what its bytes support."""
    p = Path(path)
    if not p.is_file():
        return FileFacts(path=str(p), readable=False, notes=["file not present"])
    data = p.read_bytes()
    facts = FileFacts(
        path=str(p),
        readable=True,
        sha256=hashlib.sha256(data).hexdigest(),
        bytes_len=len(data),
    )
    packets: list[bytes] = []

    if data.startswith(PNG_SIGNATURE):
        facts.container = "png"
        for ctype, chunk in _iter_png_chunks(data):
            if ctype == b"IHDR" and len(chunk) >= 8:
                facts.width, facts.height = struct.unpack(">II", chunk[:8])
            elif ctype == b"iTXt":
                parsed = _png_itxt_payload(chunk)
                if parsed and parsed[0] == PNG_XMP_KEYWORD:
                    packets.append(parsed[1])
            elif ctype in (b"tEXt", b"zTXt"):
                # Not the standard place for XMP -- that is `iTXt` -- but some
                # tools write it here, and reading only where we write would
                # report a marked file as unmarked.
                parsed = _png_text_payload(ctype, chunk)
                if parsed and parsed[0] == PNG_XMP_KEYWORD:
                    packets.append(parsed[1])
            elif ctype == PNG_C2PA_CHUNK:
                facts.c2pa = "present_unverified"
    elif data[:2] == b"\xff\xd8":
        facts.container = "jpeg"
        for marker, payload in _iter_jpeg_segments(data):
            if marker == 0xE1 and payload.startswith(XMP_JPEG_HEADER):
                packets.append(payload[len(XMP_JPEG_HEADER) :])
            elif marker == 0xEB and (b"c2pa" in payload or b"jumb" in payload):
                facts.c2pa = "present_unverified"
            elif marker in SOF_MARKERS and len(payload) >= 5:
                facts.height, facts.width = struct.unpack(">HH", payload[1:5])
    else:
        facts.notes.append("container not recognised: not PNG and not JPEG")
        return facts

    facts.xmp_packets = len(packets)
    facts.digital_source_type = _extract_digital_source_type(packets)
    return facts


def xmp_packet(source_type: str = TRAINED_ALGORITHMIC_MEDIA) -> bytes:
    """The smallest XMP packet that carries the property, and nothing else.

    Kept minimal on purpose: every extra property is another thing a channel
    could drop, and the study would then not know which drop it measured.
    """
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
        f'Iptc4xmpExt:DigitalSourceType="{source_type}"/>'
        "</rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode("utf-8")


def _png_chunk(ctype: bytes, payload: bytes) -> bytes:
    import zlib

    return (
        struct.pack(">I", len(payload))
        + ctype
        + payload
        + struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF)
    )


def write_marking(path: str | Path, source_type: str = TRAINED_ALGORITHMIC_MEDIA) -> None:
    """Add the marking in place. PNG gets an iTXt chunk, JPEG an APP1 segment."""
    p = Path(path)
    data = p.read_bytes()
    packet = xmp_packet(source_type)

    if data.startswith(PNG_SIGNATURE):
        payload = PNG_XMP_KEYWORD + b"\x00\x00\x00" + b"\x00" + b"\x00" + packet
        chunk = _png_chunk(b"iTXt", payload)
        # After IHDR, which must be first. Position is otherwise free.
        off = len(PNG_SIGNATURE)
        (length,) = struct.unpack(">I", data[off : off + 4])
        insert_at = off + 8 + length + 4
        p.write_bytes(data[:insert_at] + chunk + data[insert_at:])
        return

    if data[:2] == b"\xff\xd8":
        body = XMP_JPEG_HEADER + packet
        segment = b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body
        p.write_bytes(data[:2] + segment + data[2:])
        return

    raise ValueError(f"cannot mark {p}: container is neither PNG nor JPEG")
