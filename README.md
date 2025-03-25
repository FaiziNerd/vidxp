# ActorDB

**A Python package for video indexing and searching based on audio and scene content.**

## Product Feature Roadmap Matrix

|Feature Category|V1 (Basic Features)|V2 (Enhanced Features)|V3 (Advanced Features)|
|----------------|-------------------|----------------------|----------------------|
|**Scene Search**|**Functionality:** Search for scenes based on text description
||**Model:** CLIP (ViT-B/32)
||**Query:** actordb scene "filepath" "scene description"
|**Dialogue Search**|**Functionality:** Search for specific dialogues and jump to the timestamps
||**Model:** WhisperX (large-v2), SentenceTransformer (all-MiniLM-L6-v2)
||**Query:** actordb dialogue "filepath" "dialogue"
|**Actor Detection**|**Functionality:** Basic actor detection (making clusters of similar faces)
||**Library:** face_recognition
||**Query:** actordb face "filepath" "cluster_id"
|**Active Speaker Recognition**|Display active speakers in a scene
|**Actor Search**|N/A
|**User Interface**|CLI + basic GUI
||CLI (Typer) 
||GUI (HTML, CSS, JS)

## Installation

### **Prerequisites**

- **Python 3.9 or higher**
- **Poetry** (Recommended for dependency and package management) – Install from [Poetry Documentation](https://python-poetry.org/docs/)
- **Alternatively, Pip and ****`build`**** package** (For manual installation)

---

### **Installation Steps**

#### **Option 1: Recommended - Using Poetry**

1.  **Clone the repository**

    ```bash
    git clone <YOUR_REPOSITORY_URL>
    cd actordb
    ```

2.  **Install dependencies using Poetry**

    ```bash
    poetry install
    ```

    - This sets up a virtual environment and installs dependencies from `poetry.lock` or `pyproject.toml`.
    - The `actordb` CLI command will be available after installation.

3.  **Activate the environment (if needed)**

    ```bash
    poetry shell
    ```

4.  **Run the CLI tool**

    ```bash
    actordb --help
    ```

---

#### **Option 2: Manual Installation - Using Pip**

If you prefer Pip instead of Poetry, follow these steps:

1.  **Clone the repository**

    ```bash
    git clone <YOUR_REPOSITORY_URL>
    cd actordb
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
    actordb --help
    ```

    - If `actordb` is not recognized, run it manually:

      ```bash
      python -m actordb.main --help
      ```

---

## **Usage**

After installation, you can use `actordb` directly from the command line:

```bash
actordb --help
actordb videoindex samplevideo.mp4  # Index the video
actordb dialogue samplevideo.mp4 "your dialogue query"
actordb scene samplevideo.mp4 "scene description"

