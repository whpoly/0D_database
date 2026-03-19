from __future__ import annotations

import json
import os
import urllib.parse
from functools import lru_cache
from itertools import combinations_with_replacement
from typing import Any

import dash
import crystal_toolkit.components as ctc
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
from pymatgen.core import Structure
from pymatgen.io.vasp.outputs import Vasprun


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "ZeroDB_test_data.json")
RADIUS_PATH = os.path.join(BASE_DIR, "atomic_radius.json")
DFT_ROOT_DIR = os.path.join(BASE_DIR, "ZeroDB_test_data", "ZeroDB_test_data")


def load_zerodb_columns(path: str) -> dict[str, dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not data:
        raise ValueError("ZeroDB_test_data.json is empty or invalid.")
    return data


ZERO_DB_COLUMNS = load_zerodb_columns(DATA_PATH)
ATOMIC_RADIUS = load_zerodb_columns(RADIUS_PATH)
FIRST_COLUMN = next(iter(ZERO_DB_COLUMNS.values()))
MATERIAL_IDS = sorted(FIRST_COLUMN.keys())


def row_for_material(material_id: str) -> dict[str, Any]:
    return {column: by_material.get(material_id) for column, by_material in ZERO_DB_COLUMNS.items()}


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def bandgap_energy(row: dict[str, Any]) -> Any:
    bandgap = row.get("bandgap")
    if isinstance(bandgap, dict):
        # Normalize known bandgap payload schemas to a scalar for DataTable numeric columns.
        for key in ("energy", "value", "Eg", "bandgap", "band_gap"):
            if key in bandgap:
                val = safe_float(bandgap.get(key))
                if val is not None:
                    return val
        return None
    return bandgap


def final_energy_value(row: dict[str, Any]) -> float | None:
    energy = row.get("final_energy")
    if isinstance(energy, dict):
        for key in ("energy", "value", "final_energy", "E", "e_tot"):
            if key in energy:
                val = safe_float(energy.get(key))
                if val is not None:
                    return val
        return None
    return safe_float(energy)


def extracted_molecules(row: dict[str, Any]) -> list[dict[str, Any]]:
    extracted = row.get("extracted_molecules")
    return extracted if isinstance(extracted, list) else []


def get_partition_entry(row: dict[str, Any], idx: int) -> dict[str, Any] | None:
    entries = extracted_molecules(row)
    if not entries:
        return None
    if idx < 0 or idx >= len(entries):
        return None
    return entries[idx]


def get_molecule_payload(entry: dict[str, Any] | None) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(entry, dict):
        return None, None
    molecule_keys = [k for k in entry.keys() if k != "decomposition"]
    if not molecule_keys:
        return None, None
    key = molecule_keys[0]
    payload = entry.get(key)
    if not isinstance(payload, dict):
        return key, None
    return key, payload


def tolerance_window(payload: dict[str, Any] | None) -> tuple[float, float]:
    if not payload:
        return 0.0, 0.0
    tol_values = payload.get("tol_window")
    if not isinstance(tol_values, list):
        return 0.0, 0.0
    nums = [safe_float(v) for v in tol_values]
    vals = [v for v in nums if v is not None]
    if not vals:
        return 0.0, 0.0
    return min(vals), max(vals)


def structure_from_row(row: dict[str, Any]) -> Structure | None:
    structure_dict = row.get("structure")
    if not isinstance(structure_dict, dict):
        return None
    try:
        return Structure.from_dict(structure_dict)
    except Exception:
        return None


def build_custom_cutoff_rows_for_structure(
    structure: Structure | None, tolerance: float
) -> tuple[list[dict[str, Any]], list[str]]:
    if structure is None:
        return [], []

    elements = sorted({site.specie.symbol for site in structure.sites})
    if not elements:
        return [], []

    updated_rows: list[dict[str, Any]] = []
    missing_elements: set[str] = set()

    for elem_a, elem_b in combinations_with_replacement(elements, 2):
        r_a = safe_float(ATOMIC_RADIUS.get(elem_a))
        r_b = safe_float(ATOMIC_RADIUS.get(elem_b))

        if r_a is None or r_b is None:
            if r_a is None:
                missing_elements.add(elem_a)
            if r_b is None:
                missing_elements.add(elem_b)
            updated_rows.append({"A": elem_a, "B": elem_b, "A—B": 0})
            continue

        cutoff = round((r_a + r_b) * (1 + tolerance), 4)
        updated_rows.append({"A": elem_a, "B": elem_b, "A—B": cutoff})

    return updated_rows, sorted(missing_elements)


def resolve_vasprun_path(step_dir: str) -> str | None:
    for filename in ("vasprun.xml.gz", "vasprun.xml"):
        candidate = os.path.join(step_dir, filename)
        if os.path.isfile(candidate):
            return candidate
    return None


@lru_cache(maxsize=64)
def load_bs_dos_for_material(material_id: str):
    material_dir = os.path.join(DFT_ROOT_DIR, material_id)
    if not os.path.isdir(material_dir):
        return None, None, f"DFT folder not found for {material_id}."

    bs = None
    dos = None
    errors: list[str] = []

    band_dir = os.path.join(material_dir, "step_15_band_str_d3")
    band_vasprun = resolve_vasprun_path(band_dir)
    if band_vasprun is None:
        errors.append("Bandstructure vasprun.xml(.gz) not found")
    else:
        try:
            band_run = Vasprun(
                band_vasprun,
                parse_projected_eigen=False,
                parse_potcar_file=False,
            )
            kpoints_path = os.path.join(band_dir, "KPOINTS")
            if os.path.isfile(kpoints_path):
                bs = band_run.get_band_structure(kpoints_filename=kpoints_path, line_mode=True)
            else:
                bs = band_run.get_band_structure(line_mode=True)
        except Exception as exc:
            errors.append(f"Bandstructure parse failed: {exc}")

    dos_dir = os.path.join(material_dir, "step_16_dos_d3")
    dos_vasprun = resolve_vasprun_path(dos_dir)
    if dos_vasprun is None:
        errors.append("DOS vasprun.xml(.gz) not found")
    else:
        try:
            dos_run = Vasprun(
                dos_vasprun,
                parse_projected_eigen=False,
                parse_potcar_file=False,
            )
            dos = dos_run.complete_dos
            if dos is None:
                errors.append("Complete DOS not available in vasprun")
        except Exception as exc:
            errors.append(f"DOS parse failed: {exc}")

    error_text = " ; ".join(errors) if errors else None
    return bs, dos, error_text


def make_table_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mid in MATERIAL_IDS:
        row = row_for_material(mid)
        rows.append(
            {
                "material_id": mid,
                "pretty_formula": row.get("pretty_formula"),
                "chem_sys": row.get("chem_sys"),
                "nsites": row.get("nsites"),
                "nelements": row.get("nelements"),
                "final_energy": final_energy_value(row),
                "total_magnetic_moment": safe_float(row.get("total_magnetic_moment")),
                "bandgap": bandgap_energy(row),
                "details": f"[Details](/details?mid={urllib.parse.quote(mid)})",
            }
        )
    return rows


TABLE_ROWS = make_table_rows()


app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server
structure_component = ctc.StructureMoleculeComponent(id="structure")


def create_table_layout() -> html.Div:
    columns = [
        {"name": "material_id", "id": "material_id", "type": "text"},
        {"name": "pretty_formula", "id": "pretty_formula", "type": "text"},
        {"name": "chem_sys", "id": "chem_sys", "type": "text"},
        {"name": "nsites", "id": "nsites", "type": "numeric"},
        {"name": "nelements", "id": "nelements", "type": "numeric"},
        {"name": "final_energy", "id": "final_energy", "type": "numeric"},
        {"name": "total_magnetic_moment", "id": "total_magnetic_moment", "type": "numeric"},
        {"name": "bandgap", "id": "bandgap", "type": "numeric"},
        {"name": "", "id": "details", "type": "text", "presentation": "markdown"},
    ]

    return html.Div(
        [
            html.H1("ZeroDB Materials Dataset", style={"textAlign": "center", "margin": "20px", "fontSize": "52px"}),
            dash_table.DataTable(
                id="data-table",
                columns=columns,
                data=TABLE_ROWS,
                filter_action="native",
                sort_action="native",
                sort_mode="multi",
                page_action="native",
                page_size=20,
                filter_options={"case": "insensitive", "placeholder_text": "filter data ..."},
                style_cell={
                    "textAlign": "left",
                    "padding": "10px",
                    "minWidth": "100px",
                    "width": "150px",
                    "maxWidth": "240px",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                    "border": "None",
                    "backgroundColor": "#ffffff",
                },
                style_header={
                    "fontWeight": "bold",
                    "whiteSpace": "normal",
                    "backgroundColor": "#ffffff",
                    "height": "auto",
                    "border": "None",
                },
                style_data={"whiteSpace": "normal", "height": "auto", "border": "None"},
                style_data_conditional=[
                    {
                        "if": {"column_id": "details"},
                        "cursor": "pointer",
                        "color": "#0d6efd",
                        "textDecoration": "underline",
                    }
                ],
                style_table={"overflowX": "auto"},
            ),
        ]
    )


def create_details_layout() -> html.Div:
    section_title_style = {"fontSize": "28px", "textAlign": "center", "margin": "0"}
    left_panel_style = {"flex": "1.2", "minWidth": "500px"}
    right_panel_style = {
        "flex": "0 1 920px",
        "width": "920px",
        "maxWidth": "100%",
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "center",
        "marginLeft": "0px",
        "gap": "0px",
    }
    return html.Div(
        [
            dcc.Link(
                "Back to Table",
                href="/",
                style={
                    "padding": "10px 20px",
                    "background": "#6c757d",
                    "color": "white",
                    "borderRadius": "5px",
                    "textDecoration": "none",
                    "display": "inline-block",
                    "margin": "20px",
                },
            ),
            html.H1(id="material-title", style={"textAlign": "center", "margin": "0px", "fontSize": "34px"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Material Information", style=section_title_style),
                            html.Div(
                                id="material-details",
                                style={
                                    "padding": "20px",
                                    "backgroundColor": "white",
                                    "borderRadius": "5px",
                                    "textAlign": "left",
                                },
                            ),
                            html.H2("Molecule Partition", style={"fontSize": "24px", "textAlign": "center", "marginTop": "24px", "marginBottom": "10px"}),
                            dcc.Dropdown(id="partition-dropdown", clearable=False),
                            html.Div(id="decomposition-display", style={"marginTop": "12px"}),
                            html.H2("Bond Window", style={"fontSize": "24px", "textAlign": "center", "marginTop": "24px", "marginBottom": "10px"}),
                            dcc.Slider(
                                id="window-slider",
                                min=0.0,
                                max=0.0,
                                step=0.001,
                                value=0.0,
                                marks=None,
                                updatemode="mouseup",
                                tooltip={"always_visible": False, "placement": "bottom"},
                            ),
                            html.Button(
                                "Apply To Visualization Custom Bonds",
                                id="apply-custom-bonds-btn",
                                n_clicks=0,
                                style={
                                    "marginTop": "10px",
                                    "padding": "8px 14px",
                                    "border": "1px solid #ced4da",
                                    "borderRadius": "6px",
                                    "backgroundColor": "#f8f9fa",
                                    "cursor": "pointer",
                                },
                            ),
                            html.Div(id="custom-apply-status", style={"marginTop": "10px"}),
                        ],
                        style=left_panel_style,
                    ),
                    html.Div(
                        [
                            html.H2("Structure Visualization", style=section_title_style),
                            html.Div(
                                structure_component.layout(),
                                style={
                                    "padding": "20px",
                                    "backgroundColor": "white",
                                    "borderRadius": "5px",
                                    "height": "520px",
                                    "width": "100%",
                                    "maxWidth": "100%",
                                    "margin": "0 auto",
                                    "boxSizing": "border-box",
                                },
                            ),
                            html.H2("Bandstructure / PDOS", style={"fontSize": "28px", "textAlign": "center", "margin": "6px 0 0 0"}),
                            html.Div(
                                id="bs-dos-visualization",
                                style={"width": "100%", "maxWidth": "100%", "margin": "0 auto"},
                            ),
                        ],
                        style=right_panel_style,
                    ),
                ],
                style={
                    "display": "flex",
                    "flexDirection": "row",
                    "flexWrap": "wrap",
                    "gap": "24px",
                    "alignItems": "flex-start",
                    "margin": "30px 20px",
                },
            ),
        ]
    )


