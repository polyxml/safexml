#[derive(Debug, Clone, Default)]
pub struct EntityDeclInfo {
    pub name: String,
    pub value: Option<String>,
    pub system_id: Option<String>,
    pub public_id: Option<String>,
    pub notation: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct AttlistDeclInfo {
    pub element_name: String,
    pub attribute_name: String,
    pub default_value: String,
}

#[derive(Debug, Clone, Default)]
pub struct DocTypeInfo {
    pub name: String,
    pub system_id: Option<String>,
    pub public_id: Option<String>,
    pub has_internal_subset: bool,
    pub entities: Vec<EntityDeclInfo>,
    pub default_attributes: Vec<AttlistDeclInfo>,
}

struct StrScanner<'a> {
    s: &'a str,
    cursor: usize,
}

impl<'a> StrScanner<'a> {
    fn new(s: &'a str) -> Self {
        Self { s, cursor: 0 }
    }

    fn is_eof(&self) -> bool {
        self.cursor >= self.s.len()
    }

    fn remaining(&self) -> &'a str {
        if self.cursor >= self.s.len() {
            ""
        } else {
            &self.s[self.cursor..]
        }
    }

    fn peek_char(&self) -> Option<char> {
        self.remaining().chars().next()
    }

    fn next_char(&mut self) -> Option<char> {
        if let Some(c) = self.peek_char() {
            self.cursor += c.len_utf8();
            Some(c)
        } else {
            None
        }
    }

    fn skip_whitespace(&mut self) {
        while let Some(c) = self.peek_char() {
            if c.is_whitespace() {
                self.next_char();
            } else {
                break;
            }
        }
    }

    fn starts_with(&self, prefix: &str) -> bool {
        self.remaining().starts_with(prefix)
    }

    fn take_while<F: Fn(char) -> bool>(&mut self, f: F) -> &'a str {
        let start = self.cursor;
        while let Some(c) = self.peek_char() {
            if f(c) {
                self.next_char();
            } else {
                break;
            }
        }
        &self.s[start..self.cursor]
    }

    fn expect_quoted(&mut self) -> Option<String> {
        self.skip_whitespace();
        let quote = self.peek_char()?;
        if quote != '"' && quote != '\'' {
            return None;
        }
        self.next_char(); // consume quote
        let start = self.cursor;
        while let Some(c) = self.peek_char() {
            if c == quote {
                let val = &self.s[start..self.cursor];
                self.next_char(); // consume closing quote
                return Some(val.to_string());
            }
            self.next_char();
        }
        None
    }
}

pub fn extract_quoted(s: &str, start_pos: usize) -> Option<(String, usize)> {
    if start_pos > s.len() || !s.is_char_boundary(start_pos) {
        return None;
    }
    let mut scanner = StrScanner::new(s);
    scanner.cursor = start_pos;
    let val = scanner.expect_quoted()?;
    Some((val, scanner.cursor))
}

pub fn parse_doctype(s: &str) -> DocTypeInfo {
    let mut scanner = StrScanner::new(s);
    scanner.skip_whitespace();
    let mut info = DocTypeInfo::default();
    if scanner.is_eof() {
        return info;
    }

    // Name is up to next whitespace or '[' or '>'
    info.name = scanner
        .take_while(|c| !c.is_whitespace() && c != '[' && c != '>')
        .to_string();

    let mut subset_start: Option<usize> = None;
    while !scanner.is_eof() {
        scanner.skip_whitespace();
        if scanner.is_eof() {
            break;
        }

        if scanner.starts_with("[") {
            info.has_internal_subset = true;
            subset_start = Some(scanner.cursor);
            break;
        }

        if scanner.starts_with("PUBLIC") {
            scanner.cursor += 6;
            if let Some(pub_id) = scanner.expect_quoted() {
                info.public_id = Some(pub_id);
                if let Some(sys_id) = scanner.expect_quoted() {
                    info.system_id = Some(sys_id);
                }
            }
        } else if scanner.starts_with("SYSTEM") {
            scanner.cursor += 6;
            if let Some(sys_id) = scanner.expect_quoted() {
                info.system_id = Some(sys_id);
            }
        } else {
            scanner.next_char();
        }
    }

    // Parse internal subset if present
    if let Some(sub_start) = subset_start {
        if let Some(subset_end) = s.rfind(']') {
            if sub_start < subset_end {
                let subset = &s[sub_start + 1..subset_end];
                parse_internal_subset(subset, &mut info.entities, &mut info.default_attributes);
            }
        }
    }

    info
}

