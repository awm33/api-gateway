import binascii
import os

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import CIDR, INET
from sqlalchemy import func, Index, UniqueConstraint
from sqlalchemy.orm import validates
from flask_login import UserMixin
from passlib.hash import argon2
from netaddr import IPNetwork
from restful_ben.auth import UserAuthMixin

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

class User(UserAuthMixin, UserMixin, BaseMixin, db.Model):
    __tablename__ = 'users'

    active = db.Column(db.Boolean, nullable=False)
    email = db.Column(db.String)
    role = db.Column(db.Enum('normal','admin', name='user_roles'), nullable=False)

    @property
    def is_active(self):
        return self.active

    @property
    def is_admin(self):
        return self.role == 'admin'

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

    key = db.Column(db.String, unique=True)
    active = db.Column(db.Boolean, index=True, nullable=False)
    owner_name = db.Column(db.String)
    contact_name = db.Column(db.String)
    contact_email = db.Column(db.String)

    def __init__(self, **data):
        self.active = data.get('active')
        self.owner_name = data.get('owner_name')
        self.contact_name = data.get('contact_name')
        self.contact_email = data.get('contact_email')

        self.key = binascii.hexlify(os.urandom(32)).decode('utf-8')

    def __repr__(self):
        return '<Key id: {} active: {} owner_name: {}>'.format(self.id, \
                                                               self.active, \
                                                               self.owner_name)

class Ban(BaseMixin, db.Model):
    __tablename__ = 'bans'

    title = db.Column(db.String)
    description = db.Column(db.String)
    cidr_blocks = db.relationship('CIDRBlock',
                                  backref='ban',
                                  cascade='all, delete-orphan',
                                  passive_deletes=True # required to cascade deletes
                                  # ,
                                  # lazy='joined'
                                  )

    def __init__(self, **data):
        self.title = data.get('title')
        self.description = data.get('description')

        cidr_blocks = data.get('cidr_blocks', [])

        for block in cidr_blocks:
            self.cidr_blocks.append(block)

    def __repr__(self):
        return '<Ban id: {} cidr: {}>'.format(self.id, self.title)

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
    ip = db.Column(INET, nullable=False)
    endpoint_name = db.Column(db.String())
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
        Index('uniq_request_agg',
              func.coalesce(key_id, -1),
              ip,
              func.coalesce(endpoint_name, '&&--'),
              minute,
              unique=True),)


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
