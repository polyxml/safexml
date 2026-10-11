use crate::doctype;
use quick_xml::events::Event;
use quick_xml::name::{NamespaceResolver, QName, ResolveResult};
use quick_xml::reader::Reader;

#[derive(Debug, Clone, Default)]
pub struct RawElement {
    pub tag: String,
    pub attrib: Vec<(String, String)>,
    pub text: Option<String>,
    pub tail: Option<String>,
    pub children: Vec<RawElement>,
}

#[derive(Debug, Clone)]
pub struct ParseOptions {
    pub forbid_dtd: bool,
    pub forbid_entities: bool,
    pub forbid_external: bool,
    pub max_depth: usize,
    pub max_entity_size: usize,
    pub max_text_size: usize,
}

impl Default for ParseOptions {
    fn default() -> Self {
        Self {
            forbid_dtd: false,
            forbid_entities: true,
            forbid_external: true,
            max_depth: 1000,
            max_entity_size: 10 * 1024 * 1024,
            max_text_size: 100 * 1024 * 1024,
        }
    }
}

#[derive(Debug, Clone)]
pub struct EntityForbiddenDetails {
    pub name: String,
    pub value: Option<String>,
    pub base: Option<String>,
    pub sysid: Option<String>,
    pub pubid: Option<String>,
    pub notation_name: Option<String>,
}

#[derive(Debug, Clone)]
pub enum SafeXmlError {
    DTDForbidden {
        name: String,
        sysid: Option<String>,
        pubid: Option<String>,
    },
    EntitiesForbidden(Box<EntityForbiddenDetails>),
    ExternalReferenceForbidden {
        context: Option<String>,
        base: Option<String>,
        sysid: Option<String>,
        pubid: Option<String>,
    },
    DepthLimitExceeded(usize),
    TextLimitExceeded(usize),
    ParseError(String),
}

impl std::fmt::Display for SafeXmlError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SafeXmlError::DTDForbidden { name, sysid, pubid } => {
                write!(
                    f,
                    "DTDForbidden(name='{}', system_id={:?}, public_id={:?})",
                    name, sysid, pubid
                )
            }
            SafeXmlError::EntitiesForbidden(d) => {
                write!(
                    f,
                    "EntitiesForbidden(name='{}', system_id={:?}, public_id={:?})",
                    d.name, d.sysid, d.pubid
                )
            }
            SafeXmlError::ExternalReferenceForbidden { sysid, pubid, .. } => {
                write!(
                    f,
                    "ExternalReferenceForbidden(system_id={:?}, public_id={:?})",
                    sysid, pubid
                )
            }
            SafeXmlError::DepthLimitExceeded(limit) => {
                write!(
                    f,
                    "XML document exceeded maximum nesting depth limit of {}",
                    limit
                )
            }
            SafeXmlError::TextLimitExceeded(limit) => {
                write!(
                    f,
                    "XML document exceeded maximum text size limit of {}",
                    limit
                )
            }
            SafeXmlError::ParseError(msg) => write!(f, "XML ParseError: {}", msg),
        }
    }
}

impl std::error::Error for SafeXmlError {}

struct StackFrame {
    elem: RawElement,
}

