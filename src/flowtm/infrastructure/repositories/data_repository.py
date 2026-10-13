# FlowTM - BRT Corridor Digital Twin and Optimization Engine
# Copyright (C) 2026 FlowTM Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
flowtm.infrastructure.repositories.data_repository
==================================================
Repository Pattern: Decouples physical storage access (Parquet, In-Memory Polars)
from simulation models, optimization algorithms, and presentation layers.
"""

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
import polars as pl


class DataRepository(ABC):
    """
    Abstract contract for accessing corridor topology and simulation telemetry.
    """

    @abstractmethod
    def get_topology(self) -> pd.DataFrame:
        """Returns the corridor topology dataframe with station geo-coordinates."""
        pass

    @abstractmethod
    def get_telemetry(
        self, scenario: str
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        """Returns vehicle positions and station queue telemetry dataframes."""
        pass


class ParquetDataRepository(DataRepository):
    """
    In-memory repository implementation that reads ZSTD-compressed Parquet files
    using high-throughput Polars scanning and converts to pandas for frontend consumption.
    """

    def __init__(self, base_path: str | Path) -> None:
        self.base_path = Path(base_path)

    def get_topology(self) -> pd.DataFrame:
        path = self.base_path / "estaciones_piloto.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pl.read_parquet(path).to_pandas()

    def get_telemetry(
        self, scenario: str
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        buses_path = (
            self.base_path / f"telemetria_{scenario}" / "telemetria_buses.parquet"
        )
        queues_path = (
            self.base_path / f"telemetria_{scenario}" / "historial_colas.parquet"
        )

        buses_df = (
            pl.read_parquet(buses_path).to_pandas() if buses_path.exists() else None
        )
        queues_df = (
            pl.read_parquet(queues_path).to_pandas() if queues_path.exists() else None
        )

        return buses_df, queues_df
