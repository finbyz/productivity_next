frappe.pages['Productify Activity Analysis'].on_page_load = function (wrapper) {
	new UserProfile(wrapper);
}


UserProfile = class UserProfile {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
		});

		const urlParams = new URLSearchParams(window.location.search);
		const currentEmployee = urlParams.get('employee');
		// console.log("URL employee parameter:", currentEmployee);
		if (currentEmployee && currentEmployee !== 'undefined') {
			this.selected_employee = currentEmployee;
			// console.log("Employee set from URL:", this.selected_employee);
		} else {
			const employeePromise = frappe.db.get_value("Employee", {
				"user_id": frappe.session.user
			}, "name");
			Promise.resolve(employeePromise).then(result => {
				if (result && result.message && result.message.name) {
					this.selected_employee = result.message.name;
					const newUrl = new URL(window.location.href);
					newUrl.searchParams.set('employee', result.message.name);
					window.history.pushState({
						path: newUrl.toString()
					}, '', newUrl.toString());
					// console.log("Employee set from session and URL updated:", this.selected_employee);
				}
			}).catch(error => {
				console.error("Error retrieving employee:", error);
			});
		}

		this.sidebar = this.wrapper.find(".layout-side-section");
		this.toggle_button = this.wrapper.find(".sidebar-toggle-placeholder");
		this.main_section = this.wrapper.find(".layout-main-section");
		this.buttonsInitialized = false;

		if (urlParams.get('start_date') == null && urlParams.get('end_date') == null) {
			var endDate = new Date();
			var startDate = new Date();
			startDate.setDate(startDate.getDate() - 7); // Set the start date to one week back

			var endDay = endDate.getDate().toString().padStart(2, '0');
			var endMonth = (endDate.getMonth() + 1).toString().padStart(2, '0');
			var endYear = endDate.getFullYear();
			this.selected_end_date = endYear + '-' + endMonth + '-' + endDay;

			var startDay = startDate.getDate().toString().padStart(2, '0');
			var startMonth = (startDate.getMonth() + 1).toString().padStart(2, '0');
			var startYear = startDate.getFullYear();
			this.selected_start_date = startYear + '-' + startMonth + '-' + startDay;
		} else {
			this.selected_start_date = urlParams.get('start_date');
			this.selected_end_date = urlParams.get('end_date');
		}

		this.wrapper.bind("show", () => {
			this.show();
		});
	}


	// hide_sidebar_and_toggle() {
	//     this.sidebar.hide();
	//     // this.toggle_button.hide();
	//     this.main_section.css('width', '100%');
	// }

	show() {
		this.user_id = frappe.session.user;
		frappe.dom.freeze(__("Loading user profile") + "...");

		frappe.db.exists("User", this.user_id)
			.then((exists) => {
				if (exists) {
					this.make_user_profile();
				} else {
					frappe.dom.unfreeze();
					frappe.msgprint(__("User does not exist"));
				}
			})
			.then(() => {
				frappe.dom.unfreeze();
			})
			.catch((error) => {
				frappe.dom.unfreeze();
				console.error("Error loading user data:", error);
			});
	}


	finish_user_profile_setup() {
		this.setup_timespan();
		this.setup_user_search();
		this.main_section.empty().append(frappe.render_template("productify_activity_analysis"));
		this.overall_performance();
		this.application_usage_time();
		this.fetch_url_data();
		this.type_of_calls();
	
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
					this.work_intensity();
					this.application_usage_time();
					this.web_browsing_time();
					this.top_document_analysis();
					this.render_images();
				}
				if (target.getAttribute('aria-labelledby') === 'phone-calls-tab') {
					this.top_phone_calls();
					this.type_of_calls();
					this.hourly_calls_analysis();
				}
				
				contents.forEach(content => content.classList.remove('show', 'active'));
				target.classList.add('show', 'active');
			});
		});
	}
	

	// Timespan Select Code Starts
	setup_timespan() {
		this.$user_search_button = this.page.set_primary_action(
			__("Select Timespan"),
			() => this.setup_timespan_dialog(),
		);
	}
	setup_timespan_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: __("Select Timespan"),
			fields: [{
				fieldtype: "DateRange",
				fieldname: "timespan_range",
				label: __("Timespan Range"),
				description: __("Select a start and end date"),
			},],
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
				window.history.pushState({
					path: newUrl.toString()
				}, '', newUrl.toString());
				const urlParams = new URLSearchParams(window.location.search);
				this.selected_start_date = urlParams.get('start_date');
				this.selected_end_date = urlParams.get('end_date');
				if (urlParams.get('employee')) {
					this.selected_employee = urlParams.get('employee');
				}
				this.make_user_profile();
			},
		});
		dialog.show();
	}
	// Timespan Select Code Ends

	setup_user_profile_links() {
		if (this.user_id !== frappe.session.user) {
			this.wrapper.find(".profile-links").hide();
		} else {
			this.wrapper.find(".edit-profile-link").on("click", () => {
				this.edit_profile();
			});

			this.wrapper.find(".user-settings-link").on("click", () => {
				this.go_to_user_settings();
			});
		}
	}

	// Employee Name And Date Title Code Starts
	make_user_profile() {
		this.user = frappe.user_info(this.user_id);
		if (!this.selected_employee) {
			frappe.msgprint(__("Select Employee to view the data"));
		}
		if (!this.selected_employee) {
			this.page.set_title(this.user.fullname + " ( FROM " + this.selected_start_date + " TO " + this.selected_end_date + " )");
		} else {
			frappe.db.get_doc("Employee", this.selected_employee)
				.then(employee => {
					this.page.set_title(employee.employee_name + " ( FROM " + this.selected_start_date + " TO " + this.selected_end_date + " )");
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
	// Employee Name And Date Title Code End

	// Change Employee Button Code Starts
	setup_user_search() {
		if (!this.buttonsInitialized) { // Check if buttons have already been initialized
			// Add a refresh button with an icon
			this.page.add_action_icon("refresh", () => {
				window.location.reload();
			});

			// Set up the 'Change Employee' button
			this.$user_search_button = this.page.set_secondary_action(
				__("Change Employee"),
				() => this.show_user_search_dialog(), {
				icon: "change",
				size: "sm"
			}
			);

			this.buttonsInitialized = true; // Set the flag to true after adding buttons
		}
	}
	show_user_search_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: __("Change Employee"),
			fields: [{
				fieldtype: "Link",
				fieldname: "employee",
				options: "Employee",
				label: __("Employee"),
			},],
			primary_action_label: __("Go"),
			primary_action: ({
				employee
			}) => {
				dialog.hide();
				this.selected_employee = employee;
				this.make_user_profile()
				const newUrl = new URL(window.location.href);
				newUrl.searchParams.set('employee', employee);
				window.history.pushState({
					path: newUrl.toString()
				}, '', newUrl.toString());
			},
		});
		dialog.show();
	}
	// Change Employee Button Code Ends

	// Work Intensity Code Starts
	work_intensity() {
		let user;
		if (this.selected_employee !== null) {
			user = this.selected_employee;
		} else {
			user = this.user_id;
		}
	
		frappe.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.work_intensity", {
			user: user,
			start_date: this.selected_start_date,
			end_date: this.selected_end_date,
		}).then((response) => {
			if (response.length === 0) {
				return;
			}
	
			const hours = Array.from({ length: 17 }, (_, index) => `${index + 7}:00`);
			const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
			const data = [];
	
			response.forEach(entry => {
				const hour = entry[0];
				const value = entry[1];
				const dayOfWeek = entry[2];
				const xIndex = hour - 7;
				const yIndex = days.indexOf(dayOfWeek);
	
				if (yIndex !== -1) {
					data.push([xIndex, yIndex, value || 0]);
				}
			});
	
			const values = data.map(item => item[2]);
			const minValue = Math.min(...values);
			const maxValue = Math.max(...values);
	
			const heatMapDom = document.querySelector('.work-intensity');
			const heatMapChart = echarts.init(heatMapDom, null, { renderer: 'svg' });
	
			const option = {
				tooltip: {
					position: 'top',
					formatter: function (params) {
						const day = days[params.value[1]];
						const hour = hours[params.value[0]];
						return `${day} ${hour}: ${params.value[2]}`;
					}
				},
				grid: {
					height: '50%',
					top: '10%'
				},
				xAxis: {
					type: 'category',
					data: hours,
					splitArea: {
						show: true
					}
				},
				yAxis: {
					type: 'category',
					data: days,
					splitArea: {
						show: true
					}
				},
				visualMap: {
					min: minValue,
					max: maxValue,
					orient: 'horizontal',
					left: 'center',
					bottom: '15%',
					color: ['rgb(0,100,200)', 'rgb(230,250,255)']
				},
				series: [{
					name: 'Intensity Count',
					type: 'heatmap',
					data: data,
					label: {
						show: false
					},
					emphasis: {
						itemStyle: {
							shadowBlur: 10,
							shadowColor: 'rgba(0, 0, 0, 0.5)'
						}
					},
					itemStyle: {
						borderWidth: 2,
						borderColor: '#ffffff'
					}
				}]
			};
	
			heatMapChart.setOption(option);
	
			// Store the chart instance globally
			window.myChart = heatMapChart;
	
			// Add resize listener
			window.addEventListener('resize', function () {
				if (window.myChart) {
					window.myChart.resize();
				}
			});
		}).catch((error) => {
			console.error("Error fetching data:", error);
		});
	}
	// Work Intensity Code Ends

	// Overall Performance Chart Code Starts
	overall_performance() {
		// console.log("Overall Performance Chart", this.activeTimeData);
		let overallPerformanceDom = document.querySelector('.overall-performance');
		let overallPerformance = echarts.init(overallPerformanceDom, null, { renderer: 'svg' });
		window.addEventListener('resize', overallPerformance.resize);
		frappe
			.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.overall_performance", {
				employee: this.selected_employee,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date    
			})
			.then((r) => {
				const callsTab = document.querySelector('#summary-tab');
				const callsContent = document.querySelector('#summary');
				if (r.base_data.length === 0) {
				// console.log("No data available to plot the chart........................................");
				if (callsTab) callsTab.style.display = 'none';
				if (callsContent) callsContent.style.display = 'none';
				
				// Make system-activity tab active
				const systemActivityTab = document.querySelector('#system-activity-tab');
				const systemActivityContent = document.querySelector('#system-activity');
				
				if (systemActivityTab && systemActivityContent) {
					// Remove active class from all tabs and content
					document.querySelectorAll('.nav-link').forEach(tab => tab.classList.remove('active'));
					document.querySelectorAll('.tab-pane').forEach(content => content.classList.remove('active', 'show'));
					
					// Add active class to system-activity tab and content
					systemActivityTab.classList.add('active');
					systemActivityContent.classList.add('active', 'show');
					
					// Call functions related to system-activity tab
					this.work_intensity();
					this.application_usage_time();
					this.web_browsing_time();
					this.top_document_analysis();
					this.render_images();
				}
				return
				}
				if (r.base_data.length === 0) {
					// Handle no data scenario if needed
				} else {
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
	
					function makeOption() {
						var activityLegends = [
							{ name: 'Application', color: '#00A6E0' },
							{ name: 'Idle', color: '#FF4001' },
							{ name: 'Call', color: '#62BA46' },
							{ name: 'Internal Meeting', color: '#6420AA' },
							{ name: 'External Meeting', color: '#6699FF' },
							{ name: 'Inactive', color: '#C1C1C1' }
						];
						function convertDateTime(dateTimeString) {
							const date = new Date(dateTimeString);
							return `${date.getFullYear()}-${padZero(date.getMonth() + 1)}-${padZero(date.getDate())} ${padZero(date.getHours())}:${padZero(date.getMinutes())}:${padZero(date.getSeconds())}`;
						}
						
						function padZero(num) {
							return num < 10 ? `0${num}` : num;
						}
	
						// Add inactive periods
						var inactivePeriods = [];
						var employeeFirstEntry = {};
						_rawData.flight.data.sort((a, b) => new Date(a[2]).getTime() - new Date(b[2]).getTime());
						_rawData.flight.data.sort((a, b) => priorityOrder[a[0]] - priorityOrder[b[0]]);
						for (var i = 0; i < _rawData.parkingApron.data.length; i++) {
							var employeeName = _rawData.parkingApron.data[i];
							var employeeActivities = _rawData.flight.data.filter(item => item[1] === employeeName);
							employeeActivities.sort((a, b) => new Date(a[2]) - new Date(b[2]));

							if (employeeActivities.length > 0) {
								employeeFirstEntry[employeeName] = new Date(employeeActivities[0][2]).getTime();
								var lastEndTime = new Date(employeeActivities[0][3]).getTime();
						
								for (var j = 1; j < employeeActivities.length; j++) {
									var startTime = new Date(employeeActivities[j][2]).getTime();
									if (startTime > lastEndTime) {
										var startTimeString = convertDateTime(new Date(lastEndTime).toISOString());
										var endTimeString = convertDateTime(new Date(startTime).toISOString());
										
										inactivePeriods.push(['Inactive', employeeName, startTimeString, endTimeString]);
									}
									lastEndTime = new Date(employeeActivities[j][3]).getTime();
								}
							}
						}

						_rawData.flight.data = _rawData.flight.data.concat(inactivePeriods);
						_rawData.flight.data.sort((a, b) => new Date(a[2]).getTime() - new Date(b[2]).getTime());
						_rawData.flight.data.sort((a, b) => priorityOrder[a[0]] - priorityOrder[b[0]]);	
						_rawData.flight.data = _rawData.flight.data.map(item => {
							let date = new Date(item[1]);
							let formattedDate = `${padZero(date.getDate())}-${padZero(date.getMonth() + 1)}-${date.getFullYear()}`;
							return [item[0], formattedDate, ...item.slice(2)];
						});						
						var uniqueDates = [...new Set(_rawData.flight.data.map(item => item[1]))];
						function setFixedDate(timestamp) {
							var date = new Date(timestamp);
							date.setFullYear(2000, 0, 1);
							return date.getTime();
						}
						var startTimeList = _rawData.flight.data.map(item => setFixedDate(new Date(item[2]).getTime()));
						var endTimeList = _rawData.flight.data.map(item => setFixedDate(new Date(item[3]).getTime()));
						var minStartTime = Math.min(...startTimeList);
						var maxEndTime = Math.max(...endTimeList);
						minStartTime = minStartTime - 30 * 60 * 1000;
						maxEndTime = maxEndTime + 30 * 60 * 1000;
						var fixedStartTime = new Date(minStartTime);
						var fixedEndTime = new Date(maxEndTime);
	
						// console.log("Min Start Time:", fixedStartTime);
						// console.log("Max End Time:", fixedEndTime);
	
						return {
							backgroundColor: 'transparent',
							legend: {
								selected: {
									'Application': true,
									'Idle': true,
									'Call': true,
									'Internal Meeting': true,
									'External Meeting': true,
									'Inactive': true
								},
							},
							tooltip: {
								formatter: function(params) {
									var activityType = params.data[0];
									var date = params.data[1];
									var startTime_ = new Date(params.data[2]);
									var endTime_ = new Date(params.data[3]);
									var startTimeString = startTime_.toLocaleTimeString();
									var endTimeString = endTime_.toLocaleTimeString();
	
									var durationMs = endTime_ - startTime_;
									var durationSeconds = Math.floor(durationMs / 1000);
									var hours = Math.floor(durationSeconds / 3600);
									var minutes = Math.floor((durationSeconds % 3600) / 60);
									var seconds = durationSeconds % 60;
	
									var durationString = "";
									if (hours > 0) durationString += hours + "h ";
									if (minutes > 0) durationString += minutes + "m ";
									if (seconds > 0 || durationString === "") durationString += seconds + "s";

									var tooltipContent = `<div style="line-height: 1.5;">`;
									if (activityType === 'Call' && params.data[4]) {
										tooltipContent += `<span style="font-weight: bold;font-size:15px;"> ${params.data[4]}</span> <br>`;
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
										<span style="font-weight: bold;">Date:</span> ${date}<br>
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
							dataZoom: [
								{
									type: 'slider',
									yAxisIndex: 0,
									zoomLock: true,
									width: 10,
									right: 10,
									top: 70,
									startValue: _rawData.flight.data.length,
									endValue: _rawData.flight.data.length - 10,
									bottom: 20,
									handleSize: 0,
									showDetail: false
								},
								{
									type: 'inside',
									id: 'insideY',
									yAxisIndex: 0,
									startValue: _rawData.flight.data.length,
									endValue: _rawData.flight.data.length - 10,
									zoomOnMouseWheel: false,
									moveOnMouseMove: true,
									moveOnMouseWheel: true
								}
							],                    
							grid: {
								show: false,
								top: 20,
								bottom: 5,
								left: 120,
								right: 20,
								backgroundColor: 'transparent',
								borderWidth: 0
							},                            
							xAxis: {
								type: 'time',
								position: 'top',
								min: fixedStartTime,
								max: fixedEndTime,
								splitLine: {
									lineStyle: {
										color: ['#E9EDFF']
									}
								},
								axisLine: { show: false },
								axisTick: {
									lineStyle: {
										color: '#929ABA'
									}
								},
								axisLabel: {
									color: '#929ABA',
									inside: false,
									align: 'center',
									formatter: function (value, index) {
										var date = new Date(value);
										var hours = date.getHours();
										var minutes = date.getMinutes();
										var ampm = hours >= 12 ? 'PM' : 'AM';
										hours = hours % 12;
										hours = hours ? hours : 12;
										var minutesStr = minutes < 10 ? '0' + minutes : minutes;
										return hours + ':' + minutesStr + ' ' + ampm;
									}
								}
							},
							yAxis: {
								type: 'category',
								axisTick: { show: false },
								splitLine: { show: false },
								axisLine: { show: false },
								axisLabel: { 
									show: true,
									align: 'right',
									margin: 10,
									formatter: function(value) {
										return '{a|' + value + '}';
									},
									rich: {
										a: {
											align: 'right',
											width: 100, // Increased width to accommodate the new date format
										}
									}
								},
								data: uniqueDates,
							},							
							series: [
								{
									id: 'flightData',
									type: 'custom',
									renderItem: function (params, api) {
										var dateIndex = api.value(1);
										var xValue = new Date(api.value(2));
										var xEndValue = new Date(api.value(3));
										xValue.setFullYear(2000, 0, 1);
										xEndValue.setFullYear(2000, 0, 1);
										
										var yValue = api.coord([0, dateIndex])[1];
										var activityType = api.value(0);
									
										var color;
									
										switch (activityType) 
										{
											case 'Application': color = '#4BC0C0'; break;
											case 'Idle': color = '#FF6666'; break;
											case 'Call': color = '#FFCC66'; break;
											case 'Internal Meeting': color = '#9966FF'; break;
											case 'External Meeting': color = '#6699FF'; break;
											case 'Inactive': color = '#E9EAEC'; break;
											default: color = '#000000';
										}
									
										var barHeight = Math.min(20, api.size([0, 1])[1] * 0.8);  // Adjust bar height
	
										var item = {
											type: 'rect',
											shape: {
												x: api.coord([xValue, yValue])[0],
												y: yValue - barHeight / 2,
												width: api.size([xEndValue - xValue, 0])[0],
												height: barHeight,
											},
											style: api.style({
												fill: color,  // Add 50% opacity
												stroke: 'rgba(0,0,0,0.2)'
											})
										};
	
										return item;
									},
									dimensions: _rawData.flight.dimensions,
									encode: {
										x: [2, 3],
										y: 1,
									},
									data: _rawData.flight.data
								}
							]
						};
					}
					overallPerformance.setOption(makeOption());
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
								// console.log("Project Enabled:", subscription_response.message);
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
									// console.log("Added row:", company_representative.grid.grid_rows[0].doc);
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
				var activityAnalysisUrl = baseUrl + "/app/query-report/Productify Activity Summary?employee="+ employee +"&from_date=" + start_date + "&to_date=" + end_date;
				window.open(activityAnalysisUrl, '_blank');
			}
	}
	// Overall Performance Chart Code Ends

	// Overall Performance Timely Chart Code Starts
	overall_performance_timely(date, hour) {
		// console.log("Overall Performance Chart", date, hour);
	
		let overallPerformanceDom = document.querySelector(`#performance-chart-${date}-${hour}`);
		if (!overallPerformanceDom) {
			console.error('Chart container not found:', `#performance-chart-${date}-${hour}`);
		}
		let overallPerformance = echarts.init(overallPerformanceDom, null, { renderer: 'svg' });
		window.addEventListener('resize', overallPerformance.resize);
	
		frappe.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.overall_performance_timely", {
			employee: this.selected_employee,
			date: date,
			hour: hour
		}).then((r) => {
			if (r.base_data.length === 0) {
				// Handle no data scenario if needed
			} else {
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
					'Browser': 2,
					'Idle': 3,
					'Internal Meeting': 4,
					'External Meeting': 5,
					'Call': 6
				};
	
				function makeOption() {
					function convertDateTime(dateTimeString) {
						const date = new Date(dateTimeString);
						return `${date.getFullYear()}-${padZero(date.getMonth() + 1)}-${padZero(date.getDate())} ${padZero(date.getHours())}:${padZero(date.getMinutes())}:${padZero(date.getSeconds())}`;
					}
	
					function padZero(num) {
						return num < 10 ? `0${num}` : num;
					}
// Function to get the start of the hour for a given date
function getStartOfHour(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate(), date.getHours(), 0, 0, 0);
}

// Function to get the end of the hour for a given date
function getEndOfHour(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate(), date.getHours(), 59, 59, 999);
}

// Define the inactive periods array
var inactivePeriods = [];

// Define a map to track the last end time of each employee
var employeeLastEndTime = {};

// Sort the flight data by date and then by priority
_rawData.flight.data.sort((a, b) => new Date(a[2]).getTime() - new Date(b[2]).getTime());
_rawData.flight.data.sort((a, b) => priorityOrder[a[0]] - priorityOrder[b[0]]);

// Iterate over each activity in the flight data
for (var i = 0; i < _rawData.flight.data.length; i++) {
    var activity = _rawData.flight.data[i];
    var employeeName = activity[1];
    var startTime = new Date(activity[2]);
    var endTime = new Date(activity[3]); // Assuming end time is at index 3

    // Initialize employee's last end time if not already set
    if (!employeeLastEndTime[employeeName]) {
        employeeLastEndTime[employeeName] = getStartOfHour(startTime);
    }

    // Calculate inactive period if there is a gap between the last activity and the current start time
    if (startTime > employeeLastEndTime[employeeName]) {
        var inactiveStart = employeeLastEndTime[employeeName];
        var inactiveEnd = startTime;
        
        // If the inactive period crosses an hour boundary, split it
        while (getEndOfHour(inactiveStart) < inactiveEnd && getEndOfHour(inactiveStart) < startTime) {
            var hourEnd = getEndOfHour(inactiveStart);
            inactivePeriods.push([
                'Inactive',
                employeeName,
                convertDateTime(inactiveStart.toISOString()),
                convertDateTime(hourEnd.toISOString())
            ]);
            inactiveStart = new Date(hourEnd.getTime() + 1); // Start of next hour
        }
        
        // Add the remaining inactive period if it exists and is within the same hour
        if (inactiveStart < inactiveEnd && inactiveStart.getHours() === inactiveEnd.getHours()) {
            inactivePeriods.push([
                'Inactive',
                employeeName,
                convertDateTime(inactiveStart.toISOString()),
                convertDateTime(inactiveEnd.toISOString())
            ]);
        }
    }

    // Update the last end time to the end of the current activity
    employeeLastEndTime[employeeName] = endTime;
}

// Handle inactive periods at the end of the day for each employee
for (const employee in employeeLastEndTime) {
    var lastEnd = employeeLastEndTime[employee];
    var endOfHour = getEndOfHour(lastEnd);

    // Only add an inactive period if it's within the same hour and there's actually a gap
    if (lastEnd < endOfHour && 
        lastEnd.getHours() === endOfHour.getHours() && 
        lastEnd.getTime() !== endOfHour.getTime()) {
        
        // Ensure we're not creating a full 59-minute inactive period
        if (endOfHour.getTime() - lastEnd.getTime() < 3540000) { // 59 minutes in milliseconds
            inactivePeriods.push([
                'Inactive',
                employee,
                convertDateTime(lastEnd.toISOString()),
                convertDateTime(endOfHour.toISOString())
            ]);
        }
    }
}

// Combine flight data with inactive periods
_rawData.flight.data = _rawData.flight.data.concat(inactivePeriods);

// Sort combined data by date and priority
_rawData.flight.data.sort((a, b) => new Date(a[2]).getTime() - new Date(b[2]).getTime());
_rawData.flight.data.sort((a, b) => priorityOrder[a[0]] - priorityOrder[b[0]]);

// Format the date for each entry
_rawData.flight.data = _rawData.flight.data.map(item => {
    let date = new Date(item[2]);
    let formattedDate = `${padZero(date.getDate())}-${padZero(date.getMonth() + 1)}-${date.getFullYear()}`;
    return [item[0], formattedDate, ...item.slice(2)];
});
					var uniqueDates = [...new Set(_rawData.flight.data.map(item => item[1]))];
	
					function setFixedDate(timestamp) {
						var date = new Date(timestamp);
						date.setFullYear(2000, 0, 1);
						return date.getTime();
					}
					var startTimeList = _rawData.flight.data.map(item => setFixedDate(new Date(item[2]).getTime()));
					var endTimeList = _rawData.flight.data.map(item => setFixedDate(new Date(item[3]).getTime()));
					var minStartTime = Math.min(...startTimeList);
					var maxEndTime = Math.max(...endTimeList);
	
					var fixedStartTime = new Date(minStartTime);
					var fixedEndTime = new Date(maxEndTime);
	
					let startHour = new Date(fixedStartTime);
					startHour.setMinutes(0);
					startHour.setSeconds(0);
					let endHour = new Date(fixedStartTime);
					endHour.setHours(endHour.getHours() + 1);
					endHour.setMinutes(0);
					endHour.setSeconds(0);
					function formatTimeToHHMM(date) {
						return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
					}
					
					return {
						backgroundColor: 'transparent',

						tooltip: {
							formatter: function(params) {
								var activityType = params.data[0];
								var date = params.data[1];
								var startTime_ = new Date(params.data[2]);
								var endTime_ = new Date(params.data[3]);
								// console.log(startTime_, endTime_);
								var startTimeString = formatTimeToHHMM(startTime_);
								var endTimeString = formatTimeToHHMM(endTime_);
	
								var durationMs = endTime_ - startTime_;
								var durationSeconds = Math.floor(durationMs / 1000);
								var hours = Math.floor(durationSeconds / 3600);
								var minutes = Math.floor((durationSeconds % 3600) / 60);
								var seconds = durationSeconds % 60;
	
								var durationString = "";
								if (hours > 0) durationString += hours + "h ";
								if (minutes > 0) durationString += minutes + "m ";
								if (seconds > 0 || durationString === "") durationString += seconds + "s";
	
								var tooltipContent = ``;

								if (activityType === "Application" || activityType === "Browser") {
									tooltipContent += `
										<div class="custom-tooltip">
											<table style="border-collapse: collapse; width: 100%; font-size: 14px;">
												<tr>
													<td style="padding: 0px 10px; text-align: left; font-weight: bold;">${startTimeString}</td>
													<td style="padding: 0px 10px; font-weight: bold;">${params.data[9]}</td>
													<td style="padding: 0px 10px; text-align: right; font-weight: bold;">${durationString}</td>
												</tr>
									`;
								}
								if (activityType === "Call") {
									tooltipContent += `
										<div class="custom-tooltip">
											<table style="border-collapse: collapse; width: 100%; font-size: 14px;">
												<tr>
													<td style="padding: 0px 10px; text-align: left; font-weight: bold;">${startTimeString}</td>
													<td style="padding: 0px 10px; font-weight: bold;">Call</td>
													<td style="padding: 0px 10px; text-align: right; font-weight: bold;">${durationString}</td>
												</tr>
									`;
								}
								if (activityType === "Idle"){
									tooltipContent += `
										<div class="custom-tooltip">
											<table style="border-collapse: collapse; width: 100%; font-size: 14px;">
												<tr>
													<td style="padding: 0px 10px; text-align: left; font-weight: bold;">${startTimeString}</td>
													<td style="padding: 0px 10px; font-weight: bold;">Idle</td>
													<td style="padding: 0px 10px; text-align: right; font-weight: bold;">${durationString}</td>
												</tr>
									`;
								}
								if (activityType === "Inactive"){
									tooltipContent += `
										<div class="custom-tooltip">
											<table style="border-collapse: collapse; width: 100%; font-size: 14px;">
												<tr>
													<td style="padding: 0px 10px; text-align: left; font-weight: bold;">${startTimeString}</td>
													<td style="padding: 0px 10px; font-weight: bold;">Inactive</td>
													<td style="padding: 0px 10px; text-align: right; font-weight: bold;">${durationString}</td>
												</tr>
									`;
								}
								if (activityType === "Internal Meeting" || activityType === "External Meeting") {
									tooltipContent += `
										<div class="custom-tooltip">
											<table style="border-collapse: collapse; width: 100%; font-size: 14px;">
												<tr>
													<td style="padding: 0px 10px; text-align: left; font-weight: bold;">${startTimeString}</td>
													<td style="padding: 0px 10px; font-weight: bold;">Meeting</td>
													<td style="padding: 0px 10px; text-align: right; font-weight: bold;">${durationString}</td>
												</tr>
									`;
								}
								if (activityType === "Application" || activityType === "Browser") {
									if (params.data[4]) {
										tooltipContent += `
											<tr>
												<td colspan="3" style="padding: 0px 10px; text-align: left;">${params.data[4]}</td>
											</tr>`;
									}
									if (params.data[5]) {
										tooltipContent += `
											<tr>
												<td colspan="3" style="padding: 0px 10px; text-align: left;">${params.data[5]}</td>
											</tr>`;
									}
									if (params.data[6]) {
										tooltipContent += `
											<tr>
												<td colspan="3" style="padding: 0px 10px; text-align: left;">${params.data[6]}</td>
											</tr>`;
									}
									if (params.data[7] && params.data[8]) {
										tooltipContent += `
											<tr>
												<td style="padding: 0px 10px; text-align: left;">${params.data[7]}</td>
												<td></td>
												<td style="padding: 0px 10px; text-align: left;">${params.data[8]}</td>
											</tr>`;
									}
								}
								if (activityType === "Call") {
									// console.log("params",params);
									if (params.data[4]) {
										tooltipContent += `
											<tr>
												<td colspan="3" style="padding: 0px 10px; text-align: left;">${params.data[4]}</td>
											</tr>`;
									}
									if (params.data[6] && params.data[7]) {
										tooltipContent += `
											<tr>
												<td colspan="3" style="padding: 0px 10px; text-align: left;">${params.data[6]} - ${params.data[7]}</td>
											</tr>`;
									}
								} 
								if (activityType === "Internal Meeting" || activityType === "External Meeting") {
									if (params.data[7] && params.data[8]) {
										tooltipContent += `
											<tr>
												<td colspan="3" style="padding: 0px 10px; text-align: left;">${params.data[8]} - ${params.data[7]}</td>
											</tr>`;
									}
									if (params.data[4]) {
										tooltipContent += `
											<tr>
												<td colspan="3" style="padding: 0px 10px; text-align: left;">${params.data[4]}</td>
											</tr>`;
									}
									if (params.data[5]) {
										tooltipContent += `
											<tr>
												<td colspan="3" style="padding: 0px 10px; text-align: left;">${params.data[5]}</td>
											</tr>`;
									}
								}
								else {
									
								}

								tooltipContent += `
										</table>
									</div>`;
								
								return tooltipContent;
							},
							confine: true,  // Ensures the tooltip stays within the chart container
							textStyle: {
								fontSize: 15,
							},
							padding: [10, 15],
						},
						animation: false,
						toolbox: {
							left: 20,
							top: 0,
							itemSize: 20 
						},
						grid: {
							show: false,
							top: 20,
							bottom: 5,
							left: 120,
							right: 20,
							backgroundColor: 'transparent',
							borderWidth: 0
						},
						xAxis: {
							type: 'time',
							position: 'top',
							min: startHour,
							max: endHour,
							splitLine: {
								lineStyle: {
									color: ['#E9EDFF']
								}
							},
							axisLine: { show: false },
							axisTick: {
								lineStyle: {
									color: '#929ABA'
								}
							},
							axisLabel: {
								show: true,
								formatter: function (value) {
									let date = new Date(value);
									return `${date.getHours()}:${padZero(date.getMinutes())}`;
								}
							}
						},
						yAxis: {
							type: 'category',
							axisTick: { show: false },
							splitLine: { show: false },
							axisLine: { show: false },
							axisLabel: { 
								show: false
							},
							data: uniqueDates,
						},
						series: [
							{
								id: 'flightData',
								type: 'custom',
								renderItem: function (params, api) {
									var dateIndex = api.value(1);
									var xValue = new Date(api.value(2));
									var xEndValue = new Date(api.value(3));
									xValue.setFullYear(2000, 0, 1);
									xEndValue.setFullYear(2000, 0, 1);
	
									var yValue = api.coord([0, dateIndex])[1];
									var activityType = api.value(0);
	
									var color;
									if (activityType === 'Application') {
										color = '#4BC0C0';
									} else if (activityType === 'Inactive') {
										color = '#E9EAEC';
									} else if (activityType === 'Idle') {
										color = '#FF6666';
									} else if (activityType === 'Browser') {
										color = '#2c5278';
									} else if (activityType === 'Call') {
										color = '#FFCC66';
									} else if (activityType === 'Internal Meeting') {
										color = '#9966FF';
									} else if (activityType == 'External Meeting') {
										color = '#6699FF';
									} else {
										color = '#4BC0C0';
									}

									var barHeight = Math.min(20, api.size([0, 1])[1] * 0.8);
	
									var item = {
										type: 'rect',
										shape: {
											x: api.coord([xValue, yValue])[0],
											y: yValue - barHeight / 2,
											width: api.size([xEndValue - xValue, 0])[0],
											height: barHeight,
										},
										style: api.style({
											fill: color,
											stroke: 'rgba(0,0,0,0.2)'
										})
									};
	
									return item;
								},
								dimensions: _rawData.flight.dimensions,
								encode: {
									x: [2, 3],
									y: 1,
								},
								data: _rawData.flight.data
							}
						]
					};
				}
	
				overallPerformance.setOption(makeOption());
	
				function updateChart() {
					let legends = overallPerformance.getOption().legend[0].selected;
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
	}
	// Overall Performance Timely Chart Code Ends

	// Application Used Chart Code Starts
	application_usage_time() {
		let data = this.selected_employee;
		frappe
			.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.application_usage_time", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				// console.log(r)
				// Hide calls tab if no call data is available
				const callsTab = document.querySelector('#system-activity-tab');
				const callsContent = document.querySelector('#system-activity');
				if (r.length === 0) {
					// console.log("No data available to plot the chart........................................");
					if (callsTab) callsTab.style.display = 'none';
        			if (callsContent) callsContent.style.display = 'none';

					return;
				}
				if (r.length === 0) {
					return;
				}

				const chartDom = document.getElementById('application-usage-time');
				if (!chartDom) {
					console.error('Chart container not found.');
					return;
				}

				const myChart = echarts.init(chartDom, null, { renderer: 'svg' });

				const getCurrentThemeLabelColor = () => {
					
					return {
						labelColor: '#FFFFFF', // Default to black
						backgroundColor: 'rgba(0,0,0,0)' // Default to transparent
					};
				};

				const themeColors = getCurrentThemeLabelColor();

				const option = {
					tooltip: {
						trigger: 'item',
						formatter: function(params) {
							const hours = params.data.hours;
							const minutes = params.data.minutes;
				
							// Format hours and minutes with leading zeros
							const formattedHours = hours.toString().padStart(2, '0');
							const formattedMinutes = minutes.toString().padStart(2, '0');
				
							return `${params.name} : ${formattedHours}:${formattedMinutes}`;
						},
						show: false // Ensure tooltip is shown when hovering
					},
					legend: {
						top: '3%',
						left: 'center'
					},
					series: [
						{
							name: 'Access From',
							type: 'pie',
							radius: ['40%', '70%'],
							top: '15%',
							avoidLabelOverlap: false,
							itemStyle: {
								borderRadius: 10,
								borderColor: '#fff',
								borderWidth: 2
							},
							label: {
								show: false,
								position: 'center'
							},
							emphasis: {
								label: {
									show: true,
									fontSize: 20,
									fontWeight: 'bold',
									formatter: function(params) {
										const hours = params.data.hours;
										const minutes = params.data.minutes;
							
										// Format hours and minutes with leading zeros
										const formattedHours = hours.toString().padStart(2, '0');
										const formattedMinutes = minutes.toString().padStart(2, '0');
							
										return `${params.name}\n${formattedHours}:${formattedMinutes} Hours`;
									},
									center: ['50%', '50%']
								}
							},
							labelLine: {
								show: false
							},
							data: r // Assuming `r` contains your pie chart data
						}
					],
				
					color: [
						'#FF6384', // Red
						'#36A2EB', // Blue
						'#FFCE56', // Yellow
						'#4BC0C0', // Cyan
						'#9966FF', // Lavender
						'#FF9966', // Orange
						'#66CCCC', // Light Blue
						'#6699FF', // Light Blue
						'#FF6666', // Light Red
						'#FFCC66'  // Light Yellow
					]
				};
				

				// Set dynamic width and height for the chart
				myChart.resize();

				myChart.setOption(option);
				// Ensure `selected_start_date` and `selected_end_date` are accessible or passed as arguments
				document.getElementById('application-analysis-link').addEventListener('click', function(event) {
					event.preventDefault(); // Prevent the default action of the link
					goToApplicationAnalysis(this.selected_employee,this.selected_start_date, this.selected_end_date); // Pass the dates from context
				}.bind(this)); // Bind `this` context for access to instance properties
				myChart.resize(); // Resize to fit the container
	
				// Re-add resize listener to ensure chart resizes with window
				window.addEventListener('resize', function () {
					myChart.resize();
				});
			})
			.catch(error => {
				console.error("Error fetching chart data:", error);
			});
		// Function to redirect to Application Analysis page with selected dates
		function goToApplicationAnalysis(employee,start_date, end_date) {
			var baseUrl = window.location.origin;
			var applicationAnalysisUrl = baseUrl + "/app/query-report/Application Analysis?group_by_application_name=1&employee="+ employee +"&from_date=" + start_date + "&to_date=" + end_date;
			window.open(applicationAnalysisUrl, '_blank');
		}
	}
	// Application Used Chart Code Ends

	// Web Browsing Time Chart Code Starts
	web_browsing_time() {
		let data = this.selected_employee || this.user_id;
		frappe
			.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.web_browsing_time", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then(r => {
				if (r.length === 0) return;
	
				const chartDom = document.getElementById('web-browsing-time');
				if (!chartDom) {
					console.error('Chart container not found.');
					return;
				}
	
				// Destroy existing chart instance if it exists
				let myChart = echarts.getInstanceByDom(chartDom);
				if (!myChart) {
					myChart = echarts.init(chartDom, null, { renderer: 'svg' });
				}
	
				const option = {
					tooltip: {
						trigger: 'item',
						formatter: params => {
							let totalHours = params.value;
							let hours = Math.floor(totalHours);
							let minutes = Math.round((totalHours - hours) * 60);
							return `${params.name} : ${hours}:${minutes < 10 ? '0' + minutes : minutes} Hours`;
						}
					},
					legend: {
						orient: 'horizontal',
						left: 10
					},
					series: [{
						name: 'Access From',
						type: 'pie',
						radius: '55%',
						top: '20%',
						center: ['50%', '50%'],
						label: {
							show: false
						},
						labelLine: {
							show: false
						},
						data: r,
						emphasis: {
							itemStyle: {
								shadowBlur: 10,
								shadowOffsetX: 0,
								shadowColor: 'rgba(0, 0, 0, 0.5)'
							}
						}
					}],
					color: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9966', '#66CCCC', '#6699FF', '#FF6666', '#FFCC66'],
					textStyle: {
						color: '#FFFFFF'
					},
					backgroundColor: 'rgba(0,0,0,0)'
				};
	
				myChart.setOption(option);
				// Ensure `selected_start_date` and `selected_end_date` are accessible or passed as arguments
				document.getElementById('domain-analysis-link').addEventListener('click', function(event) {
					event.preventDefault(); // Prevent the default action of the link
					goToDomainAnalysis(this.selected_employee,this.selected_start_date, this.selected_end_date); // Pass the dates from context
				}.bind(this)); // Bind `this` context for access to instance properties
				myChart.resize(); // Resize to fit the container
	
				// Re-add resize listener to ensure chart resizes with window
				window.addEventListener('resize', function () {
					myChart.resize();
				});
			})
			.catch(error => {
				console.error("Error fetching chart data:", error);
			});
		// Function to redirect to Calls Analysis page with selected dates
		function goToDomainAnalysis(employee,start_date, end_date) {
			var baseUrl = window.location.origin;
			var activityAnalysisUrl = baseUrl + "/app/query-report/Domains Analysis?group_by_domain=1&employee="+ employee +"&from_date=" + start_date + "&to_date=" + end_date;
			window.open(activityAnalysisUrl, '_blank');
		}
	}
	
	// Web Browsing Time Chart Code Ends
	
	// Top phone calls chart code starts
	top_phone_calls() {
		let data;
		if (this.selected_employee !== null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}

		frappe
			.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.top_phone_calls", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				const containerElement = document.getElementById('calls');
				if (r.caller_details.length === 0) {
					if (containerElement) containerElement.style.display = 'none';
					return;
				}

				const chartDom = document.getElementById('top-phone-calls');
				if (!chartDom) {
					console.error('Chart container not found.');
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
								return `${params.seriesName} <br/>${params.marker} ${params.name}: ${minutes}:${formattedSeconds} Min`;
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
								width: 200,
							},
							labelLine: {
								show: true
							},
							data: r.company_details,
							color: [
								'#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
								'#9966FF', '#FF9966', '#66CCCC', '#6699FF',
								'#FF6666', '#FFCC66'
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
									return `{a|${customName}}{abg|}\n{hr|}\n  {b|${params.name}：}${minutes}:${formattedSeconds} Min`;
								},
								maxWidth: 200,
								padding: 5,
								backgroundColor: '#F6F8FC',
								borderColor: '#8C8D8E',
								borderWidth: 1,
								borderRadius: 4,
								show: true,
								rich: {
									a: {
										color: '#6E7079',
										lineHeight: 22,
										align: 'center'
									},
									hr: {
										borderColor: '#8C8D8E',
										width: '100%',
										borderWidth: 1,
										height: 0
									},
									b: {
										color: '#4C5058',
										fontSize: 14,
										fontWeight: 'bold',
										lineHeight: 33
									},
									per: {
										color: '#fff',
										backgroundColor: '#4C5058',
										padding: [3, 4],
										borderRadius: 4
									}
								},
							},
							data: r.caller_details,
							color: [
								'#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
								'#9966FF', '#FF9966', '#66CCCC', '#6699FF',
								'#FF6666', '#FFCC66'
							]
						}
					],
				};

				// Set dynamic width and height for the chart
				myChart.resize();

				myChart.setOption(option);

				// Ensure `selected_start_date` and `selected_end_date` are accessible or passed as arguments
				document.getElementById('calls-analysis-link').addEventListener('click', function(event) {
					event.preventDefault(); // Prevent the default action of the link
					goToCallsAnalysis(this.selected_employee,this.selected_start_date, this.selected_end_date); // Pass the dates from context
				}.bind(this)); // Bind `this` context for access to instance properties

				window.addEventListener('resize', function () {
					myChart.resize();
				});

				// console.log("Chart plotted successfully.");
			})
			.catch(error => {
				console.error("Error fetching chart data:", error);
			});

		// Function to redirect to Calls Analysis page with selected dates
		function goToCallsAnalysis(employee,start_date, end_date) {
			var baseUrl = window.location.origin;
			var activityAnalysisUrl = baseUrl + "/app/query-report/Calls Analysis?employee="+ employee +"&from_date=" + start_date + "&to_date=" + end_date;
			window.open(activityAnalysisUrl, '_blank');
		}
	}
	// Top phone calls chart code ends

	
	// Type of calls chart code starts
	type_of_calls() {
		let data;
		if (this.selected_employee !== null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}

		frappe
			.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.type_of_calls", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				const tabs = document.querySelectorAll('.nav-link');
				const contents = document.querySelectorAll('.tab-pane');

				// Hide calls tab if no call data is available
				const callsTab = document.querySelector('#phone-calls-tab');
				const callsContent = document.querySelector('#phone-calls');
				// console.log("call",r)
				if (r[0].value === null & r[1].value === null) {
					if (callsTab) callsTab.style.display = 'none';
        			if (callsContent) callsContent.style.display = 'none';
					
					// console.log("No data available to plot the chart.");
					return;
				}

				const chartDom = document.getElementById('type-of-calls');
				if (!chartDom) {
					console.error('Chart container not found.');
					return;
				}

				const myChart = echarts.init(chartDom, null, { renderer: 'svg' });

				// Example function to get current theme's label color
				const getCurrentThemeLabelColor = () => {
					return {
						labelColor: '#FFFFFF',
						backgroundColor: 'rgba(0,0,0,0)'
					};
				};

				const themeColors = getCurrentThemeLabelColor();

				const option = {
					tooltip: {
					  trigger: 'item',
					  formatter: function(params) {
						// Calculate minutes and seconds
						let totalMinutes = params.value;
						let minutes = Math.floor(totalMinutes); // Get the whole number of minutes
						let seconds = Math.round((totalMinutes - minutes) * 60); // Convert the fraction to seconds and round it
					
						// Format seconds to always display 2 digits
						let formattedSeconds = (seconds < 10 ? '0' : '') + seconds;
					
						// Return formatted string with colon between minutes and seconds
						return `${params.name} : ${minutes}:${formattedSeconds} Min`;
					}
					},
					legend: {
					  top: '5%',
					  left: 'center'
					},
					series: [
					  {
						name: 'Access From',
						type: 'pie',
						radius: ['40%', '70%'],
						center: ['50%', '70%'],
						// adjust the start and end angle
						startAngle: 180,
						endAngle: 360,
						data: r,
						labelLine: {
							show: false // Hide label lines
						},
						label: {
							show: false // Hide labels (text)
						}
					  }
					],
					color: [
						'#4BC0C0', // Cyan
						'#9966FF', // Lavender
					],
					textStyle: {
						color: themeColors.labelColor
					},
					backgroundColor: themeColors.backgroundColor
				};

				// Set dynamic width and height for the chart
				myChart.resize();

				myChart.setOption(option);

				window.addEventListener('resize', function () {
					myChart.resize();
				});

				// console.log("Chart plotted successfully.");
			})
			.catch(error => {
				console.error("Error fetching chart data:", error);
			});
	}
	// Type of calls chart code ends

	// URL DATA Code Starts
	fetch_url_data() {
		this.numberCardData = {};
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}

		frappe.call({
			method: "productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.fetch_url_data",
			args: {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			},
			callback: (r) => {
				if (r.message) {
					this.numberCardData = r.message;
					this.url_data(r.message);
					$(document).ready(function () {
						$('#logCountModalTrigger').click(function () {
							$('#logCountModal').modal('show');
						});
					});
					this.activity_data();
				}
			}
		});
	}
	url_data(data) {
		function getBaseURL() {
			return window.location.origin + '/app/';
		}
	
		let employee_data;
		let start_date_ = this.selected_start_date;
		let end_date_ = this.selected_end_date;
		if (this.selected_employee != null) {
			employee_data = this.selected_employee;
		} else {
			employee_data = this.user_id;
		}
	
		const baseUrl = getBaseURL();
		const container = this.main_section.find("#url-data");
		container.empty();
		let wholedata = `
			<div class="title-area">
				<h4 class="card-title">URL Data</h4>
			</div>`;
		wholedata += `
			<div class="row mt-3">
				<div class="col-md-12">
					<div class="custom-card">
						<h4 class="custom-title p-3" style="font-size: 14px !important;" align="center">Top 10 Sites Used</h4>
						<div class="table-responsive">
						<table class="table">
							<thead>
								<tr style="align:center !important;">
									<th>Domain</th>
									<th>No. of Visits</th>
									<th>Application</th>
									<th>Duration</th>
								</tr>
							</thead>
							<tbody>`;
	
		data.url_full_data.forEach(app => {
			wholedata += `
				<tr>
					<td style="color:#00A6E0 !important;"><b><a href="#" style="text-decoration:none !important;color:#00A6E0 !important;" class="url-link" data-url="${app.domain}">${app.domain}</a></b></td>
					<td style="color:#62BA46"><b>${app.count}</b></td>
					<td style="color:#62BA46"><b>${app.application_name}</b></td>
					<td style="color:#FF4001">${this.convertSecondsToTime_(app.total_duration)} H</td>
				</tr>`;
		});
	
		wholedata += `
							</tbody>
						</table>
					</div>
				</div>
			</div>`;
		container.append(wholedata);
		$(document).ready(function () {
			$(document).on('click', '.url-link', function (e) {
				e.preventDefault();
				let clickedLink = $(this); // Store reference to clicked link
	
				// AJAX call to Python function
				frappe.call({
					method: "productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.get_url_brief_data",
					args: {
						url_data: clickedLink.data('url'),
						user: employee_data,
						start_date: start_date_,
						end_date: end_date_,
					},
					freeze: true, // Optional: Freeze the screen until data is loaded
					callback: function (r) {
						if (r.message) {
							let data = r.message.data;
							render_url_brief_data(data);
						} else {
							render_url_brief_data([]); // Empty data to handle no data case
						}
					}
				});
			});
	
			function render_url_brief_data(data) {
				function convertSecondsToTime_(seconds) {
					const hours = Math.floor(seconds / 3600);
					const minutes = Math.floor((seconds % 3600) / 60);
					const formattedMinutes = minutes < 10 ? `0${minutes}` : minutes;
					return `${hours}:${formattedMinutes}`;
				}
	
				let displayContent = `
				<style>
					.url-table {
						width: 100%;
						table-layout: fixed;
					}
					.url-table th, .url-table td {
						padding: 8px;
						overflow: hidden;
						text-overflow: ellipsis;
						white-space: nowrap;
					}
					.url-table th:nth-child(1), .url-table td:nth-child(1) { width: 30%; }
					.url-table th:nth-child(2), .url-table td:nth-child(2) { width: 40%; }
					.url-table th:nth-child(3), .url-table td:nth-child(3) { width: 15%; }
					.url-table th:nth-child(4), .url-table td:nth-child(4) { width: 15%; }
				</style>
				<div class="frappe-card custom-card">
					<h4 class="custom-title p-3" style="font-size: 14px !important; text-align: center;">Top 10 URL's Used</h4>
					<div class="table-responsive" style="overflow-x: hidden;">
						<table class="table url-table">
							<thead>
								<tr>
									<th>Page Title</th>
									<th>Page URL</th>
									<th>Duration</th>
									<th>Page Visits</th>
								</tr>
							</thead>
							<tbody>`;
	
				if (data.length === 0) {
					displayContent += `<tr><td colspan="4" class="text-center">No data available for this URL.</td></tr>`;
				} else {
					data.forEach(app => {
						displayContent += `
						<tr>
							<td title="${app.application_title}"><span style="color:#00A6E0;"><b>${app.application_title}</b></span></td>
							<td title="${app.url}"><a href="${app.url}" target="_blank"><span style="color:#00A6E0;"><b>${app.url}</b></span></a></td>
							<td><span style="color:#FF4001;">${convertSecondsToTime_(app.duration)} H</span></td>
							<td><span style="color:#62BA46;"><b>${app.count}</b></span></td>
						</tr>`;
					});
				}
	
				displayContent += `
							</tbody>
						</table>
					</div>
				</div>`;
	
				let dialog = new frappe.ui.Dialog({
					title: 'URL Information',
					fields: [
						{
							fieldtype: 'HTML',
							label: '',
							fieldname: 'url_content',
							options: displayContent
						}
					],
					size: 'extra-large',
					primary_action_label: 'Close',
					primary_action: function() {
						dialog.hide();
					},
				});
				
				dialog.show();
			}				
		});
	}
	
	// URL DATA Code Ends

	// Sidebar Activity Data code starts
	activity_data() {
		function getBaseURL() {
			return window.location.origin + '/app/';
		}
		this.start_date_ = this.selected_start_date;
		this.end_date_ = this.selected_end_date;
		const baseUrl = getBaseURL();
		if (this.numberCardData) {
			this.callsHoursIncoming = this.convertSecondsToTime_(this.numberCardData.total_incoming_duration + this.numberCardData.internal_total_incoming_duration)
			this.callsHoursOutgoing = this.convertSecondsToTime_(this.numberCardData.total_outgoing_duration + this.numberCardData.internal_total_outgoing_duration)
			this.meeting_hours = this.convertSecondsToTime_(this.numberCardData.total_meeting_duration_external + this.numberCardData.total_meeting_duration_internal)
			this.internal_meeting_hours = this.convertSecondsToTime_(this.numberCardData.total_meeting_duration_internal)
			this.external_meeting_hours = this.convertSecondsToTime_(this.numberCardData.total_meeting_duration_external)
		} else {
			this.callsHoursIncoming = 0;
			this.callsHoursOutgoing = 0;
			this.meeting_hours = 0;
			this.internal_meeting_hours = 0;
			this.external_meeting_hours = 0;
		}
		frappe.db.get_value("Employee", this.selected_employee, "image")
			.then((result) => {
				const userImage = result.message.image;
				const employeeMeetingUrl = `${baseUrl}meeting?employee=${encodeURIComponent(this.selected_employee)}&meeting_from=${encodeURIComponent(`["Between",["${this.start_date_}","${this.end_date_}"]]`)}&docstatus=1`;
				const employeeFincallUrl = `${baseUrl}query-report/Calls Analysis?employee=${encodeURIComponent(this.selected_employee)}&from_date=${encodeURIComponent(this.start_date_)}&to_date=${encodeURIComponent(this.end_date_)}`;
				this.sidebar.empty().append(
					this.update_activity_chart_data(),
					frappe.render_template("productify_activity_analysis_sidebar", {
						user_image: userImage,
						user_abbr: this.user.abbr,
						user_location: this.user.location,
						numberCardData: this.numberCardData,
						employeeMeetingUrl: employeeMeetingUrl,
						employeeFincallUrl: employeeFincallUrl,
						callsHoursIncoming: this.callsHoursIncoming,
						callsHoursOutgoing: this.callsHoursOutgoing,
						meeting_total_hours: this.meeting_hours,
						internal_meeting_hours: this.internal_meeting_hours,
						external_meeting_hours: this.external_meeting_hours
					})
				);
			})
			.catch((err) => {
				console.error("Error fetching user image:", err);
			});

		this.setup_user_profile_links();
	}
	update_activity_chart_data() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.get_activity_chart_data", {
			user: data,
			start_date: this.selected_start_date,
			end_date: this.selected_end_date,
		})
			.then((r) => {

				// Convert time values from seconds to formatted hours and minutes
				const total_system_hours = this.convertSecondsToTime_(r.total_system_hours);
				const total_active_hours = this.convertSecondsToTime_(r.total_active_hours);
				const total_idle_time = this.convertSecondsToTime_(r.total_idle_time);
				const total_hours = this.convertSecondsToTime_(r.total_hours);
				const total_call_raw = this.convertSecondsToTime_(this.numberCardData.total_outgoing_duration + this.numberCardData.internal_total_outgoing_duration + this.numberCardData.total_incoming_duration + this.numberCardData.internal_total_incoming_duration);
				const total_meeting_raw = this.convertSecondsToTime_(this.numberCardData.total_meeting_duration_external + this.numberCardData.total_meeting_duration_internal);
				const overlapping = this.convertSecondsToTime_((r.total_system_hours + (this.numberCardData.total_outgoing_duration + this.numberCardData.internal_total_outgoing_duration + this.numberCardData.total_incoming_duration + this.numberCardData.internal_total_incoming_duration) + (this.numberCardData.total_meeting_duration_external + this.numberCardData.total_meeting_duration_internal)) - (r.total_active_hours));
				if (this.numberCardData.score == 0) {
					this.score2 = 100;
				}
				else {
					this.score2 = parseFloat(((r.total_active_hours/3600)/this.numberCardData.score)*100).toFixed(0);
				}
				$(document).ready(function() {

					const hovercontainer = $("#user-activity-hover");
					hovercontainer.html(`
						<div class="progress" style="max-width: 400px !important;" data-toggle="tooltip" data-html="true" data-placement="left" title="">
							<div class="progress-bar bg-success" role="progressbar" style="width: ${r.total_active_hours}%" aria-valuenow="${r.total_active_hours}" aria-valuemin="0" aria-valuemax="${r.total_hours}"></div>
							<div class="progress-bar bg-danger" role="progressbar" style="width: ${r.total_idle_time}%" aria-valuenow="${r.total_idle_time}" aria-valuemin="0" aria-valuemax="${r.total_hours}"></div>
							<div class="progress-bar bg-info" role="progressbar" style="width: ${r.total_call_data}%" aria-valuenow="${r.total_call_data}" aria-valuemin="0" aria-valuemax="${r.total_hours}"></div>
							<div class="progress-bar bg-warning" role="progressbar" style="width: ${r.total_meeting_data}%" aria-valuenow="${r.total_meeting_data}" aria-valuemin="0" aria-valuemax="${r.total_hours}"></div>
						</div>
					`);
				
					var myDefaultWhiteList = $.fn.tooltip.Constructor.Default.whiteList;
					myDefaultWhiteList.table = ['class'];
					myDefaultWhiteList.tbody = [];
					myDefaultWhiteList.tr = [];
					myDefaultWhiteList.td = [];
				
					// Define tooltip content function
					function getTooltipContent() {
						return `
							<div>
								<h4 class ="text-center text-white">User Activity</h4>
								<table class='table-borderless table-tooltip table-spacing'>
									<tbody>
					  <tr>
						<td>Call:</td>
						<td class="justify time-cell"><span>${total_call_raw} H</span></td>
					  </tr>
					  <tr>
						<td>Meeting:</td>
						<td class="justify time-cell"><span>${total_meeting_raw} H</span></td>
					  </tr>
					  <tr>
						<td>System:</td>
						<td class="justify time-cell"><span>${total_system_hours} H</span></td>
					  </tr>
					  <tr class = "border-bottom">
						<td>Overlapping:</td>
						<td class="justify time-cell"><span>-${overlapping} H</span></td>
					  </tr>
					  <tr>
						<td><b>Active Time:</b></td>
						<td class="justify time-cell"><span><b>${total_active_hours} H</b></span></td>
					  </tr>
					  <tr>
						<td><b>Idle Time:</b></td>
						<td class="justify time-cell"><span><b>${total_idle_time} H</b></span></td>
					  </tr>
					  <tr class = "border-top">
						<td><b>Total Time:</b></td>
						<td class="justify time-cell"><span><b>${total_hours} H</b></span></td>
					  </tr>
					</tbody>
								</table>
							</div>
						`;
					}
				
					$('[data-toggle="tooltip"]').tooltip({
						container: 'body',
						html: true,
						whiteList: myDefaultWhiteList,
						placement: 'left',
						template: '<div class="tooltip-custom" style="max-width: 400px !important;" role="tooltip"><div class="arrow"></div><div class="tooltip-inner tooltip-inner-custom"></div></div>',
						title: getTooltipContent
					});
				});


	const container = $("#user-activity");
	container.html(`
		 <style>
        .progress-container {
            margin-bottom: 10px; /* Space between progress bar and table */
        }
    </style>
		<div class="card border-primary shadow d-none d-lg-block table-height">
    <div class="card-body">
  <h5 class="card-title text-primary text-center">User Activity</h5>
  <table class="table table-borderless custom-table">
    <tbody>
      <tr>
        <td>Call:</td>
        <td class="justify time-cell"><span>${total_call_raw} H</span></td>
      </tr>
      <tr>
        <td>Meeting:</td>
        <td class="justify time-cell"><span>${total_meeting_raw} H</span></td>
      </tr>
      <tr>
        <td>System:</td>
        <td class="justify time-cell"><span>${total_system_hours} H</span></td>
      </tr>
      <tr style="border-bottom: 1px solid #E5E4E2;">
        <td>Overlapping:</td>
        <td class="justify time-cell"><span>-${overlapping} H</span></td>
      </tr>
      <tr>
        <td><b>Active Time:</b></td>
        <td class="justify time-cell"><span><b>${total_active_hours} H</b></span></td>
      </tr>
      <tr>
        <td><b>Idle Time:</b></td>
        <td class="justify time-cell"><span><b>${total_idle_time} H</b></span></td>
      </tr>
      <tr style="border-top: 3px solid">
        <td><b>Total Time:</b></td>
        <td class="justify time-cell"><span><b>${total_hours} H</b></span></td>
      </tr>
    </tbody>
  </table>
</div>
		</div><br><br>
	`);
	container.append(`
		<div class="score-container" style="text-align: center;">
        <span style="padding-top:10px;font-size: 18px;">
            Productivity Score : 
            <span style="font-size: 22px;"><b>${this.score2} </b></span>
        </span>
    </div>`);

			var myDefaultWhiteList = $.fn.tooltip.Constructor.Default.whiteList;
			myDefaultWhiteList.table = ['class'];
			myDefaultWhiteList.tbody = [];
			myDefaultWhiteList.tr = [];
			myDefaultWhiteList.td = [];

			$('[data-toggle="tooltip"]').tooltip({
				container: 'body',
				html: true,
				whiteList: myDefaultWhiteList,
				title: function () { return '<u>text1</u><table class="table text-light"><tr><td>text2</td></tr></table>'; }
			});

				// Enable tooltips with custom class
				$('[data-toggle="tooltip"]').tooltip({
					html: true,
					container: 'body',
					placement: 'left', // Set tooltip placement to left
					template: '<div class="tooltip-custom" style="max-width: 350px !important;" role="tooltip"><div class="arrow"></div><div class="tooltip-inner tooltip-inner-custom"></div></div>'
				});
				const styles = `
							<style>
								.custom-table td {
									padding: 0px !important; /* Adjust padding to reduce space */
									margin: 0 !important; /* Remove margin */
								}
								.custom-table {
									font-size: 14px; /* Adjust font size if needed */
								}
								.custom-table td b {
									font-weight: bold;
								}
								.card-body {
									padding: 5px;
									padding-bottom: 1px /* Adjust padding inside card body */
								}
								.card-title {
									margin-bottom: 10px; /* Adjust margin at the bottom of the title */
								}
							</style>
							`;
				const mobilecontainer = $("#user-activity-mobile");
				mobilecontainer.html(`
					${styles}
					<div class="d-lg-none">
						<div class="card border-primary shadow table-height">
							<div class="card-body">
							<h5 class="card-title text-primary text-center">User Activity</h5>
							<table class="table table-borderless custom-table">
								<tbody>
								<tr>
									<td>Call:</td>
									<td class="justify time-cell"><span>${total_call_raw} H</span></td>
								</tr>
								<tr>
									<td>Meeting:</td>
									<td class="justify time-cell"><span>${total_meeting_raw} H</span></td>
								</tr>
								<tr>
									<td>System:</td>
									<td class="justify time-cell"><span>${total_system_hours} H</span></td>
								</tr>
								<tr style="border-bottom: 1px solid #E5E4E2;">
									<td>Overlapping:</td>
									<td class="justify time-cell"><span>-${overlapping} H</span></td>
								</tr>
								<tr>
									<td><b>Active Time:</b></td>
									<td class="justify time-cell"><span><b>${total_active_hours} H</b></span></td>
								</tr>
								<tr>
									<td><b>Idle Time:</b></td>
									<td class="justify time-cell"><span><b>${total_idle_time} H</b></span></td>
								</tr>
								<tr style="border-top: 3px solid">
									<td><b>Total Time:</b></td>
									<td class="justify time-cell"><span><b>${total_hours} H</b></span></td>
								</tr>
								</tbody>
							</table>
							</div>
						</div>
					</div>`
				)
			});
			function toggleTheme(theme) {
				const body = document.body;
				if (theme === 'dark') {
					body.setAttribute('data-theme', 'dark');
				} else {
					body.removeAttribute('data-theme');
				}
			}
			
			// Example usage:
			// To set dark mode
			toggleTheme('dark');
			
			// To set light mode
			toggleTheme('light');
	}
	
	// Sidebar Activity Data code ends

	// Hourly Calls Analysis (In Minutes) Chart code starts
	hourly_calls_analysis() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
		frappe
			.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.hourly_calls_analysis", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				const containerElement = document.getElementById("hourly-calls");
				if (r.labels.length === 0) {
					if (containerElement) containerElement.style.display = 'none';
                	return;
				}else {
					let chartDom = document.querySelector('.hourly-calls-analysis')
					let chart = echarts.init(chartDom, null, {
						renderer: 'svg',
						useDirtyRect: false
					});
					let option = {
						tooltip: {
							trigger: 'axis',
							axisPointer: {
								type: 'shadow'
							},
							formatter: function(params) {
								let tooltip = params[0].name + '<br/>'; // X-axis label (hour)
							
								params.forEach(param => {
									let totalMinutes = param.value;
									let minutes = Math.floor(totalMinutes); // Get the whole number of minutes
									let seconds = Math.round((totalMinutes - minutes) * 60); // Convert the fraction to seconds and round it
							
									// Format seconds to always display 2 digits
									let formattedSeconds = (seconds < 10 ? '0' : '') + seconds;
							
									tooltip += `${param.seriesName}: ${minutes}:${formattedSeconds} Min<br/>`; // Series name and formatted time
								});
							
								return tooltip;
							}
						},
						legend: {
							data: r.legend_names
						},
						xAxis: {
							type: 'category',
							data: r.labels
						},
						yAxis: {
							type: 'value'
						},
						series: [
							{
								name: 'Incoming',
								data: r.datasets[0].values,
								type: 'bar',
								stack: 'x',
								itemStyle: {
									color: '#FFCC66' // Light Yellow
								}
							},
							{
								name: 'Outgoing',
								data: r.datasets[1].values,
								type: 'bar',
								stack: 'x',
								itemStyle: {
									color: '#FF6666' // Light Red
								}
							}
						]
					};
					
					chart.setOption(option);
					window.addEventListener('resize', chart.resize);
				}
			});
	}
	// Hourly Calls Analysis (In Minutes) Chart code ends

	// Top 7 Document Analysis (Changes Per Doctype) code starts
	top_document_analysis() {
		let data;
		if (this.selected_employee != null) {
			data = this.selected_employee;
		} else {
			data = this.user_id;
		}
	
		frappe
			.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.top_document_analysis", {
				user: data,
				start_date: this.selected_start_date,
				end_date: this.selected_end_date,
			})
			.then((r) => {
				if (r.length === 0) {
					// console.log("No data available to plot the chart.");
					return;
				}
	
				// console.log("Chart data received:", r);
	
				const chartDom = document.querySelector('.top-document-analysis');
				if (!chartDom) {
					console.error('Chart container not found.');
					return;
				}
	
				// console.log("Chart container found:", chartDom);
	
				const myChart = echarts.init(chartDom, null, { renderer: 'svg' });
				const option = {
					tooltip: {
						trigger: 'axis',
					},
					legend: {
						orient: 'vertical',
					  	center:20
					},
					grid: {
						containLabel: true,
					},
					dataset: {
						source: r,  // Ensure r is in the correct format: an array of objects
					},
					xAxis: {
						type: 'value',  // Use 'value' type for horizontal bar charts
					},
					yAxis: {
						type: 'category',  // Use 'category' type for y-axis (bars will be categorized)
						axisTick: {
							alignWithLabel: true,
						},
					},
					series: [{
						name: 'Activity Count',
						type: 'bar',
						itemStyle: {
							color: '#6699FF', // Light Blue
						},
						encode: {
							y: 'ref_doctype',  // Encode y-axis with 'ref_doctype'
							x: 'activity_count',  // Encode x-axis with 'activity_count'
						}
					}]
				};
	
				myChart.setOption(option);
	
				window.addEventListener('resize', function () {
					myChart.resize();
				});
	
				// console.log("Chart plotted successfully.");
			})
			.catch(error => {
				console.error("Error fetching or rendering chart:", error);
			});
	}
	// Top 7 Document Analysis (Changes Per Doctype) code ends
	
	// User Activity Images code starts
	async render_images() {
		let startDatetime = new Date(this.selected_start_date + " 00:00:00");
		let endDatetime = new Date(this.selected_end_date + " 23:59:59");
		let data = this.selected_employee ? this.selected_employee : this.user_id;
	
		let lastPrintedDate = null;
		let lastPrintedHour = null;
	
		const imageContainer = this.main_section.find(".recent-activity-list");
		const debounce = (func, delay) => {
			let debounceTimer;
			return function () {
				clearTimeout(debounceTimer);
				debounceTimer = setTimeout(() => func.apply(this, arguments), delay);
			};
		};
		function formatDate(date) {
			return date.toISOString().split('T')[0];
		}
	
		const loadImages = async (user, start_time, end_time) => {
			let flag = 0;
			await frappe.xcall("productivity_next.productivity_next.page.productify_activity_analysis.productify_activity_analysis.user_activity_images", {
				user: user,
				start_date: start_time,
				end_date: end_time,
			}).then((imagedata) => {
				if (imagedata.length > 0) {
					flag = 1;
				}
				imagedata.reverse();
				let slotImages = {};
				imagedata.forEach((image) => {
					const imageDateTime = new Date(image.time);
					const hour = imageDateTime.getHours();
					const date = imageDateTime.toDateString();
					const slot = Math.floor(imageDateTime.getMinutes() / 5);
					this.formattedDate_ = formatDate(imageDateTime);
					if (!slotImages[date]) {
						slotImages[date] = {};
					}
					if (!slotImages[date][hour]) {
						slotImages[date][hour] = new Array(12).fill(null);
					}
					slotImages[date][hour][slot] = image;
				});
			ssss	
				Object.keys(slotImages).reverse().forEach(date => {
					Object.keys(slotImages[date]).reverse().forEach(hour => {
						if (lastPrintedDate !== date || lastPrintedHour !== hour) {
							// console.log("hiii performance-chart-",this.formattedDate_,hour);
							const hourHeader = `<div class="col-md-1"><h5><b>${date} ${hour}:00</b></h5></div><br><div class="col-md-11">
							<div class="overall-performance-timely" id="performance-chart-${this.formattedDate_}-${hour}" style="min-height: 50px; max-height: 50px;">
								<!-- Overall Performance Chart Container -->
							</div>
							</div>`;
							imageContainer.append(hourHeader);
							lastPrintedDate = date;
							lastPrintedHour = hour;
	
							// Call the function to display chart for this hour
							this.overall_performance_timely(this.formattedDate_,hour);
						}
	
						for (let slot = 11; slot >= 0; slot--) {
							const image = slotImages[date][hour][slot];
							const slotTime = new Date(date);
							slotTime.setHours(hour);
							slotTime.setMinutes(slot * 5);
							const slotTimeString = slotTime.toLocaleTimeString('en-US',{ hour: '2-digit', minute: '2-digit', hour12: false });
	
							if (image) {
								const imgElement = `
									<div class="col-md-3">
										<div style="display: flex; justify-content: center; align-items: center; height: 160px;">
											<img src="${image.screenshot}" title="${image.time_}" data-active-app="${image.active_app}" alt="User Activity Image" style="max-width: 100%; max-height: 100%; object-fit: contain;" class="clickable-image">
										</div>
										<p style="text-align: center;"><b>${slotTimeString}</b></p>
									</div>`;
								imageContainer.append(imgElement);
							} else {
								const gapMessage = `
									<div class="col-md-3">
										<div style="width: 100%; height: 160px; background-color: #dddddd; display: flex; justify-content: center; align-items: center;">
											<span style="font-weight: bold;">Not Active</span>
										</div>
										<p style="text-align: center;"><b>${slotTimeString}</b></p>
									</div>`;
								imageContainer.append(gapMessage);
							}
						}
					});
				});
	
				function setImageHeight() {
					const windowHeight = window.innerHeight;
					const imageHeight = windowHeight * 0.2;
					const images = document.querySelectorAll('.clickable-image');
					images.forEach(img => {
						img.style.height = `${imageHeight}px`;
					});
				}
				setImageHeight();
				window.addEventListener('resize', setImageHeight);
	
				$('.clickable-image').off('click').on('click', function () {
					const imgSrc = $(this).attr('src');
					const activeApp = $(this).data('active-app');
	
					showImageDialog(imgSrc, activeApp);
				});
	
			});
			return flag;
		};
	
		function showImageDialog(imgSrc, activeApp) {
			// Create and show the Frappe dialog
			let dialog = new frappe.ui.Dialog({
				title: activeApp || 'Unknown App', // Set the title dynamically
				fields: [
					{
						fieldtype: 'HTML',
						label: '',
						fieldname: 'image_content',
						options: `
							<div class="frappe-card custom-card">
								<div class="modal-body">
									<img id="zoomedImg" src="${imgSrc}" class="img-fluid" style="width: 100%; height: auto; object-fit: contain;">
								</div>
							</div>`
					}
				],
				size: 'extra-large', // Adjust the size as needed
				primary_action_label: 'Close',
				primary_action: function () {
					dialog.hide();
				}
			});
	
			dialog.show();
		}
	
		let currentDatetime = endDatetime;
		let start_time = new Date(currentDatetime);
		let end_time = new Date(currentDatetime);
	
		imageContainer.empty();
	
		end_time = new Date(currentDatetime);
		currentDatetime.setHours(currentDatetime.getHours(), currentDatetime.getMinutes(), currentDatetime.getSeconds(), 0);
		currentDatetime.setHours(currentDatetime.getHours() - 1);
		start_time = new Date(currentDatetime);
	
		if (start_time < startDatetime) {
			return;
		} else {
			let flag = await loadImages(data, start_time.toLocaleString('en-in'), end_time.toLocaleString('en-in'));
	
			while ((flag == 0) && (start_time > startDatetime)) {
				end_time = new Date(currentDatetime);
				currentDatetime.setHours(currentDatetime.getHours(), currentDatetime.getMinutes(), currentDatetime.getSeconds(), 0);
				currentDatetime.setHours(currentDatetime.getHours() - 1);
				start_time = new Date(currentDatetime);
	
				flag = await loadImages(data, start_time.toLocaleString('en-in'), end_time.toLocaleString('en-in'));
			}
		}
	
		if (currentDatetime > startDatetime) {
			const handleScroll = debounce(async () => {
				const scrollHeight = $(document).height();
				const scrollPosition = $(window).height() + $(window).scrollTop();
				const scrollThreshold = 400;
	
				if (scrollPosition >= scrollHeight - scrollThreshold) {
					end_time = new Date(currentDatetime);
					currentDatetime.setHours(currentDatetime.getHours(), currentDatetime.getMinutes(), currentDatetime.getSeconds(), 0);
					currentDatetime.setHours(currentDatetime.getHours() - 1);
					start_time = new Date(currentDatetime);
	
					if (start_time < startDatetime) {
						return;
					} else {
						let flag = await loadImages(data, start_time.toLocaleString('en-in'), end_time.toLocaleString('en-in'));
	
						while ((flag == 0) && (start_time > startDatetime)) {
							end_time = new Date(currentDatetime);
							currentDatetime.setHours(currentDatetime.getHours(), currentDatetime.getMinutes(), currentDatetime.getSeconds(), 0);
							currentDatetime.setHours(currentDatetime.getHours() - 1);
							start_time = new Date(currentDatetime);
	
							flag = await loadImages(data, start_time.toLocaleString('en-in'), end_time.toLocaleString('en-in'));
						}
					}
				}
			}, 100);
	
			$(window).on('scroll', handleScroll);
		}
	
		// this.overall_performance_timely(); // If this is to be called at the end of all operations, ensure it is properly implemented
	}
	
	
	// User Activity Images code ends
	
	// Convert seconds to time for example 3600 seconds to 1 hours 0 minutes code starts
	convertSecondsToTime(seconds) {
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);

		return `<b>${hours}</b><span style="font-size:12px"> hours </span><b>${minutes}</b><span style="font-size:12px"> minutes</span>`;
	}
	// Convert seconds to time for example 3600 seconds to 1 hours 0 minutes code ends

	// Convert seconds to time for example 3600 seconds to 01:00 code starts
	convertSecondsToTime_(seconds) {
		const hours = Math.floor(seconds / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		const formattedMinutes = minutes < 10 ? `0${minutes}` : minutes;
		const formattedHours = hours < 10 ? `0${hours}` : hours;
		return `${formattedHours}:${formattedMinutes}`;
	}
	// Convert seconds to time for example 3600 seconds to 01:00 code ends
	
}
frappe.provide("frappe.ui");
frappe.ui.UserProfile = UserProfile;