app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="selected-material-id"),
        dcc.Store(id="pending-custom-cutoffs"),
        html.Div(id="page-content"),
    ]
)

ctc.register_crystal_toolkit(app=app, layout=app.layout)


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname: str | None):
    if pathname == "/details":
        return create_details_layout()
    return create_table_layout()


@app.callback(Output("selected-material-id", "data"), Input("url", "pathname"), Input("url", "search"))
def select_material_from_url(pathname: str | None, search: str | None):
    if pathname != "/details":
        raise dash.exceptions.PreventUpdate

    parsed = urllib.parse.parse_qs((search or "").lstrip("?"))
    material_id = parsed.get("mid", [MATERIAL_IDS[0]])[0]
    if material_id not in MATERIAL_IDS:
        material_id = MATERIAL_IDS[0]
    return material_id


@app.callback(Output("material-title", "children"), Input("selected-material-id", "data"))
def update_material_title(material_id: str | None):
    if material_id is None:
        raise dash.exceptions.PreventUpdate
    return f"Material Details: {material_id}"


@app.callback(Output(structure_component.id(), "data"), Input("selected-material-id", "data"))
def update_structure(material_id: str | None):
    if material_id is None:
        raise dash.exceptions.PreventUpdate

    structure = structure_from_row(row_for_material(material_id))
    if structure is None:
        raise dash.exceptions.PreventUpdate
    return structure


