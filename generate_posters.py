
import os
import random

POSTERS_DIR = "frontend/public/posters"
MOVIES = [
    {"id": "m_inception", "title": "Inception"},
    {"id": "m_interstellar", "title": "Interstellar"},
    {"id": "m_dark_knight", "title": "The Dark Knight"},
    {"id": "m_matrix", "title": "The Matrix"},
    {"id": "m_shawshank", "title": "The Shawshank Redemption"},
    {"id": "m_pulp_fiction", "title": "Pulp Fiction"},
    {"id": "m_fight_club", "title": "Fight Club"},
    {"id": "m_godfather", "title": "The Godfather"},
    {"id": "m_spider_verse", "title": "Spider-Man: Across the Spider-Verse"},
    {"id": "m_oppenheimer", "title": "Oppenheimer"},
    {"id": "m_barbie", "title": "Barbie"},
    {"id": "m_parasite", "title": "Parasite"}
]

COLORS = [
    ("#2c3e50", "#ecf0f1"), ("#8e44ad", "#ecf0f1"), ("#2980b9", "#ecf0f1"), 
    ("#c0392b", "#ecf0f1"), ("#16a085", "#ecf0f1"), ("#d35400", "#ecf0f1"),
    ("#7f8c8d", "#ecf0f1"), ("#27ae60", "#ecf0f1")
]

def create_svg(movie_id, title):
    bg_color, text_color = random.choice(COLORS)
    svg_content = f'''<svg width="300" height="450" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="{bg_color}"/>
  <text x="50%" y="50%" font-family="Arial, sans-serif" font-size="24" fill="{text_color}" text-anchor="middle" dy=".3em">{title}</text>
  <text x="50%" y="90%" font-family="Arial, sans-serif" font-size="14" fill="{text_color}" text-anchor="middle" opacity="0.7">MovieRec AI</text>
</svg>'''
    
    with open(f"{POSTERS_DIR}/{movie_id}.svg", "w") as f:
        f.write(svg_content)
    print(f"Generated {movie_id}.svg")

if __name__ == "__main__":
    if not os.path.exists(POSTERS_DIR):
        os.makedirs(POSTERS_DIR)
        
    for movie in MOVIES:
        create_svg(movie["id"], movie["title"])
