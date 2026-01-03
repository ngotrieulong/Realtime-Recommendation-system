---
config:
  layout: fixed
---
flowchart LR
 subgraph API["<b>🌐 API GATEWAY</b>"]
        Nginx["<b>Nginx</b><br>Load Balancer"]
        FastAPI["<b>FastAPI</b><br>Services"]
  end
 subgraph Online["<b>⚡ ONLINE SERVING</b>"]
    direction TB
        Redis[("<b>Redis</b><br><br>Feature Cache")]
        Milvus[("<b>Milvus</b><br><br>Vector Search")]
        MLflow["<b>MLflow</b><br><br>Model Registry"]
  end
 subgraph Offline["<b>⚙️ OFFLINE PROCESSING</b>"]
    direction TB
        Kafka["<b>Kafka</b><br><br>Event Stream"]
        Spark["<b>Spark</b><br><br>Batch ETL"]
        Airflow["<b>Airflow</b><br><br>Orchestration"]
  end
 subgraph Storage["<b>🏛️ DATA LAKEHOUSE</b>"]
    direction TB
        MinIO[("<b>MinIO</b><br><br>Object Storage")]
        PostgreSQL[("<b>PostgreSQL</b><br><br>Relational DB")]
  end
 subgraph Stream["<b>🌊 REAL-TIME</b>"]
        Flink["<b>Flink</b><br><br>Stream Processing"]
  end
    User["👤 USER<br><br>Web/Mobile Client"] -- ① Request --> Nginx
    Nginx --> FastAPI
    FastAPI -- ② Get Features --> Redis
    FastAPI -- ③ ANN Search --> Milvus
    FastAPI -- ④ Load Model --> MLflow
    FastAPI -- ⑤ Response --> User
    FastAPI -. Log Events .-> Kafka
    Kafka --> Flink
    Flink -- Update Features --> Redis
    Kafka -. Batch Sink .-> MinIO
    Airflow -- Schedule --> Spark
    Spark -- Read/Write --> MinIO
    Spark -- Write Features --> PostgreSQL
    Spark -- Train & Register --> MLflow
    Spark -- Update Vectors --> Milvus
    PostgreSQL -. Sync .-> Redis
    K8s["<b>☸️ Kubernetes</b><br><br>Container Orchestration"] -. Runs All Services .-> API & Online & Offline & Storage & Stream

     User:::userClass
     K8s:::k8sClass
     API:::apiClass
     Online:::onlineClass
     Offline:::offlineClass
     Storage:::storageClass
     Stream:::streamClass
    classDef userClass fill:#E3F2FD,stroke:#1976D2,stroke-width:3px,font-size:16px
    classDef apiClass fill:#FFF3E0,stroke:#F57C00,stroke-width:3px,font-size:16px
    classDef onlineClass fill:#E8F5E9,stroke:#388E3C,stroke-width:3px,font-size:16px
    classDef offlineClass fill:#F3E5F5,stroke:#7B1FA2,stroke-width:3px,font-size:16px
    classDef storageClass fill:#FCE4EC,stroke:#C2185B,stroke-width:3px,font-size:16px
    classDef streamClass fill:#E0F2F1,stroke:#00796B,stroke-width:3px,font-size:16px
    classDef k8sClass fill:#FFF9C4,stroke:#F57F17,stroke-width:3px,font-size:16px
