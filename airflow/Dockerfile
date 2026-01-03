FROM apache/airflow:3.1.5

USER root

# Install OpenJDK-17
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         openjdk-17-jre-headless \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64
# Ensure the architecture matches (arm64 for Mac M1/M2/M3)
# If running on amd64, the path might be different, e.g., /usr/lib/jvm/java-17-openjdk-amd64
# Using a wildcard or shell command to set it dynamically is safer but for now hardcoding for Mac/arm64 as per user info.
# Actually, let's try to be a bit more robust or assume standard path.
# On Debian/Ubuntu provided by airflow image:
ENV JAVA_HOME=/usr/lib/jvm/default-java

USER airflow

# Install Spark Provider
RUN pip install --no-cache-dir apache-airflow-providers-apache-spark==4.7.0
