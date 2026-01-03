
export const MOCK_MOVIES = [
    {
        "movie_id": "m_inception",
        "title": "Inception",
        "description": "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.",
        "genres": ["Sci-Fi", "Action", "Thriller"],
        "release_year": 2010,
        "director": "Christopher Nolan",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/2/2e/Inception_%282010%29_theatrical_poster.jpg",
        "score": 0.98,
        "source": "hybrid"
    },
    {
        "movie_id": "m_interstellar",
        "title": "Interstellar",
        "description": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
        "genres": ["Sci-Fi", "Drama", "Adventure"],
        "release_year": 2014,
        "director": "Christopher Nolan",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/b/bc/Interstellar_film_poster.jpg",
        "score": 0.95,
        "source": "batch"
    },
    {
        "movie_id": "m_dark_knight",
        "title": "The Dark Knight",
        "description": "When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.",
        "genres": ["Action", "Crime", "Drama"],
        "release_year": 2008,
        "director": "Christopher Nolan",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/1/1c/The_Dark_Knight_%282008_film%29.jpg",
        "score": 0.92,
        "source": "realtime"
    },
    {
        "movie_id": "m_matrix",
        "title": "The Matrix",
        "description": "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.",
        "genres": ["Sci-Fi", "Action"],
        "release_year": 1999,
        "director": "The Wachowskis",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/c/c1/The_Matrix_Poster.jpg",
        "score": 0.89,
        "source": "batch"
    },
    {
        "movie_id": "m_shawshank",
        "title": "The Shawshank Redemption",
        "description": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.",
        "genres": ["Drama", "Crime"],
        "release_year": 1994,
        "director": "Frank Darabont",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/8/81/ShawshankRedemptionMoviePoster.jpg",
        "score": 0.99,
        "source": "popular"
    },
    {
        "movie_id": "m_pulp_fiction",
        "title": "Pulp Fiction",
        "description": "The lives of two mob hitmen, a boxer, a gangster and his wife, and a pair of diner bandits intertwine in four tales of violence and redemption.",
        "genres": ["Crime", "Drama"],
        "release_year": 1994,
        "director": "Quentin Tarantino",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/3/3b/Pulp_Fiction_%281994%29_poster.jpg",
        "score": 0.94,
        "source": "hybrid"
    },
    {
        "movie_id": "m_fight_club",
        "title": "Fight Club",
        "description": "An insomniac office worker and a devil-may-care soapmaker form an underground fight club that evolves into much more.",
        "genres": ["Drama"],
        "release_year": 1999,
        "director": "David Fincher",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/f/fc/Fight_Club_poster.jpg",
        "score": 0.91,
        "source": "realtime"
    },
    {
        "movie_id": "m_godfather",
        "title": "The Godfather",
        "description": "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.",
        "genres": ["Crime", "Drama"],
        "release_year": 1972,
        "director": "Francis Ford Coppola",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/a/af/The_Godfather%2C_The_Game.jpg",
        "score": 0.97,
        "source": "batch"
    },
    {
        "movie_id": "m_spider_verse",
        "title": "Spider-Man: Across the Spider-Verse",
        "genres": ["Animation", "Action", "Adventure"],
        "release_year": 2023,
        "director": "Joaquim Dos Santos",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/b/b4/Spider-Man-_Across_the_Spider-Verse_poster.jpg",
        "score": 0.96,
        "source": "realtime"
    },
    {
        "movie_id": "m_oppenheimer",
        "title": "Oppenheimer",
        "genres": ["Biography", "Drama", "History"],
        "release_year": 2023,
        "director": "Christopher Nolan",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/4/4a/Oppenheimer_%28film%29.jpg",
        "score": 0.95,
        "source": "batch"
    },
    {
        "movie_id": "m_barbie",
        "title": "Barbie",
        "genres": ["Comedy", "Adventure", "Fantasy"],
        "release_year": 2023,
        "director": "Greta Gerwig",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/0/0b/Barbie_2023_poster.jpg",
        "score": 0.88,
        "source": "hybrid"
    },
    {
        "movie_id": "m_parasite",
        "title": "Parasite",
        "genres": ["Thriller", "Drama", "Comedy"],
        "release_year": 2019,
        "director": "Bong Joon Ho",
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/5/53/Parasite_%282019_film%29.png",
        "score": 0.93,
        "source": "realtime"
    }
];

export const MOCK_METRICS = {
    timestamp: new Date().toISOString(),
    cache: {
        total_requests: 1250,
        cache_hits: 1100,
        hit_rate_percent: 88.5
    },
    recommendations: {
        total_served: 5000,
        total_clicks: 450,
        ctr_percent: 9.0
    }
};
