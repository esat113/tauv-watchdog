# ---- build CycloneDDS ----
FROM debian:bookworm AS build
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    git cmake build-essential ca-certificates pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 --branch 0.10.5 https://github.com/eclipse-cyclonedds/cyclonedds.git

WORKDIR /src/cyclonedds/build
RUN cmake -DCMAKE_INSTALL_PREFIX=/dds .. \
 && cmake --build . --target install --parallel

# ---- runtime ----
FROM python:3.10-slim
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    gettext-base gcc g++ make \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /dds
COPY --from=build /dds/ /dds/

ENV LD_LIBRARY_PATH="/dds/lib"
ENV CYCLONEDDS_HOME="/dds"
ENV CMAKE_PREFIX_PATH="/dds"
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir cyclonedds==0.10.5

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app/ /app/
COPY config.yaml /app/config.yaml
COPY dds_config.template.xml /app/dds_config.template.xml
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
