# 0D_database

0D_database is an interactive web project for browsing and visualizing 0D materials data. It combines structure, energy, bandgap, molecule decomposition results, and selected DFT outputs in a Dash-based UI.

## Project Goals

- Provide an interactive entry point for exploring 0D materials data.
- Enable fast filtering and sorting of key material properties on an overview table.
- Show detailed structure, partition, and BS/DOS information on a material details page.
- Serve as a foundation for a larger materials database frontend.

## Core Features

- Materials table with filtering, sorting, and pagination.
- Material details page with key metadata.
- Structure visualization powered by Crystal Toolkit.
- Custom bonding cutoff generation from atomic radii and tolerance windows.
- BS/DOS visualization by reading VASP outputs from step_15 and step_16 folders.

## Data and Directory Notes

- ZeroDB_test_data.json: Primary dataset, stored in a column-wise format.
- atomic_radius.json: Atomic radius lookup used for custom bonding cutoffs.
- ZeroDB_test_data/ZeroDB_test_data/: Per-material DFT data folders.
- main.py: Dash app entry point.
- requirements.txt: Unified pip dependency list for local use and deployment.

## Tech Stack

- Python 3.11
- Dash
- Crystal Toolkit
- pymatgen

## Quick Start

### Option 1 (Recommended: fresh Conda env + pip)

Create and activate a fresh Conda environment:

```bash
conda create -n web_2 python=3.11 -y
conda activate web_2
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If you only want the minimum package needed to run the app locally, `pip install crystal-toolkit` is enough.

Run the app:

```bash
python main.py
```

Open in browser:

```text
http://127.0.0.1:8050
```

### Option 2 (minimal local install)

```bash
python -m pip install crystal-toolkit
python main.py
```

## Deployment Guidance

Production run example:

```bash
cp -n .env.example .env
# Ensure .env uses ZERO_DB_GUNICORN_BIND=127.0.0.1:8050
./scripts/run_prod.sh
```

For a practical deployment path and a scalable architecture plan for thousands of materials, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

For the concrete deployment files added to this repository, see [DEPLOYMENT.md](DEPLOYMENT.md).

## UI Usage

- Home page: Browse all materials with filter and sort support.
- Details link: Navigate to the selected material details page.
- Left panel on details page: Material metadata, partition info, tolerance window, and custom bonding controls.
- Right panel on details page: Structure visualization and BS/DOS plots.

## Troubleshooting

- Error: ModuleNotFoundError: No module named crystal_toolkit
- Fix: Activate your Conda environment and run `pip install crystal-toolkit`.

- Error: Deployment shows `ELEMENTS_HO` or `pourbaix` import issues.
- Fix: In the deployed environment's `crystal_toolkit/components/pourbaix.py`, add a fallback `ELEMENTS_HO = {Element("H"), Element("O")}` if that constant is missing.

- Error: Cannot open http://127.0.0.1:8050.
- Fix: Confirm the app is running and port 8050 is not occupied.

- Error: BS/DOS panel is empty on the details page.
- Fix: Check whether step_15_band_str_d3 and step_16_dos_d3 contain vasprun.xml or vasprun.xml.gz.

## License

See LICENSE.
