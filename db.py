import datetime
import hashlib
import os
import bcrypt

from flask_sqlalchemy import SQLAlchemy
from geopy.geocoders import Nominatim

db = SQLAlchemy()

# association table for many-to-many relationship between User and Location
association_table = db.Table(
    "association",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id")),
    db.Column("location_id", db.Integer, db.ForeignKey("locations.id"))
)


class User(db.Model):
    """
    User model

    Has a one-to-many relationship with Comment
    Has a one-to-many relationship with Position
    Has a many-to-many relationship with Location (favorites)
    """
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False, unique=True)
    password_digest = db.Column(db.String, nullable=False)
    comments = db.relationship("Comment", cascade="delete")
    positions = db.relationship("Position", cascade="delete")
    favorites = db.relationship(
        "Location", secondary=association_table, back_populates="fav_users")

    # session information
    session_token = db.Column(db.String, nullable=False, unique=True)
    session_expiration = db.Column(db.DateTime, nullable=False)
    update_token = db.Column(db.String, nullable=False, unique=True)

    def __init__(self, **kwargs):
        """
        Initializes User object
        """
        self.name = kwargs.get("name")
        self.email = kwargs.get("email")
        self.password_digest = bcrypt.hashpw(kwargs.get(
            "password").encode("utf8"), bcrypt.gensalt(rounds=13))
        self.renew_session()

    def _urlsafe_base_64(self):
        """
        Randomly generates hashed tokens (for session_token and update_token)
        """
        return hashlib.sha1(os.urandom(64)).hexdigest()

    def renew_session(self):
        """
        Renews login session (creates new sesssion token, sets expiration to be a day from now
        and creates a new update token)
        """
        self.session_token = self._urlsafe_base_64()
        self.session_expiration = datetime.datetime.now() + datetime.timedelta(days=1)
        self.update_token = self._urlsafe_base_64()

    def verify_password(self, password):
        """
        Checks if password passed in matches stored password of user
        """
        return bcrypt.checkpw(password.encode("utf8"), self.password_digest)

    def verify_session_token(self, session_token):
        """
        Checks the session token of a user
        """
        return session_token == self.session_token and datetime.datetime.now() < self.session_expiration

    def verify_update_token(self, update_token):
        """
        Checks the update token of a user
        """
        return update_token == self.update_token

    def serialize(self):
        """
        Serializes User object [not including comments or positions]
        """
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "favorites": [f.simple_serialize() for f in self.favorites],
            "session_token": self.session_token,
            "session_expiration": str(self.session_expiration),
            "update_token": self.update_token
        }

    def simple_serialize(self):
        """
        Simply serializes User object
        """
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email
        }


class Location(db.Model):
    """
    Location model (i.e. Morrison Dining, Uris Library)

    Has a one-to-many relationship with Comment
    Has a many-to-many relationship with User (favorites)
    """
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    comments = db.relationship("Comment", cascade="delete")
    address = db.Column(db.String, nullable=False)
    latitude = db.Column(db.Integer, nullable=False)
    longitude = db.Column(db.Integer, nullable=False)
    # busyness = db.Column(db.Integer, nullable=False) # might not need
    fav_users = db.relationship(
        "User", secondary=association_table, back_populates="favorites")

    def __init__(self, **kwargs):
        """
        Initializes Location object
        """
        self.name = kwargs.get("name", "")
        self.address = kwargs.get("address")
        geolocator = Nominatim(user_agent="spaced_out")
        region = geolocator.geocode(self.address)
        self.latitude = region.latitude
        self.longitude = region.longitude

    def serialize(self):
        """
        Serializes a Location object
        """
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "comments": [c.simple_serialize() for c in self.comments],
            "fav_users": [f.simple_serialize() for f in self.fav_users]
        }

    def simple_serialize(self):
        """
        Simply serializes a Location object
        """
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address
        }


class Comment(db.Model):
    """
    Model for comments

    Has a one-to-many relationship with Location and User
    Comments expire after 2 hours
    """
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    text = db.Column(db.String)
    number = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey(
        "locations.id"), nullable=False)
    timestamp = db.Column(db.String)
    expired = db.Column(db.Boolean)  # remove completely and let frontend deal?

    # keeping track of expiration date
    session_expiration = db.Column(db.DateTime, nullable=False)

    def __init__(self, **kwargs):
        """
        Initializes Comment object
        """
        self.text = kwargs.get("text", "")
        self.number = kwargs.get("number", -1)
        self.user_id = kwargs.get("user_id")
        self.location_id = kwargs.get("location_id")
        self.session_expiration = datetime.datetime.now() + datetime.timedelta(minutes=3)
        self.timestamp = datetime.datetime.now()
        self.expired = False

    def serialize(self):
        """
        Serializes a Comment object
        """
        return {
            "id": self.id,
            "text": self.text,
            "user_id":  User.query.filter_by(id=self.user_id).first().id,
            "location_id": Location.query.filter_by(id=self.location_id).first().id,
            "time_stamp": str(self.timestamp),
            "expiration": str(self.session_expiration),
            "expired": bool(self.session_expiration >= datetime.datetime.now())
        }

    def simple_serialize(self):
        """
        Simply serializes a Comment object
        """
        return {
            "id": self.id,
            "text": self.text,
            "timestamp": str(self.timestamp)
        }


class Position(db.Model):
    """
    Model for positional data of Users

    Has a one-to-many relationship with Users (Users will have multiple locations with times stored in database)    
    """
    __tablename__ = "positions"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    latitude = db.Column(db.Integer, nullable=False)
    longitude = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime)

    def __init__(self, **kwargs):
        """
        Initializes Position object
        """
        self.user_id = kwargs.get("user_id")
        self.latitude = kwargs.get("latitude")
        self.longitude = kwargs.get("longitude")
        self.timestamp = datetime.datetime.now()

    def serialize(self):
        """
        Serializes Position object
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timestamp": str(self.timestamp)
        }

    def simple_serialize(self):
        """
        Simply serializes Position object
        """
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timestamp": str(self.timestamp)
        }
