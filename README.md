# Star Chart Generator

This project creates neon-styled sci-fi **star charts** that match the visual brief described in `docs/star_chart_generator_study.md`. It is written in pure Python and ships with ready-to-use scene presets plus a command-line renderer.

## 1. Before you start

- **Python**: install Python 3.10 or newer. You can check your version by running:
  ```bash
  python --version
  ```
- **Optional**: installing [PyYAML](https://pyyaml.org/) allows loading complex YAML features (anchors, comments). The project includes a simple built-in parser, so PyYAML is not mandatory.

> 💡 If you have never used a terminal before, open *Command Prompt* on Windows or *Terminal* on macOS/Linux and type the commands exactly as shown.

## 2. Get the code and set up a virtual environment

1. **Download the repository**
   ```bash
   git clone https://github.com/<your-user>/Generator01.git
   cd Generator01
   ```
   Replace `<your-user>` with the correct account if you forked the project on GitHub.

2. **Create a virtual environment** (keeps dependencies separate from the rest of your computer):

   **Windows (PowerShell)**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS / Linux**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   The project currently uses only the Python standard library, so this command finishes quickly.

Whenever you open a new terminal, reactivate the environment (`Activate.ps1` on Windows or `source .venv/bin/activate` on macOS/Linux) before running the scripts again.

## 3. Render your first star chart

1. Choose one of the ready-made scene files inside `configs/` (for example `demo.yaml`).
2. Run the generator script from the project root:
   ```bash
   python scripts/generate_star_chart.py configs/demo.yaml output/demo.png
   ```
3. After the script finishes, open `output/demo.png` with your favourite image viewer. Rendering higher resolutions may take longer because everything is computed on the CPU.

### Optional command-line flags

- `--seed 12345` – override the random number generator seed for reproducible variations.
- `--layers-dir layers/` – export intermediate PNG layers (`stars`, `ui_core`, `ui_glow`, `final_linear`).
- `--compare path/to/reference.png` – print the mean absolute difference against a reference render.
- `--quality preview` – apply a low-quality preset (`preview` or `draft`) for much faster test renders. Use `final` to keep the original settings.

Run `python scripts/generate_star_chart.py --help` to see all options.

## 4. HTML interface

Prefer a graphical workflow? Launch the built-in HTML control panel:

```bash
python scripts/run_web_interface.py
```

The server selects a free local port and opens your default browser automatically. From the interface you can pick any YAML scene stored in `configs/`, choose a **Calidad de render** preset (`Preview` is ideal for quick iterations), optionally override the RNG seed, and trigger renders directly from the page. The resulting PNG preview is displayed inline and—when the **Guardar PNG** toggle is enabled—saved under `output/` with a timestamp.

The panel also includes a **Debug command console**. It executes arbitrary Python code inside the project context, giving you direct access to `SceneConfig`, `generate_star_chart`, `PROJECT_ROOT`, `CONFIG_DIR`, and `OUTPUT_DIR` to perform quick experiments or bug investigations.

On Windows you can double-click `launch_web_interface.bat` to start the same interface without touching the terminal. The script detects a local virtual environment (`.venv`) automatically.

Advanced flags:

- `--no-browser` – skip opening the browser automatically.
- `--host 0.0.0.0` – expose the interface to your LAN (only do this on trusted networks).
- `--port 8000` – force a specific port instead of picking one dynamically.

Press `Ctrl+C` in the terminal that started the server to stop it.

## 5. Understanding the scene configuration

Scene files are plain YAML documents. The most important sections are:

- `seed`: base random seed used when `--seed` is not provided.
- `resolution`: output width, height, and supersampling factor (`ssaa`).
- `camera`: controls the tilt and field of view used to squash rings.
- `rings`: list of UI rings. Each ring supports radius (`r`), width, colour, dash pattern, tick marks, labels, label angle, halo strength, etc.
- `stars`: parameters for the dense core and sparse halo distributions, plus star size and brightness behaviour.
- `text`: typography settings (font name, size, colour, tracking, tabular digits).
- `post`: post-processing (bloom threshold/intensity/radius, chromatic aberration, vignette, grain).

Use `configs/demo.yaml` or `configs/denso.yaml` as a template for your own layouts. Adjust one value at a time, rerun the renderer, and inspect the result to learn what each setting does.

## 6. Using the generator as a Python library

You can embed the renderer inside another Python script:

```python
from star_chart_generator import SceneConfig, generate_star_chart

config = SceneConfig.load("configs/demo.yaml")
result = generate_star_chart(config, seed=123)
result.save("output/from_code.png")
```

If you prefer to build the configuration in code (for example, loading parameters from a UI), call `SceneConfig.from_dict(...)` with the same structure used in the YAML files.

The `RenderResult` object returned by `generate_star_chart` contains the final tone-mapped image (`result.image`) and intermediate layers (`result.layers` dictionary).

## 7. Running tests (optional)

Automated tests ensure the generator still works after code changes:
```bash
pytest
```
This command should be executed inside the virtual environment from the project root.

## 8. Troubleshooting

- **PNG is all black**: make sure supersampling (`ssaa`) is set to `1` or higher and that the `rings` section is not empty.
- **`ModuleNotFoundError: No module named 'yaml'`**: either install PyYAML (`pip install pyyaml`) or remove YAML features that rely on anchors/aliases; the built-in parser supports simple key-value pairs.
- **Slow renders**: large supersampling values or very high resolutions increase render time because everything runs on the CPU. Start with `width: 1024`, `height: 1024`, `ssaa: 1`, then scale up once you like the layout.

Happy chart making! ✨
