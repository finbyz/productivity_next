# -*- coding: utf-8 -*-
# Copyright (c) 2026, FinByz Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import html
import re
from datetime import date

import frappe
from frappe import _

from productivity_next.meeting_sync.common import DEFAULT_DISCUSSIONS


def _normalized(text):
	"""Letters and digits only (any script), lower case: ignores HTML, entities and
	punctuation (the Text Editor drops "<>" from subjects such as "Constro <> Chem")."""
	text = html.unescape(re.sub(r"<[^>]*>", "", str(text or "")))
	return re.sub(r"[\W_]", "", text.casefold())


def is_mom_empty(mom_content, placeholders=()):
	"""Return whether MOM content is empty or only a placeholder.

	A synced Meeting starts with its subject (or a default such as "Online Meeting") as the
	discussion, so text equal to one of those or to one of `placeholders` (the meeting
	subjects) is not a MOM either.
	"""
	cleaned = _normalized(mom_content)
	if not cleaned or any(cleaned == _normalized(d) for d in DEFAULT_DISCUSSIONS):
		return True
	return any(p and cleaned == _normalized(p) for p in placeholders)


def _placeholders(meeting_doc):
	"""Subjects a new synced Meeting's discussion may have been pre-filled with."""
	tml_name = meeting_doc.get("meeting_call_log")
	tml_subject = frappe.db.get_value("Meeting Call Log", tml_name, "meeting_subject") if tml_name else None
	return (meeting_doc.get("subject"), tml_subject)


# --- MOM formatting -------------------------------------------------------------
# The Discussion field and the e-mail dialog are Quill editors, which keep only
# paragraphs, bold, colour/size spans, lists and plain tables (no CSS, no <hr>, no
# <thead>), and the e-mail CSS sets paragraph margins to 0. So the MOM is shaped from
# those pieces only, with empty paragraphs for spacing, like a mail typed in Outlook.
# FinByz house palette (finbyz-document-style): navy-3, blue-deep, ink-soft, ink-faint, amber
BRAND_NAVY = "#11283f"
BRAND_BLUE = "#1a4971"
BRAND_LABEL = "#41556b"
BRAND_MUTED = "#7286a0"
BRAND_AMBER = "#f29316"
HEADING_FONT = "Georgia, 'Times New Roman', serif"
BODY_FONT = "Aptos, Calibri, 'Segoe UI', Arial, sans-serif"
BRAND_INK = "#152538"
BRAND_LINE = "#e2e8f1"
BRAND_PAPER2 = "#f6f8fb"
SECTION_NAMES = (
	"overview", "executive summary", "summary", "key discussion", "discussion", "decisions",
	"client", "external", "action items", "next steps", "next sync", "open questions",
	"requirements", "blockers", "status",
)
_LIST_LINE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_ISO_DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _spacer(soup):
	p = soup.new_tag("p")
	p.append(soup.new_tag("br"))
	return p


def _is_spacer(tag):
	return getattr(tag, "name", None) == "p" and not tag.get_text(strip=True) and not tag.find("img")


def _heading(soup, text, section):
	"""Section: Georgia 18px navy (the house title face). Topic: bold blue-deep.
	Both plain paragraphs with inline spans, which the Quill editor keeps."""
	p = soup.new_tag("p")
	span = soup.new_tag("span")
	span.string = text.strip().rstrip(":").strip()
	if section:
		span["style"] = f"font-family: serif; font-size: 18px; color: {BRAND_NAVY};"
		p.append(span)
	else:
		span["style"] = f"color: {BRAND_BLUE};"
		strong = soup.new_tag("strong")
		strong.append(span)
		p.append(strong)
	return p


def _is_heading(tag):
	return getattr(tag, "name", None) == "p" and bool(
		tag.find("span", style=re.compile(BRAND_NAVY + "|" + BRAND_BLUE))
	)


def _is_section_name(text):
	t = text.strip().rstrip(":").casefold()
	return any(t.startswith(n) for n in SECTION_NAMES)


def _nice_date(match):
	y, m, d = (int(x) for x in match.groups())
	try:
		date(y, m, d)
	except ValueError:
		return match.group(0)
	return f"{d} {_MONTHS[m - 1]} {y}"


