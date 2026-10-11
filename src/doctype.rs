#[derive(Debug, Clone, Default)]
pub struct EntityDeclInfo {
    pub name: String,
    pub value: Option<String>,
    pub system_id: Option<String>,
    pub public_id: Option<String>,
    pub notation: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct DocTypeInfo {
    pub name: String,
    pub system_id: Option<String>,
    pub public_id: Option<String>,
    pub has_internal_subset: bool,
    pub entities: Vec<EntityDeclInfo>,
}

fn extract_quoted(s: &str, start_pos: usize) -> Option<(String, usize)> {
    let bytes = s.as_bytes();
    let mut i = start_pos;
    while i < bytes.len() && bytes[i].is_ascii_whitespace() {
        i += 1;
    }
    if i >= bytes.len() {
        return None;
    }
    let quote = bytes[i];
    if quote != b'"' && quote != b'\'' {
        return None;
    }
    i += 1;
    let val_start = i;
    while i < bytes.len() && bytes[i] != quote {
        i += 1;
    }
    if i >= bytes.len() {
        return None;
    }
    let val = s[val_start..i].to_string();
    Some((val, i + 1))
}

pub fn parse_doctype(s: &str) -> DocTypeInfo {
    let trimmed = s.trim();
    let mut info = DocTypeInfo::default();
    if trimmed.is_empty() {
        return info;
    }

    // Name is up to next whitespace or '[' or '>'
    let name_end = trimmed
        .find(|c: char| c.is_whitespace() || c == '[' || c == '>')
        .unwrap_or(trimmed.len());
    info.name = trimmed[..name_end].to_string();

    let rest = &trimmed[name_end..];
    let mut i = 0;
    let bytes = rest.as_bytes();

    while i < bytes.len() {
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        if i >= bytes.len() {
            break;
        }

        if bytes[i] == b'[' {
            info.has_internal_subset = true;
            break;
        }

        if rest[i..].starts_with("PUBLIC") {
            i += 6;
            if let Some((pub_id, next_i)) = extract_quoted(rest, i) {
                info.public_id = Some(pub_id);
                i = next_i;
                if let Some((sys_id, next_i2)) = extract_quoted(rest, i) {
                    info.system_id = Some(sys_id);
                    i = next_i2;
                }
            }
        } else if rest[i..].starts_with("SYSTEM") {
            i += 6;
            if let Some((sys_id, next_i)) = extract_quoted(rest, i) {
                info.system_id = Some(sys_id);
                i = next_i;
            }
        } else {
            i += 1;
        }
    }

    // Parse internal subset if present
    if let Some(subset_start) = trimmed.find('[') {
        info.has_internal_subset = true;
        if let Some(subset_end) = trimmed.rfind(']') {
            let subset = &trimmed[subset_start + 1..subset_end];
            parse_internal_subset(subset, &mut info.entities);
        }
    }

    info
}

fn parse_internal_subset(subset: &str, entities: &mut Vec<EntityDeclInfo>) {
    let mut search_pos = 0;
    while let Some(ent_pos) = subset[search_pos..].find("<!ENTITY") {
        let abs_pos = search_pos + ent_pos + 8;
        let rest = &subset[abs_pos..];
        let mut i = 0;
        let bytes = rest.as_bytes();

        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        // Check for parameter entity '%'
        if i < bytes.len() && bytes[i] == b'%' {
            i += 1;
            while i < bytes.len() && bytes[i].is_ascii_whitespace() {
                i += 1;
            }
        }

        // Read entity name
        let name_start = i;
        while i < bytes.len() && !bytes[i].is_ascii_whitespace() && bytes[i] != b'>' {
            i += 1;
        }
        let entity_name = rest[name_start..i].to_string();

        let mut entity = EntityDeclInfo {
            name: entity_name,
            ..Default::default()
        };

        while i < bytes.len() && bytes[i] != b'>' {
            while i < bytes.len() && bytes[i].is_ascii_whitespace() {
                i += 1;
            }
            if i >= bytes.len() || bytes[i] == b'>' {
                break;
            }

            if rest[i..].starts_with("SYSTEM") {
                i += 6;
                if let Some((sys_id, next_i)) = extract_quoted(rest, i) {
                    entity.system_id = Some(sys_id);
                    i = next_i;
                }
            } else if rest[i..].starts_with("PUBLIC") {
                i += 6;
                if let Some((pub_id, next_i)) = extract_quoted(rest, i) {
                    entity.public_id = Some(pub_id);
                    i = next_i;
                    if let Some((sys_id, next_i2)) = extract_quoted(rest, i) {
                        entity.system_id = Some(sys_id);
                        i = next_i2;
                    }
                }
            } else if bytes[i] == b'"' || bytes[i] == b'\'' {
                if let Some((val, next_i)) = extract_quoted(rest, i) {
                    entity.value = Some(val);
                    i = next_i;
                }
            } else if rest[i..].starts_with("NDATA") {
                i += 5;
                while i < bytes.len() && bytes[i].is_ascii_whitespace() {
                    i += 1;
                }
                let not_start = i;
                while i < bytes.len() && !bytes[i].is_ascii_whitespace() && bytes[i] != b'>' {
                    i += 1;
                }
                entity.notation = Some(rest[not_start..i].to_string());
            } else {
                i += 1;
            }
        }

        entities.push(entity);
        search_pos = abs_pos + i;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_doctype_parsing() {
        let d1 = parse_doctype(r#"root SYSTEM "http://example.com/test.dtd""#);
        assert_eq!(d1.name, "root");
        assert_eq!(d1.system_id.as_deref(), Some("http://example.com/test.dtd"));
        assert_eq!(d1.public_id, None);

        let d2 = parse_doctype(
            r#"html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd""#,
        );
        assert_eq!(d2.name, "html");
        assert_eq!(
            d2.public_id.as_deref(),
            Some("-//W3C//DTD XHTML 1.0 Transitional//EN")
        );
        assert_eq!(
            d2.system_id.as_deref(),
            Some("http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd")
        );

        let d3 = parse_doctype(
            r#"xmlbomb [
            <!ENTITY a "1234567890">
            <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">
        ]"#,
        );
        assert_eq!(d3.name, "xmlbomb");
        assert!(d3.has_internal_subset);
        assert_eq!(d3.entities.len(), 2);
        assert_eq!(d3.entities[0].name, "a");
        assert_eq!(d3.entities[0].value.as_deref(), Some("1234567890"));
        assert_eq!(d3.entities[1].name, "b");

        let d4 = parse_doctype(
            r#"external [
            <!ENTITY ee SYSTEM "http://www.w3schools.com/xml/note.xml">
        ]"#,
        );
        assert_eq!(d4.name, "external");
        assert_eq!(d4.entities.len(), 1);
        assert_eq!(d4.entities[0].name, "ee");
        assert_eq!(
            d4.entities[0].system_id.as_deref(),
            Some("http://www.w3schools.com/xml/note.xml")
        );
    }
}
