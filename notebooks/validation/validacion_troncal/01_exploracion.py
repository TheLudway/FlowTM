import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    return


@app.cell
def _():
    from pathlib import Path

    import marimo as mo
    import polars as pl

    return Path, mo, pl


@app.cell
def _(mo):
    mo.md(r"""
    # Auditoría y Exploración: Validaciones Troncales
    *Componente:* Ingesta y Diagnóstico de Datos (validacion_troncal)
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Fase 1: Auditoría y Diagnóstico Exhaustivo de Esquemas
            En esta fase se utiliza Polars en modo Lazy Evaluation para auditar automáticamente:
            - Nombres reales de columnas.
            - Tipos de datos primitivos en memoria.
            - Porcentaje exacto de valores nulos o ausentes.
            - Valores de muestra reales por campo.
    """)
    return


@app.cell
def _(Path, mo, pl):
    validations_path = Path("data/processed/validaciones_salidas/validacion_troncal")
    validation_file = next(validations_path.rglob("*.parquet"), None)

    if validation_file:
        validations_df = pl.read_parquet(validation_file)
        audit_results = [
            {
                "#": i,
                "COLUMNA": col,
                "TIPO": str(validations_df[col].dtype),
                "% NULOS": round(
                    (validations_df[col].is_null().sum() / len(validations_df)) * 100, 2
                ),
                "VALOR EJEMPLO": (
                    str(validations_df[col][0])[:25] if len(validations_df) > 0 else "N/A"
                ),
            }
            for i, col in enumerate(validations_df.columns, 1)
        ]
        phase1_table = pl.DataFrame(audit_results)
    else:
        validations_df = None
        phase1_table = pl.DataFrame()

    mo.md(
        f"### Resultados de Auditoría ({validation_file.name if validation_file else 'No hallado'})"
    )
    return validations_df, phase1_table


@app.cell
def _(mo, phase1_table):
    mo.ui.table(phase1_table)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Fase 2: Exploración de Patrones Categóricos
    Para validar la consistencia en el contenido de las variables categóricas y verificar las divergencias textuales, se ejecutó el siguiente script:
    """)
    return


@app.cell
def _(mo, pl, validations_df):
    if "validations_df" in globals() and validations_df is not None:
        columns = validations_df.columns

        station_col = "Estacion_Parada" if "Estacion_Parada" in columns else next((c for c in columns if "estacion" in c.lower()), None)
        stations_sample = (
            validations_df.select(station_col).unique().head(8)
            if station_col
            else pl.DataFrame({"Info": ["No se halló columna de estación"]})
        )

        peak_hours_dist = (
            validations_df["Hora_Pico_SN"].value_counts()
            if "Hora_Pico_SN" in columns
            else pl.DataFrame({"Info": ["Sin Hora_Pico_SN"]})
        )

        day_types_dist = (
            validations_df["Day_Group_Type"].value_counts()
            if "Day_Group_Type" in columns
            else pl.DataFrame({"Info": ["Sin Day_Group_Type"]})
        )

        user_profiles_dist = (
            validations_df["Nombre_Perfil"].value_counts().head(6)
            if "Nombre_Perfil" in columns
            else pl.DataFrame({"Info": ["Sin Nombre_Perfil"]})
        )
    else:
        stations_sample = peak_hours_dist = day_types_dist = user_profiles_dist = pl.DataFrame({"Error": ["df_v no disponible"]})

    # Layout
    phase2_view = mo.vstack([
        mo.md("## Fase 2: Exploración de Patrones Categóricos en Validaciones"),
        mo.md("#### 1. Patrón en Nombres de Estaciones (Muestra)"),
        mo.ui.table(stations_sample),
        mo.md("#### 2. Distribución de Hora Pico (Hora_Pico_SN)"),
        mo.ui.table(peak_hours_dist),
        mo.md("#### 3. Tipos de Día (Day_Group_Type)"),
        mo.ui.table(day_types_dist),
        mo.md("#### 4. Perfiles de Usuario Masivos (Nombre_Perfil)"),
        mo.ui.table(user_profiles_dist)
    ])

    phase2_view
    return


@app.cell
def _(mo):
    phase3_view = mo.vstack([
        mo.md(
            r"""
            ## Fase 3: Hallazgos Clave y Decisiones de Arquitectura

            Basándonos en la exploración de datos realizada en las Fases 1 y 2, se establecen las siguientes decisiones de ingeniería para el pipeline de *FlowTM*:

            ---

            ### 1. El Código de 5 Dígitos (XXXXX) como Llave Primaria Determinista
            - *Descubrimiento:* Todas las estaciones en la columna Estacion_Parada de validaciones inician con un código numérico de 5 dígitos entre paréntesis (ej. (08000) Portal Tunal).
            - *Decisión de Arquitectura:* Se descarta el uso de búsquedas difusas (fuzzy matching) sobre el texto descriptivo.
            - *Impacto:* La extracción del código numérico mediante expresiones regulares permite realizar un cruce relacional exacto e indexado en $O(1)$ con la columna stop_code del estándar GTFS (stops.txt).

            ---

            ### 2. Convención Geográfica y Zonificación
            - *Descubrimiento:* Los primeros dos dígitos del código identifican la Troncal / Zona Operativa (ej. 08 representa la Troncal Caracas Sur / Tunal / Usme).
            - *Decisión de Arquitectura:* Se creará una columna derivada CODIGO_TRONCAL para permitir agregaciones y filtrados por cuenca operativa de forma directa sin sobrecoste computacional.

            ---

            ### 3. Estandarización de Texto Canónico
            - *Descubrimiento:* Se identifican caracteres especiales, acentos y variaciones ortográficas en los nombres textuales.
            - *Decisión de Arquitectura:* Se aplicará una limpieza léxica vectorizada (remoción de acentos, conversión a mayúsculas y eliminación del prefijo numérico) para generar NOMBRE_ESTACION_CANONICO, garantizando consistencia en los reportes y visualizaciones.
            """
        )
    ])

    phase3_view
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ##Fase 4: Función Universal de Normalización, se formula la expresión vectorizada de Polars que realiza la extracción del código de 5 dígitos, genera el código de troncal de 2 dígitos y limpian el nombre canónico de la estación
    """)
    return


