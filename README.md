# Redial Congress

Calling members of the US Congress is [the best way](https://www.nytimes.com/2016/11/22/us/politics/heres-why-you-should-call-not-email-your-legislators.html) for a constituent's voice to be heard. But it's often a nuisance of overloaded switchboards and endless busy signals. This application aims to reduce that hassle.

## Getting started

You'll need a [Twilio](https://www.twilio.com) account and inbound number, and a server to respond to HTTP requests from Twilio.

The application needs access to a [Redis](https://redis.io/) instance and depends on the Python packages listed in [requirements.txt](./requirements.txt) (``pip install -r requirements.txt``).

Copy (config.example.py)[./config.example.py] to `config.py` and set all necessary values.

To run the application for development:

```
$ python redialer.py
 * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
```
or:

```
$ export FLASK_APP=redialer.py
$ flask run
 * Serving Flask app "redialer"
 * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
```

When developing locally behind NAT, [ngrok](https://ngrok.com/) makes things a lot easier.

Use something like [Gunicorn](http://flask.pocoo.org/docs/0.12/deploying/wsgi-standalone/) for production deployment.

When setting up your [inbound Twilio number](https://www.twilio.com/console/phone-numbers/incoming) or [TwiML app](https://www.twilio.com/console/phone-numbers/dev-tools/twiml-apps), use the following settings:
- **Request URL:** `http://example.com/` (e.g. the `/` route of the application)
- **Status Callback URL:** `http://example.com/inbound/ping` (the `/inbound/ping` route of the application)
