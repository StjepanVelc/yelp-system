from sqlalchemy import Column, String, Float, Integer, Boolean, Text, Index
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Business(Base):
    __tablename__ = "businesses"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    stars = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    is_open = Column(Boolean, nullable=True)
    categories = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_businesses_city", "city"),
        Index("ix_businesses_state", "state"),
        Index("ix_businesses_stars", "stars"),
        Index("ix_businesses_city_stars", "city", "stars"),
        Index("ix_businesses_is_open", "is_open"),
    )


class Review(Base):
    __tablename__ = "reviews"

    review_id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)
    business_id = Column(String, nullable=True)
    stars = Column(Float, nullable=True)
    useful = Column(Integer, nullable=True)
    funny = Column(Integer, nullable=True)
    cool = Column(Integer, nullable=True)
    text = Column(Text, nullable=True)
    date = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_reviews_business_id", "business_id"),
        Index("ix_reviews_user_id", "user_id"),
        Index("ix_reviews_stars", "stars"),
        Index("ix_reviews_business_stars", "business_id", "stars"),
        Index("ix_reviews_date", "date"),
    )


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    review_count = Column(Integer, nullable=True)
    yelping_since = Column(String, nullable=True)
    useful = Column(Integer, nullable=True)
    funny = Column(Integer, nullable=True)
    cool = Column(Integer, nullable=True)
    fans = Column(Integer, nullable=True)
    average_stars = Column(Float, nullable=True)
    elite = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_users_name", "name"),
        Index("ix_users_average_stars", "average_stars"),
        Index("ix_users_fans", "fans"),
    )


class Tip(Base):
    __tablename__ = "tips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=True)
    business_id = Column(String, nullable=True)
    text = Column(Text, nullable=True)
    date = Column(String, nullable=True)
    compliment_count = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_tips_business_id", "business_id"),
        Index("ix_tips_user_id", "user_id"),
        Index("ix_tips_date", "date"),
    )


class Checkin(Base):
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(String, nullable=True)
    date = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_checkins_business_id", "business_id"),
    )
  # comma-separated datetimes