pub fn parse_xml_bytes(
    xml_bytes: &[u8],
    options: &ParseOptions,
) -> Result<RawElement, SafeXmlError> {
    let mut reader = Reader::from_reader(xml_bytes);
    let mut resolver = NamespaceResolver::default();
    let mut stack: Vec<StackFrame> = Vec::new();
    let mut root: Option<RawElement> = None;
    let mut buf = Vec::new();
    let mut total_text_bytes: usize = 0;

    loop {
        let event = match reader.read_event_into(&mut buf) {
            Ok(e) => e,
            Err(e) => return Err(SafeXmlError::ParseError(e.to_string())),
        };

        match event {
            Event::DocType(dt) => {
                let dt_str = dt.as_ref();
                let info = doctype::parse_doctype(dt_str);

                if options.forbid_dtd {
                    return Err(SafeXmlError::DTDForbidden {
                        name: info.name,
                        sysid: info.system_id,
                        pubid: info.public_id,
                    });
                }

                if options.forbid_external {
                    if info.system_id.is_some() || info.public_id.is_some() {
                        return Err(SafeXmlError::ExternalReferenceForbidden {
                            context: None,
                            base: None,
                            sysid: info.system_id,
                            pubid: info.public_id,
                        });
                    }
                    for ent in &info.entities {
                        if ent.system_id.is_some() || ent.public_id.is_some() {
                            return Err(SafeXmlError::ExternalReferenceForbidden {
                                context: None,
                                base: None,
                                sysid: ent.system_id.clone(),
                                pubid: ent.public_id.clone(),
                            });
                        }
                    }
                }

                if options.forbid_entities && !info.entities.is_empty() {
                    let first = &info.entities[0];
                    return Err(SafeXmlError::EntitiesForbidden(Box::new(
                        EntityForbiddenDetails {
                            name: first.name.clone(),
                            value: first.value.clone(),
                            base: None,
                            sysid: first.system_id.clone(),
                            pubid: first.public_id.clone(),
                            notation_name: first.notation.clone(),
                        },
                    )));
                }
            }
            Event::Start(start_event) => {
                if stack.len() + 1 > options.max_depth {
                    return Err(SafeXmlError::DepthLimitExceeded(options.max_depth));
                }

                if let Err(e) = resolver.push(&start_event) {
                    return Err(SafeXmlError::ParseError(e.to_string()));
                }

                let tag = resolve_tag(&resolver, start_event.name());
                let attrib = parse_attributes(&resolver, &start_event, options)?;

                stack.push(StackFrame {
                    elem: RawElement {
                        tag,
                        attrib,
                        text: None,
                        tail: None,
                        children: Vec::new(),
                    },
                });
            }
            Event::End(_) => {
                resolver.pop();
                if let Some(frame) = stack.pop() {
                    if stack.is_empty() {
                        root = Some(frame.elem);
                    } else {
                        stack.last_mut().unwrap().elem.children.push(frame.elem);
                    }
                } else {
                    return Err(SafeXmlError::ParseError(
                        "Unexpected closing tag".to_string(),
                    ));
                }
            }
            Event::Empty(empty_event) => {
                if stack.len() + 1 > options.max_depth {
                    return Err(SafeXmlError::DepthLimitExceeded(options.max_depth));
                }

                if let Err(e) = resolver.push(&empty_event) {
                    return Err(SafeXmlError::ParseError(e.to_string()));
                }

                let tag = resolve_tag(&resolver, empty_event.name());
                let attrib = parse_attributes(&resolver, &empty_event, options)?;
                resolver.pop();

                let elem = RawElement {
                    tag,
                    attrib,
                    text: None,
                    tail: None,
                    children: Vec::new(),
                };

                if stack.is_empty() {
                    root = Some(elem);
                } else {
                    stack.last_mut().unwrap().elem.children.push(elem);
                }
            }
            Event::Text(t) => {
                let text_str = t.as_ref();
                append_text_chunk(
                    &mut stack,
                    &mut root,
                    text_str,
                    &mut total_text_bytes,
                    options,
                )?;
            }
            Event::CData(cd) => {
                let cdata_str = cd.as_ref();
                append_text_chunk(
                    &mut stack,
                    &mut root,
                    cdata_str,
                    &mut total_text_bytes,
                    options,
                )?;
            }
            Event::GeneralRef(r) => {
                let ref_str = r.as_ref();
                let expanded = resolve_entity_reference(ref_str, options)?;
                append_text_chunk(
                    &mut stack,
                    &mut root,
                    &expanded,
                    &mut total_text_bytes,
                    options,
                )?;
            }
            Event::Eof => break,
            _ => {}
        }
        buf.clear();
    }

    root.ok_or_else(|| SafeXmlError::ParseError("No XML root element found".to_string()))
}

