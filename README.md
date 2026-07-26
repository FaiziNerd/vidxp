# VidXP (Video eXPlain) - Video Indexing Engine

**A Python package for video indexing and searching based on audio and scene content.**

## Outline

1. [Product Feature Roadmap Matrix](#product-feature-roadmap-matrix)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Contribution Guidelines](docs/CONTRIBUTING.md)

## Product Feature Roadmap Matrix

|Feature Category|V1 (Basic Features)|V2 (Enhanced Features)|V3 (Advanced Features)|
|----------------|-------------------|----------------------|----------------------|
|**Scene Search**|**Functionality:** Search for scenes based on text description
||**Model:** CLIP (ViT-B/32)
||**Query:** vidxp scene "filepath" "scene description"
|**Dialogue Search**|**Functionality:** Search for specific dialogues and jump to the timestamps
||**Model:** WhisperX (large-v2), SentenceTransformer (all-MiniLM-L6-v2)
||**Query:** vidxp dialogue "filepath" "dialogue"
|**Actor Detection**|**Functionality:** Basic actor detection (making clusters of similar faces)
||**Library:** face_recognition
||**Query:** vidxp face "filepath" "cluster_id"
|**Active Speaker Detection**|**Functionality:** Display active speakers in a scene
||**Model:** TalkNet-ASD
||**Query:** 
|**Actor Search**|N/A
|**User Interface**|CLI + basic GUI
||CLI (Typer) 
||GUI (HTML, CSS, JS)

## Installation

### **Prerequisites**

- **Python 3.9 or higher**
- **Poetry** (Recommended for dependency and package management) - Install from [Poetry Documentation](https://python-poetry.org/docs/)
- **Alternatively, Pip and ****`build`**** package** (For manual installation)

---

### **Installation Steps**

#### **Option 1: Recommended - Using Poetry**

1.  **Clone the repository**

    ```bash
    git clone https://github.com/grayhatdevelopers/vix
    cd vix
    ```

2.  **Install dependencies using Poetry**

    ```bash
    poetry install
    ```

    - This sets up a virtual environment and installs dependencies from `poetry.lock` or `pyproject.toml`.
    - The `vidxp` CLI command will be available after installation.

3.  **Activate the environment (if needed)**

    ```bash
    poetry shell
    ```

4.  **Run the CLI tool**

    ```bash
    vidxp --help
    ```

---

#### **Option 2: Manual Installation - Using Pip**

If you prefer Pip instead of Poetry, follow these steps:

1.  **Clone the repository**

    ```bash
    git clone https://github.com/grayhatdevelopers/vix
    cd vix
    ```

2.  **Install build dependency**

    ```bash
    pip install build
    ```

3.  **Build the package**

    ```bash
    python -m build
    ```

    - This creates a `dist/` directory with distribution files.

4.  **Install the package**

    ```bash
    pip install dist/*.whl
    ```

5.  **Run the CLI tool**

    ```bash
    vidxp --help
    ```

    - If `vidxp` is not recognized, run it manually:

      ```bash
      python -m vidxp --help
      ```

---

## **Usage**

After installation, you can use `vidxp` directly from the command line:

```bash
vidxp --help
vidxp videoindex samplevideo.mp4  # Index the video
vidxp dialogue samplevideo.mp4 "your dialogue query"
vidxp scene samplevideo.mp4 "scene description"
```
