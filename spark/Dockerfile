# =============================================================================
# PRODUCTION-GRADE APACHE SPARK 3.5.3 DOCKERFILE
# =============================================================================
# Base image: Official Apache Spark image
# Version 3.5.3 is latest stable compatible with Airflow 3.x
# =============================================================================
FROM apache/spark:3.5.3-scala2.12-java17-python3-ubuntu

# Use bash with pipefail for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Switch to root for system packages
USER root

# =============================================================================
# SYSTEM DEPENDENCIES
# =============================================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        procps \
        vim \
        wget \
        netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# PYTHON PACKAGES FOR DATA PROCESSING
# =============================================================================
# Install Python libraries needed for Spark jobs
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir \
        # AWS SDK
        boto3==1.35.80 \
        # Data manipulation
        pandas==2.2.3 \
        pyarrow==18.1.0 \
        numpy==1.26.4 \
        # Database drivers
        psycopg2-binary==2.9.9 \
        # Redis client
        redis==5.2.1 \
        # HTTP client
        requests==2.32.3 \
        # Environment management
        python-dotenv==1.0.1

# =============================================================================
# HADOOP AWS JARS FOR S3/MINIO COMPATIBILITY
# =============================================================================
# Version matching is CRITICAL:
# - Spark 3.5.3 uses Hadoop 3.3.6
# - aws-java-sdk-bundle must be compatible with Hadoop 3.3.6
# - Tested combination: hadoop-aws 3.3.6 + aws-java-sdk-bundle 1.12.367
WORKDIR /opt/spark/jars

RUN curl -fsSL -O https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.6/hadoop-aws-3.3.6.jar && \
    curl -fsSL -O https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar && \
    echo "✅ Downloaded Hadoop AWS JARs" && \
    ls -lh hadoop-aws* aws-java-sdk-bundle*

# =============================================================================
# SPARK CONFIGURATION
# =============================================================================
# Create custom spark-defaults.conf with production-grade settings
RUN mkdir -p /opt/spark/conf && \
    cat > /opt/spark/conf/spark-defaults.conf << 'EOF'
# Adaptive Query Execution (Spark 3.x feature)
spark.sql.adaptive.enabled=true
spark.sql.adaptive.coalescePartitions.enabled=true
spark.sql.adaptive.skewJoin.enabled=true

# Shuffle configuration
spark.sql.shuffle.partitions=200

# Memory management
spark.memory.fraction=0.6
spark.memory.storageFraction=0.5

# Serialization (Kryo is faster than Java serialization)
spark.serializer=org.apache.spark.serializer.KryoSerializer

# Event logging for Spark History Server
spark.eventLog.enabled=true
spark.eventLog.dir=/opt/spark/logs/events
spark.eventLog.compress=true

# UI retention
spark.ui.retainedJobs=100
spark.ui.retainedStages=100
spark.ui.retainedTasks=1000

# Network timeout (increase for slow networks)
spark.network.timeout=300s
spark.executor.heartbeatInterval=20s

# S3/MinIO Configuration
spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem
spark.hadoop.fs.s3a.path.style.access=true
spark.hadoop.fs.s3a.connection.ssl.enabled=false
spark.hadoop.fs.s3a.fast.upload=true
EOF

# Create directories for logs and events
RUN mkdir -p /opt/spark/logs/events && \
    chmod -R 777 /opt/spark/logs

# =============================================================================
# APPLICATION CODE DIRECTORY
# =============================================================================
RUN mkdir -p /opt/spark-jobs && \
    chmod 777 /opt/spark-jobs

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================
ENV SPARK_HOME=/opt/spark
ENV PATH="${SPARK_HOME}/bin:${SPARK_HOME}/sbin:${PATH}"
ENV PYTHONPATH="${SPARK_HOME}/python:${SPARK_HOME}/python/lib/py4j-0.10.9.7-src.zip:${PYTHONPATH}"

# Ensure logs directory exists and is writable
RUN mkdir -p /opt/spark/logs && chmod 777 /opt/spark/logs

# =============================================================================
# WORKING DIRECTORY
# =============================================================================
WORKDIR /opt/spark

# =============================================================================
# USER CONFIGURATION
# =============================================================================
# Switch back to spark user (security best practice)
USER spark


# =============================================================================
# ENTRY POINT
# =============================================================================
# Command will be specified in docker-compose.yaml
# For master: /opt/spark/bin/spark-class org.apache.spark.deploy.master.Master
# For worker: /opt/spark/bin/spark-class org.apache.spark.deploy.worker.Worker spark://master:7077