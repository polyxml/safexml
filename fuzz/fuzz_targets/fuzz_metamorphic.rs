#![no_main]

use _safexml::parser::{parse_xml_bytes, ParseOptions, RawElement};
use libfuzzer_sys::fuzz_target;

fn serialize_raw_element(elem: &RawElement, out: &mut String) {
    out.push('<');
    out.push_str(&elem.tag);
    for (k, v) in &elem.attrib {
        out.push(' ');
        out.push_str(k);
        out.push_str("=\"");
        for c in v.chars() {
            match c {
                '&' => out.push_str("&amp;"),
                '<' => out.push_str("&lt;"),
                '"' => out.push_str("&quot;"),
                _ => out.push(c),
            }
        }
        out.push('"');
    }

    if elem.text.is_none() && elem.children.is_empty() {
        out.push_str("/>");
    } else {
        out.push('>');
        if let Some(t) = &elem.text {
            for c in t.chars() {
                match c {
                    '&' => out.push_str("&amp;"),
                    '<' => out.push_str("&lt;"),
                    '>' => out.push_str("&gt;"),
                    _ => out.push(c),
                }
            }
        }
        for child in &elem.children {
            serialize_raw_element(child, out);
        }
        out.push_str("</");
        out.push_str(&elem.tag);
        out.push('>');
    }

    if let Some(tl) = &elem.tail {
        for c in tl.chars() {
            match c {
                '&' => out.push_str("&amp;"),
                '<' => out.push_str("&lt;"),
                '>' => out.push_str("&gt;"),
                _ => out.push(c),
            }
        }
    }
}

fuzz_target!(|data: &[u8]| {
    let base_options = ParseOptions {
        forbid_dtd: false,
        forbid_entities: false,
        forbid_external: true,
        max_depth: 128,
        max_elements: 20_000,
        max_input_size: 1_000_000,
        ..Default::default()
    };

    // 1. Initial Parse Attempt
    let Ok(tree1) = parse_xml_bytes(data, &base_options) else {
        // If rejected under base_options, test Monotonic Security Oracle:
        // A stricter security configuration must NEVER accept what base_options rejected.
        let strict_options = ParseOptions {
            forbid_dtd: true,
            forbid_entities: true,
            forbid_external: true,
            max_depth: 32,
            max_elements: 5_000,
            ..base_options.clone()
        };
        assert!(
            parse_xml_bytes(data, &strict_options).is_err(),
            "Monotonic security invariant violated: stricter options accepted an input rejected by permissive options!"
        );
        return;
    };

    // 2. Metamorphic Property 1: Canonical Round-Trip Idempotence
    // If a document parses cleanly, serializing and re-parsing must produce an identical tree.
    let mut serialized = String::new();
    serialize_raw_element(&tree1, &mut serialized);

    let round_trip_res = parse_xml_bytes(serialized.as_bytes(), &base_options);
    if let Ok(tree2) = round_trip_res {
        // Exclude tail of root element from comparison as root tail is outside document scope
        assert_eq!(
            tree1.tag, tree2.tag,
            "Round-trip root tag mismatch: {} != {}",
            tree1.tag, tree2.tag
        );
        assert_eq!(
            tree1.attrib, tree2.attrib,
            "Round-trip attributes mismatch at <{}>",
            tree1.tag
        );
        assert_eq!(
            tree1.text, tree2.text,
            "Round-trip text mismatch at <{}>",
            tree1.tag
        );
        assert_eq!(
            tree1.children, tree2.children,
            "Round-trip children mismatch at <{}>",
            tree1.tag
        );
    }

    // 3. Metamorphic Property 2: Re-Encoding Invariance (UTF-8 <-> UTF-16)
    // If the input was valid UTF-8 without an existing XML declaration, transcoding to UTF-16
    // with an XML declaration specifying UTF-16 must produce an identical DOM tree.
    if let Ok(utf8_str) = std::str::from_utf8(data) {
        if !utf8_str.starts_with("<?xml") {
            let mut utf16_doc = String::from("<?xml version=\"1.0\" encoding=\"UTF-16\"?>\n");
            utf16_doc.push_str(utf8_str);

            let (encoded_bytes, _, _) = encoding_rs::UTF_16LE.encode(&utf16_doc);
            if let Ok(tree_utf16) = parse_xml_bytes(&encoded_bytes, &base_options) {
                assert_eq!(
                    tree1.tag, tree_utf16.tag,
                    "UTF-16 encoding transcoding altered DOM tag"
                );
                assert_eq!(
                    tree1.attrib, tree_utf16.attrib,
                    "UTF-16 encoding transcoding altered attributes"
                );
                assert_eq!(
                    tree1.children.len(),
                    tree_utf16.children.len(),
                    "UTF-16 encoding transcoding altered children count"
                );
            }
        }
    }
});

