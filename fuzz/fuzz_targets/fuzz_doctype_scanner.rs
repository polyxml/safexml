#![no_main]

use _safexml::doctype::{extract_quoted, parse_doctype};
use _safexml::parser::{
    check_doctype_casing, detect_declared_encoding, validate_attribute_whitespace, validate_xml_decl,
};
use arbitrary::Arbitrary;
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
pub struct ScannerFuzzInput<'a> {
    pub raw_slice: &'a [u8],
    pub string_slice: &'a str,
    pub offset: usize,
}

fuzz_target!(|input: ScannerFuzzInput| {
    // 1. Stress extract_quoted scanner (Must never panic on arbitrary byte offsets or strings)
    let _ = extract_quoted(input.string_slice, input.offset);

    // 2. Stress parse_doctype internal subset / entity scanner
    let info = parse_doctype(input.string_slice);
    // Sanity check invariant: entity count should be within bounds
    assert!(info.entities.len() <= input.string_slice.len());

    // 3. Stress check_doctype_casing scanner
    let _ = check_doctype_casing(input.raw_slice);

    // 4. Stress detect_declared_encoding scanner
    let _ = detect_declared_encoding(input.raw_slice);

    // 5. Stress validate_xml_decl scanner
    let _ = validate_xml_decl(input.string_slice);

    // 6. Stress validate_attribute_whitespace scanner
    let _ = validate_attribute_whitespace(input.string_slice);
});

