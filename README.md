# 🚁 SIH Drone 3D Reconstruction Pipeline

> **AI-Powered, Single-Pass Photogrammetry & Real-World Metric Analytics Engine**  
> *Developed for Smart India Hackathon (SIH)*

[![Docker](https://img.shields.io/badge/Docker-OpenDroneMap%3AGPU-blue.svg?logo=docker)](https://hub.docker.com/r/opendronemap/odm)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg?logo=python)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-SIFT%20%26%20HOG-red.svg?logo=opencv)](https://opencv.org/)
[![Trimesh](https://img.shields.io/badge/Trimesh-Watertight%20Repair-orange.svg)](https://trimesh.org/)

---

## 📌 Problem Statement Overview

In tactical surveillance, disaster response, and urban planning, transforming raw 2D drone video footage into high-precision, georeferenced 3D models typically suffers from major computational and geometric challenges:
* **The EXIF Deficit:** Standard video frames lack embedded EXIF camera metadata (focal length, GPS coordinates, altitude).
* **Loop-Closure Drift ("Banana Effect"):** Cumulative camera pose tracking errors cause 3D reconstructions of circular flight paths to warp, twist, or curl.
* **Transient Dynamic Noise:** Moving vehicles, pedestrians, and dynamic shadows corrupt feature matching and produce ghosting artifacts on 3D building surfaces.
* **Incomplete & Hollow Meshes:** Complex roof structures and occluded building facades leave gaping holes in generated 3D meshes.

This project delivers a **one-click, end-to-end photogrammetry pipeline** that ingests raw drone video footage along with sub-second SRT telemetry, eliminates dynamic object artifacts, solves loop-closure drift mathematically, repairs mesh geometries into watertight models, and outputs real-world physical metric analytics.

---

## 💡 Core Innovations

### 1. 📡 SRT Telemetry Ingestion & Linear GPS Interpolation
* **Automated Telemetry Extraction:** Extracts embedded subtitle tracks (`.SRT`) or parses external sidecar telemetry files from drone video streams.
* **Sub-Second Precision:** Linear GPS coordinate interpolation syncs keyframe capture timestamps with latitude, longitude, and absolute altitude to produce absolute ground priors (`geo.txt`), completely preventing loop-closure drift.

### 2. 🤖 AI Smart Frame Extraction & Dynamic Object Masking (`ai_prune.py`)
* **Blur Filtering:** Calculates Laplacian variance to automatically filter out blurred frames.
* **SIFT Redundancy Pruning:** Measures visual feature keypoint overlap ratios to prune redundant stationary frames while maintaining optimal visual continuity.
* **Dynamic Object Removal:** Combines Histogram of Oriented Gradients (HOG) pedestrian detection with Canny edge contour filtering to generate binary object masks (white = keep, black = erase), removing moving cars, trucks, and people before 3D reconstruction.

### 3. 🧩 Watertight Mesh Hole Sealing (`mesh_completer.py`)
* **Automated Boundary Repair:** Inspects generated 3D textured OBJ meshes for open boundaries and unclosed surface loops.
* **AI Mesh Completion:** Uses `trimesh` surface repair algorithms to fill holes and export a seamless, structurally sound `watertight.obj` 3D model.

### 4. 📊 Real-World Metric Analytics Engine (`analytics_engine.py`)
* **Physical Dimension Extraction:** Calculates structure height (m), bounding length (m), width (m), footprint roof area ($\text{m}^2$), and estimated volumetric mass ($\text{m}^3$).
* **Structural Health Metrics:** Exports vertex/polygon counts and watertight status directly to machine-readable JSON (`analytics_report.json`) and human-readable text (`analytics_summary.txt`).

---

## 🛠️ Prerequisites & One-Time Setup

### System Requirements
* **OS:** Linux (Ubuntu 20.04/22.04 recommended) or WSL2
* **NVIDIA GPU & Drivers:** Required for GPU acceleration (`--gpus all`)
* **Docker Engine:** Version 20.10+
* **Python Dependencies:** `opencv-python`, `numpy`, `trimesh`

### One-Time Docker Pull
Pull the official GPU-accelerated OpenDroneMap image:

```bash
docker pull opendronemap/odm:gpu
```

*(Note: For CPU-only environments, the script automatically falls back to `opendronemap/odm` when `--cpu` is specified).*

---

## 📁 Project Directory Structure & Input Placement

Organize your project folder as follows:

```text
/home/ubantu/Desktop/sih/project/
├── process_drone_video.py     # Master Pipeline Orchestrator
├── ai_prune.py                # Frame Extractor & AI Dynamic Object Masker
├── mesh_completer.py          # AI Watertight Mesh Hole Repair
├── analytics_engine.py        # Real-World Metric Analytics Engine
├── team_pitch.md              # SIH Pitch & Technical Architecture Document
└── images/                    # INPUT DIRECTORY (Place video & SRT here)
    ├── 312781.mp4             # Input Drone Video File
    └── 312781.SRT             # Synchronized Telemetry File (or embedded)
```

---

## 🚀 How to Run

Execute the single-command pipeline directly from your terminal:

```bash
./process_drone_video.py images/312781.mp4 --quality high
```

### Advanced CLI Options

```bash
# High-quality reconstruction using GPU (default)
./process_drone_video.py images/312781.mp4 --quality high --sample-fps 5.0

# Custom output directory and lower concurrency limit for memory optimization
./process_drone_video.py images/312781.mp4 --output-dir high_gpu_run --quality medium --max-concurrency 4

# Force CPU mode (if no NVIDIA GPU is available)
./process_drone_video.py images/312781.mp4 --cpu --quality medium
```

---

## 📦 Deliverables & Output Formats

Upon pipeline completion, the output directory will contain:

| File / Folder Path | Deliverable Description | Format |
| :--- | :--- | :--- |
| `odm_texturing/odm_textured_model_geo.obj` | Photorealistic 3D Textured Mesh | `.obj` + `.mtl` + `.png` |
| `odm_texturing/odm_textured_model_watertight.obj` | Hole-Filled Watertight 3D Geometry | `.obj` |
| `odm_orthophoto/odm_orthophoto.tif` | Georeferenced High-Res Orthomosaic Map | `.tif` (GeoTIFF) |
| `odm_filterpoints/point_cloud.ply` | Dense 3D Point Cloud | `.ply` |
| `geo.txt` | Ground Control Georeferencing Priors | `.txt` (EPSG:4326) |
| `analytics_summary.txt` | Structural Metrics & Dimension Report | `.txt` |
| `analytics_report.json` | Programmatic Analytics Data | `.json` |

### Sample Analytics Output (`analytics_summary.txt`)

```text
==========================================
   AI REAL-WORLD 3D METRIC ANALYTICS REPORT
==========================================
Maximum Structure Height : 24.15 meters
Bounding Length          : 45.30 meters
Bounding Width           : 32.10 meters
Footprint Roof Area      : 1454.13 sq meters
Estimated Structure Vol  : 35117.24 cubic meters
Total 3D Mesh Vertices   : 124,850
Total 3D Mesh Polygons   : 248,320
Watertight Sealed        : YES
==========================================
```

---

## 📄 License & Acknowledgments

* **OpenDroneMap (ODM):** GNU GPLv3
* **OpenCV / Trimesh:** Open-source BSD / MIT License
* Developed for **Smart India Hackathon (SIH)**.
