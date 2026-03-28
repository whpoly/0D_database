from __future__ import annotations

import argparse
import gzip
import json
import shutil
from pathlib import Path
from typing import Any

from monty.json import MontyEncoder
from pymatgen.io.vasp.outputs import Vasprun


DEFAULT_METADATA_JSON = Path("ZeroDB_test_data.json")
DEFAULT_DFT_ROOT = Path("ZeroDB_test_data") / "ZeroDB_test_data"
DEFAULT_OUTPUT_ROOT = Path("dos_bs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Parse bandstructure and DOS results from VASP outputs and write them "
            "to separate pymatgen-serialized JSON files."
        )
    )
    parser.add_argument(
        "--metadata-json",
        type=Path,
        default=DEFAULT_METADATA_JSON,
        help="Path to ZeroDB_test_data.json, used to determine the material_id list.",
    )
    parser.add_argument(
        "--dft-root",
        type=Path,
        default=DEFAULT_DFT_ROOT,
        help="Root directory that contains one folder per material.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Output root directory for per-material bs.json and dos.json files.",
    )
    parser.add_argument(
        "--bs-filename",
        default="bs.json",
        help="Filename used for each per-material bandstructure JSON.",
    )
    parser.add_argument(
        "--dos-filename",
        default="dos.json",
        help="Filename used for each per-material DOS JSON.",
    )
    parser.add_argument(
        "--backup-dir-suffix",
        default=".bak",
        help="Backup suffix for an existing output root directory. Use an empty string to disable backups.",
    )
    parser.add_argument(
        "--gzip-output",
        action="store_true",
        help="Write bs/dos cache files as .json.gz to reduce disk usage.",
    )
    return parser.parse_args()


def load_columnar_json(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"Invalid or empty dataset JSON: {path}")
    return payload


def material_ids_from_metadata(metadata_json: Path) -> list[str]:
    payload = load_columnar_json(metadata_json)
    first_column = next(iter(payload.values()))
    if not isinstance(first_column, dict):
        raise ValueError("Metadata JSON is not in the expected column-wise format.")
    return sorted(first_column.keys())


def resolve_vasprun_path(step_dir: Path) -> Path | None:
    for filename in ("vasprun.xml.gz", "vasprun.xml"):
        candidate = step_dir / filename
        if candidate.is_file():
            return candidate
    return None


def to_plain_json(value: Any) -> Any:
    return json.loads(json.dumps(value, cls=MontyEncoder))


def load_bandstructure(material_dir: Path) -> dict[str, Any] | None:
    band_dir = material_dir / "step_15_band_str_d3"
    vasprun_path = resolve_vasprun_path(band_dir)
    if vasprun_path is None:
        return None

    band_run = Vasprun(
        str(vasprun_path),
        parse_projected_eigen=False,
        parse_potcar_file=False,
    )
    kpoints_path = band_dir / "KPOINTS"
    if kpoints_path.is_file():
        band_structure = band_run.get_band_structure(
            kpoints_filename=str(kpoints_path),
            line_mode=True,
        )
    else:
        band_structure = band_run.get_band_structure(line_mode=True)
    return to_plain_json(band_structure.as_dict())


def load_dos(material_dir: Path) -> dict[str, Any] | None:
    dos_dir = material_dir / "step_16_dos_d3"
    vasprun_path = resolve_vasprun_path(dos_dir)
    if vasprun_path is None:
        return None

    dos_run = Vasprun(
        str(vasprun_path),
        parse_projected_eigen=False,
        parse_potcar_file=False,
    )
    complete_dos = dos_run.complete_dos
    if complete_dos is None:
        return None
    return to_plain_json(complete_dos.as_dict())


def maybe_backup(path: Path, backup_suffix: str) -> Path | None:
    if not path.exists() or not backup_suffix:
        return None
    backup_path = path.with_name(path.name + backup_suffix)
    if backup_path.exists():
        shutil.rmtree(backup_path)
    shutil.copytree(path, backup_path)
    return backup_path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == ".gz" else path.open
    with opener(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def output_path(target_dir: Path, filename: str, gzip_output: bool) -> Path:
    if gzip_output and not filename.endswith(".gz"):
        filename = f"{filename}.gz"
    return target_dir / filename


def main() -> None:
    args = parse_args()
    metadata_json = args.metadata_json.resolve()
    dft_root = args.dft_root.resolve()
    output_root = args.output_root.resolve()

    material_ids = material_ids_from_metadata(metadata_json)
    backup_root = maybe_backup(output_root, args.backup_dir_suffix)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    for index, material_id in enumerate(material_ids, start=1):
        material_dir = dft_root / material_id
        target_dir = output_root / material_id
        target_dir.mkdir(parents=True, exist_ok=True)

        if not material_dir.is_dir():
            write_json(output_path(target_dir, args.bs_filename, args.gzip_output), None)
            write_json(output_path(target_dir, args.dos_filename, args.gzip_output), None)
            print(f"[{index}/{len(material_ids)}] {material_id}: material folder missing")
            continue

        bs_error: str | None = None
        dos_error: str | None = None
        bs_payload: Any = None
        dos_payload: Any = None

        try:
            bs_payload = load_bandstructure(material_dir)
        except Exception as exc:  # pragma: no cover - batch best effort
            bs_error = f"bandstructure failed ({type(exc).__name__}: {exc})"

        try:
            dos_payload = load_dos(material_dir)
        except Exception as exc:  # pragma: no cover - batch best effort
            dos_error = f"dos failed ({type(exc).__name__}: {exc})"

        write_json(output_path(target_dir, args.bs_filename, args.gzip_output), bs_payload)
        write_json(output_path(target_dir, args.dos_filename, args.gzip_output), dos_payload)

        messages = []
        if bs_error:
            messages.append(bs_error)
        else:
            messages.append(f"bandstructure {'ok' if bs_payload is not None else 'missing'}")

        if dos_error:
            messages.append(dos_error)
        else:
            messages.append(f"dos {'ok' if dos_payload is not None else 'missing'}")

        print(f"[{index}/{len(material_ids)}] {material_id}: " + ", ".join(messages))

    if backup_root is not None:
        print(f"Backup created: {backup_root}")
    print(f"Per-material BS/DOS JSON files written under: {output_root}")


if __name__ == "__main__":
    main()
