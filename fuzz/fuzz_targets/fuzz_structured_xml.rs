#![no_main]

use _safexml::parser::{parse_xml_bytes, ParseOptions, RawElement};
use arbitrary::Arbitrary;
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
pub enum FuzzEncoding {
    Utf8,
    Utf16Le,
    Utf16Be,
    Iso8859_1,
    Custom(String),
}

#[derive(Debug, Arbitrary)]
pub struct FuzzXmlDecl {
    pub version: Option<u8>, // 0: 1.0, 1: 1.1, other: none
    pub standalone: Option<bool>,
    pub encoding: Option<u8>,
}

#[derive(Debug, Arbitrary)]
pub struct FuzzAttlistDecl {
    pub elem_name: String,
    pub attr_name: String,
    pub default_val: String,
    pub is_fixed: bool,
}

#[derive(Debug, Arbitrary)]
pub struct FuzzEntityDecl {
    pub name: String,
    pub val: String,
    pub is_param: bool,
    pub is_system: bool,
    pub sys_url: String,
}

#[derive(Debug, Arbitrary)]
pub struct FuzzDocType {
    pub root_name: String,
    pub system_id: Option<String>,
    pub public_id: Option<String>,
    pub entities: Vec<FuzzEntityDecl>,
    pub attlists: Vec<FuzzAttlistDecl>,
}

#[derive(Debug, Arbitrary)]
pub enum FuzzNode {
    Text(String),
    CData(String),
    Comment(String),
    CharRef(u32),
    PredefinedEntity(u8),
    Child(Box<FuzzElement>),
}

#[derive(Debug, Arbitrary)]
pub struct FuzzElement {
    pub prefix: Option<String>,
    pub local_name: String,
    pub xmlns: Option<String>,
    pub prefix_xmlns: Option<(String, String)>,
    pub attributes: Vec<(String, String)>,
    pub nodes: Vec<FuzzNode>,
}

#[derive(Debug, Arbitrary)]
pub enum FaultInjection {
    None,
    CorruptEndTag,
    Truncate(u16),
    MissingAttrSpace,
    DuplicateRoot,
    IllegalControlByte(u8),
    NullByteInName,
}

#[derive(Debug, Arbitrary)]
pub struct StructuredFuzzDoc {
    pub decl: Option<FuzzXmlDecl>,
    pub doctype: Option<FuzzDocType>,
    pub root: FuzzElement,
    pub fault: FaultInjection,
    pub forbid_dtd: bool,
    pub forbid_entities: bool,
    pub forbid_external: bool,
    pub max_depth: u8,
    pub max_attributes: u16,
    pub max_attribute_size: u16,
    pub max_name_size: u16,
    pub max_text_size: u32,
}

fn sanitize_ident(s: &str, default: &str) -> String {
    let clean: String = s
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '-')
        .collect();
    if clean.is_empty()
        || !clean
            .chars()
            .next()
            .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
    {
        default.to_string()
    } else {
        clean.chars().take(20).collect()
    }
}

fn sanitize_text(s: &str) -> String {
    s.replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('&', "&amp;")
        .chars()
        .filter(|c| *c >= ' ' && *c != '\x7f')
        .take(100)
        .collect()
}

fn sanitize_attr(s: &str) -> String {
    s.replace('<', "&lt;")
        .replace('"', "&quot;")
        .replace('&', "&amp;")
        .chars()
        .filter(|c| *c >= ' ' && *c != '\x7f')
        .take(50)
        .collect()
}

