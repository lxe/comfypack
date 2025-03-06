class WorkflowAnalyzer {
  constructor() {
    this.elements = {
      dropZone: document.getElementById('dropZone'),
      fileInput: document.getElementById('fileInput'),
      copyButton: document.getElementById('copyButton'),
      saveButton: document.getElementById('saveButton'),
      progressContainer: document.getElementById('progressContainer'),
      progressBar: document.getElementById('progressBar'),
      status: document.getElementById('status'),
      resultDisplay: document.getElementById('resultDisplay'),
      resultContainer: document.getElementById('resultContainer')
    };

    this.initializeEventListeners();
  }

  initializeEventListeners() {
    // Drag and drop handlers
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      this.elements.dropZone.addEventListener(eventName, this.preventDefaults);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      this.elements.dropZone.addEventListener(eventName, () => this.highlight(true));
    });

    ['dragleave', 'drop'].forEach(eventName => {
      this.elements.dropZone.addEventListener(eventName, () => this.highlight(false));
    });

    // File handling
    this.elements.dropZone.addEventListener('drop', (e) => this.handleDrop(e));
    this.elements.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
    this.elements.dropZone.addEventListener('click', () => this.elements.fileInput.click());

    // Button handlers
    this.elements.copyButton.addEventListener('click', () => this.copyToClipboard());
    this.elements.saveButton.addEventListener('click', () => this.saveToFile());
  }

  preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  highlight(shouldHighlight) {
    this.elements.dropZone.classList.toggle('border-blue-500', shouldHighlight);
  }

  handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length) {
      this.handleFiles(files[0]);
    }
  }

  handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
      this.handleFiles(file);
    }
  }

  async handleFiles(file) {
    this.resetUI();
    this.elements.progressContainer.style.display = 'block';

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      await this.processStreamResponse(response);
    } catch (error) {
      console.error('Error:', error);
      this.showError(`Error: ${error.message}`);
    }
  }

  async processStreamResponse(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const messages = buffer.split('\n');
      buffer = messages.pop() || '';

      for (const message of messages) {
        if (!message.trim()) continue;

        if (message.startsWith('data: ')) {
          try {
            const data = JSON.parse(message.slice(6));
            this.updateUI(data);
          } catch (error) {
            console.error('Error parsing SSE data:', error);
          }
        }
      }
    }
  }

  updateUI(data) {
    this.elements.status.textContent = data.message;

    if (data.progress) {
      this.elements.progressBar.style.width = `${data.progress}%`;
    }

    if (data.status === 'complete') {
      this.elements.resultContainer.style.display = 'block';
      this.elements.resultDisplay.textContent = JSON.stringify(data.data, null, 2);
      this.elements.progressBar.style.width = '100%';
    } else if (data.status === 'error') {
      this.showError(`Error: ${data.message}`);
    }
  }

  resetUI() {
    this.elements.resultDisplay.textContent = '';
    this.elements.progressBar.style.width = '0%';
    this.elements.status.textContent = '';
    this.elements.resultContainer.style.display = 'none';
  }

  showError(message) {
    this.elements.status.textContent = message;
    this.elements.resultDisplay.textContent = message;
    this.elements.resultContainer.style.display = 'block';
  }

  async copyToClipboard() {
    const textToCopy = this.elements.resultDisplay.textContent;
    
    try {
      // Try using the Clipboard API first
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(textToCopy);
      } else {
        // Fallback for non-HTTPS or unsupported browsers
        const textArea = document.createElement('textarea');
        textArea.value = textToCopy;
        
        // Make the textarea invisible
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
          document.execCommand('copy');
        } catch (err) {
          console.error('Fallback: Oops, unable to copy', err);
          throw err;
        } finally {
          document.body.removeChild(textArea);
        }
      }
      
      // Update button text to show success
      this.elements.copyButton.textContent = 'Copied!';
      setTimeout(() => {
        this.elements.copyButton.textContent = 'Copy JSON';
      }, 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
      this.elements.copyButton.textContent = 'Copy failed';
      setTimeout(() => {
        this.elements.copyButton.textContent = 'Copy JSON';
      }, 2000);
    }
  }

  saveToFile() {
    const blob = new Blob([this.elements.resultDisplay.textContent], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'workflow-analysis.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
  new WorkflowAnalyzer();
}); 