def brand_mom_html(content):
	"""Clean, on-brand MOM HTML from the stored Discussion (old or new). Safe to run twice."""
	from bs4 import BeautifulSoup, NavigableString

	soup = BeautifulSoup(content or "", "html.parser")
	wrapper = soup.find("div", class_="ql-editor")
	root = wrapper if wrapper else soup

	# a paragraph holding several lines ("**Label:** x\n- a\n- b") -> paragraphs and a list
	for p in list(root.find_all("p")):
		inner = p.decode_contents()
		inner = re.sub(r"<br\s*/?>", "\n", inner)
		lines = [ln for ln in inner.split("\n") if ln.strip()]
		if len(lines) < 2:
			continue
		new, ul = [], None
		for ln in lines:
			if _LIST_LINE.match(BeautifulSoup(ln, "html.parser").get_text()):
				if ul is None:
					ul = soup.new_tag("ul")
					new.append(ul)
				li = soup.new_tag("li")
				li.append(BeautifulSoup(_LIST_LINE.sub("", ln, count=1), "html.parser"))
				ul.append(li)
			else:
				ul = None
				np = soup.new_tag("p")
				np.append(BeautifulSoup(ln.strip(), "html.parser"))
				new.append(np)
		for n in new:
			p.insert_before(n)
		p.decompose()

	# Quill's bullet lists (<ol><li data-list="bullet">) -> <ul>
	for ol in root.find_all("ol"):
		if ol.find("li", attrs={"data-list": "bullet"}):
			ol.name = "ul"
		for li in ol.find_all("li"):
			li.attrs.pop("data-list", None)

	# headings: Markdown h1-h3 and known bold-only section lines -> section; h4-h6 and other
	# bold-only lines -> topic
	for h in list(root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])):
		h.replace_with(_heading(soup, h.get_text(" ", strip=True), h.name in ("h1", "h2", "h3")))
	for p in list(root.find_all("p")):
		strongs = p.find_all("strong", recursive=False)
		text = p.get_text(" ", strip=True)
		if len(strongs) == 1 and text and strongs[0].get_text(" ", strip=True) == text and len(text) <= 90:
			if p.find("span", style=re.compile("color")):
				continue  # already branded
			if text.endswith(":"):  # a label such as "Attendees:" above its list
				span = soup.new_tag("span", style=f"color: {BRAND_LABEL};")
				span.string = text
				strongs[0].clear()
				strongs[0].append(span)
				continue
			p.replace_with(_heading(soup, text, _is_section_name(text)))

	# label lines ("Meeting:", "Date & Time:") get the muted brand colour on the label only
	for p in root.find_all("p"):
		first = p.find(True, recursive=False)
		if first is not None and first.name == "strong" and first.get_text().strip().endswith(":") \
				and not first.find("span") and p.get_text(strip=True) != first.get_text(strip=True):
			span = soup.new_tag("span", style=f"color: {BRAND_LABEL};")
			span.string = first.get_text()
			first.clear()
			first.append(span)

	# tables: header row as a normal first row (Quill has no <thead>), bold navy
	for table in root.find_all("table"):
		table["class"] = ["table", "table-bordered"]
		head_rows = []
		thead = table.find("thead")
		if thead:
			head_rows = thead.find_all("tr")
		tbody = table.find("tbody") or table
		for tr in head_rows:
			for th in tr.find_all("th"):
				th.name = "td"
				text = th.get_text(" ", strip=True)
				th.clear()
				strong = soup.new_tag("strong")
				strong.string = text  # navy fill + white text are added when the e-mail is sent
				th.append(strong)
		if thead:
			for tr in reversed(head_rows):
				tbody.insert(0, tr.extract())
			thead.decompose()
		for cell in table.find_all(["td", "th"]):
			cell.name = "td"
			cell.attrs.pop("data-row", None)

	for s in list(root.find_all(string=re.compile(r"\bFinbyz\b|\bFINBYZ\b"))):
		s.replace_with(NavigableString(re.sub(r"\bFinbyz\b|\bFINBYZ\b", "FinByz", str(s))))

	# ISO dates -> "20 Nov 2026" (clients abroad read 2026-11-20 or 20-11-2026 differently)
	for s in list(root.find_all(string=_ISO_DATE)):
		s.replace_with(NavigableString(_ISO_DATE.sub(_nice_date, str(s))))

	for el in root.find_all(["table", "tbody", "tr", "ul", "ol"]):
		for c in list(el.children):
			if isinstance(c, NavigableString) and not c.strip():
				c.extract()

	# spacing: one empty paragraph before each heading, list and table; none doubled
	blocks = [c for c in root.children if not (isinstance(c, NavigableString) and not c.strip())]
	for c in list(root.children):
		if isinstance(c, NavigableString) and not c.strip():
			c.extract()
	for i, c in enumerate(blocks):
		if i == 0:
			continue
		if _is_heading(c) or c.name == "table":
			prev = c.find_previous_sibling()
			# no gap between a section title and what opens it
			if prev is not None and not _is_spacer(prev) and not _is_heading(prev):
				c.insert_before(_spacer(soup))
	# collapse runs of spacers and trim them from the ends
	prev_sp = True
	for c in list(root.children):
		sp = _is_spacer(c)
		if sp and prev_sp:
			c.decompose()
			continue
		prev_sp = sp
	kids = list(root.children)
	while kids and _is_spacer(kids[-1]):
		kids.pop().decompose()

	return str(root.decode_contents() if wrapper else soup)