impl FuzzElement {
    fn serialize(&self, out: &mut String, depth: usize) {
        if depth > 20 {
            return;
        }
        let tag_name = if let Some(pfx) = &self.prefix {
            format!("{}:{}", sanitize_ident(pfx, "ns"), sanitize_ident(&self.local_name, "elem"))
        } else {
            sanitize_ident(&self.local_name, "elem")
        };

        out.push('<');
        out.push_str(&tag_name);

        if let Some(ns) = &self.xmlns {
            out.push_str(" xmlns=\"");
            out.push_str(&sanitize_attr(ns));
            out.push('"');
        }

        if let Some((pfx, uri)) = &self.prefix_xmlns {
            out.push_str(" xmlns:");
            out.push_str(&sanitize_ident(pfx, "pfx"));
            out.push_str("=\"");
            out.push_str(&sanitize_attr(uri));
            out.push('"');
        }

        for (k, v) in &self.attributes {
            out.push(' ');
            out.push_str(&sanitize_ident(k, "attr"));
            out.push_str("=\"");
            out.push_str(&sanitize_attr(v));
            out.push('"');
        }

        if self.nodes.is_empty() {
            out.push_str("/>");
            return;
        }

        out.push('>');

        for node in &self.nodes {
            match node {
                FuzzNode::Text(t) => out.push_str(&sanitize_text(t)),
                FuzzNode::CData(cd) => {
                    let clean_cd = cd.replace("]]>", "]]&gt;");
                    out.push_str("<![CDATA[");
                    out.push_str(&clean_cd);
                    out.push_str("]]>");
                }
                FuzzNode::Comment(c) => {
                    let clean_c = c.replace("--", "- -");
                    let clean_c = clean_c.trim_end_matches('-');
                    out.push_str("<!-- ");
                    out.push_str(clean_c);
                    out.push_str(" -->");
                }
                FuzzNode::CharRef(cp) => {
                    let valid_cp = match cp % 3 {
                        0 => 0x20 + (cp % 0x7E),
                        1 => 0x3A0 + (cp % 30),
                        _ => 0x1F600 + (cp % 20),
                    };
                    out.push_str(&format!("&#x{:X};", valid_cp));
                }
                FuzzNode::PredefinedEntity(b) => match b % 5 {
                    0 => out.push_str("&lt;"),
                    1 => out.push_str("&gt;"),
                    2 => out.push_str("&amp;"),
                    3 => out.push_str("&quot;"),
                    _ => out.push_str("&apos;"),
                },
                FuzzNode::Child(child) => child.serialize(out, depth + 1),
            }
        }

        out.push_str("</");
        out.push_str(&tag_name);
        out.push('>');
    }
}

impl StructuredFuzzDoc {
    pub fn to_xml_bytes(&self) -> Vec<u8> {
        let mut s = String::new();

        if let Some(decl) = &self.decl {
            s.push_str("<?xml");
            if let Some(v) = decl.version {
                s.push_str(if v % 2 == 0 { " version=\"1.0\"" } else { " version=\"1.1\"" });
            } else {
                s.push_str(" version=\"1.0\"");
            }
            if let Some(e) = decl.encoding {
                let enc_str = match e % 3 {
                    0 => "UTF-8",
                    1 => "ISO-8859-1",
                    _ => "US-ASCII",
                };
                s.push_str(&format!(" encoding=\"{}\"", enc_str));
            }
            if let Some(st) = decl.standalone {
                s.push_str(if st { " standalone=\"yes\"" } else { " standalone=\"no\"" });
            }
            s.push_str("?>\n");
        }

        if let Some(dt) = &self.doctype {
            let root_name = sanitize_ident(&dt.root_name, "root");
            s.push_str(&format!("<!DOCTYPE {}", root_name));
            if let Some(sys) = &dt.system_id {
                s.push_str(&format!(" SYSTEM \"{}\"", sanitize_attr(sys)));
            } else if let Some(pub_id) = &dt.public_id {
                s.push_str(&format!(" PUBLIC \"{}\" \"sys.dtd\"", sanitize_attr(pub_id)));
            }

            if !dt.entities.is_empty() || !dt.attlists.is_empty() {
                s.push_str(" [\n");
                for ent in dt.entities.iter().take(5) {
                    let ent_name = sanitize_ident(&ent.name, "ent");
                    let pfx = if ent.is_param { "% " } else { "" };
                    if ent.is_system {
                        s.push_str(&format!("  <!ENTITY {}{} SYSTEM \"{}\">\n", pfx, ent_name, sanitize_attr(&ent.sys_url)));
                    } else {
                        s.push_str(&format!("  <!ENTITY {}{} \"{}\">\n", pfx, ent_name, sanitize_attr(&ent.val)));
                    }
                }
                for att in dt.attlists.iter().take(5) {
                    let el = sanitize_ident(&att.elem_name, &root_name);
                    let at = sanitize_ident(&att.attr_name, "attr");
                    let val = sanitize_attr(&att.default_val);
                    let fixed = if att.is_fixed { "#FIXED " } else { "" };
                    s.push_str(&format!("  <!ATTLIST {} {} CDATA {}\"{}\">\n", el, at, fixed, val));
                }
                s.push_str("]");
            }
            s.push_str(">\n");
        }

        self.root.serialize(&mut s, 1);

        let mut bytes = s.into_bytes();

        match &self.fault {
            FaultInjection::None => {}
            FaultInjection::CorruptEndTag => {
                if let Some(pos) = bytes.windows(2).rposition(|w| w == b"</") {
                    bytes.insert(pos + 1, b'/');
                }
            }
            FaultInjection::Truncate(pct) => {
                let cut = ((bytes.len() as u32 * (*pct as u32 % 100)) / 100) as usize;
                if cut > 2 {
                    bytes.truncate(cut);
                }
            }
            FaultInjection::MissingAttrSpace => {
                if let Some(pos) = bytes.windows(2).position(|w| w == b"\" ") {
                    bytes.remove(pos + 1);
                }
            }
            FaultInjection::DuplicateRoot => {
                bytes.extend_from_slice(b"<extra_root/>");
            }
            FaultInjection::IllegalControlByte(ctrl) => {
                let illegal = match ctrl % 4 {
                    0 => 0x00,
                    1 => 0x0B,
                    2 => 0x0C,
                    _ => 0x1F,
                };
                if let Some(pos) = bytes.iter().position(|&b| b == b'>') {
                    bytes.insert(pos + 1, illegal);
                }
            }
            FaultInjection::NullByteInName => {
                if let Some(pos) = bytes.windows(2).position(|w| w == b"<a" || w == b"<e" || w == b"<r") {
                    bytes[pos + 1] = 0x00;
                }
            }
        }

        bytes
    }
}

