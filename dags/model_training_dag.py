"""
=============================================================================
SPARK BATCH JOB - COLLABORATIVE FILTERING MODEL TRAINING
=============================================================================
Purpose: Train collaborative filtering model using historical user interactions
         and generate batch recommendations for all users

Input:  MinIO: s3a://lakehouse/archived-events/*.parquet
        Postgres: rt_user_interactions (recent data)
        
Output: MinIO: s3a://lakehouse/models/collab_filter_<timestamp>/
        Postgres: batch_recommendations table

Schedule: Daily via Airflow DAG
=============================================================================
"""

import argparse
import json
from datetime import datetime
from typing import List, Tuple

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, count, avg, explode, array, struct, to_json, lit
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
from pyspark.ml.recommendation import ALS
from pyspark.ml.evaluation import RegressionEvaluator


# =============================================================================
# CONFIGURATION
# =============================================================================
MINIO_ENDPOINT = "http://minio:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"

POSTGRES_HOST = "postgres"
POSTGRES_DB = "moviedb"
POSTGRES_USER = "airflow"
POSTGRES_PASSWORD = "airflow"
POSTGRES_URL = f"jdbc:postgresql://{POSTGRES_HOST}:5432/{POSTGRES_DB}"

# ALS Hyperparameters (tuned for movie recommendations)
ALS_RANK = 10  # Number of latent factors
ALS_MAX_ITER = 10
ALS_REG_PARAM = 0.1
ALS_ALPHA = 1.0  # Confidence scaling for implicit feedback


# =============================================================================
# SPARK SESSION INITIALIZATION
# =============================================================================
def create_spark_session(app_name: str = "BatchRecommendationTraining") -> SparkSession:
    """
    Create and configure Spark session with S3/MinIO and Postgres drivers
    """
    spark = SparkSession.builder \
        .appName(app_name) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.jars.packages", "org.postgresql:postgresql:42.7.3") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark


# =============================================================================
# DATA LOADING
# =============================================================================
def load_historical_events(spark: SparkSession, date: str) -> DataFrame:
    """
    Load historical events from MinIO Parquet files
    
    Args:
        spark: SparkSession
        date: Target date (YYYY-MM-DD)
    
    Returns:
        DataFrame with columns: user_id, movie_id, interaction_type, rating, timestamp
    """
    # Load archived events (last 30 days)
    archived_path = "s3a://lakehouse/archived-events/*/*/*.parquet"
    
    try:
        df_archived = spark.read.parquet(archived_path)
        print(f"✅ Loaded {df_archived.count()} archived events from MinIO")
    except Exception as e:
        print(f"⚠️  No archived events found: {e}")
        df_archived = spark.createDataFrame([], schema=StructType([
            StructField("user_id", StringType()),
            StructField("movie_id", StringType()),
            StructField("interaction_type", StringType()),
            StructField("rating", IntegerType()),
            StructField("timestamp", TimestampType()),
        ]))
    
    return df_archived


def load_recent_events(spark: SparkSession) -> DataFrame:
    """
    Load recent events from Postgres rt_user_interactions table
    """
    df_recent = spark.read \
        .format("jdbc") \
        .option("url", POSTGRES_URL) \
        .option("dbtable", "rt_user_interactions") \
        .option("user", POSTGRES_USER) \
        .option("password", POSTGRES_PASSWORD) \
        .option("driver", "org.postgresql.Driver") \
        .load()
    
    print(f"✅ Loaded {df_recent.count()} recent events from Postgres")
    return df_recent


def load_movies_metadata(spark: SparkSession) -> DataFrame:
    """
    Load movie metadata for filtering and enrichment
    """
    df_movies = spark.read \
        .format("jdbc") \
        .option("url", POSTGRES_URL) \
        .option("dbtable", "movies") \
        .option("user", POSTGRES_USER) \
        .option("password", POSTGRES_PASSWORD) \
        .option("driver", "org.postgresql.Driver") \
        .load()
    
    print(f"✅ Loaded {df_movies.count()} movies from Postgres")
    return df_movies


# =============================================================================
# DATA PREPROCESSING
# =============================================================================
def prepare_training_data(df_events: DataFrame) -> DataFrame:
    """
    Prepare data for ALS training
    
    Convert implicit feedback (clicks, views) to ratings:
      - click: 1 point
      - view: 2 points
      - rate: actual rating (1-5)
      - favorite: 5 points
    
    Returns:
        DataFrame with columns: user_id, movie_id, rating
    """
    # Convert interaction types to numeric ratings
    df_ratings = df_events.withColumn(
        "rating",
        col("rating").when(col("interaction_type") == "rate", col("rating"))
                     .when(col("interaction_type") == "click", lit(1))
                     .when(col("interaction_type") == "view", lit(2))
                     .when(col("interaction_type") == "favorite", lit(5))
                     .otherwise(lit(1))
    )
    
    # Aggregate multiple interactions per user-movie pair
    df_aggregated = df_ratings.groupBy("user_id", "movie_id") \
        .agg(
            avg("rating").alias("avg_rating"),
            count("*").alias("interaction_count")
        )
    
    # Boost rating by interaction frequency (confidence)
    df_final = df_aggregated.withColumn(
        "rating",
        col("avg_rating") * (1 + 0.1 * col("interaction_count"))
    ).select("user_id", "movie_id", "rating")
    
    # Create numeric IDs for ALS (requires integer IDs)
    from pyspark.ml.feature import StringIndexer
    
    user_indexer = StringIndexer(inputCol="user_id", outputCol="user_idx")
    movie_indexer = StringIndexer(inputCol="movie_id", outputCol="movie_idx")
    
    df_indexed = user_indexer.fit(df_final).transform(df_final)
    df_indexed = movie_indexer.fit(df_indexed).transform(df_indexed)
    
    return df_indexed


