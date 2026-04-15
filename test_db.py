from sqlalchemy import create_engine

engine = create_engine("postgresql://postgres:stipe245gaba@localhost:5432/yelp")

try:
    conn = engine.connect()
    print("CONNECTED")
    conn.close()
except Exception as e:
    print("ERROR:", e)
