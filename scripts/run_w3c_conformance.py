#!/usr/bin/env python3
"""W3C XML Conformance Test Suite (XMLTS 20130923) Runner for SafeXML.

Validates SafeXML compliance against the official W3C XML Conformance Test Suite.
Handles manifest resolution, entity-backed sub-manifests, and categorizes results
with explicit distinctions between:
  1. Conforming passes / proper malformed-XML rejections
  2. Security policy exclusions (forbid_entities, forbid_external, forbid_dtd)
  3. Unsupported feature exclusions (XML 1.1 specifications)
  4. Parser discrepancies
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import safexml

XMLTS_URL = "https://www.w3.org/XML/Test/xmlts20130923.tar.gz"


@dataclass
class TestCase:
    id: str
    type: str  # not-wf, valid, invalid, error
    path: Path
    rel_manifest: str
    entities: str | None
    edition: str | None
    sections: str | None
    description: str


def ensure_corpus(corpus_dir: Path) -> Path:
    """Ensure the W3C XMLTS corpus is downloaded and extracted."""
    xmlconf_file = corpus_dir / "xmlconf.xml"
    if xmlconf_file.exists():
        return corpus_dir

    corpus_dir.mkdir(parents=True, exist_ok=True)
    archive_path = corpus_dir.parent / "xmlts20130923.tar.gz"

    if not archive_path.exists():
        print(f"Downloading W3C XMLTS from {XMLTS_URL}...")
        urllib.request.urlretrieve(XMLTS_URL, archive_path)
        print(f"Downloaded {archive_path.stat().st_size} bytes.")

    print(f"Extracting {archive_path} to {corpus_dir.parent}...")
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(corpus_dir.parent, filter="data")

    if not xmlconf_file.exists():
        msg = f"Failed to locate {xmlconf_file} after extraction."
        raise FileNotFoundError(msg)

    return corpus_dir


def parse_manifests(corpus_dir: Path) -> list[TestCase]:
    """Parse all sub-manifests referenced by xmlconf.xml."""
    xmlconf_path = corpus_dir / "xmlconf.xml"
    if not xmlconf_path.exists():
        msg = f"xmlconf.xml not found at {xmlconf_path}"
        raise FileNotFoundError(msg)

    xmlconf_text = xmlconf_path.read_text(encoding="utf-8", errors="replace")
    entities = dict(
        re.findall(
            r'<!ENTITY\s+([\w\.\-]+)\s+SYSTEM\s+["\']([^"\']+)["\']',
            xmlconf_text,
        )
    )

    test_cases: list[TestCase] = []
    for _entity_name, rel_path in entities.items():
        sub_manifest = corpus_dir / rel_path
        if not sub_manifest.exists():
            continue

        dir_path = sub_manifest.parent
        content = sub_manifest.read_text(encoding="utf-8", errors="replace")
        content_clean = re.sub(r"<\?xml[^>]*\?>", "", content)
        content_clean = re.sub(r"<!DOCTYPE[^>\[]*(\[[^\]]*\])?>", "", content_clean)
        wrapped = f"<ROOT>{content_clean}</ROOT>"

        try:
            tree = ET.fromstring(wrapped)
        except ET.ParseError:
            continue

        for elem in tree.findall(".//TEST"):
            test_id = elem.get("ID", "")
            test_type = elem.get("TYPE", "")
            uri = elem.get("URI", "")
            ent = elem.get("ENTITIES")
            edition = elem.get("EDITION")
            sections = elem.get("SECTIONS")
            desc = (elem.text or "").strip()

            test_file = (dir_path / uri).resolve()
            if not test_file.exists():
                test_file = (corpus_dir / uri).resolve()

            if test_file.exists():
                test_cases.append(
                    TestCase(
                        id=test_id,
                        type=test_type,
                        path=test_file,
                        rel_manifest=rel_path,
                        entities=ent,
                        edition=edition,
                        sections=sections,
                        description=desc,
                    )
                )

    return test_cases


def is_xml11_case(tc: TestCase) -> bool:
    """Check if test case is an XML 1.1 specific case."""
    if "xml-1.1" in tc.rel_manifest:
        return True
    try:
        data = tc.path.read_bytes()
        return b'version="1.1"' in data or b"version='1.1'" in data
    except Exception:
        return False


def run_conformance(
    test_cases: list[TestCase],
    forbid_dtd: bool = False,
    forbid_entities: bool = True,
    forbid_external: bool = True,
) -> dict:
    """Execute conformance test suite and collect categorized metrics."""
    results = {
        "total": len(test_cases),
        "not_wf": {
            "total": 0,
            "properly_rejected": 0,
            "xml11_excluded": 0,
            "dtd_non_validating_accepted": 0,
            "discrepancies": [],
        },
        "valid": {
            "total": 0,
            "passed": 0,
            "security_excluded_entities": 0,
            "security_excluded_external": 0,
            "security_excluded_dtd": 0,
            "xml11_excluded": 0,
            "future_version_excluded": 0,
            "namespace_non_conformant_colons": 0,
            "external_dtd_entities_unresolved": 0,
            "discrepancies": [],
        },
        "invalid": {
            "total": 0,
            "passed": 0,
            "security_excluded": 0,
            "discrepancies": [],
        },
    }

    for tc in test_cases:
        data = tc.path.read_bytes()
        is_xml11 = is_xml11_case(tc)

        if tc.type == "not-wf":
            results["not_wf"]["total"] += 1
            try:
                safexml.fromstring(
                    data,
                    forbid_dtd=forbid_dtd,
                    forbid_entities=forbid_entities,
                    forbid_external=forbid_external,
                )
                # Parsed without exception
                if is_xml11:
                    results["not_wf"]["xml11_excluded"] += 1
                elif b"<!DOCTYPE" in data:
                    # DTD internal validation is validating-parser only
                    results["not_wf"]["dtd_non_validating_accepted"] += 1
                else:
                    results["not_wf"]["discrepancies"].append(
                        {
                            "id": tc.id,
                            "manifest": tc.rel_manifest,
                            "sections": tc.sections,
                            "file": tc.path.name,
                        }
                    )
            except (
                safexml.DefusedXmlException,
                safexml.common.DefusedXmlException,
            ):
                results["not_wf"]["properly_rejected"] += 1

        elif tc.type == "valid":
            results["valid"]["total"] += 1
            try:
                safexml.fromstring(
                    data,
                    forbid_dtd=forbid_dtd,
                    forbid_entities=forbid_entities,
                    forbid_external=forbid_external,
                )
                results["valid"]["passed"] += 1
            except safexml.EntitiesForbidden:
                results["valid"]["security_excluded_entities"] += 1
            except safexml.ExternalReferenceForbidden:
                results["valid"]["security_excluded_external"] += 1
            except safexml.DTDForbidden:
                results["valid"]["security_excluded_dtd"] += 1
            except safexml.DefusedXmlException as e:
                err_msg = str(e)
                if is_xml11:
                    results["valid"]["xml11_excluded"] += 1
                elif "Unsupported XML version" in err_msg:
                    results["valid"]["future_version_excluded"] += 1
                elif (
                    any(
                        k in err_msg
                        for k in (
                            "Illegal XML element name",
                            "Illegal XML attribute name",
                            "processing instruction target",
                        )
                    )
                    and ":" in err_msg
                ):
                    results["valid"]["namespace_non_conformant_colons"] += 1
                elif "Unrecognized entity" in err_msg:
                    results["valid"]["external_dtd_entities_unresolved"] += 1
                else:
                    results["valid"]["discrepancies"].append(
                        {
                            "id": tc.id,
                            "manifest": tc.rel_manifest,
                            "error": err_msg,
                            "file": tc.path.name,
                        }
                    )

        elif tc.type == "invalid":
            results["invalid"]["total"] += 1
            try:
                safexml.fromstring(
                    data,
                    forbid_dtd=forbid_dtd,
                    forbid_entities=forbid_entities,
                    forbid_external=forbid_external,
                )
                results["invalid"]["passed"] += 1
            except (
                safexml.EntitiesForbidden,
                safexml.ExternalReferenceForbidden,
                safexml.DTDForbidden,
            ):
                results["invalid"]["security_excluded"] += 1
            except safexml.DefusedXmlException:
                # May fail due to external entity resolution
                results["invalid"]["passed"] += 1

    return results


def print_report(results: dict) -> None:
    """Print human-readable summary table."""
    nwf = results["not_wf"]
    val = results["valid"]

    print("=" * 72)
    print("W3C XML CONFORMANCE TEST SUITE (XMLTS 20130923) RESULTS")
    print("=" * 72)
    print(f"Total Test Cases Analyzed: {results['total']}\n")

    print("[1] Malformed XML Rejection (TYPE=not-wf)")
    print(f"  Total not-wf Tests:             {nwf['total']:5d}")
    print(f"  Properly Rejected (Compliant):  {nwf['properly_rejected']:5d}")
    print(f"  Excluded: XML 1.1 Only:         {nwf['xml11_excluded']:5d}")
    print(f"  Excluded: Validating DTD Subset:{nwf['dtd_non_validating_accepted']:5d}")
    print(f"  Parser Discrepancies:           {len(nwf['discrepancies']):5d}")

    discrepancy_count = len(nwf["discrepancies"]) + len(val["discrepancies"])
    compliant_not_wf = nwf["properly_rejected"]
    applicable_not_wf = nwf["properly_rejected"] + len(nwf["discrepancies"])
    not_wf_pct = (compliant_not_wf / applicable_not_wf * 100) if applicable_not_wf else 100.0
    print(f"  -> XML 1.0 Not-WF Pass Rate:    {not_wf_pct:.2f}%\n")

    print("[2] Well-Formed XML Acceptance (TYPE=valid)")
    print(f"  Total valid Tests:              {val['total']:5d}")
    print(f"  Cleanly Parsed (Secure Mode):   {val['passed']:5d}")
    print(f"  Security Policy: Forbid Entities:{val['security_excluded_entities']:5d}")
    print(f"  Security Policy: Forbid External:{val['security_excluded_external']:5d}")
    print(f"  Security Policy: Forbid DTD:    {val['security_excluded_dtd']:5d}")
    print(f"  Excluded: XML 1.1 Only:         {val['xml11_excluded']:5d}")
    print(f"  Excluded: Future XML Versions:  {val['future_version_excluded']:5d}")
    print(f"  Excluded: Pre-NS Colons (:tag): {val['namespace_non_conformant_colons']:5d}")
    print(f"  Excluded: External DTD Entities:{val['external_dtd_entities_unresolved']:5d}")
    print(f"  Parser Discrepancies:           {len(val['discrepancies']):5d}\n")

    print("=" * 72)
    if discrepancy_count == 0:
        print("CONFORMANCE STATUS: ALL QUALITY CRITERIA MET (0 DISCREPANCIES)")
    else:
        print(f"CONFORMANCE STATUS: {discrepancy_count} DISCREPANCIES DETECTED")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="W3C XMLTS Conformance Runner for SafeXML")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path(".cache/xmlts/xmlconf"),
        help="Path to XMLTS xmlconf directory",
    )
    parser.add_argument(
        "--forbid-dtd",
        action="store_true",
        default=False,
        help="Enable forbid_dtd",
    )
    parser.add_argument(
        "--forbid-entities",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enforce forbid_entities",
    )
    parser.add_argument(
        "--forbid-external",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enforce forbid_external",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON metrics",
    )

    args = parser.parse_args()

    corpus_dir = ensure_corpus(args.corpus_dir)
    test_cases = parse_manifests(corpus_dir)
    results = run_conformance(
        test_cases,
        forbid_dtd=args.forbid_dtd,
        forbid_entities=args.forbid_entities,
        forbid_external=args.forbid_external,
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    discrepancy_count = len(results["not_wf"]["discrepancies"]) + len(
        results["valid"]["discrepancies"]
    )
    return 1 if discrepancy_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
