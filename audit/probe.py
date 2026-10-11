"""Read-only audit probes. Run with the locally built safexml installed."""

import io
import json
import subprocess
import sys
import xml.etree.ElementTree as std
from xml.sax.handler import ContentHandler

import defusedxml.ElementTree as defused

import safexml
import safexml.ElementTree as safe


def outcome(fn, value, **kwargs):
    try:
        r = fn(value, **kwargs)
        return {
            "accepted": True,
            "tag": r.tag,
            "text": r.text,
            "attrs": r.attrib,
            "children": len(r),
        }
    except BaseException as e:
        return {"accepted": False, "exception": type(e).__name__, "message": str(e)}


def isolated(xml):
    code = "import safexml; safexml.fromstring(" + repr(xml) + ")"
    try:
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=2)
        return {"exit": p.returncode, "stderr": p.stderr[-1600:]}
    except subprocess.TimeoutExpired:
        return {"timeout": True}


cases = {
    "multiple_roots": "<signed/><unsigned/>",
    "unclosed_after_root": "<signed/><unsigned>",
    "unbound_prefix": "<p:root/>",
    "duplicate_expanded_attribute": '<r xmlns:a="urn:x" xmlns:b="urn:x" a:id="signed" b:id="unsigned"/>',
    "illegal_name": "<1root/>",
    "illegal_text_char": "<r>\x00</r>",
    "illegal_numeric_char": "<r>&#0;</r>",
    "uppercase_hex": "<r>&#X41;</r>",
    "raw_lt_attribute": '<r a="<"/>',
    "bad_comment": "<r><!--a--b--></r>",
    "line_endings": "<r>a\r\nb\rc</r>",
    "attribute_crlf": '<r a="a\r\nb"/>',
    "namespace_entity": '<r xmlns="urn:a&amp;b"/>',
    "latin1": b'<?xml version="1.0" encoding="ISO-8859-1"?><r>\xe9</r>',
    "utf16": "<r>hello</r>".encode("utf-16"),
    "dtd_default_attr": '<!DOCTYPE r [<!ATTLIST r role CDATA "user">]><r/>',
    "entity_in_comment": '<!DOCTYPE r [<!-- <!ENTITY fake "x"> -->]><r/>',
    "unknown_entity_namespace": '<r xmlns="urn:&evil;"/>',
    "doctype_after_root": "<r/><!DOCTYPE r>",
}
results = {
    name: {
        "safe": outcome(safe.fromstring, xml),
        "defused": outcome(defused.fromstring, xml),
        "stdlib": outcome(std.fromstring, xml),
    }
    for name, xml in cases.items()
}
results["isolated"] = {
    name: isolated(xml)
    for name, xml in {
        "unicode_dtd": "<!DOCTYPE r é><r/>",
        "unicode_entity_token": "<!DOCTYPE r [<!ENTITY e é>]><r/>",
        "valid_comment_dtd_panic": "<!DOCTYPE r [<!-- <!ENTITY fake é> -->]><r/>",
        "unterminated_entity_quote": '<!DOCTYPE r [<!ENTITY e "x>]><r/>',
        "valid_deep_default": "<r>" * 1000 + "</r>" * 1000,
    }.items()
}
results["namespace_limits"] = outcome(
    safe.fromstring,
    '<r xmlns:a="' + "x" * 100 + '" xmlns:b="u"/>',
    max_attributes=0,
    max_attribute_size=1,
)
results["entity_limit"] = outcome(
    safe.fromstring,
    '<!DOCTYPE r [<!ENTITY e "' + "x" * 100 + '">]><r/>',
    forbid_entities=False,
    max_entity_size=1,
)
try:
    namespace_xml = '<r xmlns="' + "x" * 16384 + '">' + "<c/>" * 2000 + "</r>"
    namespace_root = safe.fromstring(namespace_xml, max_attributes=0, max_attribute_size=1)
    results["namespace_amplification"] = {
        "input_bytes": len(namespace_xml),
        "expanded_tag_bytes": sum(len(e.tag) for e in namespace_root.iter()),
        "max_name_size": 1024,
        "max_attributes": 0,
        "max_attribute_size": 1,
    }
except BaseException as e:
    results["namespace_amplification"] = {"exception": type(e).__name__, "message": str(e)}

results["deep_wrappers"] = {}
for name, fn in {
    "iterparse": lambda x: list(safe.iterparse(io.StringIO(x))),
    "sax": lambda x: safexml.sax.parseString(x, ContentHandler()),
    "minidom": lambda x: safexml.minidom.parseString(x),
}.items():
    try:
        fn("<r>" * 1000 + "</r>" * 1000)
        results["deep_wrappers"][name] = "accepted"
    except BaseException as e:
        results["deep_wrappers"][name] = type(e).__name__
results["parser_is_safe"] = {"class": safe.XMLParser.__module__}
try:
    parser = safe.XMLParser()
    parser.feed('<!DOCTYPE r [<!ENTITY e "expanded">]><r>&e;</r>')
    results["parser_expands_entity"] = parser.close().text
except BaseException as e:
    results["parser_expands_entity"] = f"blocked: {type(e).__name__}"
results["parse_error_identity"] = issubclass(safe.ParseError, std.ParseError)
results["custom_target"] = outcome(
    safe.fromstring,
    "<r><!--keep--></r>",
    parser=std.XMLParser(target=std.TreeBuilder(insert_comments=True)),
)


class ShortRead:
    def __init__(self):
        self.calls = 0

    def read(self, n):
        self.calls += 1
        return b"<r/>" if self.calls == 1 else b"<extra/>"


stream = ShortRead()
try:
    results["short_read"] = {"tag": safe.parse(stream).getroot().tag, "calls": stream.calls}
except BaseException as e:
    results["short_read"] = {"exception": type(e).__name__}
iterator = safe.iterparse(io.BytesIO(b"<r/>"), events=("start-ns", "end-ns"))
results["iterparse"] = {"namespace_events": list(iterator), "has_root": hasattr(iterator, "root")}


def check_defuse():
    code = (
        "import safexml, io, json, xml.etree.ElementTree as e\n"
        "safexml.defuse_stdlib()\n"
        "x = '<!DOCTYPE r [<!ENTITY a \"expanded\">]><r>&a;</r>'\n"
        "res = {}\n"
        "try:\n"
        "    res['class_parse'] = e.ElementTree().parse(io.StringIO(x)).text\n"
        "except Exception as ex:\n"
        "    res['class_parse'] = f'blocked: {type(ex).__name__}'\n"
        "try:\n"
        "    res['fromstringlist'] = e.fromstringlist([x]).text\n"
        "except Exception as ex:\n"
        "    res['fromstringlist'] = f'blocked: {type(ex).__name__}'\n"
        "print(json.dumps(res))\n"
    )
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"error": p.stderr}


results["defuse_stdlib"] = check_defuse()
print(json.dumps(results, indent=2))
