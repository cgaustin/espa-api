CONTAINERS=`docker ps -a -q`
IMAGES=`docker images -q`

# pull the tag from version.py
TAG=0.0.1
WORKERIMAGE=espa-api:$(TAG)

docker-build:
	docker build -t $(WORKERIMAGE) $(PWD)

docker-shell:
	docker run -it --entrypoint=/bin/bash usgseros/$(WORKERIMAGE)

docker-deps-up:
	docker network create backend
	docker-compose -f setup/docker-compose.yml up -d

docker-deps-up-nodaemon:
	docker-compose -f setup/docker-compose.yml up

docker-deps-down:
	docker-compose -f setup/docker-compose.yml down
	docker network rm backend

docker-deps-down-nuke:
	docker-compose -f setup/docker-compose.yml down
	docker network rm backend
	docker image rm setup_postgres:latest
	docker system prune -f --volumes

deploy-pypi:

deploy-dockerhub:

clean-venv:
	@rm -rf .venv

clean:
	@rm -rf dist build lcmap_pyccd_worker.egg-info
	@find . -name '*.pyc' -delete
	@find . -name '__pycache__' -delete

