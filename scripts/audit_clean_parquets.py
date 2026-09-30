import polars as pl
from pathlib import Path

base_path = Path("data/processed/validaciones_salidas")
salidas_path = base_path / "salidas_troncal"
validaciones_path = base_path / "validacion_troncal"

def audit_dir(p: Path):
    clean_files = sorted(list(p.glob("*_clean.parquet")))
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

salidas_audit = audit_dir(salidas_path)
validaciones_audit = audit_dir(validaciones_path)

print("=" * 80)
print("AUDITORIA: SALIDAS TRONCALES (Torniquetes)")
print("=" * 80)
print("Archivos limpios:     ", salidas_audit["num_files"])
print(f"Filas totales:         {salidas_audit['total_rows']:,}")
print("Tamano total en disco: ", salidas_audit["total_size_mb"], "MB")
print("Archivo de muestra:   ", salidas_audit["first_file"])
print("\nSchema completo de columnas:")
for col, dtype in salidas_audit["sample_df"].schema.items():
    print(f"  - {col:<56}: {dtype}")
print("\nPrimeros 5 registros (columnas clave de negocio y normalizacion):")
cols_sal = ["CODIGO_ESTACION", "CODIGO_TRONCAL", "NOMBRE_ESTACION_CANONICO", "Salidas_S", "Tiempo"]
print(salidas_audit["sample_df"].select(cols_sal))

print("\n" + "=" * 80)
print("AUDITORIA: VALIDACIONES TRONCALES (Entradas)")
print("=" * 80)
print("Archivos limpios:     ", validaciones_audit["num_files"])
print(f"Filas totales:         {validaciones_audit['total_rows']:,}")
print("Tamano total en disco: ", validaciones_audit["total_size_mb"], "MB")
print("Archivo de muestra:   ", validaciones_audit["first_file"])
print("\nSchema completo de columnas:")
for col, dtype in validaciones_audit["sample_df"].schema.items():
    print(f"  - {col:<56}: {dtype}")
print("\nPrimeros 5 registros (columnas clave de negocio y normalizacion):")
cols_val = ["CODIGO_ESTACION", "CODIGO_TRONCAL", "NOMBRE_ESTACION_CANONICO", "Fecha_Transaccion", "Day_Group_Type", "Hora_Pico_SN"]
print(validaciones_audit["sample_df"].select(cols_val))
