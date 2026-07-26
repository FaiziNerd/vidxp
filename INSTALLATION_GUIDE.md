1. Install Dlib

- On Linux and macOS, install it from PyPI as part of the normal requirements install.

- On Windows, if pip cannot build `dlib` for your environment, you can use a prebuilt wheel from a trusted source or install the matching PyPI package if available for your Python version.

- Do not keep a platform-specific `.whl` file in the project root.

2. Set Up a Virtual Environment

- Open a terminal in the project folder and run:

- Create a virtual environment named 'venv': python -m venv venv

- Activate the virtual environment

- On Windows: venv\Scripts\activate

- On macOS/Linux: source venv/bin/activate

3. Install Project Requirements

- Install the remaining dependencies with: pip install -r requirements.txt

4. Run the Application

- Start the Streamlit application: streamlit run src/vidxp/frontend.py
