"""Common exceptions and constants for safexml.

Drop-in compatible with `defusedxml.common`, with fixes for modern Python (>=3.12)
and improved exception formatting for `rich` tracebacks.
"""

from __future__ import annotations

import xml.etree.ElementTree as _stdlib_etree


class DefusedXmlException(ValueError):
    """Base exception for all XML security violations in safexml."""

    def __init__(self, message: str = "XML security violation detected") -> None:
        """Initialize the base security exception.

        Args:
            message: Human-readable description of the security violation.
        """
        super().__init__(message)
        self.message = message

    def __repr__(self) -> str:
        """Return a developer-friendly string representation of the exception."""
        return f"{self.__class__.__name__}({self.message!r})"


class DTDForbidden(DefusedXmlException):
    """Document Type Definition (DTD) is forbidden.

    Raised when a `<!DOCTYPE ...>` declaration is encountered and `forbid_dtd=True`.
    """

    def __init__(
        self,
        name: str,
        sysid: str | None = None,
        pubid: str | None = None,
    ) -> None:
        """Initialize a `DTDForbidden` exception.

        Args:
            name: The declared root element name in the `DOCTYPE`.
            sysid: Optional `SYSTEM` identifier URI.
            pubid: Optional `PUBLIC` identifier string.
        """
        msg = f"DTDForbidden(name='{name}', system_id={sysid!r}, public_id={pubid!r})"
        super().__init__(msg)
        self.name = name
        self.sysid = sysid
        self.pubid = pubid

    def __repr__(self) -> str:
        """Return a developer-friendly string representation of the exception."""
        return (
            f"DTDForbidden(name='{self.name}', system_id={self.sysid!r}, public_id={self.pubid!r})"
        )


class EntitiesForbidden(DefusedXmlException):
    """Entity declaration or reference is forbidden.

    Raised when an `<!ENTITY ...>` declaration or general entity reference
    is encountered and `forbid_entities=True`.
    """

    def __init__(
        self,
        name: str,
        value: str | None = None,
        base: str | None = None,
        sysid: str | None = None,
        pubid: str | None = None,
        notation_name: str | None = None,
    ) -> None:
        """Initialize an `EntitiesForbidden` exception.

        Args:
            name: Name of the forbidden entity.
            value: Optional replacement text of the entity.
            base: Optional base URI for resolving relative references.
            sysid: Optional `SYSTEM` identifier URI.
            pubid: Optional `PUBLIC` identifier string.
            notation_name: Optional `NDATA` notation name for unparsed entities.
        """
        msg = f"EntitiesForbidden(name='{name}', system_id={sysid!r}, public_id={pubid!r})"
        super().__init__(msg)
        self.name = name
        self.value = value
        self.base = base
        self.sysid = sysid
        self.pubid = pubid
        self.notation_name = notation_name

    def __repr__(self) -> str:
        """Return a developer-friendly string representation of the exception."""
        return f"EntitiesForbidden(name='{self.name}', system_id={self.sysid!r}, public_id={self.pubid!r})"


class ExternalReferenceForbidden(DefusedXmlException):
    """Resolving an external XML reference (SYSTEM or PUBLIC) is forbidden.

    Raised when an external entity or external DTD subset reference is encountered
    and `forbid_external=True`.
    """

    def __init__(
        self,
        context: str | None = None,
        base: str | None = None,
        sysid: str | None = None,
        pubid: str | None = None,
    ) -> None:
        """Initialize an `ExternalReferenceForbidden` exception.

        Args:
            context: Optional parser context string.
            base: Optional base URI for resolving relative references.
            sysid: Optional `SYSTEM` identifier URI.
            pubid: Optional `PUBLIC` identifier string.
        """
        msg = f"ExternalReferenceForbidden(system_id={sysid!r}, public_id={pubid!r})"
        super().__init__(msg)
        self.context = context
        self.base = base
        self.sysid = sysid
        self.pubid = pubid

    def __repr__(self) -> str:
        """Return a developer-friendly string representation of the exception."""
        return f"ExternalReferenceForbidden(system_id={self.sysid!r}, public_id={self.pubid!r})"


class NotSupportedError(DefusedXmlException):
    """The requested operation or XML feature is not supported."""


class ParseError(_stdlib_etree.ParseError, DefusedXmlException):
    """Raised when XML syntax parsing fails."""

    def __init__(self, message: str = "XML parse error") -> None:
        """Initialize a `ParseError` exception.

        Args:
            message: Details of the XML syntax or well-formedness error.
        """
        super().__init__(message)
        self.message = message

    def __repr__(self) -> str:
        """Return a developer-friendly string representation of the exception."""
        return f"{self.__class__.__name__}({self.message!r})"


__all__ = [
    "DTDForbidden",
    "DefusedXmlException",
    "EntitiesForbidden",
    "ExternalReferenceForbidden",
    "NotSupportedError",
    "ParseError",
]
