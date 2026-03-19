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
- environment.yml: Recommended Conda environment definition.
- requirements.txt: Optional pip dependency list (mainly for Linux/macOS).

## Tech Stack

- Python 3.10
- Dash
- Crystal Toolkit
- pymatgen

## Quick Start

### Option 1 (Recommended for Windows/Conda)

Create environment (first time only):

```bash
conda env create -f environment.yml
```

Update environment (if web already exists):

```bash
conda env update -n web -f environment.yml
```

Activate and run:

```bash
conda activate web
python main.py
```

Open in browser:

```text
http://127.0.0.1:8050
```

### Option 2 (pip, usually Linux/macOS)

```bash
python -m pip install -r requirements.txt
python main.py
```

## UI Usage

- Home page: Browse all materials with filter and sort support.
- Details link: Navigate to the selected material details page.
- Left panel on details page: Material metadata, partition info, tolerance window, and custom bonding controls.
- Right panel on details page: Structure visualization and BS/DOS plots.

## Troubleshooting

- Error: ModuleNotFoundError: No module named crystal_toolkit
- Fix: Activate the web environment and install dependencies using environment.yml.

- Error: pip install fails on Windows while building boltztrap2.
- Fix: Use the Conda workflow with conda env create/update -f environment.yml.

- Error: Cannot open http://127.0.0.1:8050.
- Fix: Confirm the app is running and port 8050 is not occupied.

- Error: BS/DOS panel is empty on the details page.
- Fix: Check whether step_15_band_str_d3 and step_16_dos_d3 contain vasprun.xml or vasprun.xml.gz.

## License

See LICENSE.
