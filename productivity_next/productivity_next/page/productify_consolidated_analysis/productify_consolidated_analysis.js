frappe.pages['Productify Consolidated Analysis'].on_page_load = function (wrapper) {
	new UserProfile(wrapper);
}

UserProfile = class UserProfile {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
		});
		this.sidebar = this.wrapper.find(".layout-side-section");
		this.toggle_button = this.wrapper.find(".sidebar-toggle-placeholder");
		this.main_section = this.wrapper.find(".layout-main-section");
		this.buttonsInitialized = false;
		const urlParams = new URLSearchParams(window.location.search);
		if (urlParams.get('start_date') == null && urlParams.get('end_date') == null) {
			var currentDate = new Date();
			currentDate.setDate(currentDate.getDate() - 1);
			var day = currentDate.getDate().toString().padStart(2, '0');
			var month = (currentDate.getMonth() + 1).toString().padStart(2, '0');
			var year = currentDate.getFullYear();
			this.selected_start_date = year + '-' + month + '-' + day;
			this.selected_end_date = year + '-' + month + '-' + day;
		}
		else {
			this.selected_start_date = urlParams.get('start_date');
			this.selected_end_date = urlParams.get('end_date');
		}
		if (urlParams.get('employee') != null && urlParams.get('employee') != 'undefined') {
			this.selected_employee = urlParams.get('employee');
		}
		else {
			this.selected_employee = null;
		}
		this.hide_sidebar_and_toggle();
		this.wrapper.bind("show", () => {
			this.show();
		});
		this.sorting_data = {};
	}

	hide_sidebar_and_toggle() {
		this.sidebar.hide();
		this.main_section.css('width', '100%');
	}

	show() {
		this.user_id = frappe.session.user;
		frappe.dom.freeze(__("Loading user profile") + "...");
		frappe.db.exists("User", this.user_id).then((exists) => {
			frappe.dom.unfreeze();
			if (exists) {
				this.make_user_profile();
			} else {
				frappe.msgprint(__("User does not exist"));
			}
		});
	}

	finish_user_profile_setup() {
		this.setup_refresh(); // Refresh Button
		this.setup_timespan(); // Timespan Button
		this.main_section.empty().append(frappe.render_template("productify_consolidated_analysis"));
		this.user_analysis(); // User Analysis (User Productivity Stats)
		this.client_calls_chart();
		// this.overall_performance_chart(); // Overall Performance (All Employees)
		// JavaScript to handle tab switching
		const tabs = document.querySelectorAll('.nav-link');
		const contents = document.querySelectorAll('.tab-pane');
	
		tabs.forEach(tab => {
			tab.addEventListener('click', () => {
				const target = document.querySelector(tab.getAttribute('data-bs-target'));
				
				// Log aria-labelledby attribute
				// console.log(target.getAttribute('aria-labelledby'));
				
				// Manage tab and content visibility
				tabs.forEach(t => t.classList.remove('active'));
				tab.classList.add('active');
				
				// Check aria-labelledby and execute methods if needed
				if (target.getAttribute('aria-labelledby') === 'system-activity-tab') {
					this.document_analysis_chart(); // Document Analysis (Numbers Of Document Modified)
				}
				if (target.getAttribute('aria-labelledby') === 'phone-calls-tab') {
					this.client_calls_chart(); // Top 10 Clients Call Analysis (In Minutes)
					this.employee_calls_chart(); // Top 10 Employees Call Analysis
				}
				
				contents.forEach(content => content.classList.remove('show', 'active'));
				target.classList.add('show', 'active');
			});
		});
	}

	// Refresh Button Code Starts
	setup_refresh() {
		if (!this.buttonsInitialized) {
			this.page.add_action_icon("refresh", () => {
				window.location.reload();
			});
			this.buttonsInitialized = true;
		}
	}
	// Refresh Button Code Ends

	// Timespan Button Code Starts
	setup_timespan() {
		this.$user_search_button = this.page.set_primary_action(
			__("Select Timespan"),
			() => this.setup_timespan_dialog(),
		);
	}
	setup_timespan_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: __("Select Timespan"),
			fields: [
				{
					fieldtype: "DateRange",
					fieldname: "timespan_range",
					label: __("Timespan Range"),
					description: __("Select a start and end date"),
				},
			],
			primary_action_label: __("Go"),
			primary_action: (data) => {
				let startDate, endDate;
				if (data.timespan_range) {
					[startDate, endDate] = data.timespan_range;
				} else {
					const today = new Date();
					endDate = today.toISOString().split('T')[0];

					const oneYearAgo = new Date(new Date().setFullYear(today.getFullYear() - 1));
					startDate = oneYearAgo.toISOString().split('T')[0];
				}

				dialog.hide();
				const newUrl = new URL(window.location.href);
				newUrl.searchParams.set('start_date', startDate);
				newUrl.searchParams.set('end_date', endDate);
				window.history.pushState({ path: newUrl.toString() }, '', newUrl.toString());
				const urlParams = new URLSearchParams(window.location.search);
				this.selected_start_date = urlParams.get('start_date');
				this.selected_end_date = urlParams.get('end_date');
				this.make_user_profile();
			},
		});
		dialog.show();
	}
	// Timespan Button Code Ends

	// All Employees Page Title Code
	make_user_profile() {
		if (!this.selected_employee) {
			this.page.set_title("All Employees" + " ( FROM " + this.selected_start_date + " TO " + this.selected_end_date + " )");
		} else {
			frappe.db.get_doc("Employee", this.selected_employee)
				.then(employee => {
					this.page.set_title("All Employees" + " ( FROM " + this.selected_start_date + " TO " + this.selected_end_date + " )");
					this.finish_user_profile_setup();
				})
				.catch(error => {
					console.error("Failed to get employee details:", error);
					frappe.msgprint(__("Failed to load employee details"));
				});
		}
		if (!this.selected_employee) {
			this.finish_user_profile_setup();
		}
	}
	// All Employees Page Title Code Ends

	// Code to convert time in seconds to formatted time for example 3600 seconds to 1 hours 0 minutes Code Start
	convertSecondsToTime(seconds) {
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		return `<b>${hours}</b><span style="font-size:12px"> hours </span><b>${minutes}</b><span style="font-size:12px"> minutes</span>`;
	}
	// Code to convert time in seconds to formatted time for example 3600 seconds to 1 hours 0 minutes Code Ends


	// Code to convert time in seconds to formatted time for example 3600 seconds to 01:00 Code Start
	convertSecondsToTime_(seconds) {
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const formattedMinutes = minutes < 10 ? `0${minutes}` : minutes;
		const formattedHours = hours < 10 ? `0${hours}` : hours;

		return `${formattedHours}:${formattedMinutes}`;
	}
	// Code to convert time in seconds to formatted time for example 3600 seconds to 01:00 Code Ends


	// Document Analysis (Numbers Of Document Modified) Code Starts
	document_analysis_chart() {
		let barchartDom = document.querySelector('.document-analysis-chart');
		let barchart = echarts.init(barchartDom, null, { renderer: 'svg' });
		window.addEventListener('resize', barchart.resize);
		frappe
			.xcall("productivity_next.productivity_next.page.productify_consolidated_analysis.productify_consolidated_analysis.document_analysis_chart", {
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.labels.length === 0) {
				} else {
					let option = {
						grid: {
							top: 5, 
						},
						tooltip: {
							trigger: 'item'
						},
						xAxis: {
							type: 'category',
							data: r.labels,
							axisLabel: {
								interval: 0,
								rotate: 15,
							},
							z: 10
						},
						yAxis: {
							type: 'value',
						},
						dataZoom: [
							{
								type: 'inside',
								disabled: true
							},
							{
								type: 'slider',
								show: false,
								start: 0,
								end: 100,
								zoomLock: true,
								yAxisIndex: 0
							}
						],
						series: [
							{
								data: r.datasets[0].values,
								type: 'bar'
							}
						],
					};
					barchart.resize();
					barchart.setOption(option);
					barchart.getZr().on('mousewheel', function (e) {
					});
					barchart.getZr().on('pinch', function (e) {
					});
					window.addEventListener('resize', function () {
						barchart.resize();
					});
				}
			});
	};
	// Document Analysis (Numbers Of Document Modified) Code Ends
	

	// Top 10 Clients Call Analysis (In Minutes) Code Starts
	client_calls_chart() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
	
		frappe
			.xcall("productivity_next.productivity_next.page.productify_consolidated_analysis.productify_consolidated_analysis.client_calls_chart", {
				user: "Administrator",
				start_date: this.selected_start_date,
				end_date: this.selected_end_date
			})
			.then((r) => {
				const containerElement = document.getElementById('phone-calls-tab');
				if (r.caller_details.length === 0) {
					if (containerElement) containerElement.style.display = 'none';
                	return;
				}
	
				const chartDom = document.getElementById('client-calls-chart');
				if (!chartDom) {
					return;
				}
	
				const myChart = echarts.init(chartDom, null, { renderer: 'svg' });
				let customNames = r.customNames;
	
				const option = {
					tooltip: {
						trigger: 'item',
						formatter: function(params) {
							let totalMinutes = params.value;
							let minutes = Math.floor(totalMinutes); 
							let seconds = Math.round((totalMinutes - minutes) * 60);
							let formattedSeconds = (seconds < 10 ? '0' : '') + seconds;
						
							if (params.seriesName === 'Caller Origin' || params.seriesName === 'Caller Details') {
								return `${params.marker} ${params.name}: ${minutes}:${formattedSeconds} Min`;
							} else {
								return `${params.seriesName} <br/>${params.marker} ${params.name}: ${minutes}.${formattedSeconds} Min`;
							}
						},
						position: ['50%', '50%'],
					},
					series: [
						{
							name: 'Caller Origin',
							type: 'pie',
							selectedMode: 'single',
							radius: [0, '30%'],
							label: {
								position: 'inner',
								fontSize: 14,
							},
							labelLine: {
								show: true
							},
							data: r.company_details,
							color: [
								'#FF6384',
								'#36A2EB',
								'#FFCE56',
								'#4BC0C0',
								'#9966FF',
								'#FF9966',
								'#66CCCC',
								'#6699FF',
								'#FF6666',
								'#FFCC66'
							]
						},
						{
							name: 'Caller Details',
							type: 'pie',
							radius: ['45%', '60%'],
							labelLine: {
								length: 30,
								show: true
							},
							label: {
								formatter: function(params) {
									let totalMinutes = params.value;
									let minutes = Math.floor(totalMinutes);
									let seconds = Math.round((totalMinutes - minutes) * 60); 
								
									let formattedSeconds = (seconds < 10 ? '0' : '') + seconds;
								
									let customIndex = params.data.customIndex || 0; 
									let customName = customNames[customIndex];
								
									return `{a|${customName}} {abg|}\n{hr|}\n  {b|     ${params.name}：}${minutes}:${formattedSeconds} Min  `;
								},
								backgroundColor: '#F6F8FC',
								borderColor: '#8C8D8E',
								borderWidth: 1,
								borderRadius: 4,
								show: true,
								rich: {
									a: {
										color: '#6E7079',
										lineHeight: 22,
										textAlign: 'center',
										overflow: 'hidden',
										textOverflow: 'ellipsis',
										whiteSpace: 'nowrap',
									},
									hr: {
										borderColor: '#8C8D8E',
										width: '100%',
										borderWidth: 1,
										height: 0,
									},
									b: {
										color: '#4C5058',
										fontSize: 14,
										fontWeight: 'bold',
										lineHeight: 30,
										marginRight: 10,
									}
								},
							},
							data: r.caller_details,
							color: [
								'#FF6384', 
								'#36A2EB', 
								'#FFCE56', 
								'#4BC0C0', 
								'#9966FF', 
								'#FF9966', 
								'#66CCCC', 
								'#6699FF', 
								'#FF6666', 
								'#FFCC66'  
							]
						}
					],
				};
	
				myChart.resize();
				myChart.setOption(option);
				var selected_start_date = this.selected_start_date;
				var selected_end_date = this.selected_end_date;
				// Add click event listener to the link after the chart is rendered
				document.getElementById('client-calls-analysis-link').addEventListener('click', function(event) {
					goToCallsAnalysisClient(selected_start_date, selected_end_date); // Pass dates to redirect function
				});
	
				window.addEventListener('resize', function () {
					myChart.resize();
				});
			})
			.catch(error => {
				console.error('Error fetching data:', error);
			});
	
		// Function to redirect to Calls Analysis page with selected dates
		function goToCallsAnalysisClient(start_date, end_date) {
			// console.log("start_date", start_date);	
			// console.log("end_date", end_date);
			var baseUrl = window.location.origin;
			
			// Construct the URL with the parameters
			var activityAnalysisUrl = baseUrl + "/app/query-report/Calls Analysis?group_by_party=1&from_date=" + start_date + "&to_date=" + end_date;
			
			// Redirect to the constructed URL
			window.open(activityAnalysisUrl, '_blank');
		}
	}
	
	
	// Top 10 Clients Call Analysis (In Minutes) Code Ends


	// Top 10 Employees Call Analysis Code Starts
	employee_calls_chart() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		
		frappe
			.xcall("productivity_next.productivity_next.page.productify_consolidated_analysis.productify_consolidated_analysis.employee_calls_chart", {
				user: "Administrator",
				start_date: this.selected_start_date,
				end_date: this.selected_end_date
			})
			.then((r) => {
				const containerElement = document.getElementById('employee-calls');
				if (r.datasets.length === 0) {
					console.log("No data found for employee calls");
					if (containerElement) containerElement.style.display = 'none';
					return;
				}
				else{
				let seriesData = [];
				r.datasets.forEach(dataset => {
					const counts = dataset.counts.map(count => parseInt(count)); 
					const series = {
						name: dataset.name,
						data: counts,
						type: 'bar',
						stack: 'x'
					};
					seriesData.push(series);
				});	
				let option = {
					tooltip: {
						trigger: 'axis',
						axisPointer: {
							type: 'shadow'
						},
						
						formatter: function(params) {
							let html = `
								<div class="custom-tooltip" style="
									position: absolute;
									display: block;
									border-style: solid;
									white-space: nowrap;
									z-index: 9999999;
									will-change: transform;
									box-shadow: rgba(0, 0, 0, 0.2) 1px 2px 10px;
									transition: opacity 0.2s cubic-bezier(0.23, 1, 0.32, 1) 0s, visibility 0.2s cubic-bezier(0.23, 1, 0.32, 1) 0s, transform 0.4s cubic-bezier(0.23, 1, 0.32, 1) 0s;
									background-color: rgb(255, 255, 255);
									border-width: 1px;
									border-radius: 4px;
									color: rgb(102, 102, 102);
									font: 14px / 21px 'Microsoft YaHei';
									padding: 12px; /* Increased padding */
									width: 200px; /* Adjust width as needed */
									top: 0px4;
									left: 0px;
									transform: translate3d(0, 0, 0);
									border-color: rgb(255, 255, 255);
									pointer-events: none;
								">
									<div style="font-size: 16px; color: #666; font-weight: 400; margin-bottom: 10px;"> <!-- Increased font-size -->
										${params[0].axisValueLabel} 
									</div>
							`;
						
							params.forEach(param => {
								let color = '';
								if (param.seriesName === 'Incoming') {
									color = '#91cc75'; 
								} else if (param.seriesName === 'Outgoing') {
									color = '#5470c6'; 
								} else if (param.seriesName === 'Missed') {
									color = '#fac858'; 
								} else if (param.seriesName === 'Rejected') {
									color = '#ee6666'; 
								}
								html += `
									<div style="margin-bottom: 5px;">
										<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: ${color}; margin-right: 5px;"></span>
										<span style="font-size: 14px; color: #666; font-weight: 400;">${param.seriesName}</span>
										<span style="float: right; font-size: 13px; color: #666; font-weight: 900;">${param.value} Calls</span>
										<div style="clear: both;"></div>
									</div>
								`;
							});
						
							html += `
								</div>
							`;
						
							return html;
						}
					},
						
					xAxis: {
						data: r.labels,
						axisLabel: {
							interval: 0,
							rotate: 20,
						},
					},
					yAxis: {},
					series: seriesData
				};
	
				let chartDom = document.getElementById('employee-calls-chart');
				let myChart = echarts.init(chartDom, null, { renderer: 'svg' });
				myChart.setOption(option);
				var selected_start_date = this.selected_start_date;
				var selected_end_date = this.selected_end_date;
				// Add click event listener to the link after the chart is rendered
				document.getElementById('employee-calls-analysis-link').addEventListener('click', function(event) {
					goToCallsAnalysisEmployee(selected_start_date, selected_end_date); // Pass dates to redirect function
				});
				window.addEventListener('resize', function() {
					myChart.resize();
				});
				}
			})
			.catch((error) => {
				console.error("Error fetching chart data:", error);
			});

		// Function to redirect to Calls Analysis page with selected dates
		function goToCallsAnalysisEmployee(start_date, end_date) {
			// console.log("start_date", start_date);	
			// console.log("end_date", end_date);
			var baseUrl = window.location.origin;
			
			// Construct the URL with the parameters
			var activityAnalysisUrl = baseUrl + "/app/query-report/Calls Analysis?from_date=" + start_date + "&to_date=" + end_date;
			
			// Redirect to the constructed URL
			window.open(activityAnalysisUrl, '_blank');
		}
	}
	// Top 10 Employees Call Analysis Code Ends


	// Overall Performance (All Employees) Code Starts
	overall_performance_chart() {
		let overallPerformanceDom = document.querySelector('.overall-performance-chart');
		let overallPerformance = echarts.init(overallPerformanceDom, null, { renderer: 'svg' });
		window.addEventListener('resize', overallPerformance.resize);
	
		frappe.xcall("productivity_next.productivity_next.page.productify_consolidated_analysis.productify_consolidated_analysis.overall_performance_chart", {
			start_date: this.selected_start_date,
			end_date: this.selected_end_date,
		}).then((r) => {
			if (r.base_data.length === 0) {
			} else {
				// console.log(r);
				
				var _rawData = {
					flight: {
						dimensions: r.base_dimensions,
						data: r.base_data
					},
					parkingApron: {
						dimensions: r.dimensions,
						data: r.data
					}
				};
	
				var priorityOrder = {
					'Inactive': 0,
					'Application': 1,
					'Idle': 2,
					'Internal Meeting': 3,
					'External Meeting': 4,
					'Call': 5
				};

				var inactivePeriods = [];
				var employeeFirstEntry = {};

				function formatTimestamp(timestamp) {
					const date = new Date(timestamp);
					const year = date.getFullYear();
					const month = String(date.getMonth() + 1).padStart(2, '0');
					const day = String(date.getDate()).padStart(2, '0');
					const hours = String(date.getHours()).padStart(2, '0');
					const minutes = String(date.getMinutes()).padStart(2, '0');
					const seconds = String(date.getSeconds()).padStart(2, '0');
				
					return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
				}
	
				for (var i = 0; i < _rawData.parkingApron.data.length; i++) {
					var employeeName = _rawData.parkingApron.data[i][0];
					var employeeActivities = _rawData.flight.data.filter(item => item[1] === employeeName);
					employeeActivities.sort((a, b) => new Date(a[2]) - new Date(b[2]));
	
					if (employeeActivities.length > 0) {
						employeeFirstEntry[employeeName] = new Date(employeeActivities[0][2]).getTime();
						var lastEndTime = new Date(employeeActivities[0][3]).getTime();
	
						for (var j = 1; j < employeeActivities.length; j++) {
							var startTime = new Date(employeeActivities[j][2]).getTime();
							if (startTime > lastEndTime) {
								// console.log('Inactive period found for', employeeName, 'from', lastEndTime, 'to', startTime)
								var startTimeString = formatTimestamp(lastEndTime);
								var endTimeString = formatTimestamp(startTime);
								inactivePeriods.push(['Inactive', employeeName, startTimeString, endTimeString]);
							}
							lastEndTime = new Date(employeeActivities[j][3]).getTime();
						}
					}
				}
				_rawData.flight.data = _rawData.flight.data.concat(inactivePeriods);
				_rawData.flight.data.sort((a, b) => priorityOrder[a[0]] - priorityOrder[b[0]]);
	
				function renderGanttItem(params, api) {
					var xValue = api.value(2);
					var xEndValue = api.value(3);
					var gateIndex = api.value(1);
					var yValue = api.coord([0, gateIndex])[1];
					var activityType = api.value(0);
				
					var color;
				
					switch (activityType) {
						case 'Application':
							color = '#4BC0C0';
							break;
						case 'Idle':
							color = '#FF6666';
							break;
						case 'Call':
							color = '#FFCC66';
							break;
						case 'Internal Meeting':
							color = '#9966FF';
							break;
						case 'External Meeting':
							color = '#6699FF';
							break;
						case 'Inactive':
							color = '#E9EAEC';
							break;
						default:
							color = '#000000';
					}
				
					var item = {
                        type: 'rect',
                        shape: {
                            x: api.coord([xValue, yValue])[0],
                            y: yValue - 10,
                            width: api.size([xEndValue - xValue, 0])[0],
                            height: 20,
                        },
                        style: api.style({
                            fill: color,
                            stroke: 'rgba(0,0,0,0.2)'
                        })
                    };                    	
					return item;
				}
				// console.log("data",_rawData.parkingApron.data.map(item => item[0]))
				// Define the sortEmployeeNames function
				function sortEmployeeNames(sorting_data, yAxisData) {
					const employeeMap = new Map(sorting_data.map(item => [item.employeeName, item]));
				
					// console.log("Employee Map:", Array.from(employeeMap.keys()));
					// console.log("yAxisData:", yAxisData);
				
					const matchedData = yAxisData.map(name => {
						const match = Array.from(employeeMap.keys()).find(fullName => {
							const [firstName, ...rest] = fullName.split(' ');
							const lastNameInitial = rest.length > 0 ? rest[rest.length - 1][0] : '';
							const namePattern = `${firstName} ${lastNameInitial ? lastNameInitial+'.' : ''}`;
							const isMatch = name.startsWith(namePattern);
							// console.log(`Comparing ${name} with ${namePattern}: ${isMatch}`);
							return isMatch;
						});
						return { name, fullName: match };
					}).filter(item => item.fullName !== undefined);
				
					// console.log("Matched Data:", matchedData);
				
					const sortedData = matchedData.sort((a, b) => {
						return sorting_data.findIndex(item => item.employeeName === a.fullName) - 
							   sorting_data.findIndex(item => item.employeeName === b.fullName);
					}).map(item => item.name);
				
					// console.log("Sorted Data:", sortedData);
					return sortedData;
				}

				// Define the makeOption function
				function makeOption(sorting_data) {
					// console.log("sorting_data", sorting_data);
					var activityLegends = [
						{ name: 'Application', color: '#00A6E0' },
						{ name: 'Idle', color: '#FF4001' },
						{ name: 'Call', color: '#62BA46' },
						{ name: 'Internal Meeting', color: '#6420AA' },
						{ name: 'External Meeting', color: '#6699FF' },
						{ name: 'Inactive', color: '#C1C1C1' }
					];
					var legendData = [];
					activityLegends.forEach(function(item) {
						legendData.push({
							name: item.name,
							icon: 'rect',
							textStyle: {
								fontSize: 12
							}
						});
					});
					var startTimeList = _rawData.flight.data.map(item => new Date(item[2]).getTime());
					var endTimeList = _rawData.flight.data.map(item => new Date(item[3]).getTime());
					var minStartTime = Math.min(...startTimeList);
					var maxEndTime = Math.max(...endTimeList);

					// Add 30 minutes padding to both start and end times
					minStartTime = minStartTime - (60 * 60 * 1000);
					maxEndTime = maxEndTime + (60 * 60 * 1000);

					// Create Date objects for the xAxis min and max
					var fixedStartTime = new Date(minStartTime);
					var fixedEndTime = new Date(maxEndTime);

					// Sort the y-axis data
					// console.log("yAxisData", _rawData.parkingApron.data.map(item => item[0]));
					const sortedYAxisData = sortEmployeeNames(sorting_data, _rawData.parkingApron.data.map(item => item[0]));
					// console.log("sortedYAxisData", sortedYAxisData);
					return {
						backgroundColor: 'transparent',
						tooltip: {
							formatter: function(params) {
								var activityType = params.data[0];
								var employeeName = params.data[1];
								var startTime = new Date(params.data[2]);
								var endTime = new Date(params.data[3]);
								var startTimeString = startTime.toLocaleString();
								var endTimeString = endTime.toLocaleString();
							
								var durationMs = endTime - startTime;
								var durationSeconds = Math.floor(durationMs / 1000);
							
								var hours = Math.floor(durationSeconds / 3600);
								var minutes = Math.floor((durationSeconds % 3600) / 60);
								var seconds = durationSeconds % 60;
							
								var durationString = "";
								if (hours > 0) {
									durationString += hours + "h ";
								}
								if (minutes > 0) {
									durationString += minutes + "m ";
								}
								if (seconds > 0 || durationString === "") {
									durationString += seconds + "s";
								}
							
								var tooltipContent = `<div style="line-height: 1.5;">`;
							
								if (activityType === 'Call' && params.data[4]) {
									tooltipContent += `<span style="font-weight: bold;font-size:15px;"> ${params.data[4]}</span><br>`;
									tooltipContent += `<span style="font-weight: bold;font-size:15px;"> Call Type:</span> ${params.data[5]}<br>`;
								} else if (activityType === 'Internal Meeting' || activityType === 'External Meeting') {
									if (params.data[4]) tooltipContent += `<span style="font-weight: bold;font-size:15px;">Arranged By:</span> ${params.data[4]}<br>`;
									if (params.data[5]) tooltipContent += `<span style="font-weight: bold;font-size:15px;">${params.data[5]} </span><br>`;
									if (params.data[7]) tooltipContent += `<span style="font-weight: bold;">Arranged By:</span>${params.data[7]}<br>`;
									tooltipContent += `<span style="font-weight: bold;">Activity:</span>${params.data[6] || ''} Meeting<br>`;
								}
								else{
									tooltipContent += `<span style="font-weight: bold;">Activity:</span>${activityType}<br>`;
								}
							
								tooltipContent += `
									<span style="font-weight: bold;">Employee:</span> ${employeeName}<br>
									<span style="font-weight: bold;">Start:</span> ${startTimeString}<br>
									<span style="font-weight: bold;">End:</span> ${endTimeString}<br>
									<span style="font-weight: bold;">Duration:</span> ${durationString}`;
								tooltipContent += `</div>`;
							
								return tooltipContent;
							},
						},
						animation: false,
						toolbox: {
							left: 20,
							top: 0,
							itemSize: 20
						},
						legend: {
							show: true,
							selected: {
								'Application': true,
								'Idle': true,
								'Call': true,
								'Internal Meeting': true,
								'External Meeting': true,
								'Inactive': true
							},
							data: legendData,
							orient: 'horizontal',
							top: 80,
							left: 'center',
							itemWidth: 25,
							itemHeight: 14,
							itemGap: 25,
							selectedMode: false,
							formatter: function(name) {
								var item = activityLegends.find(l => l.name === name);
								return `{marker|} {name|${name}}`;
							},
							textStyle: {
								rich: {
									marker: {
										width: 25,
										height: 14,
										align: 'center',
										verticalAlign: 'middle',
										backgroundColor: function(params) {
											var item = activityLegends.find(l => l.name === params.name);
											return item ? item.color : '';
										}
									},
									name: {
										fontSize: 12,
										padding: [0, 0, 0, 5]
									}
								}
							}
						},
						zIndex: 100,
						dataZoom: [
							{
								type: 'slider',
								yAxisIndex: 0,
								zoomLock: true,
								width: 10,
								right: 10,
								top: 70,
								startValue: 0,
								endValue: 10,
								bottom: 20,
								handleSize: 0,
								showDetail: false
							},
							{
								type: 'inside',
								id: 'insideY',
								yAxisIndex: 0,
								startValue: 0,
								endValue: 10,
								zoomOnMouseWheel: false,
								moveOnMouseMove: true,
								moveOnMouseWheel: true
							}
						],  
						grid: {
							show: true,
							top: 20,
							bottom: 20,
							left: 5,
							right: 20,
							backgroundColor: 'transparent',
							borderWidth: 0
						},
						yAxis: {
							type: 'category',
							axisTick: { show: false },
							splitLine: { show: false },
							axisLine: { show: false },
							axisLabel: { 
								show: true,
								align: 'left',
								margin: 5,
								formatter: function(value) {
									return value.length > 20 ? value.substr(0, 17) + '...' : value;
								},
								rich: {
									a: {
										align: 'left',
										width: 140, 
									}
								}
							},
							data: sortedYAxisData,
							min: 0,
							max: sortedYAxisData.length - 1,
							inverse: true
						},
						xAxis: {
							type: 'time',
							position: 'top',
							splitLine: {
								lineStyle: {
									color: ['#E9EDFF']
								}
							},
							axisLine: {
								show: false
							},
							axisTick: {
								lineStyle: {
									color: '#929ABA'
								}
							},
							axisLabel: {
								color: '#929ABA',
								inside: false,
								align: 'center',
								formatter: function(value, index) {
									var date = new Date(value);
									var hours = date.getHours();
									var minutes = date.getMinutes();
									var ampm = hours >= 12 ? 'PM' : 'AM';
									hours = hours % 12;
									hours = hours ? hours : 12;
									var minutesStr = minutes < 10 ? '0' + minutes : minutes;
									var strTime = hours + ':' + minutesStr + ' ' + ampm;
									return strTime;
								}
							},
							min: fixedStartTime,
							max: fixedEndTime,
						},
						series: [									
							{
								id: 'flightData',
								type: 'custom',
								renderItem: renderGanttItem,
								dimensions: _rawData.flight.dimensions,
								encode: {
									x: [2, 3],
									y: 1,
								},
								data: _rawData.flight.data,
								barGap: '5%', // Adjust gap between bars
								barCategoryGap: '20%',
								barWidth: 8, // Adjust bar width
								barMaxWidth: 20, 
							},
							{
								type: 'custom',
								render: renderAxisLabelItem,
								dimensions: _rawData.parkingApron.dimensions,
								encode: {
									x: -1,
									y: 0
								},
								data: sortedYAxisData.map(function (item, index) {
									return [index].concat([item]);
								})
							}
						]
					};
				}

				// Assuming you have a renderGanttItem function defined elsewhere
				// function renderGanttItem(params, api) { ... }

				// Assuming you have a renderAxisLabelItem function defined elsewhere
				// function renderAxisLabelItem(params, api) { ... }

				// Usage example (you would call this when you want to create/update the chart)
				// var chart = echarts.init(document.getElementById('chartContainer'));
				// var option = makeOption(sorting_data);
				// chart.setOption(option);
	
				function renderAxisLabelItem(params, api) {
					var yIndex = api.value(0);
					var xValue = api.value(1);
	
					return {
						type: 'text',
						position: [xValue, yIndex],
						value: xValue,
						style: api.style()
					};
				}
					overallPerformance.setOption(makeOption(this.sorting_data));
					overallPerformance.on('click', function (params) {
						if (params.value[0] === 'Inactive' || params.value[0] === 'Idle') {
							var startTime = params.value[2];
							var endTime = params.value[3];
							var employeeName = params.value[1];
					
							// Fetch employee data and project enabled status
							Promise.all([
								frappe.call({
									method: "productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.get_project_enabled",
								}),
								frappe.db.get_value('Employee', {user_id: frappe.session.user}, ['name', 'employee_name'])
							]).then(([subscription_response, employee_response]) => {
								console.log("Project Enabled:", subscription_response.message);
								const projectEnabled = subscription_response.message ? subscription_response.message : false;
								const currentUserEmployee = employee_response.message;
								
								// Define fields for the dialog
								const table_fields = [
									{
										label: "Employee",
										fieldname: "employee",
										fieldtype: "Link",
										in_list_view: 1,
										options: "Employee",
										ignore_user_permissions: 1,
										reqd: 1,
									}
								];
								const party_fields = [
									{
										label: 'Contact',
										fieldname: 'contact',
										fieldtype: 'Link',
										options: 'Contact',
										in_list_view: 1,
										get_query: function() {
											const selectedParty = d.get_values().party;
											const selectedPartyType = d.get_values().party_type;
											return {
												filters: {
													link_doctype: selectedPartyType,
													link_name: selectedParty
												}
											};
										}
									}
								];
								var fields = [
									{
										fieldtype: "HTML",
										options: "<div style='color:red; margin-top: 10px;'><b>Note: This meeting will be submitted and no changes permitted after submission.</b></div>"
									},
									{
										fieldtype: 'Section Break',
									},
									{
										label: "Internal Meeting",
										fieldname: "internal_meeting",
										fieldtype: "Check",
										onchange: function() {
											const companyRepField = d.fields_dict.meeting_company_representative;
											if (this.get_value()) {
												companyRepField.df.reqd = 1;
												companyRepField.grid.min_rows = 2;
											} else {
												companyRepField.df.reqd = 0;
												companyRepField.grid.min_rows = 0;
											}
											companyRepField.refresh();
										}
									},
									{
										fieldname: 'internal_meeting_note',
										fieldtype: 'HTML',
										options: '<div class="text-muted">Note: Internal meetings require at least two company representatives.</div>',
										depends_on: 'eval:doc.internal_meeting'
									},
									{
										label: "Purpose",
										fieldname: "purpose",
										fieldtype: "Link",
										options: "Meeting Purpose",
										reqd: 1
									},
									{
										label: __("Party Type"),
										fieldtype: 'Link',
										options: "DocType",
										fieldname: 'party_type',
										get_query: function () {
											return {
												filters: {
													"name": ["in", ["Customer", "Supplier", "Lead"]]
												}
											};
										},
										depends_on: 'eval:!doc.internal_meeting',
										mandatory_depends_on: 'eval:!doc.internal_meeting',
									},
									{
										label: 'Party',
										fieldname: 'party',
										fieldtype: 'Dynamic Link',
										options: 'party_type',
										change: function() {
											const selectedParty = d.get_value('party');
											const selectedPartyType = d.get_value('party_type');
									
											if (selectedParty && selectedPartyType) {
												d.fields_dict['meeting_party_representative'].grid.get_field('contact').get_query = function() {
													return {
														filters: {
															link_doctype: selectedPartyType,
															link_name: selectedParty
														}
													};
												};
												d.fields_dict['meeting_party_representative'].grid.refresh();
											}
										},
										depends_on: 'eval:!doc.internal_meeting',
										mandatory_depends_on: 'eval:!doc.internal_meeting',
									},
									{
										label: "Meeting Arranged By",
										fieldname: "meeting_arranged_by",
										fieldtype: "Link",
										options: "User",
										default: frappe.session.user,
										reqd: 1
									},
									{
										fieldtype: 'Column Break',
									},
									{
										label: 'Meeting From',
										fieldname: 'meeting_from',
										fieldtype: 'Datetime',
										default: startTime,
										reqd: 1
									},
									{
										label: 'Meeting To',
										fieldname: 'meeting_to',
										fieldtype: 'Datetime',
										default: endTime,
										reqd: 1
									},
									{
										fieldtype: 'Section Break',
									},
									{
										label: 'Meeting Company Representative',
										"allow_bulk_edit": 1,
										fieldname: 'meeting_company_representative',
										fieldtype: 'Table',
										fields: table_fields,
										options: 'Meeting Company Representative',
										reqd: 1,
										onchange: function() {
											if (d.get_value('internal_meeting')) {
												this.grid.min_rows = 2;
											} else {
												this.grid.min_rows = 0;
											}
										}
									},
									{
										fieldtype: 'Section Break',
									},
									{
										label: 'Meeting Party Representative',
										fieldname: 'meeting_party_representative',
										fieldtype: 'Table',
										fields: party_fields,
										options: 'Meeting Party Representative',
										depends_on: 'eval:!doc.internal_meeting',
									},
									{
										label: "Discussion",
										fieldname: "discussion",
										fieldtype: "Text Editor",
										reqd: 1
									},
								];
					
								// Add Project field if enabled in Productify Subscription
								if (projectEnabled) {
									fields.splice(9, 0, {
										label: "Project",
										fieldname: "project",
										fieldtype: "Link",
										options: "Project"
									});
								}
					
								let d = new frappe.ui.Dialog({
									title: 'Add Meeting',
									fields: fields,
									primary_action_label: 'Submit',
									primary_action(values) {
										this.disable_primary_action();
										this.set_title('Submitting...');
								
										if (values.internal_meeting) {
											const companyRepresentatives = values.meeting_company_representative || [];
											if (companyRepresentatives.length < 2) {
												frappe.msgprint(__('For internal meetings, at least two company representatives are required.'));
												this.enable_primary_action();
												this.set_title('Submit');
												return;
											}
										}
								
										frappe.call({
											method: "productivity_next.api.add_meeting",
											args: {
												meeting_from: values.meeting_from,
												meeting_to: values.meeting_to,
												meeting_arranged_by: values.meeting_arranged_by,
												internal_meeting: values.internal_meeting,
												purpose: values.purpose,
												party_type: values.party_type || null,
												party: values.party || null,
												discussion: values.discussion,
												meeting_company_representative: values.meeting_company_representative || null,
												meeting_party_representative: values.meeting_party_representative || null,
												project: values.project || null  // Add project to the args
											},
											callback: (r) => {
												if (r.message) {
													frappe.msgprint({
														title: __('Success'),
														indicator: 'green',
														message: __('Meeting added successfully')
													});
													this.hide();
												} else {
													frappe.msgprint({
														title: __('Error'),
														indicator: 'red',
														message: __('Failed to add meeting. Please try again.')
													});
													this.enable_primary_action();
													this.set_title('Submit');
												}
											},
											error: (r) => {
												frappe.msgprint({
													title: __('Error'),
													indicator: 'red',
													message: __('An error occurred while adding the meeting. Please try again.')
												});
												this.enable_primary_action();
												this.set_title('Submit');
											}
										});
									}
								});
								
								// Set up the purpose field filter
								d.fields_dict.purpose.get_query = function () {
									return {
										filters: {
											internal_meeting: d.get_value('internal_meeting')
										}
									};
								};
					
								if (currentUserEmployee) {
									let company_representative = d.fields_dict.meeting_company_representative;
									
									// Force add a new row
									company_representative.grid.add_new_row(null, null, true);
									
									// Set the value directly on the grid rows
									company_representative.grid.grid_rows[0].doc.employee = currentUserEmployee.name;
									
									// Refresh the grid
									company_representative.grid.refresh();
									
									// Log for debugging
									console.log("Added row:", company_representative.grid.grid_rows[0].doc);
								}
					
								// Show the dialog
								d.show();
							})
							.catch(err => {
								console.error("Error:", err);
								frappe.msgprint("An error occurred while fetching data. Please try again.");
							});
						}
					});
					function updateChart() {
						let legends = overallPerformance.getOption().legend[0].selected
						legends = Object.keys(legends).filter(legend => legends[legend]);
						var filteredData = _rawData.flight.data.filter(item => {
							var activityType = item[0];
							return legends.includes(activityType);
						});

						overallPerformance.setOption({
							series: [{
								id: 'flightData',
								data: filteredData
							}]
						});
					}
					$('#overallChartLegends li').each(function() {
						let li = $(this);
						$(li).attr('selected', 'true');
					});
					function updateLegend() {
						let overallChartLegends = $('#overallChartLegends li');
						let legends = {};

						overallChartLegends.each(function() {
							let li = $(this);
							legends[li.attr('data-value')] = li.attr('selected') ? true : false;
							// console.log(li.attr('data-value'));
						});

						overallPerformance.setOption({
							legend: {
								selected: legends
							}
						});

						// console.log(legends);

					}
					let overallChartLegends = document.querySelectorAll('#overallChartLegends li');
					$.each(overallChartLegends, function(index, li) {
						$(li).on('click', function() {
							if ($(li).attr('selected')) {
								$(li).removeAttr('selected');
							} else {
								$(li).attr('selected', 'true');
							}
							updateLegend();
							updateChart();
						});
					});
				}
			});
			document.getElementById('activity-summary-report-link').addEventListener('click', function(event) {
				// console.log("Activity Summary Report Link Clicked");
				event.preventDefault();
				goToActivitySummaryReport(this.selected_employee,this.selected_start_date, this.selected_end_date);
			}.bind(this));
			function goToActivitySummaryReport(employee,start_date, end_date) {
				// console.log("Employee:", employee);
				var baseUrl = window.location.origin;
				var activityAnalysisUrl = baseUrl + "/app/query-report/Productify Activity Summary?from_date=" + start_date + "&to_date=" + end_date;
				window.open(activityAnalysisUrl, '_blank');
			}
	}
	// Overall Performance (All Employees) Code Ends
	
		
	// User Analysis (User Productivity Stats) Code Starts
	user_analysis() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe.call({
			method: "productivity_next.productivity_next.page.productify_consolidated_analysis.productify_consolidated_analysis.user_analysis_data",
			args: {
				user: "Administrator",
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			},
			callback: (r) => {
				if (r.message) {
					this.user_analysis_data(r.message);
					// console.log(r.message);
				}
			}
		});
		document.getElementById('user-analysis-report-link').addEventListener('click', function(event) {
			// console.log("Activity Summary Report Link Clicked");
			event.preventDefault();
			goToActivitySummaryReport(this.selected_employee,this.selected_start_date, this.selected_end_date);
		}.bind(this));
		function goToActivitySummaryReport(employee,start_date, end_date) {
			// console.log("Employee:", employee);
			var baseUrl = window.location.origin;
			var activityAnalysisUrl = baseUrl + "/app/query-report/Productify Weekly Summary?timespan=Yesterday";
			window.open(activityAnalysisUrl, '_blank');
		}
	};
	async user_analysis_data(data) {
		// console.log("Overall Performance Data", data);
		function calculateActiveTime(totalHours, totalIdleTime) {
			return totalHours - totalIdleTime;
		}
		function getBaseURL() {
			return window.location.origin + '/app/';
		}
		
		let employee_data;
		if (this.selected_employee != null) {
			employee_data = this.selected_employee;
		} else {
			employee_data = this.user_id;
		}
	
		const container = this.main_section.find("#user-analysis");
		container.empty();
		let wholedata = ``;
		const baseUrl = getBaseURL();
		const fetchPromises = Object.keys(data.total_hours_per_employee).map(async employee => {
			const response = await frappe.db.get_value("Employee", employee, "employee_name");
			const employee_name = response.message.employee_name;
			if (!employee_name) {
				return;
			}
			const meetingEmployeeData = data.meeting_employee_data?.[employee] || {};
			return {
				employee,
				employeeName: employee_name,
				totalHours: data.total_hours_per_employee[employee] || 0,
				totalIdleTime: data.total_idle_time[employee] || 0,
				incomingFincallCount: data.employee_fincall_data[employee]?.incoming_fincall_count || 0,
				outgoingFincallCount: data.employee_fincall_data[employee]?.outgoing_fincall_count || 0,
				missedFincallCount: data.employee_fincall_data[employee]?.missed_fincall_count || 0,
				rejectedFincallCount: data.employee_fincall_data[employee]?.rejected_fincall_count || 0,
				totalIncomingDuration: data.employee_fincall_data[employee]?.total_incoming_duration || 0,
				totalOutgoingDuration: data.employee_fincall_data[employee]?.total_outgoing_duration || 0,
				totalDays: data.total_days[employee] || 1,
				meetingCount: meetingEmployeeData.count || 0,
				meetingDuration: meetingEmployeeData.duration || 0,
				keystroke: data.work_intensity_data[employee]?.total_keystrokes || 0,
				clicks: data.work_intensity_data[employee]?.total_mouse_clicks || 0,
				scrolls: data.work_intensity_data[employee]?.total_scroll || 0,
				score: data.productivity_score[employee] || 0
			};
		});
	
		const employeeDataArray = await Promise.all(fetchPromises);
		employeeDataArray.sort((a, b) => {
			const scoreA = ((((a.totalHours/3600) - (a.totalIdleTime/3600))/a.score)*100);
			const scoreB = ((((b.totalHours/3600) - (b.totalIdleTime/3600))/b.score)*100);
			return scoreB - scoreA; // For descending order
		});
		// console.log("employeeDataArray", employeeDataArray);
		this.sorting_data = employeeDataArray;
		this.overall_performance_chart(); 
		let count = 1;
		let totalHours = 0;
		let totalIdleTime = 0;
		let totalIncomingFincallCount = 0;
		let totalOutgoingFincallCount = 0;
		let totalMissedFincallCount = 0;
		let totalRejectedFincallCount = 0;
		let totalIncomingDuration = 0;
		let totalOutgoingDuration = 0;
		let totalMeetingCount = 0;
		let totalMeetingDuration = 0;
		let totalKeystrokes = 0;
		let totalMouseClicks = 0;
		let totalScrolls = 0;
		this.start_date_ = this.selected_start_date;
		this.end_date_ = this.selected_end_date;
		employeeDataArray.forEach(app => {
			const employeeUrl = `${baseUrl}Productify Activity Analysis?start_date=${encodeURIComponent(this.selected_start_date)}&end_date=${encodeURIComponent(this.selected_end_date)}&employee=${encodeURIComponent(app.employee)}`;
			const employeeMeetingUrl = `${baseUrl}meeting?employee=${encodeURIComponent(app.employee)}&meeting_from=${encodeURIComponent(`["Between",["${this.start_date_}","${this.end_date_}"]]`)}&docstatus=1`;
			const employeeFincallUrl = `${baseUrl}employee-fincall?employee=${encodeURIComponent(app.employee)}&date=${encodeURIComponent(`["Between",["${this.start_date_}","${this.end_date_}"]]`)}`;	
			const score_ = 0;
			if (app.score == 0) {
				this.score_ = 100;
			}
			else {
				this.score_ = parseFloat((((app.totalHours/3600) - (app.totalIdleTime/3600))/app.score)*100).toFixed(0);
			}
			wholedata += `
				<tr>
					<td align="left">
						<a href="${employeeUrl}" target="_blank">${count}. ${app.employeeName}</a>
					</td>
					<td align="center" style="color:#6420AA;"><b>${this.score_}</b></td>
					<td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(app.totalHours)}</td>
					<td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_((app.totalHours) - (app.totalIdleTime))}</td>
					<td align="center" style="color:#00A6E0;">${this.convertSecondsToTime_(app.totalIdleTime)}</td>
					<td align="center" ><a href="${employeeFincallUrl}&calltype=Incoming" style="color:#62BA46;" target="_blank">${app.incomingFincallCount} (${this.convertSecondsToTime_(app.totalIncomingDuration)} H)</a></td>
					<td align="center" ><a href="${employeeFincallUrl}&calltype=Outgoing" style="color:#62BA46;" target="_blank">${app.outgoingFincallCount} (${this.convertSecondsToTime_(app.totalOutgoingDuration)} H)</a></td>
					<td align="center" ><a href="${employeeFincallUrl}&calltype=Missed" style="color:#62BA46;" target="_blank">${app.missedFincallCount}</a></td>
					<td align="center" ><a href="${employeeFincallUrl}&calltype=Rejected" style="color:#62BA46;" target="_blank">${app.rejectedFincallCount}</a></td>
					<td align="center" style="color:#FF4001;">${app.keystroke}</td>
					<td align="center" style="color:#FF4001;">${app.clicks}</td>
					<td align="center" style="color:#FF4001;">${app.scrolls}</td>
					<td align="center"><a href="${employeeMeetingUrl}" style="color:#6420AA;" target="_blank">${app.meetingCount}</a></td>
					<td align="center"><a href="${employeeMeetingUrl}" style="color:#6420AA;" target="_blank">${this.convertSecondsToTime_(app.meetingDuration)}</a></td>
				</tr>`;
			count++;
			totalHours += app.totalHours;
			totalIdleTime += app.totalIdleTime;
			totalIncomingFincallCount += app.incomingFincallCount;
			totalOutgoingFincallCount += app.outgoingFincallCount;
			totalMissedFincallCount += app.missedFincallCount;
			totalRejectedFincallCount += app.rejectedFincallCount;
			totalIncomingDuration += app.totalIncomingDuration;
			totalOutgoingDuration += app.totalOutgoingDuration;
			totalMeetingCount += app.meetingCount;
			totalMeetingDuration += app.meetingDuration;
			totalKeystrokes += app.keystroke;
			totalMouseClicks += app.clicks;
			totalScrolls += app.scrolls;
		});
		wholedata += `
			<tr>
				<td align="left"><strong>Total</strong></td>
				<td align="center" style="color:#00A6E0;"><strong></strong></td>
				<td align="center" style="color:#00A6E0;"><strong>${this.convertSecondsToTime_(totalHours)}</strong></td>
				<td align="center" style="color:#00A6E0;"><strong>${this.convertSecondsToTime_(totalHours - totalIdleTime)}</strong></td>
				<td align="center" style="color:#00A6E0;"><strong>${this.convertSecondsToTime_(totalIdleTime)}</strong></td>
				<td align="center" style="color:#62BA46;"><strong>${totalIncomingFincallCount} (${this.convertSecondsToTime_(totalIncomingDuration)} H)</strong></td>
				<td align="center" style="color:#62BA46;"><strong>${totalOutgoingFincallCount} (${this.convertSecondsToTime_(totalOutgoingDuration)} H)</strong></td>
				<td align="center" style="color:#62BA46;"><strong>${totalMissedFincallCount}</strong></td>
				<td align="center" style="color:#62BA46;"><strong>${totalRejectedFincallCount}</strong></td>
				<td align="center" style="color:#FF4001;"><strong>${totalKeystrokes}</strong></td>
				<td align="center" style="color:#FF4001;"><strong>${totalMouseClicks}</strong></td>
				<td align="center" style="color:#FF4001;"><strong>${totalScrolls}</strong></td>
				<td align="center" style="color:#6420AA;"><strong>${totalMeetingCount}</strong></td>
				<td align="center" style="color:#6420AA;"><strong>${this.convertSecondsToTime_(totalMeetingDuration)}</strong></td>
			</tr>`;
	
		container.append(wholedata);

	};
	// User Analysis (User Productivity Stats) Code Ends
		
}
frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;