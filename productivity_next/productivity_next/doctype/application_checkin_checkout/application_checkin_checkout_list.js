frappe.listview_settings['Application Checkin Checkout'] = {
    add_fields: ["status"],
    formatters:{
        status(v, df, doc){
            if(v==='In'){
                return `
                <div class="list-row-col hidden-xs ellipsis">
					<span class="indicator-pill orange filterable no-indicator-dot ellipsis" data-filter="status,=,Out" title="Document is in draft state">
        				<span class="ellipsis">Out</span>
        			</span>
        		</div>
                `;
            }
            return `
            <div class="list-row-col hidden-xs ellipsis">
					<span class="indicator-pill green filterable no-indicator-dot ellipsis" data-filter="status,=,In" title="Document is in draft state">
        				<span class="ellipsis"> In</span>
        			</span>
        	</div>
            `;
            
        }
    }
};

