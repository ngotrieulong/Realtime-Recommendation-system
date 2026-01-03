# Dockerfile Fixes Changelog

## Airflow
- Switched to `apache/airflow:3.1.5`
- Added `openjdk-17-jdk` for Spark compatibility on ARM64.
- Installed `apache-airflow-providers-apache-spark`.

## Spark
- Verified `bitnami/spark:3.5.3` usage.

## FastAPI
- Created lightweight `python:3.10-slim` image.
- Added `pgvector` support.