fn resolve_tag(resolver: &NamespaceResolver, qname: QName) -> String {
    let (res, local) = resolver.resolve_element(qname);
    match res {
        ResolveResult::Bound(ns) => format!("{{{}}}{}", ns.0, local.as_ref()),
        ResolveResult::Unbound => local.as_ref().to_string(),
        ResolveResult::Unknown(p) => format!("{}:{}", p, local.as_ref()),
    }
}

fn parse_attributes(
    resolver: &NamespaceResolver,
    event: &quick_xml::events::BytesStart,
    options: &ParseOptions,
) -> Result<Vec<(String, String)>, SafeXmlError> {
    let mut attrib = Vec::new();
    for attr in event.attributes() {
        let a = match attr {
            Ok(a) => a,
            Err(e) => return Err(SafeXmlError::ParseError(e.to_string())),
        };

        let key_str = a.key.as_ref();

        // Standard ElementTree strips xmlns and xmlns:* declarations from element.attrib
        if key_str == "xmlns" || key_str.starts_with("xmlns:") {
            continue;
        }

        let (res, local) = resolver.resolve_attribute(a.key);
        let attr_name = match res {
            ResolveResult::Bound(ns) => format!("{{{}}}{}", ns.0, local.as_ref()),
            ResolveResult::Unbound => local.as_ref().to_string(),
            ResolveResult::Unknown(p) => format!("{}:{}", p, local.as_ref()),
        };

        let val_str = a.value.as_ref();

        let unescaped_val = match quick_xml::escape::unescape(val_str) {
            Ok(u) => u.to_string(),
            Err(quick_xml::escape::EscapeError::UnrecognizedEntity(_, ent_name)) => {
                if options.forbid_entities {
                    return Err(SafeXmlError::EntitiesForbidden(Box::new(
                        EntityForbiddenDetails {
                            name: ent_name.to_string(),
                            value: None,
                            base: None,
                            sysid: None,
                            pubid: None,
                            notation_name: None,
                        },
                    )));
                } else {
                    return Err(SafeXmlError::ParseError(format!(
                        "Unrecognized entity: &{};",
                        ent_name
                    )));
                }
            }
            Err(e) => return Err(SafeXmlError::ParseError(e.to_string())),
        };

        attrib.push((attr_name, unescaped_val));
    }
    Ok(attrib)
}

fn resolve_entity_reference(
    ref_name: &str,
    options: &ParseOptions,
) -> Result<String, SafeXmlError> {
    match ref_name {
        "amp" => Ok("&".to_string()),
        "lt" => Ok("<".to_string()),
        "gt" => Ok(">".to_string()),
        "quot" => Ok("\"".to_string()),
        "apos" => Ok("'".to_string()),
        num if num.starts_with("#x") || num.starts_with("#X") => {
            let code = u32::from_str_radix(&num[2..], 16).map_err(|_| {
                SafeXmlError::ParseError(format!("Invalid character reference: &{};", ref_name))
            })?;
            char::from_u32(code).map(|c| c.to_string()).ok_or_else(|| {
                SafeXmlError::ParseError(format!("Invalid unicode character: &{};", ref_name))
            })
        }
        num if num.starts_with('#') => {
            let code = num[1..].parse::<u32>().map_err(|_| {
                SafeXmlError::ParseError(format!("Invalid character reference: &{};", ref_name))
            })?;
            char::from_u32(code).map(|c| c.to_string()).ok_or_else(|| {
                SafeXmlError::ParseError(format!("Invalid unicode character: &{};", ref_name))
            })
        }
        unknown => {
            if options.forbid_entities {
                Err(SafeXmlError::EntitiesForbidden(Box::new(
                    EntityForbiddenDetails {
                        name: unknown.to_string(),
                        value: None,
                        base: None,
                        sysid: None,
                        pubid: None,
                        notation_name: None,
                    },
                )))
            } else {
                Err(SafeXmlError::ParseError(format!(
                    "Undefined entity: &{};",
                    unknown
                )))
            }
        }
    }
}

