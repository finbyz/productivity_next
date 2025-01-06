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

@frappe.whitelist(methods=["POST"])
def bulk_insert_documents():
	"""
	Bulk insert API endpoint for specific doctypes.
	Method: POST
	Required fields in request body:
		- doctype: string
		- documents: list of document objects
	"""
	try:
		# Get the request data
		if not frappe.request or not frappe.request.data:
			frappe.throw(_("No data provided"))

		data = json.loads(frappe.request.data)

		if not isinstance(data, dict):
			frappe.throw(_("Invalid data format. Expected a dictionary"))

		# Required fields in the request
		required_fields = ["doctype", "documents"]
		for field in required_fields:
			if field not in data:
				frappe.throw(_("Missing required field: {0}").format(field))

		doctype = data["doctype"]
		documents = data["documents"]

		# Restrict to specific doctypes
		allowed_doctypes = ['Application Usage log']
		if doctype not in allowed_doctypes:
			frappe.throw(_("Bulk insert is only allowed for: {0}").format(', '.join(allowed_doctypes)))

		if not isinstance(documents, list) or not documents:
			frappe.throw(_("Documents should be a non-empty list"))

		# Check user permissions
		if not has_permission(doctype, "create"):
			frappe.throw(
				_("Not permitted to create documents of type: {0}").format(doctype), 
				frappe.PermissionError
			)

		# Initialize tracking variables
		successful_documents = []
		failed_documents = []
		
		# Validate and prepare documents
		for idx, doc_data in enumerate(documents):
			if not isinstance(doc_data, dict):
				failed_documents.append({
					"idx": idx,
					"data": doc_data,
					"error": _("Invalid document format")
				})
				continue

			try:
				# Add doctype to document data
				doc_data['doctype'] = doctype
				doc = frappe.get_doc(doc_data)
				set_new_name(doc)
				doc._validate_mandatory()
				doc._validate_data_fields()
				doc._validate_selects()
				doc._validate_non_negative()
				doc._validate_length()
				doc._fix_rating_value()
				doc._validate_code_fields()
				doc._sanitize_content()
				doc._save_passwords()
				successful_documents.append(doc)
			except Exception as e:
				failed_documents.append({
					"idx": idx,
					"data": doc_data,
					"error": str(e)
				})

		# Perform bulk insert for valid documents
		if successful_documents:
			try:
				bulk_insert_docs(
					doctype,
					[doc for doc in successful_documents],
					ignore_duplicates=True
				)
				frappe.db.commit()
			except frappe.DuplicateEntryError as e:
				# Handle duplicate entries
				for doc in successful_documents:
					if frappe.db.exists(doctype, doc.name):
						failed_documents.append({
							"idx": idx,
							"data": doc.as_dict(),
							"error": "Duplicate entry"
						})
					else:
						failed_documents.append({
							"idx": idx,
							"data": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in doc.as_dict().items()},
							"error": str(e)
						})
				successful_documents = []

		# Prepare response
		response = {
			"message": _("Bulk insert completed"),
			"total_documents": len(documents),
			"inserted": len(successful_documents),
			"failed": len(failed_documents),
			"failed_documents": failed_documents
		}

		return response
	except Exception as e:
		frappe.throw(_("An error occurred while processing your request: {0}").format(str(e)))