def get_meeting_recipients(meeting_doc):
	"""E-mail addresses of everyone on the Meeting: company and party representatives
	(and the party's contact person for external meetings), without duplicates."""
	emails = []

	def add(email):
		email = (email or "").strip()
		if email and "@" in email and email.lower() not in {e.lower() for e in emails}:
			emails.append(email)

	for rep in meeting_doc.get("meeting_company_representative") or []:
		user = rep.get("emp_user_id")
		if user and frappe.db.get_value("User", user, "enabled"):
			add(frappe.db.get_value("User", user, "email") or user)
		elif rep.get("employee"):
			row = frappe.db.get_value(
				"Employee", rep.employee, ["prefered_email", "company_email", "user_id"], as_dict=True
			)
			if row:
				add(row.prefered_email or row.company_email or row.user_id)

	if not meeting_doc.get("internal_meeting"):
		for rep in meeting_doc.get("meeting_party_representative") or []:
			add(rep.get("email_id") or (rep.get("contact") and frappe.db.get_value("Contact", rep.contact, "email_id")))
		add(meeting_doc.get("email_id"))

	return emails


def _employee_email(employee):
	row = frappe.db.get_value(
		"Employee", employee, ["user_id", "prefered_email", "company_email", "status"], as_dict=True
	)
	if not row or row.status != "Active":
		return None
	if row.user_id and frappe.db.get_value("User", row.user_id, "enabled"):
		return frappe.db.get_value("User", row.user_id, "email") or row.user_id
	return row.prefered_email or row.company_email


def get_supervisor_emails(user):
	"""E-mails of the user's Reports To and that person's Reports To."""
	emails = []
	employee = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")
	for _level in range(2):
		employee = employee and frappe.db.get_value("Employee", employee, "reports_to")
		if not employee:
			break
		email = _employee_email(employee)
		if email and email not in emails:
			emails.append(email)
	return emails


def get_mom_email_subject(meeting_doc):
	date = frappe.utils.formatdate(meeting_doc.get("posting_date") or meeting_doc.get("meeting_from"))
	title = (meeting_doc.get("subject") or meeting_doc.name).strip()
	return _("Minutes of Meeting: {0} ({1})").format(title, date) if date else _("Minutes of Meeting: {0}").format(title)


def _first_name_for(email):
	name = frappe.db.get_value("Contact", {"email_id": email}, "first_name") \
		or frappe.db.get_value("User", {"email": email}, "first_name")
	return (name or "").strip().split(" ")[0]


def _signature(sender):
	esc = frappe.utils.escape_html
	emp = frappe.db.get_value("Employee", {"user_id": sender, "status": "Active"},
		["employee_name", "designation", "company"], as_dict=True) or {}
	name = esc(emp.get("employee_name") or frappe.utils.get_fullname(sender) or sender)
	lines = [f'<p><span style="font-family: serif; font-size: 16px; color: {BRAND_NAVY};">{name}</span></p>']
	company = emp.get("company") or frappe.defaults.get_global_default("company")
	for extra in (emp.get("designation"), company):
		if extra:
			lines.append(f'<p><span style="color: {BRAND_MUTED};">{esc(extra)}</span></p>')
	return "".join(lines)


def get_mom_email_message(meeting_doc, sender, recipients=None):
	esc = frappe.utils.escape_html
	title = esc((meeting_doc.get("subject") or meeting_doc.name).strip())
	start = meeting_doc.get("meeting_from") or meeting_doc.get("posting_date")
	when = frappe.utils.formatdate(start, "d MMM yyyy") if start else ""
	discussion = brand_mom_html(meeting_doc.get("discussion") or "")
	# the AI MOM opens with "Meeting:" / "Date & Time:"; older or typed ones may not
	has_header = re.search(r"Meeting:|Date\s*(&amp;|&)\s*Time:", discussion[:1500])
	greeting = "Dear All,"
	if recipients and len(recipients) == 1:
		first = _first_name_for(recipients[0])
		greeting = f"Dear {esc(first)}," if first else greeting
	spacer = "<p><br></p>"
	intro = "Thank you for your time. Please find below the minutes of our meeting"
	intro += "." if has_header else (f" <strong>{title}</strong>" + (f" held on {esc(when)}" if when else "") + ".")
	return (
		f"<p>{greeting}</p>{spacer}"
		f"<p>{intro} Kindly go through the discussion and the action items, and let me know if "
		"anything needs to be added or corrected.</p>"
		f'{spacer}<p><strong><span style="font-size: 12px; color: {BRAND_AMBER};">MINUTES OF MEETING</span></strong></p>'
		f"{discussion}{spacer}{spacer}"
		f"<p>Regards,</p>{_signature(sender)}"
	)


