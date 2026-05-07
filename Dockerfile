FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-11-jdk-headless \
        python3 python3-pip \
        git subversion curl wget unzip rsync \
        perl cpanminus \
        build-essential \
        ant maven gradle \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir numpy scikit-learn

ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV D4J_HOME=/opt/project/defects4j
ENV PATH="${D4J_HOME}/framework/bin:${JAVA_HOME}/bin:${PATH}"
ENV TZ=America/Los_Angeles

WORKDIR /opt/project
COPY . /opt/project

RUN mkdir -p /opt/project/tools/gzoltar && \
    wget -O /opt/project/tools/gzoltar/gzoltarcli.jar https://repo1.maven.org/maven2/com/gzoltar/com.gzoltar.cli/1.7.3/com.gzoltar.cli-1.7.3-jar-with-dependencies.jar && \
    wget -O /opt/project/tools/gzoltar/gzoltaragent.jar https://repo1.maven.org/maven2/com/gzoltar/com.gzoltar.agent.rt/1.7.3/com.gzoltar.agent.rt-1.7.3-all.jar

RUN cd "${D4J_HOME}" && \
    cpanm --notest --quiet --installdeps . && \
    ./init.sh

ENV LANG=C.UTF-8
WORKDIR /opt/project

CMD ["/bin/bash"]
