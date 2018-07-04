here is the docker compose used to launch the whole stuck for test purpose

~~~~
version: '2'
services:
  zookeeper:
    image: wurstmeister/zookeeper
    ports:
      - "2181:2181"
  kafka:
    build: .
    ports:
      - "9092:9092"
    environment:
      KAFKA_ADVERTISED_HOST_NAME: 192.168.99.100
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
  kafka-manager:
    image: sheepkiller/kafka-manager
    ports:
      - "9000:9000"
    links:
      - zookeeper:zk
    environment:
      ZK_HOSTS: zk:2181
  inotify-kafka:
    image: inotify-kafka
    volumes:
      - /watched_dir:/watched_dir:ro
    links:
      - kafka:kafka
    environment:
      WATCHED_ROOT_DIR: '/watched_dir'
      WEBSERVER_URL: '127.0.0.1:9000'
      KAFKA_URL: 'kafka:9092'
      KAFKA_TOPIC: 'sftp'
  nginx:
    image: nginx-auth-static
    volumes:
      - /data:/watched_dir:ro
    ports:
      - "8090:80"
~~~~


here is the nginx server conf

    server {
        listen       80;
        server_name  localhost;
        #access_log  logs/host.access.log  main;

        #here we have to create a persistent ressourcesvolume for /data
        root /data;
        location / {
            try_files $uri $uri/ =404;
        }

