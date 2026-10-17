frappe.query_reports["Custom General Ledger"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "MultiSelectList",
			options: "Account",
			get_data: function (txt) {
				return frappe.db.get_link_options("Account", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "voucher_no",
			label: __("Voucher No"),
			fieldtype: "Data",
			on_change: function () {
				frappe.query_report.set_filter_value("categorize_by", "Categorize by Voucher (Consolidated)");
			},
		},
		{
			fieldname: "against_voucher_no",
			label: __("Against Voucher No"),
			fieldtype: "Data",
			
		},
		{
			fieldtype: "Break",
		},
		
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Autocomplete",
			options: Object.keys(frappe.boot.party_account_types),
			on_change: function () {
				frappe.query_report.set_filter_value("party", []);
			},
		},

		 {
            fieldname: "territory",
            label: __("Territory"),
            fieldtype: "Link",
            options: "Territory",
		    depends_on: "eval:doc.party_type == 'Customer'"
        },
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "MultiSelectList",
			options: "party_type",
			
			get_data: function (txt) {
				if (!frappe.query_report.filters) return;

				let party_type = frappe.query_report.get_filter_value("party_type");
				if (!party_type) return;

				return frappe.db.get_link_options(party_type, txt);
			},
			on_change: function () {
				var party_type = frappe.query_report.get_filter_value("party_type");
				var parties = frappe.query_report.get_filter_value("party");

				if (!party_type || parties.length === 0 || parties.length > 1) {
					frappe.query_report.set_filter_value("party_name", "");
					frappe.query_report.set_filter_value("tax_id", "");
					return;
				} else {
					var party = parties[0];
					var fieldname = erpnext.utils.get_party_name(party_type) || "name";
					frappe.db.get_value(party_type, party, fieldname, function (value) {
						frappe.query_report.set_filter_value("party_name", value[fieldname]);
					});

					if (party_type === "Customer" || party_type === "Supplier") {
						frappe.db.get_value(party_type, party, "tax_id", function (value) {
							frappe.query_report.set_filter_value("tax_id", value["tax_id"]);
						});
					}
				}
			},
		},
		{
			fieldname: "party_name",
			label: __("Party Name"),
			fieldtype: "Data",
			hidden: 1,
		},
		{
			fieldname: "categorize_by",
			label: __("Categorize by"),
			fieldtype: "Select",
			options: [
				"",
				{
					label: __("Categorize by Voucher"),
					value: "Categorize by Voucher",
				},
				{
					label: __("Categorize by Voucher (Consolidated)"),
					value: "Categorize by Voucher (Consolidated)",
				},
				{
					label: __("Categorize by Account"),
					value: "Categorize by Account",
				},
				{
					label: __("Categorize by Party"),
					value: "Categorize by Party",
				},
			],
			default: "Categorize by Voucher (Consolidated)",
		},
		{
			fieldname: "tax_id",
			label: __("Tax Id"),
			fieldtype: "Data",
			hidden: 1,
		},
		{
			fieldname: "presentation_currency",
			label: __("Currency"),
			fieldtype: "Select",
			options: erpnext.get_presentation_currency_list(),
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "MultiSelectList",
			options: "Cost Center",
			get_data: function (txt) {
				return frappe.db.get_link_options("Cost Center", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "MultiSelectList",
			options: "Project",
			get_data: function (txt) {
				return frappe.db.get_link_options("Project", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "include_dimensions",
			label: __("Consider Accounting Dimensions"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_opening_entries",
			label: __("Show Opening Entries"),
			fieldtype: "Check",
		},
		{
			fieldname: "include_default_book_entries",
			label: __("Include Default FB Entries"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_cancelled_entries",
			label: __("Show Cancelled Entries"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_net_values_in_party_account",
			label: __("Show Net Values in Party Account"),
			fieldtype: "Check",
		},
		{
			fieldname: "add_values_in_transaction_currency",
			label: __("Add Columns in Transaction Currency"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_remarks",
			label: __("Show Remarks"),
			fieldtype: "Check",
		},
		{
			fieldname: "ignore_err",
			label: __("Ignore Exchange Rate Revaluation and Gain / Loss Journals"),
			fieldtype: "Check",
		},
		{
			fieldname: "ignore_cr_dr_notes",
			label: __("Ignore System Generated Credit / Debit Notes"),
			fieldtype: "Check",
		},
	],

	onload: function (report) {
    // Add Print Button
    report.page.add_inner_button(__('Print Report'), function () {
        if (!report.data || !report.data.length) {
            frappe.msgprint(__('No data to print'));
            return;
        }
        showPrintView(report.data, {
            from_date: report.get_values().from_date,
            to_date: report.get_values().to_date
        });
    });
	}

};

erpnext.utils.add_dimensions("General Ledger", 15);

function showPrintView(data, filters) {
    // Group data by party
    const grouped = {};
    data.forEach(row => {
        if (!grouped[row.party]) grouped[row.party] = [];
        grouped[row.party].push(row);
    });

    let sections = "";

    Object.keys(grouped).forEach((party, index, arr) => {
        //  Skip if party is undefined or empty string
        if (!party || party === "undefined" || party.trim() === "") {
            return;
        }

		let customerName = "";
    let customerNameArabic = "";

    // 🔹 Fetch customer details from Customer doctype
    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Customer",
            name: party   // party is customer ID
        },
        async: false,   // keep synchronous for print
        callback: function(r) {
            if (r.message) {
                customerName = r.message.customer_name || "";
                customerNameArabic = r.message.customer_name_in_arabic || "";
            }
        }
    });

        let rows = "";
        let runningBalance = 0;
        let totalDebit = 0;
        let totalCredit = 0;

        // Filter only real transactions (ignore Opening/Total/Closing)
        const realTransactions = grouped[party].filter(
            row =>
                row.remarks !== "Opening" &&
                row.remarks !== "Total" &&
                row.remarks !== "Closing (Opening + Total)"
        );

        //  Skip if no real transactions
        if (realTransactions.length === 0) {
            return;
        }

        // Opening row
        rows += `
            <tr>
                <td></td>
                <td></td>
                <td><b>Opening</b></td>
                <td></td>
                <td></td>
                <td>0.00</td>
            </tr>
        `;

        // Add real transactions
        realTransactions.forEach(row => {
            runningBalance += (row.debit || 0) - (row.credit || 0);
            totalDebit += (row.debit || 0);
            totalCredit += (row.credit || 0);

            rows += `
                <tr>
                   <td>
					${row.posting_date ? frappe.datetime.str_to_obj(row.posting_date).toLocaleDateString("en-GB") : ""}
					</td>
                    <td>${row.voucher_type && row.voucher_no ? row.voucher_type + " " + row.voucher_no : ""}</td>
                    <td>${row.account || ""}</td>
                    <td>${row.debit || 0}</td>
                    <td>${row.credit || 0}</td>
                    <td>${runningBalance}</td>
                </tr>`;
        });

        // Closing row
        rows += `
            <tr>
                <td></td>
                <td></td>
                <td><b>Closing</b></td>
                <td><b>${totalDebit.toFixed(2)}</b></td>
                <td><b>${totalCredit.toFixed(2)}</b></td>
                <td><b>${runningBalance.toFixed(2)}</b></td>
            </tr>
        `;

        // Section per party
        sections += `
            <div class="section">
                <h1>STATEMENTS OF ACCOUNTS</h1>
                <h3 style="margin-top:30px; text-align:left">Customer:${customerName}</h3>
                <h3 style="text-align:left">Customer Arabic Name: ${customerNameArabic}</h3>
                <h3 style="text-align:left">Customer Code:  ${party}</h3>
                <h3 style="text-align:right">
					Date: 
					${filters.from_date ? filters.from_date.split("-").reverse().join("-") : ""} 
					to 
					${filters.to_date ? filters.to_date.split("-").reverse().join("-") : ""}
				</h3>

                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Reference</th>
                            <th>Remarks</th>
                            <th>Debit</th>
                            <th>Credit</th>
                            <th>Balance (Dr - Cr)</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
            ${index < arr.length - 1 ? '<div class="page-break"></div>' : ""}
        `;
    });

    const html = `
        <html>
        <head>
            <title>STATEMENTS OF ACCOUNTS</title>
            <style>
                @media print { 
                    @page { size: landscape; margin: 10mm; }
                    .page-break { page-break-after: always; }
                }
                body { font-family: Arial, sans-serif; font-size: 11px; }
                table { width: 100%; border-collapse: collapse; margin-bottom:30px; page-break-inside: auto; }
                th, td { border: 1px solid #ccc; padding: 5px; text-align:center; }
                th { background: #f4f4f4; }
                h1 { text-align:center; margin-bottom:40px; }
            </style>
        </head>
        <body>
            ${sections || "<h3 style='text-align:center'>No transactions found</h3>"}
        </body>
        </html>
    `;

    const printWindow = window.open('', '_blank');
    printWindow.document.write(html);
    printWindow.document.close();
    setTimeout(() => {
        printWindow.focus();
        printWindow.print();
    }, 200);
}












