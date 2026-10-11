use crate::parser::{parse_xml_bytes, ParseOptions, RawElement, SafeXmlError};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

fn map_safe_error_to_py(py: Python<'_>, err: SafeXmlError) -> PyErr {
    let to_err = || -> PyResult<PyErr> {
        let common = py.import("safexml.common")?;
        let inst =
            match err {
                SafeXmlError::DTDForbidden { name, sysid, pubid } => common
                    .getattr("DTDForbidden")?
                    .call1((name, sysid, pubid))?,
                SafeXmlError::EntitiesForbidden(d) => common
                    .getattr("EntitiesForbidden")?
                    .call1((d.name, d.value, d.base, d.sysid, d.pubid, d.notation_name))?,
                SafeXmlError::ExternalReferenceForbidden {
                    context,
                    base,
                    sysid,
                    pubid,
                } => common
                    .getattr("ExternalReferenceForbidden")?
                    .call1((context, base, sysid, pubid))?,
                SafeXmlError::DepthLimitExceeded(_)
                | SafeXmlError::TextLimitExceeded(_)
                | SafeXmlError::AttributeLimitExceeded(_)
                | SafeXmlError::AttributeSizeLimitExceeded(_)
                | SafeXmlError::NameLimitExceeded(_)
                | SafeXmlError::CommentLimitExceeded(_)
                | SafeXmlError::InputSizeLimitExceeded(_)
                | SafeXmlError::ElementLimitExceeded(_) => common
                    .getattr("DefusedXmlException")?
                    .call1((err.to_string(),))?,
                SafeXmlError::ParseError(msg) => common.getattr("ParseError")?.call1((msg,))?,
            };
        Ok(PyErr::from_value(inst))
    };

    to_err().unwrap_or_else(|e| e)
}

fn create_single_py_element<'py>(
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
    Ok(elem)
}

struct ConvertFrame<'a, 'py> {
    py_elem: Bound<'py, PyAny>,
    node: &'a RawElement,
    child_idx: usize,
}

