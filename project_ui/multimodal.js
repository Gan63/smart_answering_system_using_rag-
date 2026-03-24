class MultimodalAssistant {
  constructor() {
    this.imageInput = document.getElementById('imageInput');
    this.uploadZone = document.getElementById('uploadZone');
    this.imagePreview = document.getElementById('imagePreview');
    this.previewImg = document.getElementById('previewImg');
    this.questionInput = document.getElementById('questionInput');
    this.analyzeBtn = document.getElementById('analyzeBtn');
    this.results = document.getElementById('results');
    this.status = document.getElementById('status');
    this.answerEl = document.getElementById('answer');
    this.descEl = document.getElementById('description');
    this.visionUsed = document.getElementById('visionUsed');
    this.imageInfo = document.getElementById('imageInfo');

    this.init();
  }

  init() {
    // Upload handling
    this.uploadZone.addEventListener('click', () => this.imageInput.click());
    this.imageInput.addEventListener('change', (e) => this.handleImageSelect(e));
    
    this.clearImageBtn = document.getElementById('clearImage');
    this.clearImageBtn.addEventListener('click', () => this.clearImage());

    // Analyze
    this.analyzeBtn.addEventListener('click', () => this.analyze());

    // Enter key
    this.questionInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && this.analyzeBtn.disabled === false) {
        e.preventDefault();
        this.analyze();
      }
    });

    // Real-time enable/disable
    this.questionInput.addEventListener('input', () => this.updateAnalyzeBtn());
  }

  handleImageSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Validate
    if (!file.type.startsWith('image/')) {
      this.showStatus('Please select a JPG or PNG image.', 'error');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      this.showStatus('Image too large (max 10MB).', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      this.previewImg.src = e.target.result;
      this.imagePreview.style.display = 'block';
      this.updateAnalyzeBtn();
    };
    reader.readAsDataURL(file);
  }

  clearImage() {
    this.imageInput.value = '';
    this.imagePreview.style.display = 'none';
    this.updateAnalyzeBtn();
  }

  updateAnalyzeBtn() {
    const hasImage = this.imagePreview.style.display !== 'none';
    const hasQuestion = this.questionInput.value.trim().length > 0;
    this.analyzeBtn.disabled = !(hasImage && hasQuestion);
  }

  async analyze() {
    const question = this.questionInput.value.trim();
    if (!question) return;

    this.analyzeBtn.disabled = true;
    this.analyzeBtn.textContent = 'Analyzing...';
    this.showStatus('🔮 Calling vision LLM...', 'loading');
    this.results.style.display = 'none';

    try {
      // Get image base64 (from preview src)
      const imgSrc = this.previewImg.src;
      const base64 = imgSrc.split(',')[1];  // Remove data:image/...;

      const response = await fetch('/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          image_b64: `data:image/jpeg;base64,${base64}`
        })
      });

      const data = await response.json();

      if (response.ok) {
        this.displayResults(data);
        this.showStatus('✅ Analysis complete!', 'success');
      } else {
        throw new Error(data.detail || 'Analysis failed');
      }
    } catch (error) {
      console.error('Analyze error:', error);
      this.showStatus(`Error: ${error.message}`, 'error');
    } finally {
      this.analyzeBtn.disabled = false;
      this.analyzeBtn.textContent = 'Analyze Image + Question';
    }
  }

  displayResults(data) {
    this.answerEl.textContent = data.answer || 'No answer generated.';
    this.descEl.textContent = data.image_description || 'No description available.';
    this.visionUsed.textContent = data.used_vision ? '🧠 Vision LLM used' : 'No vision model used';
    this.imageInfo.textContent = `Image: ${data.image_size?.[0]}x${data.image_size?.[1] || 'N/A'}`;
    this.results.style.display = 'block';
  }

  showStatus(message, type = '') {
    this.status.textContent = message;
    this.status.className = `status ${type}`;
    
    if (type === 'loading') {
      this.status.innerHTML = message.replace('🔮 ', '<span class="loading"></span> ');
    }
  }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  new MultimodalAssistant();
});

