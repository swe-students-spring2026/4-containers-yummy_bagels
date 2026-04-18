const form = document.getElementById("image-upload-form");

if (form) {
  const loadingOverlay = document.getElementById("loading-overlay");
  const buttons = document.querySelectorAll("[data-source]");
  const fileSourceButton = document.querySelector('[data-source="file"]');
  const filePanel = document.getElementById("file-upload-panel");
  const cameraPanel = document.getElementById("camera-upload-panel");
  const imageInput = document.getElementById("image");
  const selectedFileName = document.getElementById("selected-file-name");
  const cameraDataInput = document.getElementById("camera-image-data");
  const video = document.getElementById("camera-stream");
  const preview = document.getElementById("camera-preview");
  const canvas = document.getElementById("camera-canvas");
  const startButton = document.getElementById("start-camera-button");
  const captureButton = document.getElementById("capture-photo-button");
  const retakeButton = document.getElementById("retake-photo-button");
  const cameraStatus = document.getElementById("camera-status");

  let activeSource = "file";
  let mediaStream = null;
  let isSubmitting = false;

  const defaultFileButtonLabel = fileSourceButton
    ? fileSourceButton.textContent.trim()
    : "Upload from files";

  function showLoading(message = "finding match...") {
    if (!loadingOverlay) return;
    const text = loadingOverlay.querySelector(".loading-text");
    if (text) text.textContent = message;
    loadingOverlay.hidden = false;
    document.body.style.cursor = "wait";
  }

  function setSelectedFileName(text) {
    if (selectedFileName) selectedFileName.textContent = text;
  }

  function updateFileUi() {
    const hasFile = imageInput.files && imageInput.files.length > 0;
    const fileName = hasFile ? imageInput.files[0].name : null;

    setSelectedFileName(hasFile ? `Selected: ${fileName}` : "No file chosen.");

    if (fileSourceButton) {
      fileSourceButton.textContent = hasFile
        ? `Change file (${fileName})`
        : defaultFileButtonLabel;
    }
  }

  function stopCamera() {
    if (!mediaStream) return;
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
    video.srcObject = null;
    video.hidden = true;
    captureButton.disabled = true;
  }

  function clearCameraCapture() {
    cameraDataInput.value = "";
    preview.removeAttribute("src");
    preview.hidden = true;
    retakeButton.hidden = true;
  }

  function setSource(source) {
    activeSource = source;
    buttons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.source === source);
    });

    filePanel.hidden = source !== "file";
    cameraPanel.hidden = source !== "camera";
    cameraStatus.textContent = "";

    if (source === "file") {
      stopCamera();
      clearCameraCapture();
    } else {
      imageInput.value = "";
      updateFileUi();
    }
  }

  async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      cameraStatus.textContent = "Cannot access camera";
      return;
    }

    try {
      stopCamera();
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      video.srcObject = mediaStream;
      video.hidden = false;
      preview.hidden = true;
      captureButton.disabled = false;
      retakeButton.hidden = true;
      cameraStatus.textContent = "Camera ready.";
    } catch {
      cameraStatus.textContent = "Camera access was blocked or unavailable.";
    }
  }

  function capturePhoto() {
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    const scale = Math.min(1, 1280 / width);

    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);

    const context = canvas.getContext("2d");
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    cameraDataInput.value = dataUrl;
    preview.src = dataUrl;
    preview.hidden = false;
    video.hidden = true;
    retakeButton.hidden = false;
    cameraStatus.textContent = "Photo captured. Submit when ready.";
    stopCamera();
  }

  buttons.forEach((button) => {
    if (button.dataset.source === "file") {
      button.addEventListener("click", () => {
        const wasActive = activeSource === "file";
        setSource("file");
        updateFileUi();
        if (!wasActive || imageInput.files.length === 0) {
          imageInput.click();
        }
      });
      return;
    }

    button.addEventListener("click", () => setSource(button.dataset.source));
  });

  startButton.addEventListener("click", startCamera);
  captureButton.addEventListener("click", capturePhoto);
  retakeButton.addEventListener("click", () => {
    clearCameraCapture();
    startCamera();
  });

  imageInput.addEventListener("change", () => {
    if (imageInput.files.length > 0) {
      clearCameraCapture();
      cameraStatus.textContent = "";
    }
    setSource("file");
    updateFileUi();
  });

  form.addEventListener("submit", (event) => {
    if (isSubmitting) return;

    const hasFile = imageInput.files.length > 0;
    const hasCameraCapture = cameraDataInput.value.length > 0;

    if (!hasFile && !hasCameraCapture) {
      event.preventDefault();
      cameraStatus.textContent =
        activeSource === "camera"
          ? "Take a photo before submitting."
          : "Choose an image file before submitting.";
      return;
    }

    event.preventDefault();
    isSubmitting = true;
    showLoading("finding match...");

    window.setTimeout(() => {
      form.requestSubmit();
    }, 60);
  });

  window.addEventListener("beforeunload", stopCamera);
  setSource("file");
  updateFileUi();
}