fn raw_to_py_element<'py>(
    py: Python<'py>,
    element_cls: &Bound<'py, PyAny>,
    root_node: &RawElement,
) -> PyResult<Bound<'py, PyAny>> {
    let root_elem = create_single_py_element(py, element_cls, root_node)?;
    let mut stack = vec![ConvertFrame {
        py_elem: root_elem,
        node: root_node,
        child_idx: 0,
    }];

    while let Some(frame) = stack.last_mut() {
        if frame.child_idx < frame.node.children.len() {
            let child_node = &frame.node.children[frame.child_idx];
            frame.child_idx += 1;
            let child_elem = create_single_py_element(py, element_cls, child_node)?;
            frame.py_elem.call_method1("append", (&child_elem,))?;
            stack.push(ConvertFrame {
                py_elem: child_elem,
                node: child_node,
                child_idx: 0,
            });
        } else {
            if stack.len() == 1 {
                return Ok(stack.pop().unwrap().py_elem);
            }
            stack.pop();
        }
    }

    create_single_py_element(py, element_cls, root_node)
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
    max_comment_size=10485760,
    max_input_size=268435456,
    max_elements=5000000
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
    max_input_size: usize,
    max_elements: usize,
) -> PyResult<Bound<'py, PyAny>> {
    let bytes_vec: Vec<u8>;
    let bytes_ref: &[u8] = if let Ok(s) = source.extract::<&str>() {
        s.as_bytes()
    } else if let Ok(b) = source.extract::<&[u8]>() {
        b
    } else if source.hasattr("read")? {
        let mut accumulated: Vec<u8> = Vec::new();
        let chunk_size = 65536.min(max_input_size.saturating_add(1));
        loop {
            let chunk_obj = source.call_method1("read", (chunk_size,))?;
            let chunk_bytes: &[u8] = if let Ok(s) = chunk_obj.extract::<&str>() {
                if s.is_empty() {
                    break;
                }
                s.as_bytes()
            } else if let Ok(b) = chunk_obj.extract::<&[u8]>() {
                if b.is_empty() {
                    break;
                }
                b
            } else {
                return Err(PyValueError::new_err(
                    "source.read() must return str or bytes",
                ));
            };

            accumulated.extend_from_slice(chunk_bytes);
            if accumulated.len() > max_input_size {
                let common = py.import("safexml.common")?;
                let msg = format!(
                    "XML input exceeded maximum size limit of {} bytes",
                    max_input_size
                );
                let inst = common.getattr("DefusedXmlException")?.call1((msg,))?;
                return Err(PyErr::from_value(inst));
            }
        }
        bytes_vec = accumulated;
        &bytes_vec
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
        max_input_size,
        max_elements,
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::EntityForbiddenDetails;
    use pyo3::types::PyList;

    fn setup_py(py: Python<'_>) {
        let sys = py.import("sys").unwrap();
        let path: Bound<'_, PyList> = sys.getattr("path").unwrap().cast_into().unwrap();
        let _ = path.insert(0, "python");
    }

    #[test]
    fn test_lib_version() {
        assert_eq!(version(), env!("CARGO_PKG_VERSION"));
    }

    #[test]
    fn test_lib_parse_xml_str_and_bytes() {
        Python::attach(|py| {
            setup_py(py);
            let s = pyo3::types::PyString::new(py, "<root id='1'><child>Text</child></root>");
            let res = parse_xml(
                py, &s, false, true, true, 1000, 10485760, 104857600, 1000, 10485760, 1024,
                10485760, 268435456, 5000000,
            )
            .unwrap();
            let tag: String = res.getattr("tag").unwrap().extract().unwrap();
            assert_eq!(tag, "root");

            let b = pyo3::types::PyBytes::new(py, b"<root><item>Hello</item>Tail</root>");
            let res2 = parse_xml(
                py, &b, false, true, true, 1000, 10485760, 104857600, 1000, 10485760, 1024,
                10485760, 268435456, 5000000,
            )
            .unwrap();
            assert_eq!(
                res2.getattr("tag").unwrap().extract::<String>().unwrap(),
                "root"
            );
        });
    }

    #[test]
    fn test_lib_parse_xml_file_like() {
        Python::attach(|py| {
            setup_py(py);
            let io = py.import("io").unwrap();
            let string_io = io.getattr("StringIO").unwrap().call1(("<root/>",)).unwrap();
            let res = parse_xml(
                py, &string_io, false, true, true, 1000, 10485760, 104857600, 1000, 10485760, 1024,
                10485760, 268435456, 5000000,
            )
            .unwrap();
            assert_eq!(
                res.getattr("tag").unwrap().extract::<String>().unwrap(),
                "root"
            );

            let bytes_io = io.getattr("BytesIO").unwrap().call1((b"<root/>",)).unwrap();
            let res2 = parse_xml(
                py, &bytes_io, false, true, true, 1000, 10485760, 104857600, 1000, 10485760, 1024,
                10485760, 268435456, 5000000,
            )
            .unwrap();
            assert_eq!(
                res2.getattr("tag").unwrap().extract::<String>().unwrap(),
                "root"
            );

            // Oversized stream: only max_input_size + 1 bytes are read, then rejected.
            let big_io = io
                .getattr("BytesIO")
                .unwrap()
                .call1((b"<root>0123456789</root>",))
                .unwrap();
            let err = parse_xml(
                py, &big_io, false, true, true, 1000, 10485760, 104857600, 1000, 10485760, 1024,
                10485760, 8, 5000000,
            )
            .unwrap_err();
            assert!(err
                .to_string()
                .contains("input exceeded maximum size limit"));
            assert_eq!(
                big_io
                    .call_method0("tell")
                    .unwrap()
                    .extract::<usize>()
                    .unwrap(),
                9
            );
        });
    }

    #[test]
    fn test_lib_parse_xml_invalid_sources() {
        Python::attach(|py| {
            setup_py(py);
            // Integer is not a valid source
            let num = pyo3::types::PyInt::new(py, 42).into_any();
            let err = parse_xml(
                py, &num, false, true, true, 1000, 10485760, 104857600, 1000, 10485760, 1024,
                10485760, 268435456, 5000000,
            )
            .unwrap_err();
            assert!(err.to_string().contains("source must be str, bytes"));

            // File-like returning non-str/non-bytes
            let fake = py
                .eval(
                    c"type('Fake', (), {'read': lambda self, *a: 123})()",
                    None,
                    None,
                )
                .unwrap();
            let err2 = parse_xml(
                py, &fake, false, true, true, 1000, 10485760, 104857600, 1000, 10485760, 1024,
                10485760, 268435456, 5000000,
            )
            .unwrap_err();
            assert!(err2
                .to_string()
                .contains("source.read() must return str or bytes"));
        });
    }

    #[test]
    fn test_lib_map_safe_errors() {
        Python::attach(|py| {
            setup_py(py);
            let e1 = SafeXmlError::DTDForbidden {
                name: "doc".to_string(),
                sysid: None,
                pubid: None,
            };
            assert!(map_safe_error_to_py(py, e1)
                .to_string()
                .contains("DTDForbidden"));

            let e2 = SafeXmlError::EntitiesForbidden(Box::new(EntityForbiddenDetails {
                name: "ent".to_string(),
                value: None,
                base: None,
                sysid: None,
                pubid: None,
                notation_name: None,
            }));
            assert!(map_safe_error_to_py(py, e2)
                .to_string()
                .contains("EntitiesForbidden"));

            let e3 = SafeXmlError::ExternalReferenceForbidden {
                context: None,
                base: None,
                sysid: Some("sys".to_string()),
                pubid: None,
            };
            assert!(map_safe_error_to_py(py, e3)
                .to_string()
                .contains("ExternalReferenceForbidden"));

            let e4 = SafeXmlError::DepthLimitExceeded(10);
            assert!(map_safe_error_to_py(py, e4)
                .to_string()
                .contains("depth limit"));

            let e5 = SafeXmlError::TextLimitExceeded(10);
            assert!(map_safe_error_to_py(py, e5)
                .to_string()
                .contains("text size limit"));

            let e6 = SafeXmlError::AttributeLimitExceeded(10);
            assert!(map_safe_error_to_py(py, e6)
                .to_string()
                .contains("attribute count limit"));

            let e7 = SafeXmlError::AttributeSizeLimitExceeded(10);
            assert!(map_safe_error_to_py(py, e7)
                .to_string()
                .contains("attribute exceeded maximum size limit"));

            let e8 = SafeXmlError::NameLimitExceeded(10);
            assert!(map_safe_error_to_py(py, e8)
                .to_string()
                .contains("tag name exceeded maximum length limit"));

            let e9 = SafeXmlError::CommentLimitExceeded(10);
            assert!(map_safe_error_to_py(py, e9)
                .to_string()
                .contains("comment exceeded maximum size limit"));

            let e10 = SafeXmlError::ParseError("syntax error".to_string());
            assert!(map_safe_error_to_py(py, e10)
                .to_string()
                .contains("syntax error"));

            let e11 = SafeXmlError::InputSizeLimitExceeded(10);
            assert!(map_safe_error_to_py(py, e11)
                .to_string()
                .contains("input exceeded maximum size limit"));

            let e12 = SafeXmlError::ElementLimitExceeded(10);
            assert!(map_safe_error_to_py(py, e12)
                .to_string()
                .contains("element count limit"));
        });
    }

    #[test]
    fn test_module_initialization() {
        Python::attach(|py| {
            let m = PyModule::new(py, "_safexml").unwrap();
            _safexml(&m).unwrap();
            assert!(m.hasattr("parse_xml").unwrap());
            assert!(m.hasattr("version").unwrap());
        });
    }
}
