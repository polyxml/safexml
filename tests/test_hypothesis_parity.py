"""Property-based differential testing between safexml and xml.etree.ElementTree using Hypothesis."""

from __future__ import annotations

from xml.etree import ElementTree as std_ET

from hypothesis import given, settings
from hypothesis import strategies as st

import safexml


def assert_trees_equal(e1: std_ET.Element, e2: std_ET.Element) -> None:
    """Recursively assert that two Element instances represent identical DOM trees."""
    assert e1.tag == e2.tag
    assert e1.attrib == e2.attrib
    assert (e1.text or "") == (e2.text or "")
    assert (e1.tail or "") == (e2.tail or "")
    assert len(e1) == len(e2)
    for c1, c2 in zip(e1, e2, strict=True):
        assert_trees_equal(c1, c2)


# Strategies for generating valid XML components
xml_names = st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,15}", fullmatch=True)

# Valid XML 1.0 characters without special delimiters
valid_xml_chars = st.characters(
    min_codepoint=0x20,
    max_codepoint=0xD7FF,
    blacklist_characters=("<", ">", "&", '"', "'", "\x7f"),
)

xml_text = st.text(alphabet=valid_xml_chars, max_size=50)
xml_attr_dict = st.dictionaries(
    keys=xml_names,
    values=st.text(alphabet=valid_xml_chars, max_size=30),
    max_size=5,
)


@st.composite
def xml_tree_strategy(draw: st.DrawFn) -> str:
    """Generate arbitrary valid XML document string."""
    root_tag = draw(xml_names)
    num_children = draw(st.integers(min_value=0, max_value=5))
    children_xml = []

    for _ in range(num_children):
        child_tag = draw(xml_names)
        child_attrs = draw(xml_attr_dict)
        attr_str = "".join(f' {k}="{v}"' for k, v in child_attrs.items())
        child_text = draw(xml_text)
        children_xml.append(f"<{child_tag}{attr_str}>{child_text}</{child_tag}>")

    root_attrs = draw(xml_attr_dict)
    root_attr_str = "".join(f' {k}="{v}"' for k, v in root_attrs.items())
    body = "".join(children_xml)
    return f"<{root_tag}{root_attr_str}>{body}</{root_tag}>"


@settings(max_examples=50, deadline=None)
@given(xml_str=xml_tree_strategy())
def test_hypothesis_dom_equivalence(xml_str: str) -> None:
    """Hypothesis property: safexml produces an identical DOM to xml.etree.ElementTree on valid XML."""
    xml_bytes = xml_str.encode("utf-8")
    elem_std = std_ET.fromstring(xml_bytes)
    elem_safe = safexml.fromstring(xml_bytes)

    assert_trees_equal(elem_std, elem_safe)
