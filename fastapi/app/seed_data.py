
import asyncio
import os
import random
import asyncpg
import numpy as np

# Database Configuration
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://airflow:airflow@postgres:5432/moviedb")

# Sample Data (High Quality)
MOVIES = [
    {
        "id": "m_inception",
        "title": "Inception",
        "description": "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.",
        "genres": ["Sci-Fi", "Action", "Thriller"],
        "year": 2010,
        "director": "Christopher Nolan",
        "poster": "https://image.tmdb.org/t/p/w500/9gk7admal4zlWH9O46ggyEBDs5e.jpg",
        "rating": 8.8
    },
    {
        "id": "m_interstellar",
        "title": "Interstellar",
        "description": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
        "genres": ["Sci-Fi", "Drama", "Adventure"],
        "year": 2014,
        "director": "Christopher Nolan",
        "poster": "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
        "rating": 8.6
    },
    {
        "id": "m_dark_knight",
        "title": "The Dark Knight",
        "description": "When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.",
        "genres": ["Action", "Crime", "Drama"],
        "year": 2008,
        "director": "Christopher Nolan",
        "poster": "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
        "rating": 9.0
    },
    {
        "id": "m_matrix",
        "title": "The Matrix",
        "description": "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.",
        "genres": ["Sci-Fi", "Action"],
        "year": 1999,
        "director": "The Wachowskis",
        "poster": "https://image.tmdb.org/t/p/w500/f89U3ADr1oiB1s9GkdPOEpQZw5.jpg",
        "rating": 8.7
    },
    {
        "id": "m_shawshank",
        "title": "The Shawshank Redemption",
        "description": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.",
        "genres": ["Drama", "Crime"],
        "year": 1994,
        "director": "Frank Darabont",
        "poster": "https://image.tmdb.org/t/p/w500/q6y0Go1tsGEsmtFryDOJo3dEmqu.jpg",
        "rating": 9.3
    },
    {
        "id": "m_pulp_fiction",
        "title": "Pulp Fiction",
        "description": "The lives of two mob hitmen, a boxer, a gangster and his wife, and a pair of diner bandits intertwine in four tales of violence and redemption.",
        "genres": ["Crime", "Drama"],
        "year": 1994,
        "director": "Quentin Tarantino",
        "poster": "https://image.tmdb.org/t/p/w500/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg",
        "rating": 8.9
    },
    {
        "id": "m_fight_club",
        "title": "Fight Club",
        "description": "An insomniac office worker and a devil-may-care soapmaker form an underground fight club that evolves into much more.",
        "genres": ["Drama"],
        "year": 1999,
        "director": "David Fincher",
        "poster": "https://image.tmdb.org/t/p/w500/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
        "rating": 8.8
    },
    {
        "id": "m_forrest_gump",
        "title": "Forrest Gump",
        "description": "The presidencies of Kennedy and Johnson, the events of Vietnam, Watergate and other historical events unfold from the perspective of an Alabama man with an IQ of 75.",
        "genres": ["Drama", "Romance"],
        "year": 1994,
        "director": "Robert Zemeckis",
        "poster": "https://image.tmdb.org/t/p/w500/arw2vcBveWOVZr6pxd9XTd1TdQa.jpg",
        "rating": 8.8
    },
    {
        "id": "m_lotr_return",
        "title": "The Lord of the Rings: The Return of the King",
        "description": "Gandalf and Aragorn lead the World of Men against Sauron's army to draw his gaze from Frodo and Sam as they approach Mount Doom with the One Ring.",
        "genres": ["Adventure", "Fantasy", "Action"],
        "year": 2003,
        "director": "Peter Jackson",
        "poster": "https://image.tmdb.org/t/p/w500/rCzpDGLbOoPwLjy3OAm5NUPOTrC.jpg",
        "rating": 9.0
    },
    {
        "id": "m_godfather",
        "title": "The Godfather",
        "description": "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.",
        "genres": ["Crime", "Drama"],
        "year": 1972,
        "director": "Francis Ford Coppola",
        "poster": "https://image.tmdb.org/t/p/w500/3bhkrj58Vtu7enYsRolD1fZdja1.jpg",
        "rating": 9.2
    },
    {
        "id": "m_spider_verse",
        "title": "Spider-Man: Across the Spider-Verse",
        "description": "Miles Morales catapults across the Multiverse, where he encounters a team of Spider-People charged with protecting its very existence.",
        "genres": ["Animation", "Action", "Adventure"],
        "year": 2023,
        "director": "Joaquim Dos Santos",
        "poster": "https://image.tmdb.org/t/p/w500/8Vt6mWEReuy4Of61Lnj5Xj704m8.jpg",
        "rating": 8.7
    },
    {
        "id": "m_oppenheimer",
        "title": "Oppenheimer",
        "description": "The story of American scientist J. Robert Oppenheimer and his role in the developing of the atomic bomb.",
        "genres": ["Biography", "Drama", "History"],
        "year": 2023,
        "director": "Christopher Nolan",
        "poster": "https://image.tmdb.org/t/p/w500/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg",
        "rating": 8.6
    },
    {
        "id": "m_barbie",
        "title": "Barbie",
        "description": "Barbie and Ken are having the time of their lives in the colorful and seemingly perfect world of Barbie Land. However, when they get a chance to go to the real world, they soon discover the joys and perils of living among humans.",
        "genres": ["Comedy", "Adventure", "Fantasy"],
        "year": 2023,
        "director": "Greta Gerwig",
        "poster": "https://image.tmdb.org/t/p/w500/iuFNMS8U5cb6xf8gc9524E69LzR.jpg",
        "rating": 7.3
    },
    {
        "id": "m_parasite",
        "title": "Parasite",
        "description": "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.",
        "genres": ["Thriller", "Drama", "Comedy"],
        "year": 2019,
        "director": "Bong Joon Ho",
        "poster": "https://image.tmdb.org/t/p/w500/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg",
        "rating": 8.5
    },
    {
        "id": "m_dune2",
        "title": "Dune: Part Two",
        "description": "Paul Atreides unites with Chani and the Fremen while on a warpath of revenge against the conspirators who destroyed his family.",
        "genres": ["Sci-Fi", "Adventure"],
        "year": 2024,
        "director": "Denis Villeneuve",
        "poster": "https://image.tmdb.org/t/p/w500/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg",
        "rating": 8.8
    }
]

