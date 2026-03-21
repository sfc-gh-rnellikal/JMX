FROM eclipse-temurin:21-jre

ENV JMETER_VERSION=5.6.3
ENV JMETER_HOME=/opt/apache-jmeter-${JMETER_VERSION}
ENV PATH=${JMETER_HOME}/bin:${PATH}

RUN apt-get update && apt-get install -y wget curl && \
    wget https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz && \
    tar -xzf apache-jmeter-${JMETER_VERSION}.tgz -C /opt && \
    rm apache-jmeter-${JMETER_VERSION}.tgz && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN wget -P ${JMETER_HOME}/lib/ https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/3.20.0/snowflake-jdbc-3.20.0.jar

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /jmeter

ENTRYPOINT ["/entrypoint.sh"]
