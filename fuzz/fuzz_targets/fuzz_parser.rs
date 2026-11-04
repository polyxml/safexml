#![no_main]

use _safexml::parser::{parse_xml_bytes, ParseOptions, RawElement};
use arbitrary::{Arbitrary, Unstructured};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
struct FuzzInput<'a> {
    forbid_dtd: bool,
    forbid_entities: bool,
    forbid_external: bool,
    max_depth: u16,
    max_entity_size: u32,
    max_text_size: u32,
    max_attributes: u16,
    max_attribute_size: u32,
    max_name_size: u16,
    max_comment_size: u32,
    max_input_size: u32,
    max_elements: u32,
    xml_data: &'a [u8],
}

/// Recursively computes tree depth, total element count, max attributes on an element,
/// max name length, and expanded text size to verify parser post-condition invariants.
fn verify_tree_invariants(
    elem: &RawElement,
    current_depth: usize,
    options: &ParseOptions,
    total_elements: &mut usize,
    total_text_bytes: &mut usize,
) {
    *total_elements += 1;
    assert!(
        *total_elements <= options.max_elements,
        "Element count invariant violated: {} > {}",
        *total_elements,
        options.max_elements
    );

    assert!(
        current_depth <= options.max_depth,
        "Depth invariant violated: {} > {}",
        current_depth,
        options.max_depth
    );

    assert!(
        elem.tag.len() <= options.max_name_size,
        "Tag name length invariant violated: {} > {}",
        elem.tag.len(),
        options.max_name_size
    );

    assert!(
        elem.attrib.len() <= options.max_attributes,
        "Attribute count invariant violated: {} > {}",
        elem.attrib.len(),
        options.max_attributes
    );

    for (k, v) in &elem.attrib {
        assert!(
            k.len() <= options.max_name_size,
            "Attribute name length invariant violated: {} > {}",
            k.len(),
            options.max_name_size
        );
        assert!(
            v.len() <= options.max_attribute_size,
            "Attribute value size invariant violated: {} > {}",
            v.len(),
            options.max_attribute_size
        );
    }

    if let Some(t) = &elem.text {
        *total_text_bytes += t.len();
    }
    if let Some(tl) = &elem.tail {
        *total_text_bytes += tl.len();
    }

    for child in &elem.children {
        verify_tree_invariants(
            child,
            current_depth + 1,
            options,
            total_elements,
            total_text_bytes,
        );
    }
}

fuzz_target!(|data: &[u8]| {
    // If the data is large enough to unpack structured parameters, randomize options.
    // Otherwise, treat the entire byte slice as XML data with default/strictest options.
    if let Ok(input) = FuzzInput::arbitrary(&mut Unstructured::new(data)) {
        let options = ParseOptions {
            forbid_dtd: input.forbid_dtd,
            forbid_entities: input.forbid_entities,
            forbid_external: input.forbid_external,
            // Bound limits to reasonable fuzzing ranges so we test limit enforcement
            // without allocating gigabytes of memory per iteration.
            max_depth: (input.max_depth as usize % 512).max(1),
            max_entity_size: (input.max_entity_size as usize % (1024 * 1024)).max(1),
            max_text_size: (input.max_text_size as usize % (1024 * 1024)).max(1),
            max_attributes: (input.max_attributes as usize % 1024).max(1),
            max_attribute_size: (input.max_attribute_size as usize % (1024 * 1024)).max(1),
            max_name_size: (input.max_name_size as usize % 2048).max(1),
            max_comment_size: (input.max_comment_size as usize % (1024 * 1024)).max(1),
            max_input_size: (input.max_input_size as usize % (2 * 1024 * 1024)).max(1),
            max_elements: (input.max_elements as usize % 100_000).max(1),
        };
        if let Ok(root) = parse_xml_bytes(input.xml_data, &options) {
            let mut total_elements = 0;
            let mut total_text_bytes = 0;
            verify_tree_invariants(&root, 1, &options, &mut total_elements, &mut total_text_bytes);
        }
    } else {
        let options = ParseOptions {
            forbid_dtd: true,
            forbid_entities: true,
            forbid_external: true,
            max_depth: 64,
            max_elements: 10_000,
            max_input_size: 1_000_000,
            ..Default::default()
        };
        if let Ok(root) = parse_xml_bytes(data, &options) {
            let mut total_elements = 0;
            let mut total_text_bytes = 0;
            verify_tree_invariants(&root, 1, &options, &mut total_elements, &mut total_text_bytes);
        }
    }
});
