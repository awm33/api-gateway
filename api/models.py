import binascii
import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import CIDR
from sqlalchemy import func, Index, UniqueConstraint
from sqlalchemy.orm import validates
from flask_login import UserMixin
from passlib.hash import argon2
from netaddr import IPNetwork

db = SQLAlchemy()

class BaseMixin(object):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime,
                           nullable=False,
                           server_default=func.now())
    updated_at = db.Column(db.DateTime,
                           nullable=False,
                           server_default=func.now(),
                           onupdate=func.now())

class User(UserMixin, BaseMixin, db.Model):
    __tablename__ = 'users'

    active = db.Column(db.Boolean, nullable=False)
    username = db.Column(db.String, index=True, nullable=False)
    email = db.Column(db.String)
    role = db.Column(db.Enum('normal','admin', name='user_roles'), nullable=False)
    hashed_password = db.Column(db.String)

    @property
    def is_active(self):
        return self.active

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def password(self):
        raise Exception('Cannot get password from User.')

    def get_password_hash(self, password):
        return argon2.using(rounds=4).hash(password)

    @password.setter
    def password(self, password):
        if password is None:
            self.hashed_password = None
        else:
            self.hashed_password = self.get_password_hash(password)

    def verify_password(self, input_password):
        if not self.hashed_password or not input_password:
            return False

        return argon2.verify(input_password, self.hashed_password)

    def __init__(self, **data):
        self.active = data.get('active')
        self.username = data.get('username')
        self.email = data.get('email')
        self.role = data.get('role')
        self.password = data.get('password')

    def __repr__(self):
        return '<User id: {} active {} username: {} email: {}>'.format(self.id, \
                                                                       self.active, \
                                                                       self.username, \
                                                                       self.email)

class Key(BaseMixin, db.Model):
    __tablename__ = 'keys'

    key = db.Column(db.String, index=True)
    active = db.Column(db.Boolean, nullable=False)
    owner_name = db.Column(db.String)
    contact_name = db.Column(db.String)
    contact_email = db.Column(db.String)
    expires_at = db.Column(db.DateTime)

    ## TODO: add columns for custom rate limit

    def __init__(self, **data):
        self.active = data.get('active')
        self.owner_name = data.get('owner_name')
        self.contact_name = data.get('contact_name')
        self.contact_email = data.get('contact_email')
        self.expires_at = data.get('expires_at')

        self.key = binascii.hexlify(os.urandom(32)).decode('utf-8')

    def __repr__(self):
        return '<Key id: {} active: {} owner_name: {}>'.format(self.id, \
                                                               self.active, \
                                                               self.owner_name)

class Ban(BaseMixin, db.Model):
    __tablename__ = 'bans'

    active = db.Column(db.Boolean, nullable=False)
    title = db.Column(db.String)
    description = db.Column(db.String)
    cidr_blocks = db.relationship('CIDRBlock',
                                  backref='ban',
                                  passive_deletes=True # required to cascade deletes
                                  # ,
                                  # lazy='joined'
                                  )
    expires_at = db.Column(db.DateTime)

    def __init__(self, **data):
        self.active = data.get('active')
        self.title = data.get('title')
        self.description = data.get('description')
        self.expires_at = data.get('expires_at')

        cidr_blocks = data.get('cidr_blocks', [])

        for block in cidr_blocks:
            self.cidr_blocks.append(block)

    def __repr__(self):
        return '<Ban id: {} cidr: {} active: {} expires_at: {}>'.format(self.id, \
                                                                        self.active, \
                                                                        self.title, \
                                                                        self.expires_at)

class CIDRBlock(BaseMixin, db.Model):
    __tablename__ = 'cidr_blocks'

    ban_id = db.Column(db.Integer, db.ForeignKey('bans.id', ondelete='CASCADE'))
    cidr = db.Column(CIDR, nullable=False)

    __table_args__ = (
        Index('idx_cidr', cidr, postgresql_using='gist', postgresql_ops={'cidr': 'inet_ops'}),)

    def __init__(self, **data):
        self.cidr = data['cidr']

    def __repr__(self):
        return '<CIDRBlock id: {} ban_id: {} cidr: {}>'.format(self.id, self.ban_id, self.cidr)

    @validates('cidr')
    def validate_cidr(self, key, cidr):
        IPNetwork(cidr) # will raise an exception on an invalid network
        return cidr

class RequestsAggregate(db.Model):
    __tablename__ = 'requests_aggregates'

    id = db.Column(db.BigInteger, primary_key=True)
    key_id = db.Column(db.Integer, db.ForeignKey('keys.id'))
    ip = db.Column(db.String(), nullable=False) ## TODO: inet ????
    endpoint_name = db.Column(db.String()) ## TODO: !!! nullable?
    minute = db.Column(db.DateTime(), nullable=False)
    request_count = db.Column(db.BigInteger(), nullable=False)
    sum_elapsed_time = db.Column(db.BigInteger(), nullable=False)
    sum_bytes = db.Column(db.BigInteger(), nullable=False)
    sum_2xx = db.Column(db.BigInteger(), nullable=False)
    sum_3xx = db.Column(db.BigInteger(), nullable=False)
    sum_4xx = db.Column(db.BigInteger(), nullable=False)
    sum_429 = db.Column(db.BigInteger(), nullable=False)
    sum_5xx = db.Column(db.BigInteger(), nullable=False)

    __table_args__ = (
        Index('uniq_request_agg_null',
              ip,
              endpoint_name,
              minute,
              unique=True,
              postgresql_where=key_id == None),
        Index('uniq_request_agg_not_null',
              key_id,
              ip,
              endpoint_name,
              minute,
              unique=True,
              postgresql_where=key_id != None),)


    def __init__(self, **data):
        self.key_id = data['key_id']
        self.ip = data['ip']
        self.endpoint_name = data['endpoint_name']
        self.minute = data['minute']
        self.request_count = data['request_count']
        self.sum_elapsed_time = data['sum_elapsed_time']
        self.sum_bytes = data['sum_bytes']
        self.sum_2xx = data['sum_2xx']
        self.sum_3xx = data['sum_3xx']
        self.sum_4xx = data['sum_4xx']
        self.sum_429 = data['sum_429']
        self.sum_5xx = data['sum_5xx']

    def __repr__(self):
        return '<RequestsAggregate id: {} key_id: {} ip: {} endpoint_name: {} minute: {} request_count: {}>'.format(
            self.id,
            self.key_id,
            self.ip,
            self.endpoint_name,
            self.minute,
            self.request_count)