@app.cell
def _(mo, pl, validations_df):
    def normalize_stations(column_name: str) -> list[pl.Expr]:
        return [
            pl.col(column_name)
            .str.extract(r"\((\d{5})\)", 1)
            .alias("CODIGO_ESTACION"),
            pl.col(column_name)
            .str.extract(r"\((\d{2})\)\d{3}", 1)
            .alias("CODIGO_TRONCAL"),
            (
                pl.col(column_name)
                .str.replace(r"^\(\d+\)\s*", "")
                .str.to_uppercase()
                .str.replace(r"[ÁÀÄÂ]", "A")
                .str.replace(r"[ÉÈËÊ]", "E")
                .str.replace(r"[ÍÌÏÎ]", "I")
                .str.replace(r"[ÓÒÖÔ]", "O")
                .str.replace(r"[ÚÙÜÛ]", "U")
                .str.replace(r"[\u2013\u2014]", "-")
                .str.strip_chars()
                .alias("NOMBRE_ESTACION_CANONICO")
            ),
        ]

    if "validations_df" in globals() and validations_df is not None:
        phase4_columns = validations_df.columns
        phase4_station_col = (
            "Estacion_Parada"
            if "Estacion_Parada" in phase4_columns
            else next((c for c in phase4_columns if "estacion" in c.lower()), phase4_columns[0])
        )

        normalized_sample = (
            validations_df.select([phase4_station_col, *normalize_stations(phase4_station_col)])
            .unique(subset=["CODIGO_ESTACION"])
            .head(10)
        )

    else:
        normalized_sample = pl.DataFrame(
            {"Error": ["df_v no está disponible para probar la normalización"]}
        )

    phase4_view = mo.vstack([
        mo.md(
            "## Fase 4: Función Universal de Normalización de Estaciones"
        ),
        mo.md(
            "A continuación se presenta el resultado de aplicar la transformación vectorizada en Polars sobre las estaciones encontradas en las validaciones:"
        ),
        mo.ui.table(normalized_sample),
    ])

    phase4_view
    return


if __name__ == "__main__":
    app.run()
