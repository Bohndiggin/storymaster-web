"""Pydantic DTOs for the v1 REST API.

Hand-written rather than auto-generated from SQLAlchemy because the on-the-wire
shape doesn't always match the ORM (we strip user_id from responses, expose
enums as their string values, etc.).
"""
