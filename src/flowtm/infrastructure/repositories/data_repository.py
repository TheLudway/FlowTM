import polars as pl
import pandas as pd
from pathlib import Path
from abc import ABC, abstractmethod

class DataRepository(ABC):
    """
    Contrato abstracto para el acceso a datos del sistema BRT (Topología y Telemetría).
    Permite desacoplar el motor y el dashboard de la fuente de datos subyacente.
    """
    @abstractmethod
    def get_topology(self) -> pd.DataFrame:
        pass
        
    @abstractmethod
    def get_telemetry(self, scenario: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        pass

class ParquetDataRepository(DataRepository):
    """
    Implementación en memoria que consume archivos Parquet comprimidos usando Polars para alta velocidad.
    """
    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)
        
    def get_topology(self) -> pd.DataFrame:
        path = self.base_path / "estaciones_piloto.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pl.read_parquet(path).to_pandas()
        
    def get_telemetry(self, scenario: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        buses_path = self.base_path / f"telemetria_{scenario}" / "telemetria_buses.parquet"
        colas_path = self.base_path / f"telemetria_{scenario}" / "historial_colas.parquet"
        
        buses_df = pl.read_parquet(buses_path).to_pandas() if buses_path.exists() else None
        colas_df = pl.read_parquet(colas_path).to_pandas() if colas_path.exists() else None
        
        return buses_df, colas_df
