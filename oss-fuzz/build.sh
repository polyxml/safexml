#!/bin/bash -eu

# Build fuzz targets using cargo-fuzz
cd $SRC/safexml/fuzz
cargo fuzz build -O --debug-assertions

# Copy compiled fuzz binaries to $OUT
FUZZ_TARGET_OUTPUT_DIR="$SRC/safexml/fuzz/target/x86_64-unknown-linux-gnu/release"
cp -v "$FUZZ_TARGET_OUTPUT_DIR/fuzz_parser" "$OUT/"

# Copy dictionary
cp -v "$SRC/safexml/fuzz/xml.dict" "$OUT/fuzz_parser.dict"

# Package seed corpus if present
if [ -d "$SRC/safexml/fuzz/seeds" ]; then
    zip -j "$OUT/fuzz_parser_seed_corpus.zip" "$SRC/safexml/fuzz/seeds/"*
fi
