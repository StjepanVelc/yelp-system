import jwt
import datetime

secret = 'dev-secret-change-me'
payload = {
    'iss': 'yelp-auth',
    'aud': 'yelp-api',
    'sub': 'qVc8ODYU5SZjKXVBgXdI7w',
    'roles': ['business:read', 'recommendation:read'],
    'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
}
token = jwt.encode(payload, secret, algorithm='HS256')
print(token)
