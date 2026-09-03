#!/bin/sh

TOKEN=$(cat /run/secrets/quack_token)

duckdb /database/transport.duckdb <<SQL
INSTALL quack;
LOAD quack;

CALL quack_serve(
    'quack:0.0.0.0:9494',
    token = '${TOKEN}',
    allow_other_hostname = true
);
SQL
