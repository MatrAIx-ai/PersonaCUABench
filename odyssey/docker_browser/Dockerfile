FROM selenium/standalone-chrome@sha256:7efe71e7e4a83bdf574b26bd354690928075e8f443223d2ced16a2c208eae1d7

USER root
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends socat \
    && rm -rf /var/lib/apt/lists/*
USER seluser
