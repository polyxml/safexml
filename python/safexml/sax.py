"""safexml.sax: Secure drop-in replacement for xml.sax and defusedxml.sax."""

from __future__ import annotations

import io
import os
from typing import IO, Any
from xml.sax import (
    ContentHandler,
    ErrorHandler,
    InputSource,
    SAXException,
    SAXParseException,
)
from xml.sax.xmlreader import AttributesImpl, XMLReader

from safexml import ElementTree as _safexml_etree


def _walk_element(root: _safexml_etree.Element, handler: ContentHandler) -> None:
    stack: list[tuple[_safexml_etree.Element, bool, str | None]] = [(root, False, None)]
    while stack:
        elem, visited, tail = stack.pop()
        if visited:
            handler.endElement(elem.tag)
            if tail:
                handler.characters(tail)
        else:
            handler.startElement(elem.tag, AttributesImpl(elem.attrib))
            if elem.text:
                handler.characters(elem.text)
            stack.append((elem, True, tail))
            for child in reversed(elem):
                stack.append((child, False, child.tail))


class SafeXMLParser(XMLReader):
    """Secure SAX XMLReader powered by SafeXML."""

    def __init__(
        self,
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
        max_elements: int = 5_000_000,
        max_input_size: int = 256 * 1024 * 1024,
    ) -> None:
        """Initialize a `SafeXMLParser` SAX reader.

        Args:
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
            max_elements: Maximum total number of elements in the document.
            max_input_size: Maximum size in bytes of the raw input document.
        """
        super().__init__()
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
        self.max_elements = max_elements
        self.max_input_size = max_input_size
        self._content_handler = ContentHandler()
        self._error_handler = ErrorHandler()

    def setContentHandler(self, handler: ContentHandler) -> None:  # type: ignore[override]
        """Set the SAX `ContentHandler` for document events.

        Args:
            handler: The `ContentHandler` instance to receive SAX callbacks.
        """
        self._content_handler = handler

    def getContentHandler(self) -> ContentHandler:
        """Return the active SAX `ContentHandler`.

        Returns:
            The currently registered `ContentHandler`.
        """
        return self._content_handler

    def setErrorHandler(self, handler: ErrorHandler) -> None:  # type: ignore[override]
        """Set the SAX `ErrorHandler` for error callbacks.

        Args:
            handler: The `ErrorHandler` instance.
        """
        self._error_handler = handler

    def getErrorHandler(self) -> ErrorHandler:
        """Return the active SAX `ErrorHandler`.

        Returns:
            The currently registered `ErrorHandler`.
        """
        return self._error_handler

    def parse(  # type: ignore[override]
        self, source: str | bytes | os.PathLike[Any] | IO[Any] | InputSource
    ) -> None:
        """Parse an XML source and emit SAX events to the configured `ContentHandler`.

        Args:
            source: File path, file-like object, or SAX `InputSource`.
        """
        actual_source: Any
        if isinstance(source, InputSource):
            byte_stream = source.getByteStream()
            char_stream = source.getCharacterStream()
            if byte_stream is not None:
                actual_source = byte_stream
            elif char_stream is not None:
                actual_source = char_stream
            else:
                actual_source = source.getSystemId()
        else:
            actual_source = source

        tree = _safexml_etree.parse(
            actual_source,
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
            max_elements=self.max_elements,
            max_input_size=self.max_input_size,
        )
        root = tree.getroot()
        self._content_handler.startDocument()
        _walk_element(root, self._content_handler)
        self._content_handler.endDocument()


def make_parser(parser_list: list[str] | None = None) -> SafeXMLParser:
    """Return a safe XML SAX parser instance.

    Args:
        parser_list: Optional list of parser module names (ignored; retained for stdlib compatibility).

    Returns:
        A `SafeXMLParser` instance.
    """
    return SafeXMLParser()


def parse(
    source: str | bytes | os.PathLike[Any] | IO[Any] | InputSource,
    handler: ContentHandler,
    errorHandler: ErrorHandler | None = None,
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
    max_elements: int = 5_000_000,
    max_input_size: int = 256 * 1024 * 1024,
) -> None:
    """Parse an XML source into a SAX `ContentHandler` safely.

    Args:
        source: File path, file-like object, or SAX `InputSource`.
        handler: SAX `ContentHandler` to receive document events.
        errorHandler: Optional SAX `ErrorHandler` instance.
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
        max_elements: Maximum total number of elements in the document.
        max_input_size: Maximum size in bytes of the raw input document.
    """
    parser = make_parser()
    parser.forbid_dtd = forbid_dtd
    parser.forbid_entities = forbid_entities
    parser.forbid_external = forbid_external
    parser.max_depth = max_depth
    parser.max_entity_size = max_entity_size
    parser.max_text_size = max_text_size
    parser.max_attributes = max_attributes
    parser.max_attribute_size = max_attribute_size
    parser.max_name_size = max_name_size
    parser.max_comment_size = max_comment_size
    parser.max_elements = max_elements
    parser.max_input_size = max_input_size
    parser.setContentHandler(handler)
    if errorHandler is not None:
        parser.setErrorHandler(errorHandler)
    parser.parse(source)


def parseString(
    string: str | bytes,
    handler: ContentHandler,
    errorHandler: ErrorHandler | None = None,
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
    max_elements: int = 5_000_000,
    max_input_size: int = 256 * 1024 * 1024,
) -> None:
    """Parse an XML string or bytes into a SAX `ContentHandler` safely.

    Args:
        string: XML document string or byte sequence.
        handler: SAX `ContentHandler` to receive document events.
        errorHandler: Optional SAX `ErrorHandler` instance.
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
        max_elements: Maximum total number of elements in the document.
        max_input_size: Maximum size in bytes of the raw input document.
    """
    stream: IO[Any] = io.StringIO(string) if isinstance(string, str) else io.BytesIO(string)
    parse(
        stream,
        handler=handler,
        errorHandler=errorHandler,
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
        max_elements=max_elements,
        max_input_size=max_input_size,
    )


__all__ = [
    "ContentHandler",
    "ErrorHandler",
    "InputSource",
    "SAXException",
    "SAXParseException",
    "SafeXMLParser",
    "make_parser",
    "parse",
    "parseString",
]
