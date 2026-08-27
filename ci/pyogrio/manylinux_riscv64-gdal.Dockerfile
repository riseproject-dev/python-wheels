# SPDX-FileCopyrightText: 2026 The RISE Project
# SPDX-License-Identifier: MIT
#
# manylinux_riscv64 build image for pyogrio, standing in for the vcpkg-based
# images upstream builds its Linux wheels with
# (pyogrio ci/manylinux_2_28_*-vcpkg-gdal.Dockerfile): vcpkg has no riscv64
# binary cache, so GEOS/PROJ/SpatiaLite/GDAL are compiled from source here instead.
ARG BASEIMAGE=quay.io/pypa/manylinux_2_39_riscv64:latest
FROM ${BASEIMAGE}

ARG GEOS_VERSION
ARG PROJ_VERSION
ARG SPATIALITE_VERSION
ARG GDAL_VERSION

SHELL ["/bin/bash", "-euxo", "pipefail", "-c"]

ENV PREFIX=/usr/local

# sqlite (the CLI) builds PROJ's proj.db and glibc-gconv-extra carries the
# charset converters GDAL recodes shapefile attributes with; the rest are
# GDAL/PROJ/SpatiaLite dependencies.
RUN dnf -y install sqlite sqlite-devel libtiff-devel libcurl-devel expat-devel \
        libxml2-devel openssl-devel glibc-gconv-extra \
    && dnf clean all \
    && echo "${PREFIX}/lib" > /etc/ld.so.conf.d/pyogrio-local.conf \
    && mkdir -p /opt/licenses /src

RUN cd /src \
    && curl -sSLo geos.tar.bz2 "https://download.osgeo.org/geos/geos-${GEOS_VERSION}.tar.bz2" \
    && tar xf geos.tar.bz2 \
    && cd "geos-${GEOS_VERSION}" \
    && cp COPYING /opt/licenses/LICENSE_GEOS \
    && cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_INSTALL_LIBDIR=lib \
        -DBUILD_TESTING=OFF \
        -DBUILD_DOCUMENTATION=OFF \
        -DBUILD_BENCHMARKS=OFF \
    && cmake --build build -j"$(nproc)" \
    && cmake --install build \
    && ldconfig \
    && rm -rf /src/*

RUN cd /src \
    && curl -sSLo proj.tar.gz "https://download.osgeo.org/proj/proj-${PROJ_VERSION}.tar.gz" \
    && tar xf proj.tar.gz \
    && cd "proj-${PROJ_VERSION}" \
    && cp COPYING /opt/licenses/LICENSE_PROJ \
    && cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_INSTALL_LIBDIR=lib \
        -DBUILD_TESTING=OFF \
        -DBUILD_APPS=OFF \
        -DENABLE_CURL=ON \
        -DENABLE_TIFF=ON \
    && cmake --build build -j"$(nproc)" \
    && cmake --install build \
    && ldconfig \
    && rm -rf /src/*

# pyogrio's vcpkg manifest asks for libspatialite with its default features
# off, so freexl and rttopo are left out here too. Its config.guess/config.sub
# date from 2009 and know neither aarch64 nor riscv64, hence automake's.
RUN cd /src \
    && curl -sSLo spatialite.tar.gz "https://www.gaia-gis.it/gaia-sins/libspatialite-sources/libspatialite-${SPATIALITE_VERSION}.tar.gz" \
    && tar xf spatialite.tar.gz \
    && cd "libspatialite-${SPATIALITE_VERSION}" \
    && cp COPYING /opt/licenses/LICENSE_SPATIALITE \
    && cp /usr/share/automake-*/config.guess /usr/share/automake-*/config.sub . \
    && ./configure --prefix="${PREFIX}" --libdir="${PREFIX}/lib" \
        --disable-static --disable-freexl --disable-rttopo --disable-examples \
        --disable-minizip \
    && make -j"$(nproc)" \
    && make install \
    && ldconfig \
    && rm -rf /src/*

RUN cd /src \
    && curl -sSLo gdal.tar.gz "https://github.com/OSGeo/gdal/releases/download/v${GDAL_VERSION}/gdal-${GDAL_VERSION}.tar.gz" \
    && tar xf gdal.tar.gz \
    && cd "gdal-${GDAL_VERSION}" \
    && cp LICENSE.TXT /opt/licenses/LICENSE_GDAL \
    && cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
        -DCMAKE_INSTALL_LIBDIR=lib \
        -DBUILD_TESTING=OFF \
        -DBUILD_APPS=OFF \
        -DBUILD_PYTHON_BINDINGS=OFF \
        -DBUILD_JAVA_BINDINGS=OFF \
        -DBUILD_CSHARP_BINDINGS=OFF \
    && cmake --build build -j"$(nproc)" \
    && cmake --install build \
    && ldconfig \
    && rm -rf /src/*

COPY collect-licenses.sh /usr/local/bin/collect-licenses.sh
RUN collect-licenses.sh && dnf clean all
