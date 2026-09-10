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
    ruta_val = Path("data/processed/validaciones_salidas/validacion_troncal")
    arch_val = next(ruta_val.rglob("*.parquet"), None)

    if arch_val:
        df_v = pl.read_parquet(arch_val)
        res_audit = [
            {
                "#": i,
                "COLUMNA": col,
                "TIPO": str(df_v[col].dtype),
                "% NULOS": round(
                    (df_v[col].is_null().sum() / len(df_v)) * 100, 2
                ),
                "VALOR EJEMPLO": (
                    str(df_v[col][0])[:25] if len(df_v) > 0 else "N/A"
                ),
            }
            for i, col in enumerate(df_v.columns, 1)
        ]
        tabla_fase1 = pl.DataFrame(res_audit)
    else:
        df_v = None
        tabla_fase1 = pl.DataFrame()

    mo.md(
        f"### Resultados de Auditoría ({arch_val.name if arch_val else 'No hallado'})"
    )
    return df_v, tabla_fase1


@app.cell
def _(mo, tabla_fase1):
    mo.ui.table(tabla_fase1)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Fase 2: Exploración de Patrones Categóricos
    Para validar la consistencia en el contenido de las variables categóricas y verificar las divergencias textuales, se ejecutó el siguiente script:
    """)
    return


@app.cell
def _(df_v, mo, pl):
    if "df_v" in globals() and df_v is not None:
        cols = df_v.columns

        col_est = "Estacion_Parada" if "Estacion_Parada" in cols else next((c for c in cols if "estacion" in c.lower()), None)
        m_estaciones = (
            df_v.select(col_est).unique().head(8)
            if col_est
            else pl.DataFrame({"Info": ["No se halló columna de estación"]})
        )

        m_picos = (
            df_v["Hora_Pico_SN"].value_counts()
            if "Hora_Pico_SN" in cols
            else pl.DataFrame({"Info": ["Sin Hora_Pico_SN"]})
        )

        m_dias = (
            df_v["Day_Group_Type"].value_counts()
            if "Day_Group_Type" in cols
            else pl.DataFrame({"Info": ["Sin Day_Group_Type"]})
        )

        m_perfiles = (
            df_v["Nombre_Perfil"].value_counts().head(6)
            if "Nombre_Perfil" in cols
            else pl.DataFrame({"Info": ["Sin Nombre_Perfil"]})
        )
    else:
        m_estaciones = m_picos = m_dias = m_perfiles = pl.DataFrame({"Error": ["df_v no disponible"]})

    # Layout
    vista_fase2 = mo.vstack([
        mo.md("## Fase 2: Exploración de Patrones Categóricos en Validaciones"),
        mo.md("#### 1. Patrón en Nombres de Estaciones (Muestra)"),
        mo.ui.table(m_estaciones),
        mo.md("#### 2. Distribución de Hora Pico (Hora_Pico_SN)"),
        mo.ui.table(m_picos),
        mo.md("#### 3. Tipos de Día (Day_Group_Type)"),
        mo.ui.table(m_dias),
        mo.md("#### 4. Perfiles de Usuario Masivos (Nombre_Perfil)"),
        mo.ui.table(m_perfiles)
    ])

    vista_fase2
    return


@app.cell
def _(mo):
    vista_fase3 = mo.vstack([
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

            ### 3. Estandarización de Texto Canónico
            - *Descubrimiento:* Se identifican caracteres especiales, acentos y variaciones ortográficas en los nombres textuales.
            - *Decisión de Arquitectura:* Se aplicará una limpieza léxica vectorizada (remoción de acentos, conversión a mayúsculas y eliminación del prefijo numérico) para generar NOMBRE_ESTACION_CANONICO, garantizando consistencia en los reportes y visualizaciones.
            """
        )
    ])

    # Renderizado final
    vista_fase3
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ##Fase 4: Función Universal de Normalización, se formula la expresión vectorizada de Polars que realiza la extracción del código de 5 dígitos, genera el código de troncal de 2 dígitos y limpian el nombre canónico de la estación
    """)
    return


@app.cell
def _(df_v, mo, pl):
    def normalizar_estaciones(columna: str) -> list[pl.Expr]:
        return [
            pl.col(columna)
            .str.extract(r"\((\d{5})\)", 1)
            .alias("CODIGO_ESTACION"),
            pl.col(columna)
            .str.extract(r"\((\d{2})\)\d{3}", 1)
            .alias("CODIGO_TRONCAL"),
            (
                pl.col(columna)
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


    if "df_v" in globals() and df_v is not None:
        cols_f4 = df_v.columns
        col_est_f4 = (
            "Estacion_Parada"
            if "Estacion_Parada" in cols_f4
            else next((c for c in cols_f4 if "estacion" in c.lower()), cols_f4[0])
        )

        muestra_norm = (
            df_v.select([col_est_f4, *normalizar_estaciones(col_est_f4)])
            .unique(subset=["CODIGO_ESTACION"])
            .head(10)
        )

    else:
        muestra_norm = pl.DataFrame(
            {"Error": ["df_v no está disponible para probar la normalización"]}
        )

    vista_fase4 = mo.vstack([
        mo.md(
            "## Fase 4: Función Universal de Normalización de Estaciones"
        ),
        mo.md(
            "A continuación se presenta el resultado de aplicar la transformación vectorizada en Polars sobre las estaciones encontradas en las validaciones:"
        ),
        mo.ui.table(muestra_norm),
    ])


    vista_fase4
    return


if __name__ == "__main__":
    app.run()
