"""SQLAlchemy declarative base shared across all models."""
from sqlalchemy.orm import DeclarativeBase, MappedColumn
from sqlalchemy import Column, DateTime, func
from datetime import datetime


class Base(DeclarativeBase):
    pass
