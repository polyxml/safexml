"""safexml: High-performance, secure, modern XML parser and drop-in defusedxml replacement built in Rust.

Provides drop-in compatibility with `defusedxml` and Python's standard `xml.etree.ElementTree`.
Targets Python >= 3.12 exclusively.
"""

from __future__ import annotations

from xml.etree import ElementTree as _stdlib_etree

from safexml import ElementTree
from safexml._safexml import version as _rust_version
from safexml.common import (
    DefusedXmlException,
    DTDForbidden,
    EntitiesForbidden,
    ExternalReferenceForbidden,
    NotSupportedError,
    ParseError,
)
from safexml.ElementTree import (
    PI,
    XML,
    Comment,
    Element,
    ProcessingInstruction,
    QName,
    SubElement,
    TreeBuilder,
    XMLParse,
    XMLParser,
    canonicalize,
    dump,
    fromstring,
    indent,
    iterparse,
    parse,
    register_namespace,
    tostring,
    tostringlist,
)

__version__ = _rust_version()


def defuse_stdlib() -> None:
    """Safely patch standard library `xml.etree.ElementTree` to use safexml parsers.

    Preserves standard library attributes and Element class identities.
    """
    _stdlib_etree.fromstring = fromstring
    _stdlib_etree.parse = parse
    _stdlib_etree.iterparse = iterparse
    _stdlib_etree.XML = XML


__all__ = [
    "Comment",
    "DTDForbidden",
    "DefusedXmlException",
    "Element",
    "ElementTree",
    "EntitiesForbidden",
    "ExternalReferenceForbidden",
    "NotSupportedError",
    "PI",
    "ParseError",
    "ProcessingInstruction",
    "QName",
    "SubElement",
    "TreeBuilder",
    "XML",
    "XMLParse",
    "XMLParser",
    "canonicalize",
    "defuse_stdlib",
    "dump",
    "fromstring",
    "indent",
    "iterparse",
    "parse",
    "register_namespace",
    "tostring",
    "tostringlist",
]