@app.callback(Output("bs-dos-visualization", "children"), Input("selected-material-id", "data"))
def update_bs_dos_visualization(material_id: str | None):
    if material_id is None:
        raise dash.exceptions.PreventUpdate

    bs, dos, error_text = load_bs_dos_for_material(material_id)
    if bs is None and dos is None:
        return html.Div(
            error_text or "No bandstructure or DOS data available.",
            style={"backgroundColor": "#f6f7f9", "padding": "12px", "borderRadius": "4px"},
        )

    try:
        fig = ctc.BandstructureAndDosComponent.get_figure(bs, dos)

        def _tighten_axis_spacing(layout_dict: dict[str, Any]) -> None:
            # Keep axis titles clear of tick labels on both BS and DOS subplots.
            for axis_key, standoff in (
                ("xaxis", 6),
                ("xaxis2", 12),
                ("yaxis", 2),
                ("yaxis2", 6),
            ):
                axis = layout_dict.get(axis_key)
                if not isinstance(axis, dict):
                    continue

                axis["automargin"] = True
                title = axis.get("title")
                if isinstance(title, str):
                    axis["title"] = {"text": title, "standoff": standoff}
                elif isinstance(title, dict):
                    title["standoff"] = standoff

        if isinstance(fig, dict):
            layout = fig.setdefault("layout", {})
            layout.pop("width", None)
            layout["autosize"] = True
            layout["height"] = 560
            layout["margin"] = {"l": 20, "r": 20, "t": 20, "b": 20}
            _tighten_axis_spacing(layout)
        elif hasattr(fig, "update_layout") and hasattr(fig, "layout"):
            fig.update_layout(autosize=True, height=560, margin={"l": 20, "r": 20, "t": 20, "b": 20})
            _tighten_axis_spacing(fig.layout)
        graph_block = dcc.Graph(
            figure=fig,
            config={"displayModeBar": False},
            responsive=True,
            style={"width": "100%", "margin": "0 auto"},
        )
    except Exception as exc:
        return html.Div(
            f"Failed to render BS/DOS figure: {exc}",
            style={"backgroundColor": "#f6f7f9", "padding": "12px", "borderRadius": "4px"},
        )

    if not error_text:
        return graph_block

    return html.Div(
        [
            graph_block,
            html.Div(
                error_text,
                style={
                    "marginTop": "8px",
                    "backgroundColor": "#fff7e6",
                    "border": "1px solid #ffe58f",
                    "padding": "8px",
                    "borderRadius": "4px",
                },
            ),
        ]
    )


