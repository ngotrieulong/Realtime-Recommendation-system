
import sys
import os

# Add parent directory to path so we can import app
sys.path.append("/Users/ngolong/Documents/CODE_BASED/movie-recommendation/fastapi")

try:
    from app.main import app
    print("✅ Successfully imported app.main.app")
    
    from app.models.movie import MovieDB
    print("✅ Successfully imported app.models.movie")
    
    from app.services.recommendation_service import RecommendationService
    print("✅ Successfully imported app.services.recommendation_service")
    
    print("Verification passed!")
except ImportError as e:
    import traceback
    traceback.print_exc()
    print(f"❌ ImportError: {e}")
    sys.exit(1)
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"❌ Exception: {e}")
    sys.exit(1)
