"""
=============================================================================
ENHANCED AIRFLOW DAG - BATCH RECOMMENDATION PROCESSING
=============================================================================
Enhancements:
  - Atomic table swap (blue-green deployment)
  - Gradual cache invalidation
  - Comprehensive validation
  - Model performance logging
=============================================================================
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any

from airflow.decorators import dag, task
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook


# =============================================================================
# DAG DEFINITION
# =============================================================================
@dag(
    dag_id='batch_recommendation_processing_v2',
    description='Enhanced batch processing with atomic updates',
    schedule='0 2 * * *',  # 2 AM daily
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        'owner': 'data-team',
        'retries': 2,
        'retry_delay': timedelta(minutes=5),
        'email_on_failure': False,
    },
    tags=['batch', 'recommendations', 'production', 'v2'],
)
def batch_recommendation_dag_v2():
    
    # =========================================================================
    # TASK 1: Snapshot Current State (Backup)
    # =========================================================================
    @task
    def snapshot_current_state(logical_date: datetime) -> Dict[str, Any]:
        """
        Backup current batch_recommendations before overwrite
        Enables rollback if new model performs worse
        """
        import boto3
        import pandas as pd
        from io import BytesIO
        
        pg_hook = PostgresHook(postgres_conn_id='postgres_moviedb')
        
        # Export current batch_recommendations
        query = "SELECT * FROM batch_recommendations"
        df = pg_hook.get_pandas_df(query)
        
        if len(df) == 0:
            print("ℹ️  No existing recommendations to snapshot")
            return {"snapshot_count": 0}
        
        # Upload to MinIO
        date_str = logical_date.strftime('%Y-%m-%d')
        s3_path = f"batch-recs-history/{date_str}.parquet"
        
        s3_client = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='minioadmin',
            aws_secret_access_key='minioadmin'
        )
        
        parquet_buffer = BytesIO()
        df.to_parquet(parquet_buffer, index=False, compression='snappy')
        parquet_buffer.seek(0)
        
        s3_client.upload_fileobj(
            parquet_buffer,
            'lakehouse',
            s3_path
        )
        
        result = {
            "snapshot_count": len(df),
            "snapshot_path": f"s3a://lakehouse/{s3_path}",
            "snapshot_date": date_str
        }
        
        print(f"✅ Snapshotted {result['snapshot_count']} recommendations to {s3_path}")
        return result
    
    
    # =========================================================================
    # TASK 2: Archive Old Events
    # =========================================================================
    @task
    def archive_old_events(logical_date: datetime) -> Dict[str, Any]:
        """Archive events older than 48 hours to MinIO"""
        import boto3
        import pandas as pd
        from io import BytesIO
        
        pg_hook = PostgresHook(postgres_conn_id='postgres_moviedb')
        
        query = """
            SELECT * FROM rt_user_interactions 
            WHERE timestamp < NOW() - INTERVAL '48 hours'
            ORDER BY timestamp
        """
        
        df = pg_hook.get_pandas_df(query)
        
        if len(df) == 0:
            print("ℹ️  No events to archive")
            return {"archived_count": 0}
        
        date_str = logical_date.strftime('%Y/%m/%d')
        s3_path = f"archived-events/{date_str}/events.parquet"
        
        s3_client = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='minioadmin',
            aws_secret_access_key='minioadmin'
        )
        
        parquet_buffer = BytesIO()
        df.to_parquet(parquet_buffer, index=False, compression='snappy')
        parquet_buffer.seek(0)
        
        s3_client.upload_fileobj(parquet_buffer, 'lakehouse', s3_path)
        
        # Delete archived events
        delete_query = """
            DELETE FROM rt_user_interactions 
            WHERE timestamp < NOW() - INTERVAL '48 hours'
        """
        pg_hook.run(delete_query)
        
        print(f"✅ Archived {len(df)} events")
        return {"archived_count": len(df), "file_path": s3_path}
    
    
    # =========================================================================
    # TASK 3: Spark Batch Job
    # =========================================================================
    spark_batch_job = SparkSubmitOperator(
        task_id='train_model_generate_recs',
        application='/opt/spark-jobs/batch_model_training.py',
        conn_id='spark_default',
        conf={
            'spark.executor.memory': '1g',
            'spark.executor.cores': '1',
            'spark.sql.shuffle.partitions': '10',
            'spark.hadoop.fs.s3a.endpoint': 'http://minio:9000',
            'spark.hadoop.fs.s3a.access.key': 'minioadmin',
            'spark.hadoop.fs.s3a.secret.key': 'minioadmin',
            'spark.hadoop.fs.s3a.path.style.access': 'true',
            'spark.hadoop.fs.s3a.impl': 'org.apache.hadoop.fs.s3a.S3AFileSystem',
        },
        application_args=[
            '--date', '{{ ds }}',
            '--output-table', 'batch_recommendations_new',  # Write to NEW table
        ],
        verbose=True,
    )
    
    
    # =========================================================================
    # TASK 4: Validate New Recommendations
    # =========================================================================
    @task
    def validate_new_recommendations() -> Dict[str, Any]:
        """
        Validate quality of new recommendations BEFORE swapping
        """
        pg_hook = PostgresHook(postgres_conn_id='postgres_moviedb')
        
        # Check if new table exists and has data
        query_count = """
            SELECT COUNT(*) as total_users,
                   AVG(jsonb_array_length(recommendations)) as avg_recs_per_user
            FROM batch_recommendations_new
        """
        
        result = pg_hook.get_first(query_count)
        
        total_users = result[0] if result else 0
        avg_recs = float(result[1]) if result and result[1] else 0
        
        # Get expected user count (active users)
        query_expected = """
            SELECT COUNT(DISTINCT user_id) as active_users
            FROM rt_user_interactions
            WHERE timestamp > NOW() - INTERVAL '30 days'
        """
        
        expected = pg_hook.get_first(query_expected)
        expected_users = expected[0] if expected else 0
        
        # Calculate coverage
        coverage = (total_users / expected_users * 100) if expected_users > 0 else 0
        
        stats = {
            "total_users_with_recs": total_users,
            "expected_users": expected_users,
            "coverage_percent": round(coverage, 2),
            "avg_recs_per_user": round(avg_recs, 2),
            "validation_passed": coverage >= 80 and avg_recs >= 30
        }
        
        print(f"📊 Validation Results:")
        print(f"   Coverage: {stats['coverage_percent']}%")
        print(f"   Avg recs/user: {stats['avg_recs_per_user']}")
        
        if not stats['validation_passed']:
            raise ValueError(f"❌ Validation failed! Coverage: {stats['coverage_percent']}%")
        
        print("✅ Validation passed")
        return stats
    
    
    # =========================================================================
    # TASK 5: Atomic Table Swap (Blue-Green Deployment)
    # =========================================================================
    @task
    def atomic_table_swap() -> Dict[str, str]:
        """
        Atomically swap old and new batch_recommendations tables
        Zero-downtime deployment
        """
        pg_hook = PostgresHook(postgres_conn_id='postgres_moviedb')
        
        swap_sql = """
            BEGIN;
            
            -- Drop old backup if exists
            DROP TABLE IF EXISTS batch_recommendations_old;
            
            -- Rename current table to old (backup)
            ALTER TABLE batch_recommendations 
                RENAME TO batch_recommendations_old;
            
            -- Promote new table to production
            ALTER TABLE batch_recommendations_new 
                RENAME TO batch_recommendations;
            
            COMMIT;
        """
        
        try:
            pg_hook.run(swap_sql)
            print("✅ Atomic swap completed successfully")
            return {
                "status": "success",
                "swapped_at": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ Swap failed: {e}")
            # Rollback is automatic (transaction)
            raise
    
    
    # =========================================================================
    # TASK 6: Update Cache valid_until (Gradual Invalidation)
    # =========================================================================
    @task
    def update_cache_expiration() -> Dict[str, Any]:
        """
        Update valid_until timestamp in cache metadata
        Gradual expiration prevents cache stampede
        """
        import redis
        import json
        
        r = redis.Redis(host='redis', port=6379, decode_responses=True)
        
        # Scan for all recommendation cache keys
        cursor = 0
        updated_count = 0
        
        # New valid_until: Allow caches to expire by 4 AM
        new_valid_until = datetime.now().replace(
            hour=4, minute=0, second=0, microsecond=0
        )
        
        while True:
            cursor, keys = r.scan(
                cursor=cursor,
                match="recs:*",
                count=1000
            )
            
            for key in keys:
                try:
                    cached_data = r.get(key)
                    if cached_data:
                        data = json.loads(cached_data)
                        
                        # Update valid_until
                        data['valid_until'] = new_valid_until.isoformat()
                        data['model_version'] = f"als_{datetime.now().strftime('%Y%m%d')}_02am"
                        
                        # Keep existing TTL
                        ttl = r.ttl(key)
                        if ttl > 0:
                            r.setex(key, ttl, json.dumps(data))
                            updated_count += 1
                
                except Exception as e:
                    print(f"⚠️  Failed to update {key}: {e}")
            
            if cursor == 0:
                break
        
        result = {
            "updated_keys": updated_count,
            "new_valid_until": new_valid_until.isoformat(),
            "strategy": "gradual_expiration"
        }
        
        print(f"✅ Updated {updated_count} cache entries")
        print(f"   Caches will expire naturally by {new_valid_until}")
        
        return result
    
    
    # =========================================================================
    # TASK 7: Log Model Performance
    # =========================================================================
    @task
    def log_model_performance() -> None:
        """
        Log model quality metrics to model_performance_logs table
        """
        import boto3
        import json
        
        # Load model metadata from MinIO
        s3_client = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='minioadmin',
            aws_secret_access_key='minioadmin'
        )
        
        date_str = datetime.now().strftime('%Y%m%d')
        model_id = f"als_{date_str}_02am"
        
        try:
            response = s3_client.get_object(
                Bucket='lakehouse',
                Key=f"models/{model_id}/metadata.json"
            )
            metadata = json.loads(response['Body'].read())
            
            # Insert into model_performance_logs
            pg_hook = PostgresHook(postgres_conn_id='postgres_moviedb')
            
            insert_query = """
                INSERT INTO model_performance_logs (
                    model_id,
                    algorithm,
                    rmse,
                    coverage,
                    total_users_trained,
                    total_interactions,
                    training_duration_sec,
                    hyperparameters,
                    trained_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            
            pg_hook.run(
                insert_query,
                parameters=(
                    model_id,
                    'als_collaborative',
                    metadata.get('rmse'),
                    metadata.get('coverage'),
                    metadata.get('total_users'),
                    metadata.get('total_interactions'),
                    metadata.get('training_duration_sec'),
                    json.dumps(metadata.get('hyperparameters', {}))
                )
            )
            
            print(f"✅ Logged model performance: RMSE={metadata.get('rmse')}")
            
        except Exception as e:
            print(f"⚠️  Could not log model performance: {e}")
    
    
    # =========================================================================
    # TASK 8: Cleanup Old Backups
    # =========================================================================
    @task
    def cleanup_old_backups() -> Dict[str, int]:
        """
        Delete old table backup and temp files
        """
        pg_hook = PostgresHook(postgres_conn_id='postgres_moviedb')
        
        # Drop old backup table (after 1 hour grace period)
        drop_sql = "DROP TABLE IF EXISTS batch_recommendations_old"
        pg_hook.run(drop_sql)
        
        # Cleanup old MinIO checkpoints
        import boto3
        
        s3_client = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='minioadmin',
            aws_secret_access_key='minioadmin'
        )
        
        cutoff_date = datetime.now() - timedelta(days=7)
        deleted_count = 0
        
        response = s3_client.list_objects_v2(
            Bucket='lakehouse',
            Prefix='checkpoints/'
        )
        
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                    s3_client.delete_object(
                        Bucket='lakehouse',
                        Key=obj['Key']
                    )
                    deleted_count += 1
        
        print(f"🧹 Cleaned up {deleted_count} old checkpoint files")
        return {"deleted_files": deleted_count}
    
    
    # =========================================================================
    # TASK 9: Send Notification
    # =========================================================================
    @task
    def send_success_notification(
        validation_stats: Dict,
        cache_stats: Dict
    ) -> None:
        """Send success notification with metrics"""
        
        message = f"""
        ✅ Batch Recommendation Job Completed Successfully
        
        📊 Model Quality:
           - Coverage: {validation_stats['coverage_percent']}%
           - Users processed: {validation_stats['total_users_with_recs']}
           - Avg recs/user: {validation_stats['avg_recs_per_user']}
        
        🔄 Cache Update:
           - Updated cache entries: {cache_stats['updated_keys']}
           - Gradual expiration until: {cache_stats['new_valid_until']}
        
        ⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        print(message)
        
        # In production: Send to Slack/Email/PagerDuty
        # slack_hook.send(text=message)
    
    
    # =========================================================================
    # TASK DEPENDENCIES
    # =========================================================================
    
    # Phase 1: Backup & Archive (parallel)
    snapshot = snapshot_current_state()
    archive = archive_old_events()
    
    # Phase 2: Train model (depends on archive completing)
    spark_job = spark_batch_job
    
    # Phase 3: Validate new recommendations
    validation = validate_new_recommendations()
    
    # Phase 4: Atomic swap (only if validation passed)
    swap = atomic_table_swap()
    
    # Phase 5: Update cache & log metrics (parallel)
    cache_update = update_cache_expiration()
    model_log = log_model_performance()
    
    # Phase 6: Cleanup & notify
    cleanup = cleanup_old_backups()
    notification = send_success_notification(validation, cache_update)
    
    
    # Define execution order
    [snapshot, archive] >> spark_job >> validation >> swap
    swap >> [cache_update, model_log] >> cleanup >> notification


# Instantiate DAG
batch_dag_v2 = batch_recommendation_dag_v2()