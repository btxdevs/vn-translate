# Visual Novel Translator

## Introduction

Visual Novel Translator is a desktop application designed to assist users in reading visual novels (or other screen content) in foreign languages. It captures text from a selected application window using specified Regions of Interest (ROIs), performs Optical Character Recognition (OCR) on these regions, translates the extracted text using AI language models, and displays the results, primarily through customizable floating overlay windows.

It offers flexibility through multiple OCR engines, various translation service presets, per-game configurations, and features like color filtering for improved text extraction and a quick "Snip & Translate" tool.

<!-- Add Screenshots/GIFs Here showing the main UI, ROI definition, overlays, snip tool, etc.-->

## Core Features

*   **Window Capture:** Select any visible window on your system as the source for text capture.
*   **Region of Interest (ROI) Definition:** Draw rectangles (ROIs) directly onto a snapshot of the selected window to specify exactly where the application should look for text (e.g., dialogue boxes, menus). Configurations are saved per game.
*   **Color Filtering:** Apply color filters to each ROI individually. This helps isolate text from complex backgrounds by replacing pixels close to a target color with a solid replacement color, improving OCR accuracy.
*   **Multiple OCR Engines:** Choose between different OCR engines for text extraction:
    *   **PaddleOCR:** A versatile and popular OCR engine.
    *   **EasyOCR:** Another widely used OCR library.
    *   **Windows OCR:** Utilizes the built-in Windows 10/11 OCR capabilities (Windows only).
    *   *(GPU acceleration is attempted for PaddleOCR and EasyOCR if prerequisites are met).*
*   **AI Translation:** Translate extracted text using various large language models via API calls.
    *   **Presets:** Comes with default presets for OpenAI (GPT-3.5, GPT-4), Claude, Mistral, and a template for local models (like LM Studio/Ollama).
    *   **Customization:** Manage presets (save, save as, delete), configure API keys, URLs, models, and advanced parameters (temperature, context limit, etc.).
    *   **Caching:** Translation results are cached per-game to avoid redundant API calls and save costs. Cache can be cleared per-game or entirely.
    *   **Context Management:** Maintains translation history per-game to provide context to the AI for potentially more coherent translations. Context can be reset. Supports adding game-specific background information.
*   **Customizable Overlays:** Display translations in floating, draggable, and resizable overlay windows.
    *   **Per-ROI Configuration:** Customize the appearance (font, size, color, background, transparency, alignment, wrap width) for each ROI's overlay.
    *   **Global Toggle:** Easily show or hide all translation overlays.
    *   **Position Reset:** Reset an overlay's position and size to default.
*   **Snip & Translate:** Quickly select *any* rectangular region on your screen (outside the main target window if needed) for instant OCR and translation in a temporary, closable overlay.
*   **Floating Controls:** A small, always-on-top control bar for quick access to common actions:
    *   Retranslate (use cache)
    *   Force Retranslate (ignore cache)
    *   Copy Last Translation
    *   Start Snip & Translate
    *   Toggle Auto-Translate
    *   Toggle Overlays
    *   Hide Controls
*   **Text Previews:** Dedicated tabs to see:
    *   **Live Text:** Raw OCR results extracted frame-by-frame.
    *   **Stable Text:** Text that hasn't changed for a set number of frames (controlled by a threshold slider), which is the input used for translation.
    *   **Translation:** The final translated output text.
*   **Configuration Management:**
    *   **Game-Specific ROIs:** ROI definitions and color filter settings are saved automatically based on the selected game's executable path and file size.
    *   **Translation Presets:** API configurations are saved globally.
    *   **General Settings:** Other preferences like default language, OCR engine, overlay states, etc., are saved.

## Prerequisites