fn verify_invariants(
    elem: &RawElement,
    depth: usize,
    options: &ParseOptions,
    total_elements: &mut usize,
    total_text: &mut usize,
) {
    *total_elements += 1;
    assert!(
        *total_elements <= options.max_elements,
        "Element limit escaped: {} > {}",
        *total_elements,
        options.max_elements
    );
    assert!(
        depth <= options.max_depth,
        "Depth limit escaped: {} > {}",
        depth,
        options.max_depth
    );
    assert!(
        elem.tag.len() <= options.max_name_size,
        "Tag length escaped: {} > {}",
        elem.tag.len(),
        options.max_name_size
    );
    assert!(
        elem.attrib.len() <= options.max_attributes,
        "Attr count escaped: {} > {}",
        elem.attrib.len(),
        options.max_attributes
    );
    for (k, v) in &elem.attrib {
        assert!(
            k.len() <= options.max_name_size,
            "Attr name escaped: {} > {}",
            k.len(),
            options.max_name_size
        );
        assert!(
            v.len() <= options.max_attribute_size,
            "Attr val escaped: {} > {}",
            v.len(),
            options.max_attribute_size
        );
    }
    if let Some(t) = &elem.text {
        *total_text += t.len();
    }
    if let Some(t) = &elem.tail {
        *total_text += t.len();
    }

    for child in &elem.children {
        verify_invariants(child, depth + 1, options, total_elements, total_text);
    }
}

fuzz_target!(|doc: StructuredFuzzDoc| {
    let raw_bytes = doc.to_xml_bytes();
    let options = ParseOptions {
        forbid_dtd: doc.forbid_dtd,
        forbid_entities: doc.forbid_entities,
        forbid_external: doc.forbid_external,
        max_depth: (doc.max_depth as usize % 64).max(1),
        max_attributes: (doc.max_attributes as usize % 256).max(1),
        max_attribute_size: (doc.max_attribute_size as usize % (64 * 1024)).max(1),
        max_name_size: (doc.max_name_size as usize % 1024).max(1),
        max_text_size: (doc.max_text_size as usize % (512 * 1024)).max(1),
        max_entity_size: 64 * 1024,
        max_comment_size: 64 * 1024,
        max_input_size: 2 * 1024 * 1024,
        max_elements: 10_000,
    };

    if let Ok(root) = parse_xml_bytes(&raw_bytes, &options) {
        let mut total_elements = 0;
        let mut total_text = 0;
        verify_invariants(&root, 1, &options, &mut total_elements, &mut total_text);
    }
});
