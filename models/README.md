# Models Directory

This directory contains the face **detection** model (YuNet) and the face
**recognition** model (ArcFace).

## Model Files

- `face_detection_yunet_2023mar.onnx` (~230 KB) - YuNet CNN face detector.
  Auto-downloaded on first use. Used in preference to OpenCV's legacy Haar
  Cascade because it is far more robust across ethnicities and head poses
  while still being light enough to run on a Raspberry Pi. (Haar Cascade
  remains as an automatic fallback if YuNet cannot be loaded.)
- `w600k_r50.onnx` (~166 MB) - ArcFace ResNet50 face recognition model.

## Download

If the recognition model is missing, download from:

https://huggingface.co/Aitrepreneur/insightface/blob/main/models/buffalo_l/w600k_r50.onnx

The YuNet detector is downloaded automatically on first run from the OpenCV
Zoo; no manual step is required.

## Model Info

**YuNet (detection)**
- **Type**: ONNX Runtime via `cv2.FaceDetectorYN`
- **Score threshold**: 0.6 · **NMS threshold**: 0.3

**ArcFace (recognition)**
- **Input**: [1, 3, 112, 112] (batch, channels, height, width)
- **Output**: [1, 512] (512-dimensional face embedding)
- **Type**: ONNX Runtime
- **Similarity Metric**: Cosine Similarity
- **Threshold**: 0.45 (for matching)

