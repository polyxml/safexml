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
    pub max_attributes: usize,
    pub max_attribute_size: usize,
    pub max_name_size: usize,
    pub max_comment_size: usize,
    /// Maximum size of the raw input document in bytes.
    pub max_input_size: usize,
    /// Maximum total number of elements in the document.
    pub max_elements: usize,
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
            max_attributes: 1000,
            max_attribute_size: 10 * 1024 * 1024,
            max_name_size: 1024,
            max_comment_size: 10 * 1024 * 1024,
            max_input_size: 256 * 1024 * 1024,
            max_elements: 5_000_000,
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
    AttributeLimitExceeded(usize),
    AttributeSizeLimitExceeded(usize),
    NameLimitExceeded(usize),
    CommentLimitExceeded(usize),
    InputSizeLimitExceeded(usize),
    ElementLimitExceeded(usize),
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
            SafeXmlError::AttributeLimitExceeded(limit) => {
                write!(
                    f,
                    "XML element exceeded maximum attribute count limit of {}",
                    limit
                )
            }
            SafeXmlError::AttributeSizeLimitExceeded(limit) => {
                write!(f, "XML attribute exceeded maximum size limit of {}", limit)
            }
            SafeXmlError::NameLimitExceeded(limit) => {
                write!(f, "XML tag name exceeded maximum length limit of {}", limit)
            }
            SafeXmlError::CommentLimitExceeded(limit) => {
                write!(f, "XML comment exceeded maximum size limit of {}", limit)
            }
            SafeXmlError::InputSizeLimitExceeded(limit) => {
                write!(
                    f,
                    "XML input exceeded maximum size limit of {} bytes",
                    limit
                )
            }
            SafeXmlError::ElementLimitExceeded(limit) => {
                write!(
                    f,
                    "XML document exceeded maximum element count limit of {}",
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
    if xml_bytes.len() > options.max_input_size {
        return Err(SafeXmlError::InputSizeLimitExceeded(options.max_input_size));
    }

    let mut reader = Reader::from_reader(xml_bytes);
    let mut resolver = NamespaceResolver::default();
    let mut stack: Vec<StackFrame> = Vec::new();
    let mut root: Option<RawElement> = None;
    let mut buf = Vec::new();
    let mut total_text_bytes: usize = 0;
    let mut total_elements: usize = 0;

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
                let name_bytes = start_event.name().into_inner();
                if name_bytes.len() > options.max_name_size {
                    return Err(SafeXmlError::NameLimitExceeded(options.max_name_size));
                }
                if name_bytes.contains('\0') {
                    return Err(SafeXmlError::ParseError(
                        "Null byte detected in XML identifier".to_string(),
                    ));
                }

                if stack.len() + 1 > options.max_depth {
                    return Err(SafeXmlError::DepthLimitExceeded(options.max_depth));
                }

                total_elements += 1;
                if total_elements > options.max_elements {
                    return Err(SafeXmlError::ElementLimitExceeded(options.max_elements));
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
                }
            }
            Event::Empty(empty_event) => {
                let name_bytes = empty_event.name().into_inner();
                if name_bytes.len() > options.max_name_size {
                    return Err(SafeXmlError::NameLimitExceeded(options.max_name_size));
                }
                if name_bytes.contains('\0') {
                    return Err(SafeXmlError::ParseError(
                        "Null byte detected in XML identifier".to_string(),
                    ));
                }

                if stack.len() + 1 > options.max_depth {
                    return Err(SafeXmlError::DepthLimitExceeded(options.max_depth));
                }

                total_elements += 1;
                if total_elements > options.max_elements {
                    return Err(SafeXmlError::ElementLimitExceeded(options.max_elements));
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
            Event::Comment(c) => {
                if c.as_ref().len() > options.max_comment_size {
                    return Err(SafeXmlError::CommentLimitExceeded(options.max_comment_size));
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

        let key_bytes = a.key.into_inner();
        if key_bytes.len() > options.max_name_size {
            return Err(SafeXmlError::NameLimitExceeded(options.max_name_size));
        }
        if key_bytes.contains('\0') {
            return Err(SafeXmlError::ParseError(
                "Null byte detected in XML identifier".to_string(),
            ));
        }

        let key_str = a.key.as_ref();

        // Standard ElementTree strips xmlns and xmlns:* declarations from element.attrib
        if key_str == "xmlns" || key_str.starts_with("xmlns:") {
            continue;
        }

        if attrib.len() + 1 > options.max_attributes {
            return Err(SafeXmlError::AttributeLimitExceeded(options.max_attributes));
        }

        let (res, local) = resolver.resolve_attribute(a.key);
        let attr_name = match res {
            ResolveResult::Bound(ns) => format!("{{{}}}{}", ns.0, local.as_ref()),
            ResolveResult::Unbound => local.as_ref().to_string(),
            ResolveResult::Unknown(p) => format!("{}:{}", p, local.as_ref()),
        };

        let val_str = a.value.as_ref();
        if val_str.len() > options.max_attribute_size {
            return Err(SafeXmlError::AttributeSizeLimitExceeded(
                options.max_attribute_size,
            ));
        }

        // XML 1.0 Attribute-Value Normalization: literal whitespace (\r, \n, \t)
        // is normalized to space (#x20) before unescaping character references.
        let normalized_raw = if val_str.contains(['\r', '\n', '\t']) {
            val_str
                .chars()
                .map(|c| {
                    if c == '\r' || c == '\n' || c == '\t' {
                        ' '
                    } else {
                        c
                    }
                })
                .collect::<String>()
        } else {
            val_str.to_string()
        };

        let unescaped_val = match quick_xml::escape::unescape(&normalized_raw) {
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
        let SafeXmlError::EntitiesForbidden(d) = err else {
            panic!()
        };
        assert_eq!(d.name, "a");
    }

    #[test]
    fn test_external_reference_forbidden() {
        let xml = br#"<!DOCTYPE external [
            <!ENTITY ee SYSTEM "http://www.w3schools.com/xml/note.xml">
        ]>
        <root>&ee;</root>"#;
        let opt = ParseOptions::default();
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        let SafeXmlError::ExternalReferenceForbidden { sysid, .. } = err else {
            panic!()
        };
        assert_eq!(
            sysid.as_deref(),
            Some("http://www.w3schools.com/xml/note.xml")
        );

        let xml2 = br#"<!DOCTYPE root SYSTEM "http://example.com/test.dtd"><root/>"#;
        let err2 = parse_xml_bytes(xml2, &opt).unwrap_err();
        let SafeXmlError::ExternalReferenceForbidden { sysid: sys2, .. } = err2 else {
            panic!()
        };
        assert_eq!(sys2.as_deref(), Some("http://example.com/test.dtd"));
    }

    #[test]
    fn test_dtd_forbidden() {
        let xml = br#"<!DOCTYPE root><root/>"#;
        let opt = ParseOptions {
            forbid_dtd: true,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        let SafeXmlError::DTDForbidden { name, .. } = err else {
            panic!()
        };
        assert_eq!(name, "root");
    }

    #[test]
    fn test_depth_limit() {
        let xml = br#"<a><b><c><d><e/></d></c></b></a>"#;
        let opt = ParseOptions {
            max_depth: 3,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        assert!(matches!(err, SafeXmlError::DepthLimitExceeded(3)));
    }

    #[test]
    fn test_attribute_limit() {
        let xml = br#"<root a1="1" a2="2" a3="3" a4="4"/>"#;
        let opt = ParseOptions {
            max_attributes: 3,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        assert!(matches!(err, SafeXmlError::AttributeLimitExceeded(3)));
    }

    #[test]
    fn test_attribute_size_limit() {
        let xml = br#"<root a="12345678901"/>"#;
        let opt = ParseOptions {
            max_attribute_size: 10,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        assert!(matches!(err, SafeXmlError::AttributeSizeLimitExceeded(10)));
    }

    #[test]
    fn test_name_limit() {
        let xml = br#"<verylongtagnamehere/>"#;
        let opt = ParseOptions {
            max_name_size: 10,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        assert!(matches!(err, SafeXmlError::NameLimitExceeded(10)));

        let xml_start = br#"<verylongtagnamehere>content</verylongtagnamehere>"#;
        let err_start = parse_xml_bytes(xml_start, &opt).unwrap_err();
        assert!(matches!(err_start, SafeXmlError::NameLimitExceeded(10)));
    }

    #[test]
    fn test_comment_limit() {
        let xml = br#"<root><!-- this is a long comment --></root>"#;
        let opt = ParseOptions {
            max_comment_size: 10,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        assert!(matches!(err, SafeXmlError::CommentLimitExceeded(10)));
    }

    #[test]
    fn test_input_size_limit() {
        let xml = b"<root>0123456789</root>";
        let at_limit = ParseOptions {
            max_input_size: xml.len(),
            ..Default::default()
        };
        assert!(parse_xml_bytes(xml, &at_limit).is_ok());

        let below = ParseOptions {
            max_input_size: xml.len() - 1,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &below).unwrap_err();
        assert!(matches!(err, SafeXmlError::InputSizeLimitExceeded(_)));
        assert!(err
            .to_string()
            .contains("input exceeded maximum size limit"));
    }

    #[test]
    fn test_element_count_limit() {
        // root + 3 empty children + 1 start/end child = 5 elements
        let xml = b"<root><a/><a/><a/><b></b></root>";
        let at_limit = ParseOptions {
            max_elements: 5,
            ..Default::default()
        };
        assert!(parse_xml_bytes(xml, &at_limit).is_ok());

        let empty_over = ParseOptions {
            max_elements: 3,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &empty_over).unwrap_err();
        assert!(matches!(err, SafeXmlError::ElementLimitExceeded(3)));
        assert!(err.to_string().contains("element count limit"));

        let start_over = ParseOptions {
            max_elements: 4,
            ..Default::default()
        };
        let err = parse_xml_bytes(xml, &start_over).unwrap_err();
        assert!(matches!(err, SafeXmlError::ElementLimitExceeded(4)));
    }

    #[test]
    fn test_null_byte_rejection() {
        let xml = b"<root\0name/>";
        let opt = ParseOptions::default();
        let err = parse_xml_bytes(xml, &opt).unwrap_err();
        assert!(format!("{}", err).contains("Null byte"));

        let xml_start = b"<root\0name>content</root\0name>";
        let err_start = parse_xml_bytes(xml_start, &opt).unwrap_err();
        assert!(format!("{}", err_start).contains("Null byte"));
    }

    #[test]
    fn test_error_display_and_default_traits() {
        let _elem = RawElement::default();
        let opt = ParseOptions::default();
        assert_eq!(opt.max_depth, 1000);

        let e1 = SafeXmlError::DTDForbidden {
            name: "n".into(),
            sysid: Some("s".into()),
            pubid: Some("p".into()),
        };
        assert!(format!("{}", e1).contains("DTDForbidden"));

        let e2 = SafeXmlError::EntitiesForbidden(Box::new(EntityForbiddenDetails {
            name: "e".into(),
            value: Some("v".into()),
            base: None,
            sysid: None,
            pubid: None,
            notation_name: None,
        }));
        assert!(format!("{}", e2).contains("EntitiesForbidden"));

        let e3 = SafeXmlError::ExternalReferenceForbidden {
            context: None,
            base: None,
            sysid: Some("s".into()),
            pubid: None,
        };
        assert!(format!("{}", e3).contains("ExternalReferenceForbidden"));

        let e4 = SafeXmlError::DepthLimitExceeded(10);
        assert!(format!("{}", e4).contains("depth limit"));

        let e5 = SafeXmlError::TextLimitExceeded(10);
        assert!(format!("{}", e5).contains("text size limit"));

        let e6 = SafeXmlError::AttributeLimitExceeded(10);
        assert!(format!("{}", e6).contains("attribute count limit"));

        let e7 = SafeXmlError::AttributeSizeLimitExceeded(10);
        assert!(format!("{}", e7).contains("attribute exceeded"));

        let e8 = SafeXmlError::NameLimitExceeded(10);
        assert!(format!("{}", e8).contains("tag name exceeded"));

        let e9 = SafeXmlError::CommentLimitExceeded(10);
        assert!(format!("{}", e9).contains("comment exceeded"));

        let e10 = SafeXmlError::ParseError("syntax error".into());
        assert!(format!("{}", e10).contains("syntax error"));
    }

    #[test]
    fn test_cdata_and_tail_and_entities() {
        let xml = br#"<root>
            <child id="c1">Hello &amp; &lt; &gt; &quot; &apos; &#65; &#x42; &#X43; <![CDATA[raw <data>]]></child>
            Tail text here<![CDATA[ more tail]]>
        </root>"#;
        let opt = ParseOptions::default();
        let root = parse_xml_bytes(xml, &opt).unwrap();
        assert_eq!(root.tag, "root");
        assert_eq!(root.children.len(), 1);
        let child = &root.children[0];
        assert_eq!(child.tag, "child");
        assert!(child
            .text
            .as_ref()
            .unwrap()
            .contains("Hello & < > \" ' A B C raw <data>"));
        assert!(child
            .tail
            .as_ref()
            .unwrap()
            .contains("Tail text here more tail"));
    }

    #[test]
    fn test_entity_resolution_errors() {
        let opt = ParseOptions {
            forbid_entities: false,
            ..Default::default()
        };
        // Invalid hex
        let err1 = parse_xml_bytes(b"<root>&#xZZ;</root>", &opt).unwrap_err();
        assert!(format!("{}", err1).contains("Invalid character reference"));

        // Invalid dec
        let err2 = parse_xml_bytes(b"<root>&#ZZ;</root>", &opt).unwrap_err();
        assert!(format!("{}", err2).contains("Invalid character reference"));

        // Invalid unicode surrogate code point
        let err3 = parse_xml_bytes(b"<root>&#xD800;</root>", &opt).unwrap_err();
        assert!(format!("{}", err3).contains("Invalid unicode character"));

        // Undefined entity with forbid_entities = false
        let err4 = parse_xml_bytes(b"<root>&custom;</root>", &opt).unwrap_err();
        assert!(format!("{}", err4).contains("Undefined entity: &custom;"));

        // Undefined entity with forbid_entities = true
        let opt_forbid = ParseOptions::default();
        let err5 = parse_xml_bytes(b"<root>&custom;</root>", &opt_forbid).unwrap_err();
        let SafeXmlError::EntitiesForbidden(d) = err5 else {
            panic!()
        };
        assert_eq!(d.name, "custom");
    }

    #[test]
    fn test_attribute_namespaces_and_entities() {
        let xml = br#"<p:root xmlns="http://default.com" xmlns:p="http://prefix.com" p:attr="val" regular="plain &amp; simple"/>"#;
        let opt = ParseOptions::default();
        let root = parse_xml_bytes(xml, &opt).unwrap();
        assert_eq!(root.tag, "{http://prefix.com}root");
        assert_eq!(root.attrib.len(), 2);
        assert_eq!(
            root.attrib[0],
            ("{http://prefix.com}attr".to_string(), "val".to_string())
        );
        assert_eq!(
            root.attrib[1],
            ("regular".to_string(), "plain & simple".to_string())
        );

        // Unknown namespace prefix
        let xml_unk = br#"<unk:root unk:attr="val"/>"#;
        let root_unk = parse_xml_bytes(xml_unk, &opt).unwrap();
        assert_eq!(root_unk.tag, "unk:root");
        assert_eq!(
            root_unk.attrib[0],
            ("unk:attr".to_string(), "val".to_string())
        );

        // Attribute with unknown entity when forbid_entities = true
        let xml_attr_ent = br#"<root attr="&unknown;"/>"#;
        let err = parse_xml_bytes(xml_attr_ent, &opt).unwrap_err();
        let SafeXmlError::EntitiesForbidden(d) = err else {
            panic!()
        };
        assert_eq!(d.name, "unknown");

        // Attribute with unknown entity when forbid_entities = false
        let opt_no_forbid = ParseOptions {
            forbid_entities: false,
            ..Default::default()
        };
        let err2 = parse_xml_bytes(xml_attr_ent, &opt_no_forbid).unwrap_err();
        assert!(format!("{}", err2).contains("Unrecognized entity"));

        // Attribute with null byte
        let xml_attr_nul = b"<root at\x00tr='1'/>";
        let err3 = parse_xml_bytes(xml_attr_nul, &opt).unwrap_err();
        assert!(format!("{}", err3).contains("Null byte"));

        // Tag name with null byte
        let xml_tag_nul = b"<ro\x00ot/>";
        let err4 = parse_xml_bytes(xml_tag_nul, &opt).unwrap_err();
        assert!(format!("{}", err4).contains("Null byte"));

        // Attribute name size limit
        let opt_name_lim = ParseOptions {
            max_name_size: 5,
            ..Default::default()
        };
        let err5 = parse_xml_bytes(b"<root verylongattr='1'/>", &opt_name_lim).unwrap_err();
        assert!(matches!(err5, SafeXmlError::NameLimitExceeded(5)));

        // Attribute value size limit
        let opt_attr_lim = ParseOptions {
            max_attribute_size: 5,
            ..Default::default()
        };
        let err6 = parse_xml_bytes(b"<root a='123456'/>", &opt_attr_lim).unwrap_err();
        assert!(matches!(err6, SafeXmlError::AttributeSizeLimitExceeded(5)));
    }

    #[test]
    fn test_text_limits_and_junk() {
        let opt_text_lim = ParseOptions {
            max_text_size: 5,
            ..Default::default()
        };
        let err1 = parse_xml_bytes(b"<root>123456</root>", &opt_text_lim).unwrap_err();
        assert!(matches!(err1, SafeXmlError::TextLimitExceeded(5)));

        // Content before document element
        let opt = ParseOptions::default();
        let err2 = parse_xml_bytes(b"junk <root/>", &opt).unwrap_err();
        assert!(format!("{}", err2).contains("Content before document element"));

        // Junk after document element
        let err3 = parse_xml_bytes(b"<root/> junk", &opt).unwrap_err();
        assert!(format!("{}", err3).contains("Junk after document element"));

        // No root element
        let err4 = parse_xml_bytes(b"<!-- just a comment -->", &opt).unwrap_err();
        assert!(format!("{}", err4).contains("No XML root element found"));

        // Malformed closing tag
        let err5 = parse_xml_bytes(b"<root></mismatch>", &opt).unwrap_err();
        assert!(format!("{}", err5).contains("ParseError"));

        // Whitespace before and after root
        let root_spaces = parse_xml_bytes(b"  \n  <root/>  \n  ", &opt).unwrap();
        assert_eq!(root_spaces.tag, "root");

        // CDATA text limit exceeded
        let err6 =
            parse_xml_bytes(b"<root><![CDATA[toolongtext]]></root>", &opt_text_lim).unwrap_err();
        assert!(matches!(err6, SafeXmlError::TextLimitExceeded(5)));

        // Entity expansion text limit exceeded
        let err7 = parse_xml_bytes(
            b"<root>&amp;&amp;&amp;&amp;&amp;&amp;</root>",
            &opt_text_lim,
        )
        .unwrap_err();
        assert!(matches!(err7, SafeXmlError::TextLimitExceeded(5)));
    }

    #[test]
    fn test_empty_elements_and_instructions_and_closings() {
        let opt = ParseOptions::default();
        // Standalone empty root
        let root =
            parse_xml_bytes(b"<?xml version='1.0'?><?pi target?><single id='1'/>", &opt).unwrap();
        assert_eq!(root.tag, "single");
        assert_eq!(root.attrib, vec![("id".to_string(), "1".to_string())]);

        // Empty element as child
        let root2 = parse_xml_bytes(b"<root><empty/></root>", &opt).unwrap();
        assert_eq!(root2.children.len(), 1);
        assert_eq!(root2.children[0].tag, "empty");

        // Unexpected closing tag after root is closed
        let err = parse_xml_bytes(b"<root></root></unexpected>", &opt).unwrap_err();
        assert!(format!("{}", err).contains("ParseError"));

        // Null byte in empty element tag name
        let err2 = parse_xml_bytes(b"<ro\0ot/>", &opt).unwrap_err();
        assert!(format!("{}", err2).contains("Null byte"));

        // Name limit in empty element
        let opt_name = ParseOptions {
            max_name_size: 3,
            ..Default::default()
        };
        let err3 = parse_xml_bytes(b"<verylong/>", &opt_name).unwrap_err();
        assert!(matches!(err3, SafeXmlError::NameLimitExceeded(3)));

        // Depth limit on empty element
        let opt_depth = ParseOptions {
            max_depth: 0,
            ..Default::default()
        };
        let err4 = parse_xml_bytes(b"<single/>", &opt_depth).unwrap_err();
        assert!(matches!(err4, SafeXmlError::DepthLimitExceeded(0)));

        // Appending text chunks to existing text and tail
        let root3 = parse_xml_bytes(
            b"<root>part1<![CDATA[part2]]><child/>tail1<![CDATA[tail2]]></root>",
            &opt,
        )
        .unwrap();
        assert_eq!(root3.text.as_deref(), Some("part1part2"));
        assert_eq!(root3.children[0].tail.as_deref(), Some("tail1tail2"));

        // Invalid unicode char reference in decimal (surrogate code point 55296)
        let opt_entities = ParseOptions {
            forbid_entities: false,
            ..Default::default()
        };
        let err5 = parse_xml_bytes(b"<root>&#55296;</root>", &opt_entities).unwrap_err();
        assert!(format!("{}", err5).contains("Invalid unicode character"));

        // Unknown entity in attribute with forbid_entities = true vs false
        let err6 = parse_xml_bytes(b"<root attr='&custom;'/>", &opt).unwrap_err();
        let SafeXmlError::EntitiesForbidden(d) = err6 else {
            panic!()
        };
        assert_eq!(d.name, "custom");

        // Namespace push error on start tag
        let err7 = parse_xml_bytes(b"<root xmlns:xmlns='http://foo'></root>", &opt).unwrap_err();
        assert!(format!("{}", err7).contains("xmlns"));

        // Namespace push error on empty tag
        let err8 = parse_xml_bytes(b"<root xmlns:xmlns='http://foo'/>", &opt).unwrap_err();
        assert!(format!("{}", err8).contains("xmlns"));

        // Malformed attribute syntax
        let err9 = parse_xml_bytes(b"<root key=val/>", &opt).unwrap_err();
        assert!(format!("{}", err9).contains("ParseError"));

        // Escape error in attribute unescape
        let err10 = parse_xml_bytes(b"<root attr='&#x999999999999;'/>", &opt).unwrap_err();
        assert!(format!("{}", err10).contains("invalid character reference"));
    }
}
