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
    # Auditoría y Exploración: Salidas Troncales
    *Componente:* Ingesta y Diagnóstico de Datos de Torniquetes (salidas_troncal)
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
    ruta_sal = (
        project_root / "data/processed/validaciones_salidas/salidas_troncal"
    )
    arch_sal = next(ruta_sal.rglob("*.parquet"), None)

    if arch_sal:
        df_s = pl.read_parquet(arch_sal)
        res_audit = [
            {
                "#": i,
                "COLUMNA": col,
                "TIPO": str(df_s[col].dtype),
                "% NULOS": round(
                    (df_s[col].is_null().sum() / len(df_s)) * 100, 2
                ),
                "VALOR EJEMPLO": (
                    str(df_s[col][0])[:25] if len(df_s) > 0 else "N/A"
                ),
            }
            for i, col in enumerate(df_s.columns, 1)
        ]
        tabla_fase1 = pl.DataFrame(res_audit)
    else:
        df_s = None
        tabla_fase1 = pl.DataFrame()

    mo.md(
        f"### Resultados de Auditoría ({arch_sal.name if arch_sal else 'No hallado'})"
    )
    return df_s, tabla_fase1


@app.cell
def _(mo, tabla_fase1):
    mo.ui.table(tabla_fase1)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Fase 2: Exploración de Patrones Categóricos y Métricas de Flujo
    En esta fase analizamos el comportamiento de las variables de conteo numérico y la consistencia en los nombres de estaciones registrados por las lectoras de los torniquetes.
    """)
    return


@app.cell
def _(df_s, mo, pl):
    if "df_s" in globals() and df_s is not None:
        cols = df_s.columns

        col_est = (
            "Estacion"
            if "Estacion" in cols
            else next(
                (c for c in cols if "estacion" in c.lower()),
                cols[0],
            )
        )
        m_estaciones = (
            df_s.select(col_est).unique().head(8)
            if col_est
            else pl.DataFrame({"Info": ["No se halló columna de estación"]})
        )

        m_salidas = (
            df_s.select("Salidas_S").describe()
            if "Salidas_S" in cols
            else pl.DataFrame({"Info": ["Sin columna Salidas_S"]})
        )

        m_entradas = (
            df_s.select("Entradas_E").describe()
            if "Entradas_E" in cols
            else pl.DataFrame({"Info": ["Sin columna Entradas_E"]})
        )

        m_tiempo = (
            df_s.select("Tiempo").head(6)
            if "Tiempo" in cols
            else pl.DataFrame({"Info": ["Sin columna Tiempo"]})
        )
    else:
        m_estaciones = m_salidas = m_entradas = m_tiempo = pl.DataFrame(
            {"Error": ["df_s no disponible"]}
        )

    # Layout
    vista_fase2 = mo.vstack([
        mo.md("## Fase 2: Exploración de Patrones Categóricos en Salidas"),
        mo.md("#### 1. Patrón en Nombres de Estaciones en Torniquetes"),
        mo.ui.table(m_estaciones),
        mo.md("#### 2. Distribución Estadística de Salidas (`Salidas_S`)"),
        mo.ui.table(m_salidas),
        mo.md("#### 3. Distribución Estadística de Entradas (`Entradas_E`)"),
        mo.ui.table(m_entradas),
        mo.md("#### 4. Muestra del Campo Registro Temporal (`Tiempo`)"),
        mo.ui.table(m_tiempo),
    ])

    vista_fase2
    return


@app.cell
def _(mo):
    vista_fase3 = mo.vstack([
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

    vista_fase3
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
