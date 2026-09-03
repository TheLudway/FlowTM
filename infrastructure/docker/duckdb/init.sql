INSTALL quack;
LOAD quack;

CALL quack_serve(
    'quack:0.0.0.0:9494',
    token = getenv('QUACK_TOKEN'),
    allow_other_hostname = true,
    disable_ssl = true
);
