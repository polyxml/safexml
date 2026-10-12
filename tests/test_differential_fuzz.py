"""Structure-aware automated differential fuzzing against stdlib ElementTree and defusedxml."""

from __future__ import annotations

import contextlib
from pathlib import Path
from xml.etree import ElementTree as std_ET

import defusedxml.common as defused_common
import defusedxml.ElementTree as defused_ET
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import safexml
from safexml.common import DefusedXmlException


def compute_dom_size(elem: std_ET.Element) -> int:
    """Compute total byte size of expanded DOM nodes (tags, attributes, text, tail)."""
    size = len(elem.tag.encode("utf-8"))
    for k, v in elem.attrib.items():
        size += len(k.encode("utf-8")) + len(v.encode("utf-8"))
    if elem.text:
        size += len(elem.text.encode("utf-8"))
    if elem.tail:
        size += len(elem.tail.encode("utf-8"))
    for child in elem:
        size += compute_dom_size(child)
    return size


def assert_dom_equal(e1: std_ET.Element, e2: std_ET.Element) -> None:
    """Recursively assert that two Element instances represent identical DOM trees."""
    assert e1.tag == e2.tag, f"Tag mismatch: {e1.tag} != {e2.tag}"
    assert e1.attrib == e2.attrib, f"Attribute mismatch at <{e1.tag}>: {e1.attrib} != {e2.attrib}"
    assert (e1.text or "") == (e2.text or ""), (
        f"Text mismatch at <{e1.tag}>: {repr(e1.text)} != {repr(e2.text)}"
    )
    assert (e1.tail or "") == (e2.tail or ""), (
        f"Tail mismatch at <{e1.tag}>: {repr(e1.tail)} != {repr(e2.tail)}"
    )
    assert len(e1) == len(e2), f"Child count mismatch at <{e1.tag}>: {len(e1)} != {len(e2)}"
    for c1, c2 in zip(e1, e2, strict=True):
        assert_dom_equal(c1, c2)


# Strategies for generating valid XML components
xml_ident = st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,12}", fullmatch=True)
xml_chars = st.characters(
    min_codepoint=0x20,
    max_codepoint=0xD7FF,
    blacklist_characters=("<", ">", "&", '"', "'", "\x7f"),
)
xml_attr_dict = st.dictionaries(
    keys=xml_ident,
    values=st.text(alphabet=xml_chars, max_size=20),
    max_size=4,
)


@st.composite
def structured_xml_strategy(draw: st.DrawFn) -> bytes:
    """Generate arbitrary structured XML documents with namespaces, attributes, comments, and CDATA."""
    root_tag = draw(xml_ident)
    ns_uri = draw(
        st.one_of(st.none(), st.sampled_from(["http://example.com/ns1", "http://example.org/ns2"]))
    )
    ns_attr = f' xmlns="{ns_uri}"' if ns_uri else ""

    num_children = draw(st.integers(min_value=0, max_value=4))
    children = []

    for _ in range(num_children):
        c_tag = draw(xml_ident)
        c_attrs = draw(xml_attr_dict)
        attr_str = "".join(f' {k}="{v}"' for k, v in c_attrs.items())
        c_text = draw(st.text(alphabet=xml_chars, max_size=30))
        include_cdata = draw(st.booleans())
        cdata_str = (
            f"<![CDATA[{draw(st.text(alphabet=xml_chars, max_size=20))}]]>" if include_cdata else ""
        )
        children.append(f"<{c_tag}{attr_str}>{c_text}{cdata_str}</{c_tag}>")

    root_attrs = draw(xml_attr_dict)
    root_attr_str = "".join(f' {k}="{v}"' for k, v in root_attrs.items())
    body = "".join(children)
    xml_str = f"<{root_tag}{ns_attr}{root_attr_str}>{body}</{root_tag}>"
    return xml_str.encode("utf-8")


@st.composite
def mutated_xml_strategy(draw: st.DrawFn) -> bytes:
    """Generate XML with deliberate structural mutations to test rejection parity."""
    valid_xml = draw(structured_xml_strategy())
    mutation_type = draw(
        st.sampled_from(
            [
                "truncate",
                "corrupt_end_tag",
                "junk_after_root",
                "unclosed_quote",
                "illegal_control_char",
                "null_byte",
            ]
        )
    )

    if mutation_type == "truncate" and len(valid_xml) > 5:
        cutoff = draw(st.integers(min_value=1, max_value=len(valid_xml) - 2))
        return valid_xml[:cutoff]
    elif mutation_type == "corrupt_end_tag":
        return valid_xml.replace(b"</", b"<//")
    elif mutation_type == "junk_after_root":
        return valid_xml + b"<extra_junk/>"
    elif mutation_type == "unclosed_quote":
        return valid_xml.replace(b'="', b"=")
    elif mutation_type == "illegal_control_char":
        return valid_xml.replace(b">", b">\x0b", 1)
    elif mutation_type == "null_byte":
        return valid_xml.replace(b">", b">\x00", 1)

    return valid_xml + b"<!-- trailing -->"


