frappe.listview_settings['Employee Fincall'] = {
    add_fields: ["calltype"],
    formatters: {
        calltype(call_type, df, doc) {
            call_type = call_type.toLowerCase();
            if (call_type === 'outgoing') {
                return `
                	   <div class="list-row-col hidden-xs ellipsis">
            					<span class="indicator-pill orange filterable no-indicator-dot ellipsis" data-filter="calltype,=,Missed" title="Document is in draft state">
                    				<span class="ellipsis" style='color:orange'>
                                        <svg style='width:14px' fill="orange" version="1.1" id="Capa_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="64px" height="64px" viewBox="0 0 355.694 355.694" xml:space="preserve" stroke="orange"><g id="SVGRepo_bgCarrier" stroke-width="0"></g><g id="SVGRepo_tracerCarrier" stroke-linecap="round" stroke-linejoin="round" stroke="#CCCCCC" stroke-width="3.55694"></g><g id="SVGRepo_iconCarrier"> <g> <g> <g> <path d="M345.923,287.653l-55.22-55.25c-4.3-4.293-10.299-6.652-16.874-6.652c-6.924,0-13.606,2.695-18.326,7.416l-29.844,29.855 l-8.077-4.479c-17.75-9.849-42.045-23.329-67.716-49.035c-25.772-25.737-39.268-50.099-49.137-67.912l-4.414-7.839l29.901-29.897 c9.893-9.917,10.232-25.707,0.75-35.212L71.732,13.421c-4.305-4.29-10.289-6.659-16.855-6.659 c-6.929,0-13.607,2.708-18.324,7.443L22.982,27.848l-1.279,2.083c-5.041,6.476-9.175,13.757-12.274,21.683 c-2.87,7.563-4.66,14.745-5.476,21.945c-7.116,59.195,20.173,113.527,94.218,187.559c87.77,87.748,161.109,94.576,181.495,94.576 c3.482,0,5.603-0.187,6.197-0.252c7.529-0.907,14.735-2.721,22.014-5.543c7.848-3.062,15.102-7.17,21.557-12.214l3.087-2.426 l12.688-12.454C355.086,312.916,355.41,297.142,345.923,287.653z"></path> </g> <g> <path d="M226.283,155.849c2.246,2.252,4.51,3.408,6.726,3.432c1.711,0.018,3.326-0.646,4.569-1.895 c0.312-0.318,0.528-0.594,0.696-0.816l69.896-69.89l21.119,21.109c4.594,4.594,7.619,2.564,8.707,1.462 c2.396-2.39,2.449-7.371,2.396-8.497l8.545-90.469c0.023-0.462,0.282-4.611-2.456-7.569C345.347,1.469,343.257,0,339.696,0 c-9.771,0.006-87.832,10.968-90.757,11.406c-0.931,0-5.74,0.111-8.196,2.57c-1.531,1.537-3.309,4.93,2.102,10.331l19.348,19.354 l-69.188,69.175c-1.682,1.693-3.675,6.059,0.811,10.553L226.283,155.849z"></path> </g> </g> </g> </g></svg>
                    				    Outgoing
                    				</span>
                    			</span>
                    	</div>
                `;
            }
            else if (call_type == "missed") {
                return `
                    <div class="list-row-col hidden-xs ellipsis">
        					<span class="indicator-pill red filterable no-indicator-dot ellipsis" data-filter="calltype,=,Missed" title="Document is in draft state">
                				<span class="ellipsis" style='color:red'>
                                <svg fill='red' xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="#5f6368"><path d="m139-149-79-80q-14-14-14.5-33.5T59-296q79-85 187-134.5T480-480q126 0 234 49.5T901-296q14 14 13.5 33.5T900-229l-79 80q-11 11-28 14t-34-9l-115-82q-9-7-14.5-17.5T624-265v-121q-35-11-70.5-16.5T480-408q-38 0-73.5 5.5T336-386v121q0 11-5.5 21.5T316-226l-115 82q-17 12-34.5 8.5T139-149Zm341-376L312-693v69h-72v-192h192v72h-69l117 117 189-189 51 51-240 240Z"/></svg>
                				    Missed
                				</span>
                			</span>
                	</div>
                `;
            }
            else if (call_type == "incoming") {
                return `
                    <div class="list-row-col hidden-xs ellipsis">
        					<span class="indicator-pill green filterable no-indicator-dot ellipsis" data-filter="calltype,=,Incoming" title="Document is in draft state">
                				<span class="ellipsis" style='color:green'>
                                <svg fill="green" xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 -960 960 960" width="20px" fill="#5f6368"><path d="M763-145q-121-9-229.5-59.5T339-341q-86-86-136-194.5T144-765q-2-21 12.5-36.5T192-817h136q17 0 29.5 10.5T374-780l24 107q2 13-1.5 25T385-628l-97 98q20 38 46 73t58 66q30 30 64 55.5t72 45.5l99-96q8-8 20-11.5t25-1.5l107 23q17 5 27 17.5t10 29.5v136q0 21-16 35.5T763-145ZM528-528v-192h72v69l165-165 51 50-165 166h69v72H528Z"/></svg>
                				    Incoming
                				</span>
                			</span>
                	</div>
                `;
            }
            else {
                return `
                    <div class="list-row-col hidden-xs ellipsis">
        					<span class="indicator-pill blue filterable no-indicator-dot ellipsis" data-filter="calltype,=,Rejected" title="Document is in draft state">
                				<span class="ellipsis">
                				<svg fill='blue' style='width:14px' xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="blue" class="lucide lucide-phone-missed"><line x1="22" x2="16" y1="2" y2="8"/><line x1="16" x2="22" y1="2" y2="8"/><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
                				    Rejected
                				</span>
                			</span>
                	</div>
                `;
            }
        }
    }
};

