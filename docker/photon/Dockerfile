FROM eclipse-temurin:21-jre-jammy
RUN apt-get update && apt-get install -y --no-install-recommends curl bzip2 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home photon \
    && mkdir /data && chown photon:photon /data
RUN curl -fL --retry 3 https://github.com/komoot/photon/releases/download/1.3.0/photon-1.3.0.jar -o /opt/photon.jar \
    && echo 'a89707c0045e4807b2a1180e132e68e108d998709f48b6c94b98a6e281f571a5  /opt/photon.jar' | sha256sum -c -
USER photon
WORKDIR /data
ENV JAVA_TOOL_OPTIONS="-Xms512m -Xmx2g"
ENTRYPOINT ["java", "-jar", "/opt/photon.jar"]
CMD ["serve", "-listen-ip", "0.0.0.0", "-data-dir", "/data"]