fn parse_internal_subset(
    subset: &str,
    entities: &mut Vec<EntityDeclInfo>,
    default_attrs: &mut Vec<AttlistDeclInfo>,
) {
    let mut scanner = StrScanner::new(subset);
    while !scanner.is_eof() {
        scanner.skip_whitespace();
        if scanner.is_eof() {
            break;
        }

        if scanner.starts_with("<!--") {
            // Comment in internal subset - skip it
            scanner.cursor += 4;
            if let Some(end) = scanner.remaining().find("-->") {
                scanner.cursor += end + 3;
            } else {
                break;
            }
        } else if scanner.starts_with("<!ENTITY") {
            scanner.cursor += 8;
            scanner.skip_whitespace();

            // Check for parameter entity '%'
            if scanner.starts_with("%") {
                scanner.cursor += 1;
                scanner.skip_whitespace();
            }

            let entity_name = scanner
                .take_while(|c| !c.is_whitespace() && c != '>' && c != '[')
                .to_string();

            let mut entity = EntityDeclInfo {
                name: entity_name,
                ..Default::default()
            };

            while !scanner.is_eof() && !scanner.starts_with(">") {
                scanner.skip_whitespace();
                if scanner.is_eof() || scanner.starts_with(">") {
                    break;
                }

                if scanner.starts_with("SYSTEM") {
                    scanner.cursor += 6;
                    if let Some(sys_id) = scanner.expect_quoted() {
                        entity.system_id = Some(sys_id);
                    }
                } else if scanner.starts_with("PUBLIC") {
                    scanner.cursor += 6;
                    if let Some(pub_id) = scanner.expect_quoted() {
                        entity.public_id = Some(pub_id);
                        if let Some(sys_id) = scanner.expect_quoted() {
                            entity.system_id = Some(sys_id);
                        }
                    }
                } else if scanner.starts_with("\"") || scanner.starts_with("'") {
                    if let Some(val) = scanner.expect_quoted() {
                        entity.value = Some(val);
                    }
                } else if scanner.starts_with("NDATA") {
                    scanner.cursor += 5;
                    scanner.skip_whitespace();
                    let not_name = scanner
                        .take_while(|c| !c.is_whitespace() && c != '>')
                        .to_string();
                    entity.notation = Some(not_name);
                } else {
                    scanner.next_char();
                }
            }

            if scanner.starts_with(">") {
                scanner.next_char();
            }

            entities.push(entity);
        } else if scanner.starts_with("<!ATTLIST") {
            scanner.cursor += 9;
            scanner.skip_whitespace();
            let elem_name = scanner
                .take_while(|c| !c.is_whitespace() && c != '>')
                .to_string();

            while !scanner.is_eof() {
                scanner.skip_whitespace();
                if scanner.is_eof() || scanner.starts_with(">") {
                    break;
                }
                let attr_name = scanner
                    .take_while(|c| !c.is_whitespace() && c != '>')
                    .to_string();
                if attr_name.is_empty() {
                    break;
                }
                scanner.skip_whitespace();
                if scanner.is_eof() || scanner.starts_with(">") {
                    break;
                }
                // attribute type (e.g. CDATA, ID, NOTATION (...), or enumeration (...))
                if scanner.starts_with("NOTATION") {
                    scanner.cursor += 8;
                    scanner.skip_whitespace();
                }
                if scanner.starts_with("(") {
                    scanner.next_char();
                    while let Some(c) = scanner.next_char() {
                        if c == ')' || c == '>' {
                            break;
                        }
                    }
                } else {
                    let _attr_type = scanner
                        .take_while(|c| !c.is_whitespace() && c != '>')
                        .to_string();
                }
                scanner.skip_whitespace();
                if scanner.is_eof() || scanner.starts_with(">") {
                    break;
                }

                if scanner.starts_with("#FIXED") {
                    scanner.cursor += 6;
                    scanner.skip_whitespace();
                }

                if scanner.starts_with("#REQUIRED") {
                    scanner.cursor += 9;
                } else if scanner.starts_with("#IMPLIED") {
                    scanner.cursor += 8;
                } else if scanner.starts_with("\"") || scanner.starts_with("'") {
                    if let Some(val) = scanner.expect_quoted() {
                        if !elem_name.is_empty() && !attr_name.is_empty() {
                            default_attrs.push(AttlistDeclInfo {
                                element_name: elem_name.clone(),
                                attribute_name: attr_name,
                                default_value: val,
                            });
                        }
                    }
                } else {
                    while !scanner.is_eof() && !scanner.starts_with(">") {
                        scanner.next_char();
                    }
                    break;
                }
            }
            if scanner.starts_with(">") {
                scanner.next_char();
            }
        } else {
            scanner.next_char();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_quoted() {
        assert_eq!(extract_quoted("", 0), None);
        assert_eq!(extract_quoted("   ", 0), None);
        assert_eq!(extract_quoted("noquote", 0), None);
        assert_eq!(extract_quoted("\"unterminated", 0), None);
        assert_eq!(
            extract_quoted("'single'", 0),
            Some(("single".to_string(), 8))
        );
        assert_eq!(
            extract_quoted("   \"double\"  ", 0),
            Some(("double".to_string(), 11))
        );
    }

    #[test]
    fn test_doctype_parsing() {
        // Empty
        let empty = parse_doctype("   ");
        assert_eq!(empty.name, "");

        // No subset, SYSTEM
        let d1 = parse_doctype(r#"root SYSTEM "http://example.com/test.dtd""#);
        assert_eq!(d1.name, "root");
        assert_eq!(d1.system_id.as_deref(), Some("http://example.com/test.dtd"));
        assert_eq!(d1.public_id, None);

        // PUBLIC with system
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

        // PUBLIC without system
        let d2b = parse_doctype(r#"root PUBLIC "pub_only""#);
        assert_eq!(d2b.public_id.as_deref(), Some("pub_only"));
        assert_eq!(d2b.system_id, None);

        // With internal subset and entity declarations
        let d3 = parse_doctype(
            r#"xmlbomb [
            <!ENTITY a "1234567890">
            <!ENTITY b '&a;&a;&a;&a;&a;&a;&a;&a;'>
            <!ENTITY % pe "param">
            <!ENTITY pub_ent PUBLIC "pub_id" "sys_id">
            <!ENTITY pic SYSTEM "pic.gif" NDATA gif>
            <!ENTITY empty_junk >
            <!ENTITY other ignore_unrecognized_token >
        ]"#,
        );
        assert_eq!(d3.name, "xmlbomb");
        assert!(d3.has_internal_subset);
        assert_eq!(d3.entities.len(), 7);
        assert_eq!(d3.entities[0].name, "a");
        assert_eq!(d3.entities[0].value.as_deref(), Some("1234567890"));
        assert_eq!(d3.entities[1].name, "b");
        assert_eq!(
            d3.entities[1].value.as_deref(),
            Some("&a;&a;&a;&a;&a;&a;&a;&a;")
        );
        assert_eq!(d3.entities[2].name, "pe");
        assert_eq!(d3.entities[3].name, "pub_ent");
        assert_eq!(d3.entities[3].public_id.as_deref(), Some("pub_id"));
        assert_eq!(d3.entities[3].system_id.as_deref(), Some("sys_id"));
        assert_eq!(d3.entities[4].name, "pic");
        assert_eq!(d3.entities[4].system_id.as_deref(), Some("pic.gif"));
        assert_eq!(d3.entities[4].notation.as_deref(), Some("gif"));

        // DTD with unmatched '[' bracket
        let d_unmatched = parse_doctype("root [ unterminated");
        assert!(d_unmatched.has_internal_subset);
        assert_eq!(d_unmatched.entities.len(), 0);

        // DTD with arbitrary whitespace and tokens before bracket
        let d_tokens = parse_doctype("root SOMETOKEN [ ]");
        assert!(d_tokens.has_internal_subset);

        // DTD with trailing whitespace
        let d_spaces = parse_doctype("root   ");
        assert_eq!(d_spaces.name, "root");

        // Unicode DTD and entities in comments must not panic
        let d_unicode = parse_doctype("r é");
        assert_eq!(d_unicode.name, "r");

        let d_comment = parse_doctype("r [<!-- <!ENTITY fake é> -->]");
        assert_eq!(d_comment.name, "r");
        assert_eq!(d_comment.entities.len(), 0);

        // ATTLIST default attribute
        let d_att = parse_doctype(r#"r [<!ATTLIST r role CDATA "user">]"#);
        assert_eq!(d_att.default_attributes.len(), 1);
        assert_eq!(d_att.default_attributes[0].element_name, "r");
        assert_eq!(d_att.default_attributes[0].attribute_name, "role");
        assert_eq!(d_att.default_attributes[0].default_value, "user");
    }
}
