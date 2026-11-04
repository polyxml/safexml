#!/bin/bash -eu

# Build fuzz targets using cargo-fuzz
cd $SRC/safexml/fuzz
cargo fuzz build -O --debug-assertions

FUZZ_TARGET_OUTPUT_DIR="$SRC/safexml/fuzz/target/x86_64-unknown-linux-gnu/release"
TARGETS="fuzz_parser fuzz_structured_xml fuzz_metamorphic fuzz_doctype_scanner"

for target in $TARGETS; do
    # Copy compiled fuzz binary
    cp -v "$FUZZ_TARGET_OUTPUT_DIR/$target" "$OUT/"

    # Copy dictionary
    cp -v "$SRC/safexml/fuzz/xml.dict" "$OUT/${target}.dict"

    # Package seed corpus if present
    if [ -d "$SRC/safexml/fuzz/seeds" ]; then
        zip -j "$OUT/${target}_seed_corpus.zip" "$SRC/safexml/fuzz/seeds/"*
    fi
done
