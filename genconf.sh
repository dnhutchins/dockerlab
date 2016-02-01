#!/bin/bash

echo "server {
	listen 443 ssl;
	server_name _;
"

for port in {6000..7000}
do
echo "
        location /$port/websockify {
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \"upgrade\";
            proxy_pass http://127.0.0.1:$port/websockify;
        }

        location  /$port/ {
            proxy_pass http://127.0.0.1:$port/;
        }
"
done

echo "
        location / {
             proxy_pass http://127.0.0.1:8080/;
        }

        location /static {
             root /opt/dockerlab;
        }

        error_page 502 /502_error.html;
        location /502_error.html {
            return 307 /;
        }
}"
