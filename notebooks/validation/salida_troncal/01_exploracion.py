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
    mo.md(r"\"\"
    # Auditoría y Exploración: Salidas Troncales
    *Componente:* Ingesta y Diagnóstico de Datos de Torniquetes (salidas_troncal)
    "\"\")
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Fase 1: Auditoría y Diagnóstico Exhaustivo de Esquemas en Salidas
    En esta fase se evalúan los esquemas de los archivos de salidas/torniquetes en modo *Lazy Evaluation* para auditar:
    - Tipos de datos en campos de conteo (`Entradas_E`, `Salidas_S`).
    - Nombres reales de la columna de estación/torniquete.
    - Porcentaje exacto de valores nulos o ausentes.
    - Valores de muestra por variable.
    """)
    return


@app.cell
def _(Path, mo, pl):
    project_root = Path(__file__).resolve().parents[3]
    outputs_path = (
        project_root / "data/processed/validaciones_salidas/salidas_troncal"
    )
    output_file = next(outputs_path.rglob("*.parquet"), None)

    if output_file:
        df_outputs = pl.read_parquet(output_file)
        audit_results = [
            {
                "#": i,
                "COLUMNA": col,
                "TIPO": str(df_outputs[col].dtype),
                "% NULOS": round(
                    (df_outputs[col].is_null().sum() / len(df_outputs)) * 100, 2
                ),
                "VALOR EJEMPLO": (
                    str(df_outputs[col][0])[:25]
                    if len(df_outputs) > 0
                    else "N/A"
                ),
            }
            for i, col in enumerate(df_outputs.columns, 1)
        ]
        phase1_table = pl.DataFrame(audit_results)
    else:
        df_outputs = None
        phase1_table = pl.DataFrame()

    mo.md(
        f"### Resultados de Auditoría ({output_file.name if output_file else 'No hallado'})"
    )
    return df_outputs, phase1_table


@app.cell
def _(mo, phase1_table):
    mo.ui.table(phase1_table)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Fase 2: Exploración de Patrones Categóricos y Métricas de Flujo
    En esta fase analizamos el comportamiento de las variables de conteo numérico y la consistencia en los nombres de estaciones registrados por las lectoras de los torniquetes.
    """)
    return


@app.cell
def _(df_outputs, mo, pl):
    if "df_outputs" in globals() and df_outputs is not None:
        columns = df_outputs.columns

        station_col = (
            "Estacion"
            if "Estacion" in columns
            else next(
                (c for c in columns if "estacion" in c.lower()),
                columns[0],
            )
        )
        stations_sample = (
            df_outputs.select(station_col).unique().head(8)
            if station_col
            else pl.DataFrame({"Info": ["No se halló columna de estación"]})
        )

        exits_summary = (
            df_outputs.select("Salidas_S").describe()
            if "Salidas_S" in columns
            else pl.DataFrame({"Info": ["Sin columna Salidas_S"]})
        )

        entries_summary = (
            df_outputs.select("Entradas_E").describe()
            if "Entradas_E" in columns
            else pl.DataFrame({"Info": ["Sin columna Entradas_E"]})
        )

        time_sample = (
            df_outputs.select("Tiempo").head(6)
            if "Tiempo" in columns
            else pl.DataFrame({"Info": ["Sin columna Tiempo"]})
        )
    else:
        stations_sample = (
            exits_summary
        ) = entries_summary = time_sample = pl.DataFrame(
            {"Error": ["df_outputs no disponible"]}
        )

    # Layout
    phase2_view = mo.vstack([
        mo.md("## Fase 2: Exploración de Patrones Categóricos en Salidas"),
        mo.md("#### 1. Patrón en Nombres de Estaciones en Torniquetes"),
        mo.ui.table(stations_sample),
        mo.md("#### 2. Distribución Estadística de Salidas (`Salidas_S`)"),
        mo.ui.table(exits_summary),
        mo.md("#### 3. Distribución Estadística de Entradas (`Entradas_E`)"),
        mo.ui.table(entries_summary),
        mo.md("#### 4. Muestra del Campo Registro Temporal (`Tiempo`)"),
        mo.ui.table(time_sample),
    ])

    phase2_view
    return


@app.cell
def _(mo):
    phase3_view = mo.vstack([
        mo.md(
            r"""
            ## Fase 3: Hallazgos Clave y Decisiones de Arquitectura en Salidas

            Basándonos en la auditoría y exploración realizada en las Fases 1 y 2 sobre el conjunto de datos de torniquetes (`salidas_troncal`), se documentan los siguientes hallazgos y decisiones de ingeniería:

            ---

            ### 1. Conservación de Volúmenes y Flujos de Tráfico
            - *Descubrimiento:* Las columnas `Salidas_S` y `Entradas_E` contienen conteos discretos de pasajeros agrupados por intervalos de tiempo en cada estación/torniquete.
            - *Decisión de Arquitectura:* Mantener ambas métricas numéricas sin modificaciones de escala ni agregaciones agresivas en la etapa de limpieza para conservar la granularidad original de los flujos.
            - *Impacto:* Permite calcular la tasa neta de ocupación por estación al contrastar estos volúmenes con las validaciones de acceso.

            ---

            ### 2. Estructura Nomenclatural de Estaciones en Torniquetes
            - *Descubrimiento:* Los nombres registrados en la columna de estación contienen el patrón de código numérico entre paréntesis `(XXXXX)` seguido del texto descriptivo.
            - *Decisión de Arquitectura:* Validar que el formato de origen es consistente para garantizar que el script de procesamiento por lotes (`02_limpieza.py`) pueda extraer `CODIGO_ESTACION` y `CODIGO_TRONCAL` mediante expresiones regulares.

            ---

            ### 3. Preservación del Registro Temporal (`Tiempo`)
            - *Descubrimiento:* La columna `Tiempo` almacena la marca temporal del intervalo de conteo registrado por la máquina del torniquete.
            - *Decisión de Arquitectura:* Preservar el campo de tiempo sin alterar su estructura en la etapa de filtrado preliminar para facilitar su posterior alineación con las franjas horarias del sistema.
            """
        )
    ])

    phase3_view
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Fase 4: Función Universal de Normalización Aplicada a Salidas
    Definición y prueba de las expresiones vectorizadas de Polars sobre la columna de estación detectada en el archivo de salidas.
    """)
    return


if __name__ == "__main__":
    app.run()