async def seed_data():
    print("🌱 Starting data seeding...")
    
    try:
        conn = await asyncpg.connect(POSTGRES_DSN)
        
        # 1. Update Schema if needed
        print("🔧 Checking schema...")
        try:
            await conn.execute("ALTER TABLE movies ADD COLUMN IF NOT EXISTS poster_url VARCHAR(1000);")
            print("✅ Schema updated (poster_url added)")
        except Exception as e:
            print(f"⚠️ Schema check warning: {e}")

        # 2. Insert Movies
        print("🎬 Inserting movies...")
        for movie in MOVIES:
            # Generate random embedding
            embedding = np.random.rand(768).tolist()
            # Convert to string format for SQL
            embedding_str = f"[{','.join(map(str, embedding))}]"
            
            await conn.execute("""
                INSERT INTO movies (
                    movie_id, title, description, genres, release_year, 
                    director, poster_url, avg_rating, embedding
                ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9::vector)
                ON CONFLICT (movie_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    poster_url = EXCLUDED.poster_url,
                    avg_rating = EXCLUDED.avg_rating
            """, 
            movie['id'], 
            movie['title'], 
            movie['description'], 
            json.dumps(movie['genres']),
            movie['year'],
            movie['director'],
            movie['poster'],
            movie['rating'],
            embedding_str
            )
        print(f"✅ Inserted/Updated {len(MOVIES)} movies")

        # 3. Insert Interactions (Demo User)
        print("👤 Creating demo user interactions...")
        
        demo_user = "user_demo_1"
        watched_movies = MOVIES[:3] # First 3 movies
        
        # Upsert user profile
        user_vector = np.random.rand(768).tolist()
        user_vector_str = f"[{','.join(map(str, user_vector))}]"
        
        await conn.execute("""
            INSERT INTO user_profiles (user_id, preference_vector, total_interactions)
            VALUES ($1, $2::vector, $3)
            ON CONFLICT (user_id) DO NOTHING
        """, demo_user, user_vector_str, len(watched_movies))
        
        # Insert interactions
        for movie in watched_movies:
            await conn.execute("""
                INSERT INTO rt_user_interactions (
                    user_id, movie_id, interaction_type, rating
                ) VALUES ($1, $2, 'rate', 5)
                ON CONFLICT DO NOTHING
            """, demo_user, movie['id'])

        print("✅ Demo user created")
        
    except Exception as e:
        print(f"❌ Error during seeding: {e}")
    finally:
        await conn.close()
        print("🌱 Seeding complete!")

import json
if __name__ == "__main__":
    asyncio.run(seed_data())