fn append_text_chunk(
    stack: &mut [StackFrame],
    root: &mut Option<RawElement>,
    chunk: &str,
    total_text_bytes: &mut usize,
    options: &ParseOptions,
) -> Result<(), SafeXmlError> {
    *total_text_bytes += chunk.len();
    if *total_text_bytes > options.max_text_size {
        return Err(SafeXmlError::TextLimitExceeded(options.max_text_size));
    }

    if stack.is_empty() {
        if !chunk.trim().is_empty() {
            if root.is_some() {
                return Err(SafeXmlError::ParseError(
                    "Junk after document element".to_string(),
                ));
            } else {
                return Err(SafeXmlError::ParseError(
                    "Content before document element".to_string(),
                ));
            }
        }
        return Ok(());
    }

    let top = stack.last_mut().unwrap();
    if top.elem.children.is_empty() {
        match &mut top.elem.text {
            Some(existing) => existing.push_str(chunk),
            None => top.elem.text = Some(chunk.to_string()),
        }
    } else {
        let last_child = top.elem.children.last_mut().unwrap();
        match &mut last_child.tail {
            Some(existing) => existing.push_str(chunk),
            None => last_child.tail = Some(chunk.to_string()),
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normal_parse() {
        let xml = br#"<root id="1"><child>Hello &amp; world</child><child2/></root>"#;
        let opt = ParseOptions::default();
        let root = parse_xml_bytes(xml, &opt).unwrap();
        assert_eq!(root.tag, "root");
        assert_eq!(root.attrib, vec![("id".to_string(), "1".to_string())]);
        assert_eq!(root.children.len(), 2);
        assert_eq!(root.children[0].tag, "child");
        assert_eq!(root.children[0].text.as_deref(), Some("Hello & world"));
        assert_eq!(root.children[1].tag, "child2");
    }

    #[test]
    fn test_xmlbomb_entity_forbidden() {
        let xml = br#"<!DOCTYPE xmlbomb [
            <!ENTITY a "1234567890">
            <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">
        ]>
        <bomb>&a;</bomb>"#;
        let opt = ParseOptions::default();
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        match err {
            SafeXmlError::EntitiesForbidden(d) => assert_eq!(d.name, "a"),
            other => panic!("Expected EntitiesForbidden, got {:?}", other),
        }
    }

    #[test]
    fn test_external_reference_forbidden() {
        let xml = br#"<!DOCTYPE external [
            <!ENTITY ee SYSTEM "http://www.w3schools.com/xml/note.xml">
        ]>
        <root>&ee;</root>"#;
        let opt = ParseOptions::default();
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        match err {
            SafeXmlError::ExternalReferenceForbidden { sysid, .. } => {
                assert_eq!(
                    sysid.as_deref(),
                    Some("http://www.w3schools.com/xml/note.xml")
                );
            }
            other => panic!("Expected ExternalReferenceForbidden, got {:?}", other),
        }
    }

    #[test]
    fn test_dtd_forbidden() {
        let xml = br#"<!DOCTYPE root><root/>"#;
        let opt = ParseOptions {
            forbid_dtd: true,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        match err {
            SafeXmlError::DTDForbidden { name, .. } => assert_eq!(name, "root"),
            other => panic!("Expected DTDForbidden, got {:?}", other),
        }
    }

    #[test]
    fn test_depth_limit() {
        let xml = br#"<a><b><c><d><e/></d></c></b></a>"#;
        let opt = ParseOptions {
            max_depth: 3,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        match err {
            SafeXmlError::DepthLimitExceeded(3) => {}
            other => panic!("Expected DepthLimitExceeded, got {:?}", other),
        }
    }
}
