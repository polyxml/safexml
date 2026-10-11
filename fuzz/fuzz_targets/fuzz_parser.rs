#![no_main]

use _safexml::parser::{parse_xml_bytes, ParseOptions};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let options = ParseOptions {
        forbid_dtd: true,
        forbid_entities: true,
        forbid_external: true,
        max_depth: 64,
        max_elements: 10_000,
        max_input_size: 1_000_000,
        ..Default::default()
    };
    let _ = parse_xml_bytes(data, &options);
});
