// ======================================================================
// 🔹 Global helpers (simple global functions)
// ======================================================================

const GSM7_BASIC = /^[\n\r\u0020-\u007E€£¥èéùìòÇØøÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ!"#\$%&'\(\)\*\+,\-\.\/0-9:;<=>\?@A-Z\[\\\]\^_a-z\{\|\}~]*$/;

function detectEncoding(text) {
	return GSM7_BASIC.test(text) ? 'GSM7' : 'UNICODE';
}

function getSmsLimits(encoding, length) {
	if (encoding === 'GSM7') {
		return length <= 160
			? { perSms: 160 }
			: { perSms: 153 };
	}
	return length <= 70
		? { perSms: 70 }
		: { perSms: 67 };
}

// ======================================================================
// 🔹 Vue app
// ======================================================================

const { createVuetify } = Vuetify;

const vuetify = createVuetify ( {
	rtl: { fa: true } ,
} ) ;

const app = Vue.createApp ( {

	el: '#app' ,

	data() {
		return {
			appVersion: "",
			availableCountries: [],
			
			projects: [],
			selectedProject: null,

			newProjectName: "",

			editName: "",
			editProject: null,

			delProjDialog: false,
			projToDelete: null,

			activeCountry: null,

			csvFiles: [],
			selectedCsv: null,

			editCsv: null,
			editCsvName: "",

			delCSVDialog: false,
			csvToDelete: null,

			csvDirty: false,

			toast: "",
			toastVisible: false,
			toastTimeout: 5000,

			showCSV: false,
			
			csvHeaders: [],
			csvRows: [],
			csvLoaded: false,

			txtFiles: [],
			selectedTxt: null,

			editTxt: null,
			editTxtName: "",

			delTXTDialog: false,
			txtToDelete: null,

			editorIsRTL: false,
			txtDirty: false,

			message: '',
			txtOrginal: '',

			msgCharCount: 0,
			msgSmsCount: 0,
			msgRemainingChars: 0,
			
			showOnlyAllowed: false,
			previewMode: false,
			previewIndex: 0,
			previewText: '',
			
			previewCharCount: 0,
			previewSmsCount: 0,
			previewRemainingChars: 0,

			devices: [],
			selectedDeviceName: '',
			loadingDevices: false,

			kdeconnect_activation: false,
			dryrunMode: true,
			delay_seconds: 10,

			delay_options: [10,15,20,30,60],

			// send process state
			sendJobId: null,
			pollingTimer: null,
			sending: false,
			sendStats: {
				total: 0,
				pending: 0,
				sent: 0,
				failed: 0,
				skipped: 0,
			},
			sendResults: [],

			sendCompletedDialog: false,
			sendCompletedMessage: "",

		}
	} ,

	computed: {

		charCount() {

			if (this.previewMode) {
				
				this.countPreviewChars();
				return this.previewCharCount;
			
			} else {
				
				this.countMessageChars();
				return this.msgCharCount;

			}
			
		},

		smsCount() {

			if (this.previewMode)
				return this.previewSmsCount;
			else
				return this.msgSmsCount;
			
		},

		remainingChars() {

			if (this.previewMode)
				return this.previewRemainingChars;
			else
				return this.msgRemainingChars;

		},

		deviceName_selected() {
			const d = this.devices.find(x => x.name === this.selectedDeviceName);
			return d ? d.name : '';
		},

		sendProgressPercent() {
			if (!this.sendStats.total) return 0;
			const done = this.sendStats.sent + this.sendStats.failed + this.sendStats.skipped;
			return Math.min(100, Math.round((done / this.sendStats.total) * 100));
		},

		csvButtonDisabled() {
			return !this.selectedCsv || this.csvFiles.length === 0;
		},

		csvFields() {
			return this.csvHeaders?.map(h => h.trim()) || [];
		},

		previewRows() {
			if (this.showOnlyAllowed) {
				return this.csvRows.filter(row => row.send === "1");
			}
			return this.csvRows;
		},
	
	} ,

	methods: {

		// ======================================================================
		// Helpers
		// ======================================================================

		snackbarBuilder (msg, time = 5) {
			this.toast = msg;
			this.toastTimeout = time * 1000;
			this.toastVisible = true;
		},


		// ======================================================================
		// Methodes for projects manipulation
		// ======================================================================

		async loadProjects() {
			const res = await fetch("/api/projects")
			const data = await res.json()

			if (data.ok) {
				this.projects = data.projects
			}
		},

		async setProject(name) {

			this.selectedProject = name;

			await fetch("/api/config", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ project_name: name })
			})

			this.txtDirty = false;
			this.csvDirty = false;
			
			await this.loadConfigs();

			await this.loadTxtFiles();
			await this.loadCsvFiles();

		},

		async setCountry(){

			await fetch("/api/project-settings",{
				method:"POST",
				headers:{'Content-Type':'application/json'},
				body:JSON.stringify({
					project_name: this.selectedProject,
					country: this.activeCountry
				})
			})

		},

		async createProject() {
			if (!this.newProjectName.trim()) return

			const res = await fetch("/api/projects", {
				method: "POST",
				headers: {
					"Content-Type": "application/json"
				},
				body: JSON.stringify({
					name: this.newProjectName
				})
			})

			const data = await res.json()


			if (!data.ok) {
				alert("Project already exists")
				return
			}

			this.newProjectName = ""
			this.loadProjects()

		},

		// Open the confirmation dialog
		openDelProjDialog(name) {
			this.projToDelete = name;
			this.delProjDialog = true;
		},

		// Execute project deletion
		async deleteProject() {

			const name = this.projToDelete;
			if (!name) return;

			const res = await fetch("/api/projects/" + name, {
				method: "DELETE"
			})

			const data = await res.json()

			if (data.ok) {
				if (this.selectedProject === name) {
					// this.selectedProject = null;
					this.setProject(null);
				}
				this.loadProjects()
			} else {
				msg = `❌ CSV or TEMPLATES folders are not empty.<br/>Deletion of "${name}" project was canceled.`;
				this.snackbarBuilder(msg, 10);
			}

			// Close the dialog and clear the selected project
			this.delProjDialog = false;
			this.projToDelete = null;
		},

		startRename(name) {
			this.editProject = name
			this.editName = name
		},

		cancelRename() {
			this.editProject = null
			this.editName = ""
		},

		async finishRename() {
			if (!this.editName.trim()) return

			const res = await fetch("/api/projects/rename", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ 
					old: this.editProject, 
					new: this.editName 
				})
			})

			const data = await res.json()

			if (data.ok) {
				if (this.selectedProject === this.editProject) {
					this.setProject(this.editName);
				}
				this.editProject = null
				this.editName = ""
				this.loadProjects()
			}
		},

		async loadPhoneRules() {
			try {
				const res = await fetch('/api/phone-rules');
				const data = await res.json();
				if (data.ok) {
					this.availableCountries = data.countries;
				}
			} catch (err) {
				console.error("Error loading phone rules:", err);
			}
		},

		async updateProjectCountry(projectName, country) {
			try {
				const res = await fetch(`/api/projects/${projectName}/country`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ country: country })
				});
				const data = await res.json();
				if (data.ok) {
					// Update the value in the table without needing a refresh
					const p = this.projects.find(x => x.name === projectName);
					if (p) p.country = country;

					this.activeCountry = country

				} else {
					alert('Error updating country: ' + data.error);
				}
			} catch (err) {
				console.error("Error updating project country:", err);
			}
		},

		// ======================================================================
		// Methodes | TXT files manipulation
		// ======================================================================

		async loadTxtFiles(){

			if(!this.selectedProject) return

			const r = await fetch(`/api/projects/${this.selectedProject}/templates`)
			const data = await r.json()

			this.txtFiles = data.files

			if(this.txtFiles.length > 0){
				if(!this.selectedTxt || !this.txtFiles.includes(this.selectedTxt)){
					await this.setTxt(this.txtFiles[0]);
				}
			}

		},

		async setTxt(file){

			this.selectedTxt = file;

			await fetch("/api/project-settings",{
				method:"POST",
				headers:{'Content-Type':'application/json'},
				body:JSON.stringify({
					project_name: this.selectedProject,
					template_file: file
				})
			})

			this.txtDirty = false;

		},

		async setEditorRTL(){

			await fetch("/api/project-settings",{
				method:"POST",
				headers:{'Content-Type':'application/json'},
				body:JSON.stringify({
					project_name: this.selectedProject,
					editorRTL: this.editorIsRTL
				})
			})

		},

		async uploadTXT(e){

			const file = e.target.files[0]
			if(!file) return

			const fd = new FormData()
			fd.append("file", file)

			await fetch(`/api/projects/${this.selectedProject}/templates/upload`,{
				method:"POST",
				body:fd
			})

			this.loadTxtFiles()

		},

		// Open the confirmation dialog
		openDelTXTDialog(name) {
			this.txtToDelete = name;
			this.delTXTDialog = true;
		},

		async deleteTXT(){

			const name = this.txtToDelete;
			if (!name) return;

			await fetch(`/api/projects/${this.selectedProject}/templates/${name}`,{
				method:"DELETE"
			})

			// Close the dialog and clear the selected template file
			this.delTXTDialog = false;
			this.txtToDelete = null;

			this.loadTxtFiles()

		},

		async duplicateTXT(name){
			// Generate a default name for the new file
			let defaultName = name;
			if (name.endsWith('.txt')) {
				defaultName = name.slice(0, -4) + '_copy.txt';
			} else {
				defaultName += '_copy';
			}

			// Prompt the user for a new name
			const newName = prompt("Enter name for duplicated file:", defaultName);
			
			// If the user cancels or the new name is empty/duplicate, do nothing
			if(!newName || newName === name) return;

			try {
				const r = await fetch(`/api/projects/${this.selectedProject}/templates/duplicate`, {
					method: "POST",
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						original: name,
						new_name: newName
					})
				});
				const data = await r.json();
				
				if(data.ok) {
					await this.loadTxtFiles(); // Update the table
				} else {
					alert("Error: " + data.error);
				}
			} catch (error) {
				console.error("Duplicate failed:", error);
			}
		},
		
		startRenameTXT(name){

			this.editTxt = name
			this.editTxtName = name

		},

		cancelRenameTxt(){

			this.editTxt = null

		},

		async finishRenameTxt(){

			await fetch(`/api/projects/${this.selectedProject}/templates/rename`,{
				method:"POST",
				headers:{'Content-Type':'application/json'},
				body:JSON.stringify({
					old:this.editTxt,
					new:this.editTxtName
				})
			})

			if (this.selectedTxt == this.editTxt){
				await this.setTxt(this.editTxtName);
			}

			this.editTxt = null;
			this.loadConfigs();
			this.loadTxtFiles();


		},

		async loadTemplateContent() {

			if (!this.selectedProject || !this.selectedTxt) return;
			const res = await fetch(`/api/projects/${this.selectedProject}/templates/${this.selectedTxt}`);
			const data = await res.json();

			this.txtDirty = false;

			this.message = data.text;
			this.txtOrginal = this.message;

		},

		async saveTemplateContent() {

			if (!this.selectedProject || !this.selectedTxt) return;

			const text = this.message;

			await fetch(`/api/projects/${this.selectedProject}/templates/${this.selectedTxt}`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json"
				},
				body: JSON.stringify({ text })
			});

		},

		async toggleEditorDirection() {
			this.editorIsRTL = !this.editorIsRTL;
			await this.setEditorRTL();

		},

		markTXTDirty(){
			if (this.message !== this.txtOrginal) {
				this.txtDirty = true;
			}
		},

		async btnSaveTXT(){

			try {
				await this.saveTemplateContent();
				this.txtDirty = false;

				if (!this.sending) {
					msg = `✅ Changes saved successfully | Template (txt) file: ${this.selectedTxt}`;
					this.snackbarBuilder(msg, 5);
				}

			} catch(err) {
				msg = `❌ Save failed | Template (txt) file: ${this.selectedTxt}`;
				this.snackbarBuilder(msg, 5);
				console.error(err)
			}

		},

		async btnCancelTXT(){

			this.txtDirty = false;
			await this.loadTemplateContent();

		},

		insertField(fieldName) {
			// Find the actual textarea
			const textarea = this.$refs.editor?.$el?.querySelector("textarea");
			if (!textarea) return;

			const start = textarea.selectionStart;
			const end = textarea.selectionEnd;

			// Current text
			const before = this.message.slice(0, start);
			const after = this.message.slice(end);

			// Insert the field
			const inserted = `{${fieldName}}`;
			this.message = before + inserted + after;

			// Return focus to the textarea
			textarea.focus();

			// Cursor position after insertion
			const newPos = start + inserted.length;

			// Update the cursor (requires nextTick or setTimeout)
			setTimeout(() => {
				textarea.selectionStart = textarea.selectionEnd = newPos;
			}, 0);

			this.markTXTDirty();
		},

		buildPreviewText() {
			if (!this.message) return;

			// CSV empty check: simple linebreaks only
			if (!this.previewRows.length) {
				this.previewText = this.message.replace(/\n/g, '<br>');
				this.countPreviewChars();
				return;
			}

			const row = this.previewRows[this.previewIndex];
			if (!row) {
				this.previewText = this.message.replace(/\n/g, '<br>');
				this.countPreviewChars();
				return;
			}
			
			let txt = this.message;

			const csvKeys = Object.keys(row);

			// Replace fields in the CSV
			for (const key of csvKeys) {
				const val = row[key] ?? '';
				const re = new RegExp(`\\{${key}\\}`, 'g');
				if (val.length > 0){
					txt = txt.replace(re, `<mark class="selected-field">${val}</mark>`);
				} else {
					txt = txt.replace(re, ``);
				}
			}

			// Highlight missing fields
			const missingRegex = /\{([^}]+)\}/g;
			txt = txt.replace(missingRegex, (match, fieldName) => {
				if (!csvKeys.includes(fieldName)) {
					return `<mark class="missing-field">${match}</mark>`;
				}
				return match;
			});

			// Convert newline to <br>
			this.previewText = txt.replace(/\n/g, '<br>');
			
			// Count characters in preview without HTML tags
			this.countPreviewChars();
		},

		countMessageChars() {
			const txt = this.message
				.replace(/\r\n/g, '\n')
				.replace(/\r/g, '');

			const encoding = detectEncoding(txt);
			const length = txt.length;
			const limits = getSmsLimits(encoding, length);

			this.msgCharCount = length;
			this.msgSmsCount = Math.max(1, Math.ceil(length / limits.perSms));

			const mod = length % limits.perSms;
			this.msgRemainingChars = mod === 0 ? limits.perSms : limits.perSms - mod;
		},

		countPreviewChars() {
			const plainText = this.previewText
				.replace('<br>', '\n')
				.replace(/<[^>]+>/g, '')	// remove HTML tags
				.replace(/&nbsp;/g, ' ')	// replace non-breaking spaces
				.replace(/\r\n/g, '\n')
				.replace(/\r/g, '')			// normalize newlines (SMS counts LF as 1 char)
				.trimEnd();

			const encoding = detectEncoding(plainText);
			const length = plainText.length;
			const limits = getSmsLimits(encoding, length);

			this.previewCharCount = length;
			this.previewSmsCount = Math.max(1, Math.ceil(length / limits.perSms));

			const mod = length % limits.perSms;
			this.previewRemainingChars = mod === 0 ? limits.perSms : limits.perSms - mod;
		},

		togglePreview() {
			this.previewMode = !this.previewMode;

			if (this.previewMode) {
				this.previewIndex = 0;
				this.buildPreviewText();
			}
		},

		prevPreview() {
			if (!this.previewMode) return;
			if (this.previewIndex > 0) {
				this.previewIndex--;
				this.buildPreviewText();
			}
		},

		nextPreview() {
			if (!this.previewMode) return;
			if (this.previewIndex < this.previewRows.length - 1) {
				this.previewIndex++;
				this.buildPreviewText();
			}
		},

		// ======================================================================
		// Methodes for CSV files manipulation
		// ======================================================================

		async loadCsvFiles(){

			if(!this.selectedProject) return

			const r = await fetch(`/api/projects/${this.selectedProject}/csv`)
			const data = await r.json()

			this.csvFiles = data.files

			// If selectedCsv is not set or doesn't exist → select the first file
			if(this.csvFiles.length > 0){
				if(!this.selectedCsv || !this.csvFiles.includes(this.selectedCsv)){
					await this.setCsv(this.csvFiles[0]);
				}
			} else {
				this.delCSVTable()
			}

		},

		async setCsv(file){

			this.selectedCsv = file;

			await fetch("/api/project-settings",{
				method:"POST",
				headers:{'Content-Type':'application/json'},
				body:JSON.stringify({
					project_name: this.selectedProject,
					csv_file: file
				})
			})

			this.csvDirty = false;

		},

		async uploadCsv(e){

			const file = e.target.files[0]
			if(!file) return

			const fd = new FormData()
			fd.append("file", file)

			await fetch(`/api/projects/${this.selectedProject}/csv/upload`,{
				method:"POST",
				body:fd
			})

			this.loadCsvFiles()

		},

		// Open the confirmation dialog
		openDelCSVDialog(name) {
			this.csvToDelete = name;
			this.delCSVDialog = true;
		},

		async deleteCsv(){

			const name = this.csvToDelete;
			if (!name) return;

			await fetch(`/api/projects/${this.selectedProject}/csv/${name}`,{
				method:"DELETE"
			})

			// Close the dialog and clear the selected csv file
			this.delCSVDialog = false;
			this.csvToDelete = null;

			this.loadCsvFiles()

		},

		async duplicateCSV(name){
			// Generate a default name for the new file
			let defaultName = name;
			if (name.endsWith('.csv')) {
				defaultName = name.slice(0, -4) + '_copy.csv';
			} else {
				defaultName += '_copy';
			}

			// Prompt the user for a new name
			const newName = prompt("Enter name for duplicated file:", defaultName);
			
			// If the user cancels or the new name is empty/duplicate, do nothing
			if(!newName || newName === name) return;

			try {

				const r = await fetch(`/api/projects/${this.selectedProject}/csv/duplicate`, {
					method: "POST",
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						original: name,
						new_name: newName
					})
				});
				const data = await r.json();
				
				if(data.ok) {
					await this.loadCsvFiles(); // Update the table
				} else {
					alert("Error: " + data.error);
				}

			} catch (error) {
				console.error("Duplicate failed:", error);
			}
		},

		startRenameCsv(name){

			this.editCsv = name
			this.editCsvName = name

		},

		cancelRenameCsv(){

			this.editCsv = null

		},

		async finishRenameCsv(){

			await fetch(`/api/projects/${this.selectedProject}/csv/rename`,{
				method:"POST",
				headers:{'Content-Type':'application/json'},
				body:JSON.stringify({
					old:this.editCsv,
					new:this.editCsvName
				})
			})

			if (this.selectedCsv == this.editCsv){
				await this.setCsv(this.editCsvName);
			}

			this.editCsv = null
			this.loadCsvFiles()

		},

		async loadCSV() {
			if (!this.selectedProject || !this.selectedCsv) return;
			const res = await fetch(`/api/projects/${this.selectedProject}/csv/${this.selectedCsv}`);
			const data = await res.json();
			
			if (!data.ok) {
				alert(data.error);
				return;
			}

			this.csvHeaders = data.headers || [];
			this.csvRows = data.rows || [];
			this.csvLoaded = true;
			// this.showCSV = true;

			this.$nextTick(() => {
				this.renderCSV();
			});
		},

		renderCSV() {
			const container = document.getElementById("csvBox");
			if (!container) return;
			
			// Step 1: Build the HTML (without @input and @blur)
			let html = `
				<div class="csv-table-wrap">
					<table class="csv-table">
						<thead>
							<tr>
			`;

			// Columns of CSV
			for (const h of this.csvHeaders) {
				html += `<th>${h}</th>`;
			}

			// Add action column
			html += `<th style="width:80px;">Action</th>`;

			html += `
							</tr>
						</thead>
						<tbody>
			`;

			// Render of records
			this.csvRows.forEach((row, rIdx) => {
				html += '<tr>';

				this.csvHeaders.forEach(h => {
					const val = row[h] || '';
					const dir = (h === 'mob') ? 'dir="ltr"' : '';

					html += `
						<td contenteditable="true" ${dir}
							data-row="${rIdx}"
							data-col="${h}">
							${val}
						</td>`;
				});

				// Del btn
				html += `
					<td>
						<button
							class="delete-row-btn"
							data-del-row="${rIdx}"
						>
							🗑️
						</button>
					</td>
				`;
				// <i class="mdi mdi-delete" style="font-size: 20px; pointer-events: none;"></i>
				html += '</tr>';
			});

			// Add new record
			html += `
				<tr>
					<td colspan="${this.csvHeaders.length + 1}" style="text-align:center;">
						<button id="addRowBtn" class="add-row-btn">➕ Add Row</button>
					</td>
				</tr>
			`;

			html += `
						</tbody>
					</table>
				</div>
			`;

			// Step 2: Inject the HTML
			container.innerHTML = html;

			// Step 3: Add event listeners to all cells
			const cells = container.querySelectorAll("td[contenteditable='true']");

			cells.forEach(cell => {
				cell.addEventListener("input", this._onCellEdit.bind(this));
				cell.addEventListener("blur", this._onCellEdit.bind(this));
			});

			// Del btns
			const deleteBtns = container.querySelectorAll(".delete-row-btn");
			deleteBtns.forEach(btn => {
				btn.addEventListener("click", (e) => {
					const idx = parseInt(e.target.getAttribute("data-del-row"));

					if (confirm("Are you sure you want to delete this record?")) {
						this.csvRows.splice(idx, 1);
						this.csvDirty = true;
						this.renderCSV();
					}
				});
			});


			// Add record button
			const addBtn = document.getElementById("addRowBtn");
			if (addBtn) {
				addBtn.addEventListener("click", () => {
					const newRow = {};
					this.csvHeaders.forEach(h => newRow[h] = "");

					this.csvRows.push(newRow);
					this.csvDirty = true;
					this.renderCSV();
				});
			}

		},

		_onCellEdit(event){
			const cell = event.target;
			const rowIndex = parseInt(cell.dataset.row);
			const colName = cell.dataset.col;

			let raw = cell.innerText;

			raw = raw.replace(/"/g, '');			// Remove forbidden characters
			raw = raw.replace(/,/g, '');			// Remove forbidden characters
			raw = raw.replace(/\u00A0/g, ' ');		// normalize whitespace
			raw = raw.trim();

			if (cell.innerText !== raw)
				cell.innerText = raw;

			// Update the value in Vue state
			this.csvRows[rowIndex][colName] = cell.innerText;

			// Declare that the CSV has changed
			this.csvDirty = true;
		},

		delCSVTable() {
			this.showCSV = false;
			const box = document.getElementById("csvBox");
			if (box) box.innerHTML = "";
		},

		toggleCSV() {
			if (this.csvButtonDisabled) return;

			if (!this.showCSV) {
				this.showCSV = true;
				this.loadCSV();
			} else {
				this.showCSV = false;
			}
		},

		markCSVDirty(){
			this.csvDirty = true
		},

		async btnSaveCSV(){

			try {
				await this.saveCSV();
				this.csvDirty = false;
				if (!this.sending) {
					msg = `✅ Changes saved successfully | CSV file: ${this.selectedCsv}`;
					this.snackbarBuilder(msg, 5);
				}
			} catch(err) {
				msg = `❌ Save failed | CSV file: ${this.selectedCsv}`;
				this.snackbarBuilder(msg, 5);

				console.error(err)
			}

		},

		async btnCancelCSV(){

			this.csvDirty = false;
			await this.loadCSV();

		},

		async saveCSV() {

			if (!this.selectedProject || !this.selectedCsv) return;

			const res = await fetch(`/api/projects/${this.selectedProject}/csv/${this.selectedCsv}`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					headers: this.csvHeaders,
					rows: this.csvRows,
				}),
			});

			const data = await res.json();

		},

		async dryRun() {

			if (!this.selectedProject || !this.selectedCsv) return;

			const res = await fetch(`/api/projects/${this.selectedProject}/dry-run`)
			const data = await res.json();

			if (!data.ok) {
				alert("Some errors :(");
				return;
			}
			
			const map = {};
			data.rows.forEach(r => {
				map[r.row] = r;
			});

			// Add dry-run statuse column to CSV table
			document.querySelectorAll("#csvBox table tr").forEach((tr, idx) => {
				if (idx === 0) {
					if (!tr.querySelector("th:last-child") || tr.querySelector("th:last-child")?.innerText !== "Status") {
						tr.insertAdjacentHTML("beforeend", "<th>Status</th>");
					}
					return;
				}

				const info = map[idx];
				if (!info) return;

				let color = "#ddd";
				if (info.status === "READY") color = "#c8e6c9";
				if (info.status === "SKIPPED") color = "#eeeeee";
				if (info.status === "NO_PHONE") color = "#ffcdd2";
				if (info.status === "INVALID") color = "#ffe0b2";

				const existingStatusCell = tr.querySelector("td.status-cell");
				if (existingStatusCell) {
					existingStatusCell.innerText = info.status;
					existingStatusCell.style.background = color;
				} else {
					tr.insertAdjacentHTML(
						"beforeend",
						`<td class="status-cell" style="background:${color}">${info.status}</td>`
					);
				}
			});
		},

		onPanelChange(val) {
			if (val !== undefined) {
				this.showCSV = false;
			}
		},


		// ======================================================================
		// Methodes | Configs files manipulation (.json files)
		// ======================================================================

		async loadConfigs() {
			try {
				const res = await fetch("/api/config");
				const data = await res.json();

				if (data.ok) {

					this.selectedProject = data.project.general_config.project_name
					this.selectedCsv = data.project.project_config.csv_file
					this.selectedTxt = data.project.project_config.template_file
					this.editorIsRTL = data.project.project_config.editorRTL
					this.activeCountry = data.project.project_config.country
					
					this.kdeconnect_activation =
						data.project?.general_config?.kdeconnect ?? false
					
					this.dryrunMode =
						data.project?.general_config?.dryrun ?? true
					
					this.delay_seconds =
						data.project?.general_config?.delay_seconds ?? 10

				}

			} catch (err) {
				console.error("❌ Error in loadConfigs:", err);
			}
		},

		async saveKDEConnect(){

			await fetch("/api/config",{
				method:"POST",
				headers:{ "Content-Type":"application/json" },
				body:JSON.stringify({
					project_name: this.selectedProject,
					kdeconnect: this.kdeconnect_activation
				})
			})

		},

		async saveDryRun(){

			await fetch("/api/config",{
				method:"POST",
				headers:{ "Content-Type":"application/json" },
				body:JSON.stringify({
					project_name: this.selectedProject,
					dryrun: this.dryrunMode
				})
			})

		},

		async saveDelay(newDelay){

			this.delay_seconds = newDelay

			await fetch("/api/config",{
				method:"POST",
				headers:{ "Content-Type":"application/json" },
				body:JSON.stringify({
					project_name:this.selectedProject,
					delay_seconds:this.delay_seconds
				})
			})

		},


		// ======================================================================
		// Methodes | Detect Devices
		// ======================================================================

		async loadDevices() {
			try {
				this.loadingDevices = true;
				this.selectedDeviceName = '';
				this.devices = []

				const res = await fetch('/api/kdeconnect/devices');
				const data = await res.json();
				
				if (!data.ok) {
					msg = data.error || `❌ Error fetching devices.`;
					this.snackbarBuilder(msg, 10);

					return;
				}


				this.devices = data.devices || [];

				if (this.devices.length === 1) {
					this.selectedDeviceName = this.devices[0].name;
				}
			} catch (e) {
				msg = `❌ Connection to server failed.`;
				this.snackbarBuilder(msg, 10);
			} finally {
				this.loadingDevices = false;
			}
		},


		// ======================================================================
		// Methodes | Srart sending SMS
		// ======================================================================

		statusColor(status) {
			switch ((status || '').toUpperCase()) {
				case 'SENT':
					return 'green';
				case 'FAILED':
					return 'red';
				case 'SKIPPED':
					return 'orange';
				case 'PENDING':
					return 'blue';
				case 'SENDING':
					return 'purple';
				default:
					return 'grey';
			}
		},


		async startSending(){

			if(!this.selectedProject || !this.selectedDeviceName){
				alert("Project or device not selected")
				return
			}

			try {

				this.sending = true;

				// First save the CSV
				await this.btnSaveCSV();
				await this.btnSaveTXT();

				// Then start sending
				const res = await fetch("/api/send/start",{
					method:"POST",
					headers:{
						"Content-Type":"application/json"
					},
					body:JSON.stringify({
						project_name:this.selectedProject,
						device_name:this.selectedDeviceName
					})
				})

				const data = await res.json()

				this.sendJobId = data.job_id

				// Starter state
				this.sendStats = {
					total:this.csvRows.length,
					sent:0,
					failed:0,
					skipped:0,
					pending:this.csvRows.length
				}

				this.sendResults = []

				this.startPollingSendStatus()

			} catch(err) {

				console.error(err)
				alert("Failed to start sending")

			}

		},


		startPollingSendStatus() {

			if (!this.sendJobId) return;

			this.stopPollingSendStatus();

			const poll = async () => {

				try {
				
					const res = await fetch(`/api/send/status/${this.sendJobId}`);
					const data = await res.json();
					
					if (!data.ok) {
						console.warn(data.error);
						return;
					}
					
					const job = data.job || {};
					
					// Updating final result
					this.sendStats.total = job.total || 0;
					this.sendStats.sent = job.sent || 0;
					this.sendStats.failed = job.failed || 0;
					this.sendStats.skipped = job.skipped || 0;

					this.sendStats.pending =
						this.sendStats.total -
						this.sendStats.sent -
						this.sendStats.failed -
						this.sendStats.skipped;

					if (Array.isArray(job.results)) {

						this.sendResults = job.results;

					}

					if (job.finished) {

						this.stopPollingSendStatus();
						this.sending = false;

						this.sendCompletedMessage = "✅ SMS sending complete";
						this.sendCompletedDialog = true;

					}

				} catch (e) {
					console.warn('poll error:', e);
				}
			};

			// First run
			poll();

			// Then for 2 seconds periods 
			this.pollingTimer = setInterval(poll, 2000);
		},


		stopPollingSendStatus() {
			if (this.pollingTimer) {
				clearInterval(this.pollingTimer);
				this.pollingTimer = null;
			}
		},

	} ,

	watch: {
		sendResults() {
			this.$nextTick(() => {
				const anchor = this.$refs.bottomAnchor;
				if (anchor) {
					anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
				}
			});
		},

		selectedTxt(newVal) {
			if (newVal) {
				this.loadTemplateContent();
			} else {
				this.message = "";
			}
		},

		selectedCsv(newVal) {
			if (newVal) {
				this.loadCSV();
			}
		},

		kdeconnect_activation(newVal) {
			if (newVal === true) {
				this.dryrunMode = false;
			}
		},

		message() {
			if (this.previewMode) {
				this.buildPreviewText();
			}
		},

		showOnlyAllowed() {
			if (this.previewMode) {
				this.previewIndex = 0;
				this.buildPreviewText();
			}
		},

	} ,

	async mounted() {
		await this.loadProjects();

		await this.loadConfigs();
		await this.loadTxtFiles();
		await this.loadCsvFiles();

		await this.loadPhoneRules();

		await axios.get('/api/version').then(response => {
			this.appVersion = response.data.version;
			document.title = "MergeSMS | " + this.appVersion; 
		});

		console.log("Veujs version:", document.querySelector('#app').__vue_app__.version);
		console.log("Vuetify version:", Vuetify.version);
	} ,

	beforeUnmount() {
		this.stopPollingSendStatus();
	} ,

} )

app.use(vuetify).mount('#app');
