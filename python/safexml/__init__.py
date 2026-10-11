"""safexml: High-performance, secure, modern XML parser and drop-in defusedxml replacement built in Rust.

Provides drop-in compatibility with `defusedxml` and Python's standard `xml.etree.ElementTree`,
`xml.dom.minidom`, and `xml.sax`.
Targets Python >= 3.12 exclusively.
"""

from __future__ import annotations

import xml.dom.minidom as _stdlib_minidom
import xml.sax as _stdlib_sax
from xml.etree import ElementTree as _stdlib_etree

from safexml import ElementTree, minidom, sax
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
    fromstringlist,
    indent,
    iterparse,
    parse,
    register_namespace,
    tostring,
    tostringlist,
)

__version__ = _rust_version()


def defuse_stdlib() -> dict[str, object]:
    """Safely patch standard library `xml.etree.ElementTree`, `xml.dom.minidom`, and `xml.sax` to use safexml parsers.

    Preserves standard library attributes and Element class identities.
    Returns a dictionary mapping module names to the patched standard library modules.
    """
    _stdlib_etree.fromstring = fromstring
    _stdlib_etree.parse = parse
    _stdlib_etree.iterparse = iterparse
    _stdlib_etree.XML = XML
    _stdlib_etree.XMLParser = XMLParser
    _stdlib_etree.fromstringlist = fromstringlist

    def _patched_et_parse(self, source, parser=None, **kwargs):
        root = parse(source, parser=parser, **kwargs).getroot()
        self._setroot(root)
        return root

    _stdlib_etree.ElementTree.parse = _patched_et_parse

    _stdlib_minidom.parse = minidom.parse
    _stdlib_minidom.parseString = minidom.parseString

    _stdlib_sax.parse = sax.parse
    _stdlib_sax.parseString = sax.parseString
    _stdlib_sax.make_parser = sax.make_parser

    return {
        "xml.etree.ElementTree": _stdlib_etree,
        "xml.dom.minidom": _stdlib_minidom,
        "xml.sax": _stdlib_sax,
    }


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
    "fromstringlist",
    "indent",
    "iterparse",
    "minidom",
    "parse",
    "register_namespace",
    "sax",
    "tostring",
    "tostringlist",
]