@app.callback(Output("material-details", "children"), Input("selected-material-id", "data"))
def display_material_details(material_id: str | None):
    if material_id is None:
        raise dash.exceptions.PreventUpdate

    row = row_for_material(material_id)
    details_data = {
        "material_id": material_id,
        "pretty_formula": row.get("pretty_formula"),
        "chem_sys": row.get("chem_sys"),
        "space_group": row.get("space_group", {}).get("symbol") if isinstance(row.get("space_group"), dict) else row.get("space_group"),
        "nsites": row.get("nsites"),
        "nelements": row.get("nelements"),
        "elements": row.get("elements"),
        "final_energy": row.get("final_energy"),
        "total_magnetic_moment": row.get("total_magnetic_moment"),
        "bandgap": bandgap_energy(row),
    }

    return html.Div(
        [
            html.Div(
                [html.Strong(f"{key}: "), html.Span(format_value(value))],
                style={"margin": "10px 0"},
            )
            for key, value in details_data.items()
        ]
    )


@app.callback(
    Output("partition-dropdown", "options"),
    Output("partition-dropdown", "value"),
    Input("selected-material-id", "data"),
)
def update_partition_options(material_id: str | None):
    if material_id is None:
        raise dash.exceptions.PreventUpdate

    row = row_for_material(material_id)
    entries = extracted_molecules(row)

    if not entries:
        return [{"label": "No partition data", "value": 0}], 0

    options = []
    for idx, entry in enumerate(entries):
        decomposition = entry.get("decomposition", "(no decomposition)")
        options.append({"label": f"Partition {idx + 1}: {decomposition}", "value": idx})

    return options, 0