@settings(max_examples=60, deadline=None)
@given(xml_data=structured_xml_strategy())
def test_differential_fuzz_valid_structured(xml_data: bytes) -> None:
    """Differential Oracle: safexml must produce 1:1 identical DOM to stdlib ElementTree on valid XML."""
    elem_std = std_ET.fromstring(xml_data)
    elem_safe = safexml.fromstring(xml_data)

    assert_dom_equal(elem_std, elem_safe)


@settings(max_examples=60, deadline=None)
@given(xml_data=mutated_xml_strategy())
def test_differential_fuzz_mutated_rejection_parity(xml_data: bytes) -> None:
    """Rejection Parity Oracle: if stdlib rejects malformed XML, safexml must also reject it and never panic."""
    std_failed = False
    try:
        std_ET.fromstring(xml_data)
    except std_ET.ParseError:
        std_failed = True

    safe_failed = False
    try:
        safexml.fromstring(xml_data)
    except DefusedXmlException:
        safe_failed = True

    if std_failed:
        assert safe_failed, f"SafeXML was more permissive than stdlib on: {xml_data!r}"


@settings(max_examples=50, deadline=None)
@given(
    tag=xml_ident,
    text=st.text(alphabet=xml_chars, min_size=5, max_size=50),
    multiplier=st.integers(min_value=1, max_value=5),
)
def test_differential_fuzz_amplification_detector(tag: str, text: str, multiplier: int) -> None:
    """Amplification Detector: assert no unbounded DOM expansion (> 10x) without limit enforcement."""
    xml_str = f"<{tag}>{text * multiplier}</{tag}>"
    xml_bytes = xml_str.encode("utf-8")
    elem = safexml.fromstring(xml_bytes)

    dom_size = compute_dom_size(elem)
    ratio = dom_size / max(len(xml_bytes), 1)

    # Valid regular XML should never expand > 10x its encoded byte size
    assert ratio <= 10.0, (
        f"Amplification ratio {ratio:.2f} exceeded threshold 10.0 for {xml_bytes!r}"
    )


@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE lolz [<!ENTITY lol "lol">]><lolz>&lol;</lolz>',
        b'<!DOCTYPE bomb [<!ENTITY a "123">]><bomb>&a;&a;</bomb>',
        b'<!DOCTYPE root [<!ENTITY ext SYSTEM "http://127.0.0.1:8080/evil.dtd">]><root>&ext;</root>',
        b'<!DOCTYPE root [<!ENTITY % pe SYSTEM "http://127.0.0.1/xxe.dtd">%pe;]><root/>',
    ],
)
def test_differential_fuzz_defusedxml_parity(payload: bytes) -> None:
    """Security Oracle: defusedxml and safexml must both reject entity and DTD attack vectors."""
    with pytest.raises((defused_common.DefusedXmlException, std_ET.ParseError)):
        defused_ET.fromstring(payload)

    with pytest.raises(DefusedXmlException):
        safexml.fromstring(payload)


def test_differential_fuzz_external_dtd_system_reference() -> None:
    """SafeXML blocks external DTD system references by default even when defusedxml requires forbid_dtd=True."""
    payload = b'<!DOCTYPE root SYSTEM "http://127.0.0.1:8080/evil.dtd"><root/>'
    # defusedxml requires explicit forbid_dtd=True to reject external DTD doctype
    with pytest.raises((defused_common.DefusedXmlException, std_ET.ParseError)):
        defused_ET.fromstring(payload, forbid_dtd=True)

    # SafeXML rejects external system references by default (forbid_external=True)
    with pytest.raises(DefusedXmlException):
        safexml.fromstring(payload)


def test_differential_regressions() -> None:
    """Regression Harness: execute all saved regression test cases to verify ongoing stability."""
    regressions_dir = Path(__file__).parent / "regressions"
    regression_files = list(regressions_dir.glob("*.xml"))

    for reg_path in regression_files:
        data = reg_path.read_bytes()
        # Regressions must execute without panic or crash
        with contextlib.suppress(DefusedXmlException):
            safexml.fromstring(data)
