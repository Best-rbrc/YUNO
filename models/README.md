# Models Directory

This directory contains the ArcFace face recognition model.

## Model File

`arcface_model.onnx` (~260 MB) - ArcFace ResNet100 model

## Download

If the model is missing, download from:

https://huggingface.co/Aitrepreneur/insightface/blob/main/models/buffalo_l/w600k_r50.onnx
```

## Model Info

- **Input**: [1, 3, 112, 112] (batch, channels, height, width)
- **Output**: [1, 512] (512-dimensional face embedding)
- **Type**: ONNX Runtime
- **Similarity Metric**: Cosine Similarity
- **Threshold**: 0.45 (for matching)