@app.callback(
    Output("window-slider", "min"),
    Output("window-slider", "max"),
    Output("window-slider", "value"),
    Output("window-slider", "step"),
    Input("selected-material-id", "data"),
    Input("partition-dropdown", "value"),
)
def sync_tolerance_window_slider(material_id: str | None, partition_idx: int | None):
    if material_id is None:
        raise dash.exceptions.PreventUpdate

    row = row_for_material(material_id)
    entry = get_partition_entry(row, int(partition_idx or 0))
    _, payload = get_molecule_payload(entry)
    tol_min, tol_max = tolerance_window(payload)
    step = max((tol_max - tol_min) / 200.0, 0.001)
    return tol_min, tol_max, tol_max, step


@app.callback(Output("decomposition-display", "children"), Input("selected-material-id", "data"), Input("partition-dropdown", "value"))
def update_decomposition(material_id: str | None, partition_idx: int | None):
    if material_id is None:
        raise dash.exceptions.PreventUpdate

    row = row_for_material(material_id)
    entry = get_partition_entry(row, int(partition_idx or 0))
    if entry is None:
        return html.Div("No extracted_molecules data.")

    mol_key, payload = get_molecule_payload(entry)
    if payload is None:
        return html.Div([html.Strong("decomposition: "), html.Span(format_value(entry.get("decomposition")))])

    return html.Div(
        [
            html.Div([html.Strong("decomposition: "), html.Span(format_value(entry.get("decomposition")))]),
            html.Div([html.Strong("molecule_key: "), html.Span(format_value(mol_key))]),
            html.Div([html.Strong("reduced_formula: "), html.Span(format_value(payload.get("reduced_formula")))]),
            html.Div([html.Strong("multiplicity: "), html.Span(format_value(payload.get("multiplicity")))]),
            html.Div([html.Strong("HTC_mol_name: "), html.Span(format_value(payload.get("HTC_mol_name")))]),
            html.Div([html.Strong("url_to_molecule: "), html.Span(format_value(payload.get("url_to_molecule")))]),
        ],
        style={"lineHeight": "1.7", "padding": "8px", "backgroundColor": "#f6f7f9", "borderRadius": "4px"},
    )