*   **Python:** Version 3.8 or higher is required. During installation, ensure you check the option "Add Python to PATH". You can download Python from [python.org](https://www.python.org/).
*   **Git (Optional):** Needed if you plan to clone the repository directly from a Git source.
*   **(Optional) NVIDIA GPU Setup for Acceleration:**
    *   If you have an NVIDIA GPU and want to use GPU acceleration for PaddleOCR or EasyOCR (highly recommended for performance), you **must** install the following *before* running the setup script or manual installation:
        1.  **NVIDIA GPU Drivers:** Install the latest drivers for your graphics card from the NVIDIA website.
        2.  **CUDA Toolkit:** Download and install the CUDA Toolkit version compatible with the libraries (PyTorch/PaddlePaddle often specify compatible versions). Check the PyTorch and PaddlePaddle websites for current recommendations (Note: `requirements.txt` is set for CUDA 11.8 via the PyTorch index URL, ensure your toolkit matches or adjust `requirements.txt`).
        3.  **cuDNN:** Download and install the cuDNN library compatible with your CUDA Toolkit version. Follow NVIDIA's instructions to place the cuDNN files into your CUDA Toolkit installation directory.
    *   Verify CUDA setup *before* proceeding. You can often check PyTorch's CUDA availability after installation (see Manual Installation steps).
*   **(Optional) C++ Build Tools:** Some Python packages might require C++ compilation during installation. If you encounter errors related to missing compilers, you may need to install the "C++ build tools" workload from the [Visual Studio Installer](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
*   **(Optional) Windows Language Packs for OCR:** If using the "Windows OCR" engine for languages other than English, ensure the corresponding OCR language pack is installed via Windows Settings (Time & Language -> Language & region -> Add a language -> Select language -> Options -> Ensure "Optical character recognition" is installed).

## Installation

You can install the necessary dependencies and set up the environment using either the provided setup script (recommended for ease of use) or by following the manual steps.

### Using the Setup Script (Recommended)

The `setup_and_run.bat` script automates the creation of a virtual environment and installation of all required Python packages.

1.  **Download/Clone:** Obtain the application files (including `main.py`, `requirements.txt`, `setup_and_run.bat`, and all other `.py` files and subdirectories).
2.  **Open Terminal:** Open a Command Prompt (`cmd.exe`) or PowerShell window.
3.  **Navigate:** Use the `cd` command to navigate into the directory where you placed the application files.
    ```bash
    cd path\to\vn-translate
    ```
4.  **Run Script:** Execute the setup script:
    ```bash
    .\setup_and_run.bat
    ```
5.  **First Run:**
    *   The script will check for Python.
    *   It will create a Python virtual environment named `.venv` in the current directory.
    *   It will then install all dependencies listed in `requirements.txt` into this virtual environment. This step can take a significant amount of time, especially when downloading large libraries like PyTorch or PaddlePaddle. Please be patient.
    *   If installation is successful, it will create a marker file (`.setup_complete`) inside the `.venv` folder and then launch the Visual Novel Translator application.
6.  **Subsequent Runs:**
    *   Simply run `.\setup_and_run.bat` again.
    *   The script will detect the `.venv` folder and the `.setup_complete` file.
    *   It will skip the setup steps and directly launch the application using the Python interpreter from the existing virtual environment.

**Troubleshooting (Script):**
*   If the script fails with Python errors, ensure Python 3.8+ is installed and added to your PATH.
*   If it fails during dependency installation:
    *   Check your internet connection.
    *   Look for specific error messages. You might be missing C++ Build Tools or have CUDA/cuDNN compatibility issues if installing GPU versions.
    *   Consider deleting the `.venv` folder and running the script again after addressing the underlying issue.

### Manual Installation

Follow these steps if you prefer to set up the environment manually or encounter issues with the script.

1.  **Download/Clone:** Obtain the application files as described above.
2.  **Open Terminal:** Open Command Prompt (`cmd.exe`) or PowerShell.
3.  **Navigate:** Use `cd` to navigate into the application's directory.
4.  **Create Virtual Environment:** It's highly recommended to use a virtual environment to avoid conflicts with other Python projects.
    ```bash
    python -m venv .venv
    ```
    *(This creates a folder named `.venv`)*
5.  **Activate Virtual Environment:** You need to activate the environment in your current terminal session.
    *   On Command Prompt:
        ```bash
        .\.venv\Scripts\activate.bat
        ```
    *   On PowerShell:
        ```bash
        .\.venv\Scripts\Activate.ps1
        ```
        *(If you get an error about execution policies in PowerShell, you might need to run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` and try activating again)*
    *   Your terminal prompt should now change to indicate the active environment (e.g., `(.venv) C:\path\to\app>`).
6.  **Install Dependencies:** Install all required packages from the `requirements.txt` file. The `--extra-index-url` for PyTorch/CUDA is included in the file and will be handled automatically by pip.
    ```bash
    pip install -r requirements.txt
    ```
    *(This step can take a while)*
7.  **Run the Application:** Once dependencies are installed, run the main script:
    ```bash
    python main.py
    ```
8.  **Running Subsequently:** To run the application after the initial setup:
    *   Navigate to the application directory in your terminal.
    *   Activate the virtual environment (`.\.venv\Scripts\activate`).
    *   Run the application (`python main.py`).

**Troubleshooting (Manual):**
*   If `python -m venv .venv` fails, ensure Python is installed correctly and in your PATH.
*   If `pip install` fails, check error messages carefully. Ensure prerequisites (like C++ Build Tools or correct CUDA versions for GPU) are met.
*   If PyTorch/PaddlePaddle GPU versions install but don't use the GPU, double-check your NVIDIA driver, CUDA, and cuDNN setup and compatibility. You can often test PyTorch CUDA availability in Python after activation: `python -c "import torch; print(torch.cuda.is_available())"` (should print `True`).

## How to Use

1.  **Select Target Window (Capture Tab):**
    *   Run the visual novel or application you want to translate.
    *   Go to the "Capture" tab in the translator.
    *   Click "Refresh List" to find the target window.
    *   Select the window from the dropdown list. The window title and HWND (handle) will be displayed.

2.  **Define Regions of Interest (ROIs) (ROI Tab):**
    *   Once a window is selected, click "Take Snapshot" on the "Capture" tab. This freezes the display in the left pane.
    *   Go to the "ROI" tab.
    *   Enter a descriptive name for your first ROI (e.g., `dialogue`, `name_box`) in the "New ROI Name" entry field.
    *   Click the "Define ROI" button (it will change to "Cancel Define").
    *   Move your mouse over the image preview in the left pane. Click and drag to draw a rectangle around the text area you want to capture.
    *   Release the mouse button. The ROI will be created with the name you entered and added to the "Current Game ROIs" list.
    *   The "Define ROI" button will revert, and the preview will return to live view (if capture was running) or remain on the snapshot.
    *   Repeat for all text areas you need (dialogue boxes, character names, choices, etc.), entering a unique name for each.
    *   Use the "▲ Up", "▼ Down", and "Delete" buttons to manage the ROIs in the list. The order can sometimes matter for context.
    *   **Crucially, click "Save All ROI Settings for Current Game"** to save your defined ROIs for this specific game. They will be loaded automatically next time you select this game window.

3.  **Configure Color Filtering (Optional) (ROI Tab):**
    *   Select an ROI from the list in the "ROI" tab.
    *   The "Color Filtering" section will become active.
    *   Check "Enable Color Filter" to activate it for the selected ROI.
    *   **Target Color:** Click "Pick..." to choose the *text color* you want to keep, or "Screen" to pick it directly from anywhere on your screen. The colored square shows the current selection.
    *   **Replace With:** Click "Pick..." to choose the color that everything *else* (non-text pixels) should be turned into. Often black (`#000000`) or white (`#FFFFFF`) works well depending on the OCR engine and text color.
    *   **Threshold:** Adjust the slider. This determines how close a pixel's color needs to be to the "Target Color" to be kept. Higher values are more lenient.
    *   Use "Preview Original" and "Preview Filtered" to see the effect of your settings on the ROI content (requires a snapshot or live capture).
    *   Click "Apply Filter Settings" to apply the changes to the *in-memory* ROI. **Remember to "Save All ROI Settings" again** to make these changes persistent for the game.

4.  **Configure Overlays (Optional) (Overlay Tab):**
    *   Go to the "Overlays" tab.
    *   Select the ROI (or "Snip Translate") whose overlay you want to configure from the dropdown menu.
    *   Adjust the font, size, colors, transparency (alpha), text alignment, and wrap width using the controls.
    *   Use the "Enabled" checkbox to turn the overlay for that specific ROI on or off (this is overridden by the global toggle). Snip Translate is always enabled when active.
    *   Click "Apply Appearance" to save the settings for the selected ROI's overlay. These settings are saved globally in `vn_translator_settings.json`.
    *   If an overlay window's position or size gets messed up, select the ROI and click "Reset Position/Size".
    *   Use the "Enable Translation Overlays Globally" checkbox at the top to turn ALL overlays (except Snip) on or off quickly. This state syncs with the Floating Controls button.

5.  **Configure Translation (Translation Tab):**
    *   Go to the "Translation" tab.
    *   **Preset:** Select a translation service preset (e.g., "OpenAI (GPT-3.5)").
    *   **Preset Details:** Fill in the required details for the selected preset:
        *   `API Key`: Your secret API key for the service.
        *   `API URL`: The API endpoint URL.
        *   `Model`: The specific model name (e.g., `gpt-3.5-turbo`, `claude-3-haiku-20240307`).
        *   Adjust `Context Limit`, `Temperature`, `Max Tokens`, etc., as needed.
    *   **Save Preset:** Click "Save" to update the currently selected preset with the values you entered, or "Save As..." to create a new preset. Use "Delete" to remove the selected preset.
    *   **General Settings:**
        *   `Target Language`: Enter the language code you want to translate *into* (e.g., `en`, `es`, `fr`).
        *   `Additional Context (Game Specific)`: Add any helpful background info for the translator about the current game (character names, lore, setting). This is saved per game.
    *   **Auto-Translate:** Check the box if you want the application to automatically request a translation whenever the text in the "Stable Text" tab changes.

6.  **Capture and Translate:**
    *   Go to the "Capture" tab.
    *   Select your desired "OCR Engine" and "Language". The application will initialize the engine (this might take a few seconds the first time).
    *   Click "Start Capture".
    *   Text should appear in the "Live Text" and "Stable Text" tabs as it's detected in your ROIs.
    *   If "Auto-Translate" is enabled, translations will appear in the "Translation" tab and overlays shortly after text stabilizes.
    *   If "Auto-Translate" is disabled, click "Translate" (uses cache) or "Force Retranslate" (ignores cache) in the "Translation" tab or use the corresponding buttons on the Floating Controls.
    *   Click "Stop Capture" when finished.

7.  **Using Overlays:**
    *   If the global overlay toggle is enabled (and the specific ROI overlay is enabled), floating windows will appear containing the translations for each ROI.
    *   You can click and drag the body of an overlay window to move it.
    *   Click and drag the small gray square (grip) in the bottom-right corner to resize the overlay.
    *   Position and size are saved automatically when you release the mouse.

8.  **Snip & Translate:**
    *   Click the "✂️" button on the Floating Controls.
    *   Your screen will dim slightly, and the cursor will become a crosshair.
    *   Click and drag to select any rectangular area on your screen.
    *   Release the mouse button.
    *   The selected region will be captured, OCR'd, and translated. The result will appear in a temporary, closable floating window near the region you selected.
    *   Click the "✕" button on the snip result window to close it. Press `Esc` during selection to cancel.

9.  **Floating Controls:**
    *   This small window provides quick access:
        *   `🔄`: Retranslate last stable text (uses cache).
        *   `⚡`: Force retranslation (ignores cache).
        *   `📋`: Copy the last translation result(s) to the clipboard.
        *   `✂️`: Start Snip & Translate mode.
        *   `🤖`: Toggle Auto-Translate on/off.
        *   `👁️`: Toggle all overlays on/off globally.
        *   `✕`: Hide the Floating Controls window (show again via Window menu).
    *   Click and drag the background of the Floating Controls window to move it. Its position is saved when you release the mouse.

10. **Text Tabs:**
    *   **Live Text:** Shows the raw OCR output for every frame. Useful for debugging OCR quality.
    *   **Stable Text:** Shows text only after it has remained the same for the number of frames set by the "Stability Threshold" slider. This is the text sent for translation.
    *   **Translation:** Shows the latest translation result received from the API.

11. **Cache and Context Management (Translation Tab):**
    *   `Clear Current Game Cache`: Deletes the saved translations specifically for the currently selected game window. Useful if translations seem stuck or wrong.
    *   `Clear All Cache`: Deletes *all* saved translation cache files for *all* games.
    *   `Reset Translation Context`: Clears the conversational history sent to the AI for the current game and deletes the history file. Useful if the AI seems confused or stuck on previous dialogue.

## Configuration Files

The application saves configurations automatically:

*   `vn_translator_settings.json`: Stores general settings, OCR preferences, global overlay state, individual overlay appearance settings, floating controls position, and game-specific context.
*   `translation_presets.json`: Stores your translation API presets (URLs, keys, models, parameters).
*   `roi_configs/GAMEHASH_rois.json`: Stores ROI definitions (name, coordinates, color filter settings) for each game. `GAMEHASH` is generated based on the game's executable path and size.
*   `cache/GAMEHASH.json`: Stores cached translations for each game.
*   `context_history/GAMEHASH_context.json`: Stores the translation conversation history for each game.

These files are located in the same directory as the application or in subdirectories (`roi_configs`, `cache`, `context_history`).