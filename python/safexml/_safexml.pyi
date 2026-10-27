"""Type stubs for the native Rust extension `safexml._safexml`."""

from __future__ import annotations

from typing import IO, Any, Protocol
from xml.etree.ElementTree import Element

class _SupportsRead(Protocol):
    def read(self, size: int = ..., /) -> str | bytes: ...

def version() -> str:
    """Return the compiled `safexml` package version string.

    Returns:
        The semantic version string compiled from `Cargo.toml`.
    """

def parse_xml(
    source: str | bytes | IO[Any] | _SupportsRead | Any,
    forbid_dtd: bool = False,
    forbid_entities: bool = True,
    forbid_external: bool = True,
    max_depth: int = 1000,
    max_entity_size: int = 10485760,
    max_text_size: int = 104857600,
    max_attributes: int = 1000,
    max_attribute_size: int = 10485760,
    max_name_size: int = 1024,
    max_comment_size: int = 10485760,
    max_input_size: int = 268435456,
    max_elements: int = 5000000,
) -> Element:
    """Parse an XML document from string, bytes, or readable stream into an Element.

    Args:
        source: XML string, bytes, or file-like object with a `.read()` method.
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
        The root `xml.etree.ElementTree.Element` of the parsed document.

    Raises:
        DTDForbidden: If `forbid_dtd=True` and a `DOCTYPE` is encountered.
        EntitiesForbidden: If `forbid_entities=True` and an entity declaration or reference is encountered.
        ExternalReferenceForbidden: If `forbid_external=True` and an external reference is encountered.
        ParseError: If the XML document is not well-formed.
        DefusedXmlException: If any configured resource limit is exceeded.
    """
