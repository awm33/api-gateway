import os

import flask
from flask.sessions import SecureCookieSessionInterface
from flask_restful import Resource, Api
from flask_login import LoginManager, AnonymousUserMixin, current_user
from flask_cors import CORS
from restful_ben.auth import SessionResource

from api_gateway.models import db, User
from api_gateway import resources

app = flask.Flask(__name__)
app.config['DEBUG'] = os.getenv('DEBUG', False)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SESSION_COOKIE_NAME'] = 'gatewaysession'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = int(os.getenv('FLASK_PERMANENT_SESSION_LIFETIME', 43200))
app.config['SESSION_COOKIE_DOMAIN'] = os.getenv('FLASK_SESSION_DOMAIN', None)
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_SESSION_SECURE', False)
app.config['SECRET_KEY'] = os.getenv('FLASK_SESSION_SECRET_KEY')

# secret to identify gateway API requests
GATEWAY_KEY = os.getenv('GATEWAY_KEY', None)

db.init_app(app)
api = Api(app)
CORS(app, supports_credentials=True)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).filter(User.id == user_id).first()

class GatewayUser(AnonymousUserMixin):
    role = 'gateway'

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

@login_manager.request_loader
def load_user_from_request(request):
    if GATEWAY_KEY == None:
        return None
    api_key = request.headers.get('Authorization')
    if api_key:
        api_key = api_key.replace('Bearer ', '', 1)
        if api_key == GATEWAY_KEY:
            return GatewayUser()
    return None

## Skip creating a session for API requests
class CustomSessionInterface(SecureCookieSessionInterface):
    def save_session(self, *args, **kwargs):
        if current_user and hasattr(current_user, 'role') and current_user.role == 'gateway':
            return
        return super(CustomSessionInterface, self).save_session(*args,
                                                                **kwargs)

app.session_interface = CustomSessionInterface()

class LocalSessionResource(SessionResource):
    User = User
    session = db.session
    csrf = resources.csrf

with app.app_context():
    ## TODO: analytics reporting resource(s)
    ## TODO: endpoints resource - will need to load config file

    api.add_resource(resources.UserListResource, '/users')
    api.add_resource(resources.UserResource, '/users/<int:instance_id>')
    api.add_resource(LocalSessionResource, '/session')
    api.add_resource(resources.BanListResource, '/bans')
    api.add_resource(resources.BanResource, '/bans/<int:instance_id>')
    api.add_resource(resources.CIDRBlockListResource, '/bans/cidr-blocks')
    api.add_resource(resources.CIDRBlockResource, '/bans/cidr-blocks/<int:instance_id>')
    api.add_resource(resources.KeyListResource, '/keys')
    api.add_resource(resources.KeyResource, '/keys/<int:instance_id>')

## dev server
if __name__ == '__main__':
    app.run(host='0.0.0.0')
