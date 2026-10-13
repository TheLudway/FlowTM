# Estructura del repositorio

La estructura de directorios es: 

 ``` text
├── assets
├── data
│   ├── processed
│   │   ├── gtfs
│   │   │   ├── gtfs_20260318
│   │   │   ├── ...
│   │   │   └── gtfs_20260727
│   │   ├── infra_troncal
│   │   └── validaciones_salidas
│   │       ├── salidas_troncal
│   │       └── validacion_troncal
│   └── raw
│       ├── gtfs
│       │   ├── gtfs_20260318
│       │   ├── ...
│       │   └── gtfs_20260727
│       ├── infra_troncal
│       └── validaciones_salidas
│           ├── salidas_troncal
│           └── validacion_troncal
├── infrastructure
│   └── docker
│       ├── duckdb
│       ├── loader
│       ├── postgres
│       │   └── init
│       └── secrets
├── notebooks
│   ├── data_processing
│   ├── gtfs
│   ├── infra_troncal
│   └── validation
├── scripts
└── src
    └── flowtm
 ```

 
