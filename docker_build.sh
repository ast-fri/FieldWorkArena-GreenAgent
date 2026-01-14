#!/bin/bash

docker build . -f Dockerfile -t green_agent
docker build . -f scenarios/fwa/Dockerfile.purple_agent -t purple_agent
