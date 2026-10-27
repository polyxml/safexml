"""Drop-in defused XML parser and modern ElementTree implementation.

Compatible with `defusedxml.ElementTree` and `xml.etree.ElementTree`.
Powered by Rust (`quick-xml`) with GIL release and strict entity/DoS defense.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import IO, Any
from xml.etree.ElementTree import (
    PI,
    Comment,
    Element,
    ProcessingInstruction,
    QName,
    SubElement,
    TreeBuilder,
    canonicalize,
    dump,
    indent,
    register_namespace,
    tostring,
    tostringlist,
)
from xml.etree.ElementTree import (
    ElementTree as _StdlibElementTree,
)

from safexml._safexml import parse_xml as _parse_xml
from safexml.common import (
    DefusedXmlException,
    DTDForbidden,
    EntitiesForbidden,
    ExternalReferenceForbidden,
    NotSupportedError,
    ParseError,
)

# Standard alias
XMLParse = ParseError


class XMLParser:
    """Secure XMLParser compatible with xml.etree.ElementTree.XMLParser and defusedxml."""

    def __init__(
        self,
        *,
        target: Any | None = None,
        encoding: str | None = None,
        forbid_dtd: bool = False,
        forbid_entities: bool = True,
        forbid_external: bool = True,
        max_depth: int = 1000,
        max_entity_size: int = 10 * 1024 * 1024,
        max_text_size: int = 100 * 1024 * 1024,
        max_attributes: int = 1000,
        max_attribute_size: int = 10 * 1024 * 1024,
        max_name_size: int = 1024,
        max_comment_size: int = 10 * 1024 * 1024,
        max_input_size: int = 256 * 1024 * 1024,
        max_elements: int = 5_000_000,
    ) -> None:
        """Initialize a secure `XMLParser` instance.

        Args:
            target: Optional target object (retained for stdlib signature compatibility).
            encoding: Optional character encoding override name.
            forbid_dtd: Disallow `<!DOCTYPE ...>` declarations.
            forbid_entities: Disallow `<!ENTITY ...>` declarations and custom entity references.
            forbid_external: Disallow external `SYSTEM` and `PUBLIC` references.
            max_depth: Maximum allowed element nesting depth.
            max_entity_size: Maximum size in bytes of an entity value.
            max_text_size: Maximum accumulated text and synthesized attribute size in bytes.
            max_attributes: Maximum number of attributes per element.
            max_attribute_size: Maximum size in bytes of a single attribute value.
            max_name_size: Maximum length in bytes of an XML element or attribute name.
            max_comment_size: Maximum size in bytes of a comment or processing instruction.
            max_input_size: Maximum size in bytes of the raw input document.
            max_elements: Maximum total number of elements in the document.
        """
        self.target = target
        self.encoding = encoding
        self.forbid_dtd = forbid_dtd
        self.forbid_entities = forbid_entities
        self.forbid_external = forbid_external
        self.max_depth = max_depth
        self.max_entity_size = max_entity_size
        self.max_text_size = max_text_size
        self.max_attributes = max_attributes
        self.max_attribute_size = max_attribute_size
        self.max_name_size = max_name_size
        self.max_comment_size = max_comment_size
        self.max_input_size = max_input_size
        self.max_elements = max_elements
        self._chunks: list[bytes] = []
        self._total_size: int = 0

    def feed(self, data: str | bytes) -> None:
        """Feed a chunk of XML data to the parser, enforcing `max_input_size`.

        Args:
            data: XML fragment as `str` or `bytes`.

        Raises:
            DefusedXmlException: If the accumulated input exceeds `max_input_size`.
        """
        raw_bytes = data.encode("utf-8") if isinstance(data, str) else data
        if self._total_size + len(raw_bytes) > self.max_input_size:
            self._chunks.clear()
            self._total_size = 0
            raise DefusedXmlException(
                f"Input document size exceeds maximum allowed limit ({self.max_input_size} bytes)"
            )
        self._total_size += len(raw_bytes)
        self._chunks.append(raw_bytes)

    def close(self) -> Element:
        """Finish feeding data, parse the buffered document, and return the root `Element`.

        Returns:
            The root `Element` of the parsed XML document.
        """
        combined = b"".join(self._chunks)
        self._chunks.clear()
        self._total_size = 0

        return _parse_xml(
            combined,
            forbid_dtd=self.forbid_dtd,
            forbid_entities=self.forbid_entities,
            forbid_external=self.forbid_external,
            max_depth=self.max_depth,
            max_entity_size=self.max_entity_size,
            max_text_size=self.max_text_size,
            max_attributes=self.max_attributes,
            max_attribute_size=self.max_attribute_size,
            max_name_size=self.max_name_size,
            max_comment_size=self.max_comment_size,
            max_input_size=self.max_input_size,
            max_elements=self.max_elements,
        )


DefusedXMLParser = XMLParser


class ElementTree(_StdlibElementTree):
    """ElementTree wrapper with safe parsing capabilities."""

    def __init__(
        self,
        element: Element | None = None,
        file: str | bytes | os.PathLike[Any] | IO[Any] | None = None,
    ) -> None:
        """Initialize an `ElementTree` wrapper.

        Args:
            element: Optional root `Element` instance.
            file: Optional path or file-like stream to parse immediately.
        """
        super().__init__(element=element, file=file)

    def getroot(self) -> Element:
        """Return the root `Element` of this tree.

        Returns:
            The root `Element` instance.
        """
        return super().getroot()  # type: ignore[return-value]

    def parse(  # type: ignore[override]
        self,
        source: str | bytes | os.PathLike[Any] | IO[Any],
        parser: Any | None = None,
        forbid_dtd: bool = False,
        forbid_entities: bool = True,
        forbid_external: bool = True,
        max_depth: int = 1000,
        max_entity_size: int = 10 * 1024 * 1024,
        max_text_size: int = 100 * 1024 * 1024,
        max_attributes: int = 1000,
        max_attribute_size: int = 10 * 1024 * 1024,
        max_name_size: int = 1024,
        max_comment_size: int = 10 * 1024 * 1024,
        max_input_size: int = 256 * 1024 * 1024,
        max_elements: int = 5_000_000,
    ) -> Element:
        """Load an external XML document into this `ElementTree` and return the root `Element`.

        Args:
            source: File path or file-like object containing XML data.
            parser: Optional parser instance (retained for stdlib compatibility).
            forbid_dtd: Disallow `<!DOCTYPE ...>` declarations.
            forbid_entities: Disallow `<!ENTITY ...>` declarations and custom entity references.
            forbid_external: Disallow external `SYSTEM` and `PUBLIC` references.
            max_depth: Maximum allowed element nesting depth.
            max_entity_size: Maximum size in bytes of an entity value.
            max_text_size: Maximum accumulated text and synthesized attribute size in bytes.
            max_attributes: Maximum number of attributes per element.
            max_attribute_size: Maximum size in bytes of a single attribute value.
            max_name_size: Maximum length in bytes of an XML element or attribute name.
            max_comment_size: Maximum size in bytes of a comment or processing instruction.
            max_input_size: Maximum size in bytes of the raw input document.
            max_elements: Maximum total number of elements in the document.

        Returns:
            The parsed root `Element`.
        """
        root = parse(
            source=source,
            parser=parser,
            forbid_dtd=forbid_dtd,
            forbid_entities=forbid_entities,
            forbid_external=forbid_external,
            max_depth=max_depth,
            max_entity_size=max_entity_size,
            max_text_size=max_text_size,
            max_attributes=max_attributes,
            max_attribute_size=max_attribute_size,
            max_name_size=max_name_size,
            max_comment_size=max_comment_size,
            max_input_size=max_input_size,
            max_elements=max_elements,
        ).getroot()
        self._setroot(root)
        return root


def fromstring(
    text: str | bytes,
    parser: Any | None = None,
    forbid_dtd: bool = False,
    forbid_entities: bool = True,
    forbid_external: bool = True,
    max_depth: int = 1000,
    max_entity_size: int = 10 * 1024 * 1024,
    max_text_size: int = 100 * 1024 * 1024,
    max_attributes: int = 1000,
    max_attribute_size: int = 10 * 1024 * 1024,
    max_name_size: int = 1024,
    max_comment_size: int = 10 * 1024 * 1024,
    max_input_size: int = 256 * 1024 * 1024,
    max_elements: int = 5_000_000,
) -> Element:
    """Parse XML from string or bytes with strict security defenses.

    Args:
        text: XML document string or byte sequence.
        parser: Optional parser instance (retained for stdlib compatibility).
        forbid_dtd: Disallow `<!DOCTYPE ...>` declarations.
        forbid_entities: Disallow `<!ENTITY ...>` declarations and custom entity references.
        forbid_external: Disallow external `SYSTEM` and `PUBLIC` references.
        max_depth: Maximum allowed element nesting depth.
        max_entity_size: Maximum size in bytes of an entity value.
        max_text_size: Maximum accumulated text and synthesized attribute size in bytes.
        max_attributes: Maximum number of attributes per element.
        max_attribute_size: Maximum size in bytes of a single attribute value.
        max_name_size: Maximum length in bytes of an XML element or attribute name.
        max_comment_size: Maximum size in bytes of a comment or processing instruction.
        max_input_size: Maximum size in bytes of the raw input document.
        max_elements: Maximum total number of elements in the document.

    Returns:
        The parsed root `Element`.
    """
    return _parse_xml(
        text,
        forbid_dtd=forbid_dtd,
        forbid_entities=forbid_entities,
        forbid_external=forbid_external,
        max_depth=max_depth,
        max_entity_size=max_entity_size,
        max_text_size=max_text_size,
        max_attributes=max_attributes,
        max_attribute_size=max_attribute_size,
        max_name_size=max_name_size,
        max_comment_size=max_comment_size,
        max_input_size=max_input_size,
        max_elements=max_elements,
    )


XML = fromstring


def XMLID(
    text: str | bytes,
    parser: Any | None = None,
    forbid_dtd: bool = False,
    forbid_entities: bool = True,
    forbid_external: bool = True,
    max_depth: int = 1000,
    max_entity_size: int = 10 * 1024 * 1024,
    max_text_size: int = 100 * 1024 * 1024,
    max_attributes: int = 1000,
    max_attribute_size: int = 10 * 1024 * 1024,
    max_name_size: int = 1024,
    max_comment_size: int = 10 * 1024 * 1024,
    max_input_size: int = 256 * 1024 * 1024,
    max_elements: int = 5_000_000,
) -> tuple[Element, dict[str, Element]]:
    """Parse XML from a string or bytes and return `(root_element, id_dict)` safely.

    Args:
        text: XML document string or byte sequence.
        parser: Optional parser instance (retained for stdlib compatibility).
        forbid_dtd: Disallow `<!DOCTYPE ...>` declarations.
        forbid_entities: Disallow `<!ENTITY ...>` declarations and custom entity references.
        forbid_external: Disallow external `SYSTEM` and `PUBLIC` references.
        max_depth: Maximum allowed element nesting depth.
        max_entity_size: Maximum size in bytes of an entity value.
        max_text_size: Maximum accumulated text and synthesized attribute size in bytes.
        max_attributes: Maximum number of attributes per element.
        max_attribute_size: Maximum size in bytes of a single attribute value.
        max_name_size: Maximum length in bytes of an XML element or attribute name.
        max_comment_size: Maximum size in bytes of a comment or processing instruction.
        max_input_size: Maximum size in bytes of the raw input document.
        max_elements: Maximum total number of elements in the document.

    Returns:
        A tuple of `(root_element, id_map)` mapping `id` attribute values to `Element` objects.
    """
    root = fromstring(
        text,
        parser=parser,
        forbid_dtd=forbid_dtd,
        forbid_entities=forbid_entities,
        forbid_external=forbid_external,
        max_depth=max_depth,
        max_entity_size=max_entity_size,
        max_text_size=max_text_size,
        max_attributes=max_attributes,
        max_attribute_size=max_attribute_size,
        max_name_size=max_name_size,
        max_comment_size=max_comment_size,
        max_input_size=max_input_size,
        max_elements=max_elements,
    )
    ids: dict[str, Element] = {}
    for elem in root.iter():
        elem_id = elem.get("id")
        if elem_id:
            ids[elem_id] = elem
    return root, ids


def fromstringlist(
    sequence: list[str] | list[bytes] | tuple[str, ...] | tuple[bytes, ...],
    parser: Any | None = None,
    forbid_dtd: bool = False,
    forbid_entities: bool = True,
    forbid_external: bool = True,
    max_depth: int = 1000,
    max_entity_size: int = 10 * 1024 * 1024,
    max_text_size: int = 100 * 1024 * 1024,
    max_attributes: int = 1000,
    max_attribute_size: int = 10 * 1024 * 1024,
    max_name_size: int = 1024,
    max_comment_size: int = 10 * 1024 * 1024,
    max_input_size: int = 256 * 1024 * 1024,
    max_elements: int = 5_000_000,
) -> Element:
    """Parse XML from a sequence of string or bytes fragments.

    Args:
        sequence: Sequence of XML string or bytes chunks.
        parser: Optional parser instance (retained for stdlib compatibility).
        forbid_dtd: Disallow `<!DOCTYPE ...>` declarations.
        forbid_entities: Disallow `<!ENTITY ...>` declarations and custom entity references.
        forbid_external: Disallow external `SYSTEM` and `PUBLIC` references.
        max_depth: Maximum allowed element nesting depth.
        max_entity_size: Maximum size in bytes of an entity value.
        max_text_size: Maximum accumulated text and synthesized attribute size in bytes.
        max_attributes: Maximum number of attributes per element.
        max_attribute_size: Maximum size in bytes of a single attribute value.
        max_name_size: Maximum length in bytes of an XML element or attribute name.
        max_comment_size: Maximum size in bytes of a comment or processing instruction.
        max_input_size: Maximum size in bytes of the raw input document.
        max_elements: Maximum total number of elements in the document.

    Returns:
        The parsed root `Element`.

    Raises:
        ParseError: If `sequence` is empty or the XML is malformed.
    """
    if not sequence:
        raise ParseError("No XML root element found")
    first = sequence[0]
    text = "".join(sequence) if isinstance(first, str) else b"".join(sequence)  # type: ignore[arg-type]
    return fromstring(
        text,
        parser=parser,
        forbid_dtd=forbid_dtd,
        forbid_entities=forbid_entities,
        forbid_external=forbid_external,
        max_depth=max_depth,
        max_entity_size=max_entity_size,
        max_text_size=max_text_size,
        max_attributes=max_attributes,
        max_attribute_size=max_attribute_size,
        max_name_size=max_name_size,
        max_comment_size=max_comment_size,
        max_input_size=max_input_size,
        max_elements=max_elements,
    )


def parse(
    source: str | bytes | os.PathLike[Any] | IO[Any],
    parser: Any | None = None,
    forbid_dtd: bool = False,
    forbid_entities: bool = True,
    forbid_external: bool = True,
    max_depth: int = 1000,
    max_entity_size: int = 10 * 1024 * 1024,
    max_text_size: int = 100 * 1024 * 1024,
    max_attributes: int = 1000,
    max_attribute_size: int = 10 * 1024 * 1024,
    max_name_size: int = 1024,
    max_comment_size: int = 10 * 1024 * 1024,
    max_input_size: int = 256 * 1024 * 1024,
    max_elements: int = 5_000_000,
) -> ElementTree:
    """Parse an XML document from a filepath or file-like object into an `ElementTree`.

    Args:
        source: File path or file-like object with a `.read()` method.
        parser: Optional parser instance (retained for stdlib compatibility).
        forbid_dtd: Disallow `<!DOCTYPE ...>` declarations.
        forbid_entities: Disallow `<!ENTITY ...>` declarations and custom entity references.
        forbid_external: Disallow external `SYSTEM` and `PUBLIC` references.
        max_depth: Maximum allowed element nesting depth.
        max_entity_size: Maximum size in bytes of an entity value.
        max_text_size: Maximum accumulated text and synthesized attribute size in bytes.
        max_attributes: Maximum number of attributes per element.
        max_attribute_size: Maximum size in bytes of a single attribute value.
        max_name_size: Maximum length in bytes of an XML element or attribute name.
        max_comment_size: Maximum size in bytes of a comment or processing instruction.
        max_input_size: Maximum size in bytes of the raw input document.
        max_elements: Maximum total number of elements in the document.

    Returns:
        An `ElementTree` wrapper initialized with the parsed document root.

    Raises:
        TypeError: If `source` is not a path or readable file-like object.
    """
    if isinstance(source, (str, bytes, os.PathLike)):
        with open(source, "rb") as f:
            root = _parse_xml(
                f,
                forbid_dtd=forbid_dtd,
                forbid_entities=forbid_entities,
                forbid_external=forbid_external,
                max_depth=max_depth,
                max_entity_size=max_entity_size,
                max_text_size=max_text_size,
                max_attributes=max_attributes,
                max_attribute_size=max_attribute_size,
                max_name_size=max_name_size,
                max_comment_size=max_comment_size,
                max_input_size=max_input_size,
                max_elements=max_elements,
            )
    elif hasattr(source, "read"):
        root = _parse_xml(
            source,
            forbid_dtd=forbid_dtd,
            forbid_entities=forbid_entities,
            forbid_external=forbid_external,
            max_depth=max_depth,
            max_entity_size=max_entity_size,
            max_text_size=max_text_size,
            max_attributes=max_attributes,
            max_attribute_size=max_attribute_size,
            max_name_size=max_name_size,
            max_comment_size=max_comment_size,
            max_input_size=max_input_size,
            max_elements=max_elements,
        )
    else:
        raise TypeError(f"Invalid source type for parse(): {type(source).__name__}")

    tree = ElementTree()
    tree._setroot(root)
    return tree


class iterparse:
    """Incrementally parse an XML document, yielding (event, elem) pairs safely."""

    def __init__(
        self,
        source: str | bytes | os.PathLike[Any] | IO[Any],
        events: tuple[str, ...] | list[str] | None = None,
        parser: Any | None = None,
        forbid_dtd: bool = False,
        forbid_entities: bool = True,
        forbid_external: bool = True,
        max_depth: int = 1000,
        max_entity_size: int = 10 * 1024 * 1024,
        max_text_size: int = 100 * 1024 * 1024,
        max_attributes: int = 1000,
        max_attribute_size: int = 10 * 1024 * 1024,
        max_name_size: int = 1024,
        max_comment_size: int = 10 * 1024 * 1024,
        max_input_size: int = 256 * 1024 * 1024,
        max_elements: int = 5_000_000,
    ) -> None:
        """Initialize an `iterparse` iterator over an XML document.

        Args:
            source: File path or file-like object containing XML data.
            events: Sequence of event names to yield (`"start"`, `"end"`). Defaults to `("end",)`.
            parser: Optional parser instance (retained for stdlib compatibility).
            forbid_dtd: Disallow `<!DOCTYPE ...>` declarations.
            forbid_entities: Disallow `<!ENTITY ...>` declarations and custom entity references.
            forbid_external: Disallow external `SYSTEM` and `PUBLIC` references.
            max_depth: Maximum allowed element nesting depth.
            max_entity_size: Maximum size in bytes of an entity value.
            max_text_size: Maximum accumulated text and synthesized attribute size in bytes.
            max_attributes: Maximum number of attributes per element.
            max_attribute_size: Maximum size in bytes of a single attribute value.
            max_name_size: Maximum length in bytes of an XML element or attribute name.
            max_comment_size: Maximum size in bytes of a comment or processing instruction.
            max_input_size: Maximum size in bytes of the raw input document.
            max_elements: Maximum total number of elements in the document.
        """
        self.root: Element | None = None
        tree = parse(
            source,
            parser=parser,
            forbid_dtd=forbid_dtd,
            forbid_entities=forbid_entities,
            forbid_external=forbid_external,
            max_depth=max_depth,
            max_entity_size=max_entity_size,
            max_text_size=max_text_size,
            max_attributes=max_attributes,
            max_attribute_size=max_attribute_size,
            max_name_size=max_name_size,
            max_comment_size=max_comment_size,
            max_input_size=max_input_size,
            max_elements=max_elements,
        )
        self.root = tree.getroot()
        self._events = tuple(events or ("end",))
        self._iter = self._generate_events(self.root, self._events)

    def _generate_events(self, root: Element, events: tuple[str, ...]) -> Iterator[tuple[str, Any]]:
        wanted = set(events)
        stack: list[tuple[Element, bool]] = [(root, False)]
        while stack:
            elem, visited = stack.pop()
            if visited:
                if "end" in wanted:
                    yield ("end", elem)
            else:
                if "start" in wanted:
                    yield ("start", elem)
                stack.append((elem, True))
                for child in reversed(elem):
                    stack.append((child, False))

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        """Return the iterator instance."""
        return self

    def __next__(self) -> tuple[str, Any]:
        """Return the next `(event, elem)` pair from the document."""
        return next(self._iter)


__all__ = [
    "PI",
    "XML",
    "XMLID",
    "Comment",
    "DTDForbidden",
    "DefusedXMLParser",
    "DefusedXmlException",
    "Element",
    "ElementTree",
    "EntitiesForbidden",
    "ExternalReferenceForbidden",
    "NotSupportedError",
    "ParseError",
    "ProcessingInstruction",
    "QName",
    "SubElement",
    "TreeBuilder",
    "XMLParse",
    "XMLParser",
    "canonicalize",
    "dump",
    "fromstring",
    "fromstringlist",
    "indent",
    "iterparse",
    "parse",
    "register_namespace",
    "tostring",
    "tostringlist",
]
