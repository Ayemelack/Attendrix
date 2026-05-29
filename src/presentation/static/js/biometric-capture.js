(function () {
    'use strict';

    var FaceCapture = {
        initialized: false,
        modelsLoaded: false,
        stream: null,
        videoEl: null,
        modelUrl: 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/',

        async init(videoElementId) {
            if (this.initialized) return;
            this.videoEl = document.getElementById(videoElementId);
            if (!this.videoEl) throw new Error('Video element not found: ' + videoElementId);
            this.initialized = true;
        },

        async loadModels() {
            if (this.modelsLoaded) return;
            if (typeof faceapi === 'undefined') {
                throw new Error('face-api.js not loaded. Include <script src=\"https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.js\"></script>');
            }
            await faceapi.nets.ssdMobilenetv1.loadFromUri(this.modelUrl);
            await faceapi.nets.faceRecognitionNet.loadFromUri(this.modelUrl);
            await faceapi.nets.faceLandmark68Net.loadFromUri(this.modelUrl);
            this.modelsLoaded = true;
        },

        async startCamera() {
            if (this.stream) this.stopCamera();
            if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
                throw new Error('Camera API not available on this device');
            }
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: 640, height: 480 }
            });
            this.videoEl.srcObject = this.stream;
            await this.videoEl.play();
        },

        stopCamera() {
            if (this.stream) {
                this.stream.getTracks().forEach(function (t) { t.stop(); });
                this.stream = null;
            }
            if (this.videoEl) this.videoEl.srcObject = null;
        },

        async captureDescriptor() {
            if (!this.modelsLoaded) await this.loadModels();
            if (!this.stream) await this.startCamera();

            var result = await faceapi
                .detectSingleFace(this.videoEl, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.5 }))
                .withFaceLandmarks()
                .withFaceDescriptor();

            if (!result) return null;

            return Array.from(result.descriptor);
        },

        async captureMultipleSamples(count) {
            count = count || 3;
            var descriptors = [];
            for (var i = 0; i < count; i++) {
                var desc = await this.captureDescriptor();
                if (desc) descriptors.push(desc);
                if (i < count - 1) await new Promise(function (r) { return setTimeout(r, 500); });
            }
            if (descriptors.length === 0) return null;
            return this.averageDescriptors(descriptors);
        },

        averageDescriptors(descriptors) {
            if (!descriptors.length) return null;
            var avg = new Array(128).fill(0);
            descriptors.forEach(function (d) {
                d.forEach(function (v, i) { avg[i] += v; });
            });
            return avg.map(function (v) { return v / descriptors.length; });
        },

        async checkCameraAvailability() {
            try {
                if (!navigator.mediaDevices || typeof navigator.mediaDevices.enumerateDevices !== 'function') {
                    return false;
                }
                var devices = await navigator.mediaDevices.enumerateDevices();
                return devices.some(function (d) { return d.kind === 'videoinput'; });
            } catch (e) {
                return false;
            }
        }
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = FaceCapture;
    } else {
        window.FaceCapture = FaceCapture;
    }
})();