@frappe.whitelist()
def get_mom_email(meeting_name, quiet=0):
	"""Draft for e-mailing the MOM (the Discussion) from the Meeting form: all participants in
	To, the sender's Reports To and that person's Reports To in CC."""
	frappe.has_permission("Meeting", "read", meeting_name, throw=True)
	meeting_doc = frappe.get_doc("Meeting", meeting_name)
	if is_mom_empty(meeting_doc.get("discussion"), _placeholders(meeting_doc)):
		if frappe.utils.cint(quiet):  # on submit: no MOM yet, so no draft
			return None
		frappe.throw(_("Discussion is empty. Write the meeting minutes in Discussion first."))
	sender = frappe.session.user
	sender_email = (frappe.db.get_value("User", sender, "email") or sender).lower()
	recipients = [e for e in get_meeting_recipients(meeting_doc) if e.lower() not in (sender.lower(), sender_email)]
	to_lower = {e.lower() for e in recipients} | {sender.lower(), sender_email}
	cc = [e for e in get_supervisor_emails(sender) if e.lower() not in to_lower]
	return {
		"recipients": recipients,
		"cc": cc,
		"subject": get_mom_email_subject(meeting_doc),
		"message": get_mom_email_message(meeting_doc, sender, recipients),
	}


def style_mom_email_html(content):
	"""Inline the FinByz house look into a MOM e-mail as it is sent: Aptos body in ink,
	Georgia headings, compact lists, and the "terms table" (navy header row with white
	text, soft zebra rows, light lines). Inline styles, because Outlook and Gmail ignore
	most <style> rules, and the dialog's editor cannot hold them while editing."""
	from bs4 import BeautifulSoup

	soup = BeautifulSoup(content or "", "html.parser")
	root = soup.find("div", class_="ql-editor")
	if root is None:
		root = soup.new_tag("div")
		root["class"] = ["ql-editor", "read-mode"]
		for c in list(soup.contents):
			root.append(c.extract())
		soup.append(root)

	def add_style(tag, css):
		tag["style"] = (tag.get("style", "").rstrip("; ") + "; " + css).strip("; ")

	add_style(root, f"font-family: {BODY_FONT}; font-size: 14px; line-height: 1.5; color: {BRAND_INK}")
	for tag in root.find_all(style=re.compile(r"font-family:\s*serif")):
		tag["style"] = re.sub(r"font-family:\s*serif", f"font-family: {HEADING_FONT}", tag["style"])
	for lst in root.find_all(["ul", "ol"]):
		add_style(lst, "margin: 4px 0 0 0; padding-left: 24px")
	for li in root.find_all("li"):
		add_style(li, "margin: 0 0 4px 0")
	for table in root.find_all("table"):
		table["cellpadding"] = "0"
		table["cellspacing"] = "0"
		add_style(table, f"width: 100%; border-collapse: collapse; border: 1px solid {BRAND_LINE}")
		for i, tr in enumerate(table.find_all("tr")):
			for td in tr.find_all(["td", "th"]):
				css = f"font-family: {BODY_FONT}; font-size: 14px; padding: 7px 10px; vertical-align: top; border: 1px solid {BRAND_LINE}; text-align: left"
				if i == 0:
					td["bgcolor"] = BRAND_NAVY
					css += f"; background-color: {BRAND_NAVY}; border-color: {BRAND_NAVY}; color: #ffffff"
					for t in td.find_all(style=re.compile("color")):  # white wins over any span colour
						t["style"] = re.sub(r"(?<![-\w])color:\s*[^;]+", "color: #ffffff", t["style"])
				elif i % 2 == 0:
					td["bgcolor"] = BRAND_PAPER2
					css += f"; background-color: {BRAND_PAPER2}; color: {BRAND_INK}"
				else:
					css += f"; color: {BRAND_INK}"
				if len(td.get_text(" ", strip=True)) <= 24:  # names, dates: keep on one line
					css += "; white-space: nowrap"
				add_style(td, css)
	return str(soup)


def on_communication_before_insert(doc, method=None):
	"""Communication before_insert: brand the MOM e-mail sent from a Meeting."""
	if (
		doc.reference_doctype == "Meeting"
		and doc.communication_type == "Communication"
		and doc.sent_or_received == "Sent"
		and doc.communication_medium == "Email"
		and doc.content
	):
		try:
			doc.content = style_mom_email_html(doc.content)
		except Exception:
			# never block an e-mail over its looks
			frappe.log_error(title=f"MOM e-mail styling failed for {doc.reference_name}")
