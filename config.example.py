# Set Twilio account parameters to be passed in to TwilioRestClient constructor
# (http://twilio-python.readthedocs.io/en/latest/api/rest/index.html#twilio.rest.TwilioRestClient)
# - account: Account SID from dashboard (https://www.twilio.com/console)
# - token: Auth Token from dashboard
#
# Alternatively, set up API keys (https://www.twilio.com/console/dev-tools/api-keys):
# - account: API Key SID
# - token: API Key Token
# - request_account: Account SID
TWILIO_REST_CLIENT_KWARGS = {
	'account': '<Account SID or API Key SID>',
	'token': '<Secret Token for account or API key>',
	'request_account': '<Account SID, but only if using API Key>'
}

# Robot voice to use for Twilio <Say> verb
# (https://www.twilio.com/docs/api/twiml/say#attributes-voice)
TWILIO_VOICE = 'woman'

# Default caller ID from number--needs to be a Twilio number under
# your account or one for which you've verified caller ID
TWILIO_DEFAULT_FROM = '+12025551234'

# Redis connection constructor arguments
# (https://redis-py.readthedocs.io/en/latest/#redis.Redis)
REDIS_CLIENT_KWARGS = {
	'host': 'localhost',
	'port': 6379,
	'db': 0
}

# TTL to use for more transient Redis data
REDIS_TTL = 60 * 60 * 2