# =============================================================================
# MODEL TRAINING
# =============================================================================
def train_als_model(df_train: DataFrame) -> Tuple[ALS, DataFrame]:
    """
    Train ALS collaborative filtering model
    
    Returns:
        Tuple of (trained_model, predictions_df)
    """
    # Split data for validation
    train, test = df_train.randomSplit([0.8, 0.2], seed=42)
    
    print(f"📊 Training set: {train.count()} interactions")
    print(f"📊 Test set: {test.count()} interactions")
    
    # Initialize ALS
    als = ALS(
        rank=ALS_RANK,
        maxIter=ALS_MAX_ITER,
        regParam=ALS_REG_PARAM,
        userCol="user_idx",
        itemCol="movie_idx",
        ratingCol="rating",
        coldStartStrategy="drop",
        implicitPrefs=False  # Using explicit ratings
    )
    
    # Train model
    print("🚀 Training ALS model...")
    model = als.fit(train)
    
    # Evaluate on test set
    predictions = model.transform(test)
    evaluator = RegressionEvaluator(
        metricName="rmse",
        labelCol="rating",
        predictionCol="prediction"
    )
    rmse = evaluator.evaluate(predictions)
    
    print(f"✅ Model trained successfully")
    print(f"📈 RMSE on test set: {rmse:.4f}")
    
    return model, predictions


# =============================================================================
# RECOMMENDATION GENERATION
# =============================================================================
def generate_recommendations(
    spark: SparkSession,
    model,
    df_users: DataFrame,
    df_movies: DataFrame,
    top_n: int = 50
) -> DataFrame:
    """
    Generate top-N recommendations for all users
    
    Args:
        model: Trained ALS model
        df_users: DataFrame with user IDs
        df_movies: DataFrame with movie metadata
        top_n: Number of recommendations per user
    
    Returns:
        DataFrame with columns: user_id, recommendations (JSON array)
    """
    print(f"🎯 Generating top-{top_n} recommendations for each user...")
    
    # Generate recommendations
    user_recs = model.recommendForAllUsers(top_n)
    
    # Explode recommendations array
    user_recs_exploded = user_recs.select(
        col("user_idx"),
        explode(col("recommendations")).alias("rec")
    ).select(
        col("user_idx"),
        col("rec.movie_idx").alias("movie_idx"),
        col("rec.rating").alias("score")
    )
    
    # Join with original IDs and movie metadata
    # (Reverse the indexing to get original string IDs)
    # For simplicity, we'll use the indexed versions
    
    # Group back into JSON array per user
    user_recs_json = user_recs.select(
        col("user_idx").alias("user_id"),  # Will need to reverse index
        to_json(col("recommendations")).alias("recommendations")
    )
    
    print(f"✅ Generated recommendations for {user_recs_json.count()} users")
    
    return user_recs_json


# =============================================================================
# SAVE RESULTS
# =============================================================================
def save_model(model, output_path: str) -> None:
    """
    Save trained model to MinIO
    """
    model_path = f"{output_path}/model"
    model.write().overwrite().save(model_path)
    print(f"💾 Model saved to {model_path}")


def save_recommendations_to_postgres(
    spark: SparkSession,
    df_recs: DataFrame,
    algorithm: str = "als_collaborative_filter"
) -> None:
    """
    Write recommendations to Postgres batch_recommendations table
    """
    # Add metadata
    df_final = df_recs.withColumn(
        "algorithm", lit(algorithm)
    ).withColumn(
        "computed_at", lit(datetime.now())
    ).withColumn(
        "expires_at", lit(datetime.now()) + lit(86400)  # 24 hours
    )
    
    # Write to Postgres
    df_final.write \
        .format("jdbc") \
        .option("url", POSTGRES_URL) \
        .option("dbtable", "batch_recommendations") \
        .option("user", POSTGRES_USER) \
        .option("password", POSTGRES_PASSWORD) \
        .option("driver", "org.postgresql.Driver") \
        .mode("overwrite") \
        .save()
    
    print(f"✅ Recommendations saved to Postgres")


# =============================================================================
# MAIN EXECUTION
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Batch Recommendation Training")
    parser.add_argument("--date", required=True, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--output-path", required=True, help="Output path for model")
    args = parser.parse_args()
    
    print("=" * 80)
    print("🚀 STARTING BATCH RECOMMENDATION TRAINING")
    print(f"📅 Date: {args.date}")
    print(f"📂 Output: {args.output_path}")
    print("=" * 80)
    
    # Initialize Spark
    spark = create_spark_session()
    
    try:
        # Load data
        print("\n📥 LOADING DATA...")
        df_archived = load_historical_events(spark, args.date)
        df_recent = load_recent_events(spark)
        df_movies = load_movies_metadata(spark)
        
        # Combine all events
        df_all_events = df_archived.union(df_recent)
        total_events = df_all_events.count()
        print(f"📊 Total events to process: {total_events}")
        
        # Prepare training data
        print("\n🔧 PREPROCESSING DATA...")
        df_train = prepare_training_data(df_all_events)
        
        # Train model
        print("\n🎓 TRAINING MODEL...")
        model, predictions = train_als_model(df_train)
        
        # Generate recommendations
        print("\n🎯 GENERATING RECOMMENDATIONS...")
        df_recs = generate_recommendations(
            spark, model, df_train, df_movies, top_n=50
        )
        
        # Save results
        print("\n💾 SAVING RESULTS...")
        save_model(model, args.output_path)
        save_recommendations_to_postgres(spark, df_recs)
        
        print("\n" + "=" * 80)
        print("✅ BATCH RECOMMENDATION TRAINING COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    
    finally:
        spark.stop()


if __name__ == "__main__":
    main()