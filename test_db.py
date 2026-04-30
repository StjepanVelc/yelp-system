import os

from sqlalchemy import create_engine, text

e = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:change_me@localhost:5432/yelp"))
with e.connect() as c:
    cols = c.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='reviews' ORDER BY ordinal_position")).fetchall()
    for col in cols:
        print(col[0], col[1])
    print()
    rows = c.execute(text("SELECT * FROM reviews WHERE business_id='ROeacJQwBeh05Rqg7F6TCg' ORDER BY date DESC LIMIT 3")).fetchall()
    for row in rows:
        print(dict(row._mapping))
