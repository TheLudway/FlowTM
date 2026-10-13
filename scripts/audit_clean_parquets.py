# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
scripts/audit_clean_parquets.py
===============================
Telemetry data auditor for cleaned trunk validation and alighting parquets.
"""

from pathlib import Path

import polars as pl

BASE_PATH = Path("data/processed/validaciones_salidas")
ALIGHTINGS_PATH = BASE_PATH / "salidas_troncal"
VALIDATIONS_PATH = BASE_PATH / "validacion_troncal"


def audit_directory(dir_path: Path) -> dict:
    clean_files = list(dir_path.glob("*_clean.parquet"))
    total_size = sum(f.stat().st_size for f in clean_files)
    total_rows = 0
    sample_df = None
    first_file = None

    for f in clean_files:
        lf = pl.scan_parquet(f)
        total_rows += lf.select(pl.len()).collect().item()
        if sample_df is None:
            first_file = f.name
            sample_df = pl.read_parquet(f).head(5)

    return {
        "num_files": len(clean_files),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "total_rows": total_rows,
        "first_file": first_file,
        "sample_df": sample_df,
    }


alightings_audit = audit_directory(ALIGHTINGS_PATH)
validations_audit = audit_directory(VALIDATIONS_PATH)

print("=" * 80)
print("AUDIT: TRUNK ALIGHTINGS (Turnstiles)")
print("=" * 80)
print(f"Clean files:         {alightings_audit['num_files']}")
print(f"Total rows:          {alightings_audit['total_rows']:,}")
print(f"Total disk size:     {alightings_audit['total_size_mb']} MB")
print(f"Sample file:         {alightings_audit['first_file']}")
print("\nFull column schema:")
if alightings_audit["sample_df"] is not None:
    for col, dtype in alightings_audit["sample_df"].schema.items():
        print(f"  - {col:<56}: {dtype}")
    print("\nFirst 5 records (key business and normalization columns):")
    cols_sal = [
        "CODIGO_ESTACION",
        "CODIGO_TRONCAL",
        "NOMBRE_ESTACION_CANONICO",
        "Salidas_S",
        "Tiempo",
    ]
    print(alightings_audit["sample_df"].select(cols_sal))

print("\n" + "=" * 80)
print("AUDIT: TRUNK VALIDATIONS (Boardings)")
print("=" * 80)
print(f"Clean files:         {validations_audit['num_files']}")
print(f"Total rows:          {validations_audit['total_rows']:,}")
print(f"Total disk size:     {validations_audit['total_size_mb']} MB")
print(f"Sample file:         {validations_audit['first_file']}")
print("\nFull column schema:")
if validations_audit["sample_df"] is not None:
    for col, dtype in validations_audit["sample_df"].schema.items():
        print(f"  - {col:<56}: {dtype}")
    print("\nFirst 5 records (key business and normalization columns):")
    cols_val = [
        "CODIGO_ESTACION",
        "CODIGO_TRONCAL",
        "NOMBRE_ESTACION_CANONICO",
        "Fecha_Transaccion",
        "Day_Group_Type",
        "Hora_Pico_SN",
    ]
    print(validations_audit["sample_df"].select(cols_val))
