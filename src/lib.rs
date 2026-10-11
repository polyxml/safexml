pub mod doctype;
pub mod parser;

use parser::{parse_xml_bytes, ParseOptions, RawElement, SafeXmlError};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

fn map_safe_error_to_py(py: Python<'_>, err: SafeXmlError) -> PyErr {
    let common = match py.import("safexml.common") {
        Ok(m) => m,
        Err(_) => return PyValueError::new_err(err.to_string()),
    };

    match err {
        SafeXmlError::DTDForbidden { name, sysid, pubid } => match common.getattr("DTDForbidden") {
            Ok(cls) => match cls.call1((name, sysid, pubid)) {
                Ok(inst) => PyErr::from_value(inst),
                Err(e) => e,
            },
            Err(e) => e,
        },
        SafeXmlError::EntitiesForbidden(d) => match common.getattr("EntitiesForbidden") {
            Ok(cls) => {
                match cls.call1((d.name, d.value, d.base, d.sysid, d.pubid, d.notation_name)) {
                    Ok(inst) => PyErr::from_value(inst),
                    Err(e) => e,
                }
            }
            Err(e) => e,
        },
        SafeXmlError::ExternalReferenceForbidden {
            context,
            base,
            sysid,
            pubid,
        } => match common.getattr("ExternalReferenceForbidden") {
            Ok(cls) => match cls.call1((context, base, sysid, pubid)) {
                Ok(inst) => PyErr::from_value(inst),
                Err(e) => e,
            },
            Err(e) => e,
        },
        SafeXmlError::DepthLimitExceeded(_)
        | SafeXmlError::TextLimitExceeded(_)
        | SafeXmlError::AttributeLimitExceeded(_)
        | SafeXmlError::AttributeSizeLimitExceeded(_)
        | SafeXmlError::NameLimitExceeded(_)
        | SafeXmlError::CommentLimitExceeded(_) => match common.getattr("DefusedXmlException") {
            Ok(cls) => match cls.call1((err.to_string(),)) {
                Ok(inst) => PyErr::from_value(inst),
                Err(e) => e,
            },
            Err(e) => e,
        },
        SafeXmlError::ParseError(msg) => match common.getattr("ParseError") {
            Ok(cls) => match cls.call1((msg,)) {
                Ok(inst) => PyErr::from_value(inst),
                Err(e) => e,
            },
            Err(e) => e,
        },
    }
}

fn raw_to_py_element<'py>(
    py: Python<'py>,
    element_cls: &Bound<'py, PyAny>,
    node: &RawElement,
) -> PyResult<Bound<'py, PyAny>> {
    let dict = PyDict::new(py);
    for (k, v) in &node.attrib {
        dict.set_item(k, v)?;
    }
    let elem = element_cls.call1((&node.tag, dict))?;
    if let Some(text) = &node.text {
        elem.setattr("text", text)?;
    }
    if let Some(tail) = &node.tail {
        elem.setattr("tail", tail)?;
    }
    for child in &node.children {
        let child_elem = raw_to_py_element(py, element_cls, child)?;
        elem.call_method1("append", (child_elem,))?;
    }
    Ok(elem)
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (
    source,
    forbid_dtd=false,
    forbid_entities=true,
    forbid_external=true,
    max_depth=1000,
    max_entity_size=10485760,
    max_text_size=104857600,
    max_attributes=1000,
    max_attribute_size=10485760,
    max_name_size=1024,
    max_comment_size=10485760
))]
fn parse_xml<'py>(
    py: Python<'py>,
    source: &Bound<'py, PyAny>,
    forbid_dtd: bool,
    forbid_entities: bool,
    forbid_external: bool,
    max_depth: usize,
    max_entity_size: usize,
    max_text_size: usize,
    max_attributes: usize,
    max_attribute_size: usize,
    max_name_size: usize,
    max_comment_size: usize,
) -> PyResult<Bound<'py, PyAny>> {
    let bytes_vec: Vec<u8>;
    let bytes_ref: &[u8] = if let Ok(s) = source.extract::<&str>() {
        s.as_bytes()
    } else if let Ok(b) = source.extract::<&[u8]>() {
        b
    } else if source.hasattr("read")? {
        let read_res = source.call_method0("read")?;
        if let Ok(s) = read_res.extract::<&str>() {
            bytes_vec = s.as_bytes().to_vec();
            &bytes_vec
        } else if let Ok(b) = read_res.extract::<&[u8]>() {
            bytes_vec = b.to_vec();
            &bytes_vec
        } else {
            return Err(PyValueError::new_err(
                "source.read() must return str or bytes",
            ));
        }
    } else {
        return Err(PyValueError::new_err(
            "source must be str, bytes, or file-like object with a read() method",
        ));
    };

    let options = ParseOptions {
        forbid_dtd,
        forbid_entities,
        forbid_external,
        max_depth,
        max_entity_size,
        max_text_size,
        max_attributes,
        max_attribute_size,
        max_name_size,
        max_comment_size,
    };

    let raw_node = py
        .detach(|| parse_xml_bytes(bytes_ref, &options))
        .map_err(|err| map_safe_error_to_py(py, err))?;

    let etree_mod = py.import("xml.etree.ElementTree")?;
    let element_cls = etree_mod.getattr("Element")?;
    raw_to_py_element(py, &element_cls, &raw_node)
}

#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pymodule]
fn _safexml(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(parse_xml, m)?)?;
    Ok(())
}
