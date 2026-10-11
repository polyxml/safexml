"""Pytest fixtures and security attack payloads for safexml testing."""

from __future__ import annotations

import pytest

XML_SIMPLE = """<?xml version="1.0" encoding="utf-8"?>
<catalog id="cat-1">
    <book id="bk101">
        <author>Gambardella, Matthew</author>
        <title>XML Developer's Guide</title>
        <genre>Computer</genre>
        <price>44.95</price>
        <publish_date>2000-10-01</publish_date>
        <description>An in-depth look at creating applications with XML.</description>
    </book>
    <book id="bk102">
        <author>Ralls, Kim</author>
        <title>Midnight Rain</title>
        <genre>Fantasy</genre>
        <price>5.95</price>
        <publish_date>2000-12-16</publish_date>
        <description>A former architect battles corporate zombies.</description>
    </book>
</catalog>
"""

XML_NAMESPACES = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
    <title>Example Feed</title>
    <entry>
        <title>Atom-Powered Robots Run Amok</title>
        <id>urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a</id>
        <dc:creator>John Doe</dc:creator>
    </entry>
</feed>
"""

# Attack 1: Billion Laughs (Exponential entity expansion)
XML_BOMB = """<?xml version="1.0"?>
<!DOCTYPE xmlbomb [
  <!ENTITY a "1234567890">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;">
  <!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;">
  <!ENTITY e "&d;&d;&d;&d;&d;&d;&d;&d;">
]>
<bomb>&e;</bomb>
"""

# Attack 2: Quadratic blowup (Single entity repeated thousands of times)
XML_QUADRATIC = (
    """<?xml version="1.0"?>
<!DOCTYPE bomb [
  <!ENTITY a "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">
]>
<bomb>"""
    + ("&a;" * 500)
    + """</bomb>
"""
)

# Attack 3: External XML Entity (XXE) with SYSTEM URI
XML_EXTERNAL = """<?xml version="1.0"?>
<!DOCTYPE external [
  <!ENTITY ee SYSTEM "http://www.w3schools.com/xml/note.xml">
]>
<root>&ee;</root>
"""

# Attack 4: External XML Entity with file:// URI
XML_EXTERNAL_FILE = """<?xml version="1.0"?>
<!DOCTYPE external [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>
"""

# Attack 5: Cyclic Entity Reference
XML_CYCLIC = """<?xml version="1.0"?>
<!DOCTYPE xmlbomb [
  <!ENTITY a "123 &b;">
  <!ENTITY b "&a;">
]>
<bomb>&a;</bomb>
"""

# Attack 6: External DTD Injection
XML_EXTERNAL_DTD = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
    <head/>
    <body>text</body>
</html>
"""


@pytest.fixture
def xml_simple() -> str:
    return XML_SIMPLE


@pytest.fixture
def xml_namespaces() -> str:
    return XML_NAMESPACES


@pytest.fixture
def xml_bomb() -> str:
    return XML_BOMB


@pytest.fixture
def xml_quadratic() -> str:
    return XML_QUADRATIC


@pytest.fixture
def xml_external() -> str:
    return XML_EXTERNAL


@pytest.fixture
def xml_external_file() -> str:
    return XML_EXTERNAL_FILE


@pytest.fixture
def xml_cyclic() -> str:
    return XML_CYCLIC


@pytest.fixture
def xml_external_dtd() -> str:
    return XML_EXTERNAL_DTD