@app.callback(
    Output(structure_component.id("bonding_algorithm"), "value"),
    Output(structure_component.id("bonding_algorithm_custom_cutoffs"), "data", allow_duplicate=True),
    Output("pending-custom-cutoffs", "data"),
    Output("custom-apply-status", "children"),
    Input("apply-custom-bonds-btn", "n_clicks"),
    State("selected-material-id", "data"),
    State("partition-dropdown", "value"),
    State("window-slider", "value"),
    prevent_initial_call=True,
)
def apply_custom_bonds(
    n_clicks: int,
    material_id: str | None,
    partition_idx: int | None,
    selected_tol: float | None,
):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if material_id is None:
        raise dash.exceptions.PreventUpdate

    row = row_for_material(material_id)
    entry = get_partition_entry(row, int(partition_idx or 0))
    _, payload = get_molecule_payload(entry)
    tol_min, tol_max = tolerance_window(payload)
    use_tol = tol_max if selected_tol is None else selected_tol
    use_tol = max(tol_min, min(tol_max, use_tol))
    structure = structure_from_row(row)

    updated_rows, missing_elements = build_custom_cutoff_rows_for_structure(structure, use_tol)
    if not updated_rows:
        return (
            "CutOffDictNN",
            dash.no_update,
            dash.no_update,
            "Could not build custom cutoffs from structure data.",
        )

    status = (
        f"Applied CutOffDictNN with selected={use_tol:.4f} in window=[{tol_min:.4f}, {tol_max:.4f}] "
        f"for {len(updated_rows)} element pairs."
    )
    if missing_elements:
        status += f" Missing atomic radius for: {', '.join(missing_elements)}."

    return "CutOffDictNN", updated_rows, {"rows": updated_rows}, status


@app.callback(
    Output(structure_component.id("bonding_algorithm_custom_cutoffs"), "data", allow_duplicate=True),
    Input("pending-custom-cutoffs", "data"),
    Input(structure_component.id("bonding_algorithm_custom_cutoffs_container"), "style"),
    State(structure_component.id("bonding_algorithm"), "value"),
    prevent_initial_call=True,
)
def push_pending_custom_cutoffs(
    pending_data: dict[str, Any] | None,
    custom_cutoff_style: dict[str, Any] | None,
    bonding_algorithm: str | None,
):
    if not pending_data:
        raise dash.exceptions.PreventUpdate

    if bonding_algorithm != "CutOffDictNN":
        raise dash.exceptions.PreventUpdate

    style = custom_cutoff_style or {}
    if style.get("display") == "none":
        raise dash.exceptions.PreventUpdate

    rows = pending_data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise dash.exceptions.PreventUpdate

    return rows


if __name__ == "__main__":
    app.run(debug=True, port=8050, dev_tools_ui=False)