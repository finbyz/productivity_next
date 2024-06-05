
frappe.listview_settings['Idle Time Log'] = {
    add_fields: ["status"],
    formatters:{
        status(v, df, doc){
            if(v==='start'){
                return `
                <div class="list-row-col hidden-xs ellipsis">
					<span class="indicator-pill orange filterable no-indicator-dot ellipsis" data-filter="status,=,Pending" title="Document is in draft state">
        				<span class="ellipsis">Start</span>
        			</span>
        		</div>
                `;
            }
            return `
            <div class="list-row-col hidden-xs ellipsis">
					<span class="indicator-pill green filterable no-indicator-dot ellipsis" data-filter="status,=,Success" title="Document is in draft state">
        				<span class="ellipsis">End</span>
        			</span>
        	</div>
            `;    
        }
    }
};

