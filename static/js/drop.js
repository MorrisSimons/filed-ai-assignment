class DocumentClassifier {
    constructor() {
        this.uploadArea = document.getElementById('uploadArea');
        this.fileInput = document.getElementById('fileInput');
        this.fileList = document.getElementById('fileList');
        this.filesContainer = document.getElementById('filesContainer');
        this.resultsArea = document.getElementById('resultsArea');
        this.resultsContainer = document.getElementById('resultsContainer');
        this.loading = document.getElementById('loading');
        this.errorArea = document.getElementById('errorArea');
        this.errorContainer = document.getElementById('errorContainer');
        
        this.files = [];
        this.results = [];
        this.errors = [];
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Drag and drop events
        this.uploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.uploadArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.uploadArea.addEventListener('drop', (e) => this.handleDrop(e));
        
        // Click to browse
        this.uploadArea.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
    }
    
    handleDragOver(e) {
        e.preventDefault();
        this.uploadArea.classList.add('dragover');
    }
    
    handleDragLeave(e) {
        e.preventDefault();
        this.uploadArea.classList.remove('dragover');
    }
    
    handleDrop(e) {
        e.preventDefault();
        this.uploadArea.classList.remove('dragover');
        
        const files = Array.from(e.dataTransfer.files);
        this.processFiles(files);
    }
    
    handleFileSelect(e) {
        const files = Array.from(e.target.files);
        this.processFiles(files);
    }
    
    processFiles(files) {
        const pdfFiles = files.filter(file => 
            file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
        );
        
        if (pdfFiles.length === 0) {
            this.showError('No valid PDF files selected');
            return;
        }
        
        // Add files to the list
        pdfFiles.forEach(file => {
            const fileObj = {
                id: Date.now() + Math.random(),
                file: file,
                name: file.name,
                size: this.formatFileSize(file.size),
                status: 'pending'
            };
            
            this.files.push(fileObj);
        });
        
        this.updateFileList();
        this.showFileList();
        this.uploadFiles();
    }
    
    async uploadFiles() {
        this.showLoading();
        
        for (const fileObj of this.files) {
            if (fileObj.status === 'pending') {
                await this.uploadFile(fileObj);
            }
        }
        
        this.hideLoading();
        this.showResults();
    }
    
    async uploadFile(fileObj) {
        try {
            fileObj.status = 'processing';
            this.updateFileStatus(fileObj.id, 'processing');
            
            const formData = new FormData();
            formData.append('file', fileObj.file);
            
            const response = await fetch('/classify', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                const result = await response.json();
                fileObj.status = 'success';
                fileObj.result = result;
                this.results.push(result);
                this.updateFileStatus(fileObj.id, 'success');
            } else {
                const errorData = await response.json();
                fileObj.status = 'error';
                fileObj.error = errorData.detail || 'Upload failed';
                this.errors.push({
                    filename: fileObj.name,
                    error: fileObj.error
                });
                this.updateFileStatus(fileObj.id, 'error');
            }
            
        } catch (error) {
            fileObj.status = 'error';
            fileObj.error = error.message || 'Network error';
            this.errors.push({
                filename: fileObj.name,
                error: fileObj.error
            });
            this.updateFileStatus(fileObj.id, 'error');
        }
    }
    
    updateFileStatus(fileId, status) {
        const fileElement = document.querySelector(`[data-file-id="${fileId}"]`);
        if (fileElement) {
            const statusElement = fileElement.querySelector('.file-status');
            if (statusElement) {
                statusElement.textContent = this.getStatusText(status);
                statusElement.className = `file-status status-${status}`;
            }
        }
    }
    
    getStatusText(status) {
        const statusMap = {
            'pending': 'Pending',
            'processing': 'Processing...',
            'success': 'Success',
            'error': 'Error'
        };
        return statusMap[status] || status;
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    updateFileList() {
        this.filesContainer.innerHTML = '';
        
        this.files.forEach(fileObj => {
            const fileElement = this.createFileElement(fileObj);
            this.filesContainer.appendChild(fileElement);
        });
    }
    
    createFileElement(fileObj) {
        const div = document.createElement('div');
        div.className = 'file-item';
        div.setAttribute('data-file-id', fileObj.id);
        
        div.innerHTML = `
            <div class="file-info">
                <div class="file-icon">📄</div>
                <div class="file-details">
                    <h4>${fileObj.name}</h4>
                    <p>${fileObj.size}</p>
                </div>
            </div>
            <div class="file-status status-${fileObj.status}">
                ${this.getStatusText(fileObj.status)}
            </div>
        `;
        
        return div;
    }
    
    showFileList() {
        this.fileList.style.display = 'block';
    }
    
    showResults() {
        if (this.results.length > 0) {
            this.resultsContainer.innerHTML = '';
            
            this.results.forEach(result => {
                const resultElement = this.createResultElement(result);
                this.resultsContainer.appendChild(resultElement);
            });
            
            this.resultsArea.style.display = 'block';
        }
        
        if (this.errors.length > 0) {
            this.errorContainer.innerHTML = '';
            
            this.errors.forEach(error => {
                const errorElement = this.createErrorElement(error);
                this.errorContainer.appendChild(errorElement);
            });
            
            this.errorArea.style.display = 'block';
        }
    }
    
    createResultElement(result) {
        const div = document.createElement('div');
        div.className = 'result-item';
        
        div.innerHTML = `
            <div class="result-header">
                <div class="result-filename">${result.filename}</div>
                <div class="result-type">${result.document_type || 'Unknown'}</div>
            </div>
            <div class="result-details">
                <div class="result-detail">
                    <h5>Document Type</h5>
                    <p>${result.document_type || 'Unknown'}</p>
                </div>
                <div class="result-detail">
                    <h5>Year</h5>
                    <p>${result.year || 'Not detected'}</p>
                </div>
                <div class="result-detail">
                    <h5>File Size</h5>
                    <p>${result.file_size_mb || 'Unknown'} MB</p>
                </div>
                <div class="result-detail">
                    <h5>Processing Time</h5>
                    <p>${new Date().toLocaleTimeString()}</p>
                </div>
            </div>
        `;
        
        return div;
    }
    
    createErrorElement(error) {
        const div = document.createElement('div');
        div.className = 'error-item';
        
        div.innerHTML = `
            <h5>${error.filename}</h5>
            <p>${error.error}</p>
        `;
        
        return div;
    }
    
    showLoading() {
        this.loading.style.display = 'block';
    }
    
    hideLoading() {
        this.loading.style.display = 'none';
    }
    
    showError(message) {
        this.errors.push({
            filename: 'General Error',
            error: message
        });
        this.showResults();
    }
    
    reset() {
        this.files = [];
        this.results = [];
        this.errors = [];
        this.fileList.style.display = 'none';
        this.resultsArea.style.display = 'none';
        this.errorArea.style.display = 'none';
        this.filesContainer.innerHTML = '';
        this.resultsContainer.innerHTML = '';
        this.errorContainer.innerHTML = '';
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new DocumentClassifier();
});
