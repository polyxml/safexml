"""Type stubs for the native Rust extension `safexml._safexml`."""

from __future__ import annotations

from typing import IO, Any, Protocol
from xml.etree.ElementTree import Element

class _SupportsRead(Protocol):
    def read(self, size: int = ..., /) -> str | bytes: ...

def version() -> str: ...
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
) -> Element: ...
