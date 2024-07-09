frappe.listview_settings['Employee Fincall'] = {
    add_fields: ["calltype"],
    formatters: {
        calltype(call_type, df, doc) {
            call_type = call_type.toLowerCase();
            if (call_type === 'outgoing') {
                return `
                	   <div class="list-row-col hidden-xs ellipsis">
            					<span class="indicator-pill white filterable no-indicator-dot ellipsis" data-filter="calltype,=,Outgoing" title="Document is in draft state">
                    				<span class="ellipsis text-info">
                                        <svg fill="rgb(23, 162, 184)" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 1000 1000">
                                            <rect width="100%" height="100%" fill="rgba(255,255,255,0)" />
                                            <path vector-effect="non-scaling-stroke"
                                                d="M853.303 969.44q-153.337 0-302.995-66.855T277.981 713.06Q155.31 590.39 88.456 440.732T21.6 137.737q0-22.08 14.72-36.8t36.801-14.721h198.725q17.174 0 30.668 11.654t15.947 27.6l31.894 171.738q2.454 19.628-1.226 33.121t-13.494 23.308l-118.99 120.216q24.534 45.388 58.268 87.71t74.216 81.575q38.027 38.027 79.735 70.535t88.322 59.495l115.31-115.31q11.04-11.04 28.828-16.56t34.96-3.067l169.285 34.348q17.174 4.906 28.214 17.787t11.04 28.827V917.92q0 22.08-14.72 36.8t-36.8 14.721z" />
                                            <path vector-effect="non-scaling-stroke" d="M493.9 507.5l-1.4-1.4 11.6-11.6h-6.6v-2h10v10h-2v-6.6l-11.6 11.6z" />
                                            <path vector-effect="non-scaling-stroke"
                                                d="M480.808 507.491l-38.085-38.085 315.566-315.567H578.743V99.431h272.04v272.04h-54.408V191.925L480.808 507.491z" />
                                        </svg>
                    				    Outgoing
                    				</span>
                    			</span>
                    	</div>
                `;
            }
            else if (call_type == "missed") {
                return `
                    <div class="list-row-col hidden-xs ellipsis">
        					<span class="indicator-pill  white filterable no-indicator-dot ellipsis" data-filter="calltype,=,Missed" title="Document is in draft state">
                				<span class="ellipsis text-warning" >
                                <svg fill="#ffc107" xmlns="http://www.w3.org/2000/svg" height="17px" viewBox="0 -960 960 960" width="17px">
                                    <path
                                        d="m136-144-92-90q-12-12-12-28t12-28q88-95 203-142.5T480-480q118 0 232.5 47.5T916-290q12 12 12 28t-12 28l-92 90q-11 11-25.5 12t-26.5-8l-116-88q-8-6-12-14t-4-18v-114q-38-12-78-19t-82-7q-42 0-82 7t-78 19v114q0 10-4 18t-12 14l-116 88q-12 9-26.5 8T136-144Zm342-362L280-704v104h-80v-240h240v80H336l141 141 226-226 57 57-282 282Z" />
                                </svg>
                				    Missed
                				</span>
                			</span>
                	</div>
                `;
            }
            else if (call_type == "incoming") {
                return `
                    <div class="list-row-col hidden-xs ellipsis">
        					<span class="indicator-pill  white  filterable no-indicator-dot ellipsis" data-filter="calltype,=,Incoming" title="Document is in draft state">
                				<span class="ellipsis text-success">
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
        					<span class="indicator-pill white filterable no-indicator-dot ellipsis" data-filter="calltype,=,Rejected" title="Document is in draft state">
                				<span class="ellipsis  text-danger">
                                <svg fill="rgb(224, 54, 54)" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1"
                                    width="14px" height="14px" viewBox="0 0 1000 1000" xml:space="preserve">
                                    <rect x="0" y="0" width="100%" height="100%" fill="rgba(255,255,255,0)" />
                                    <g transform="matrix(1.2626 0 0 1.2626 499.9905 499.9905)">
                                        <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                            d="M 798 -120 q -125 0 -247 -54.5 T 329 -329 Q 229 -429 174.5 -551 T 120 -798 q 0 -18 12 -30 t 30 -12 h 162 q 14 0 25 9.5 t 13 22.5 l 26 140 q 2 16 -1 27 t -11 19 l -97 98 q 20 37 47.5 71.5 T 387 -386 q 31 31 65 57.5 t 72 48.5 l 94 -94 q 9 -9 23.5 -13.5 T 670 -390 l 138 28 q 14 4 23 14.5 t 9 23.5 v 162 q 0 18 -12 30 t -30 12 Z"
                                            stroke-linecap="round" />
                                    </g>
                                    <g transform="matrix(0.5193 0 0 0.5193 745.8186 234.0324)">
                                        <path vector-effect="non-scaling-stroke" transform="translate(-480, 480)"
                                            d="m 256 -200 l -56 -56 l 224 -224 l -224 -224 l 56 -56 l 224 224 l 224 -224 l 56 56 l -224 224 l 224 224 l -56 56 l -224 -224 l -224 224 Z"
                                            stroke-linecap="round" />
                                    </g>
                                </svg>
                				    Rejected
                				</span>
                			</span>
                	</div>
                `;
            }
        }
    }
};

