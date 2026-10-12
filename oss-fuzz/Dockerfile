FROM gcr.io/oss-fuzz-base/base-builder-rust:v1

RUN git clone --depth 1 https://github.com/polyxml/safexml.git safexml
WORKDIR safexml
COPY build.sh $SRC/
