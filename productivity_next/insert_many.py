import frappe
from frappe import Any, _
from frappe.utils import Generator, Iterable, cstr
from frappe.permissions import has_permission
from frappe.model.document import Document
from frappe.model.naming import set_new_name
import json
from datetime import datetime

def _document_values_generator(
	doctype,
	documents: Iterable["Document"],
	columns: list[str],
) -> Generator[tuple[Any], None, None]:
	for doc in documents:
		meta = frappe.get_meta(doctype)
		doc.creation = doc.modified = frappe.utils.get_datetime()
		doc.owner = doc.created_by = doc.modified_by = frappe.session.user
		doc_values = doc.get_valid_dict(
			convert_dates_to_str=True,
			ignore_nulls=True,
			ignore_virtual=True,
		)
		new_doc = frappe.new_doc(doctype)
		new_doc.update(doc_values)
		if not new_doc.name:
			set_new_name(new_doc)
		new_doc.flags.updater_reference = {
			"doctype": new_doc.doctype,
			"docname": new_doc.name,
			"label": _("via Data Import"),
		}
		yield tuple(new_doc.get(col) for col in columns)

def bulk_insert_docs(
	doctype,
	documents: Iterable["Document"],
	ignore_duplicates: bool = False,
	chunk_size=10_000):
	columns = frappe.get_meta(doctype).get_valid_columns()
	values = _document_values_generator(doctype, documents, columns)
	doc_list = list(values)
	frappe.db.bulk_insert(
		doctype, columns, doc_list, ignore_duplicates=ignore_duplicates, chunk_size=chunk_size
	)
