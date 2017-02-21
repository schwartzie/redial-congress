from flask import Flask, request, redirect, url_for, render_template, jsonify
import datetime
import json
import math
import twilio
import twilio.twiml
from callstatemanager import CallStateManager
import congress

app = Flask(__name__)
app.config.from_object('config')

TWILIO_VOICE = app.config['TWILIO_VOICE']

TRC =twilio.rest.TwilioRestClient(**app.config['TWILIO_REST_CLIENT_KWARGS'])
CallState = CallStateManager(conn_args=app.config['REDIS_CLIENT_KWARGS'], ttl=app.config['REDIS_TTL'])

def start_outbound_call(response, inbound_sid, from_, to, label):
	'''
	Initiate an outbound call wrapped in a TwiML response. Park the inbound
	call in a conference while waiting for the outbound call to connect. 
	'''
	try:
		attempt_outbound_call(inbound_sid, from_, to)
		response.say("Connecting you to {0}.".format(label), voice=TWILIO_VOICE)
		with response.dial() as d:
			d.conference(inbound_sid, endConferenceOnExit=True, beep=True, waitUrl=url_for('wait_for_outbound'))
	except twilio.TwilioRestException as e:
		app.logger.error(e)
		response.say("Sorry, an error occurred while connecting your call. Please try again.", voice=TWILIO_VOICE)
		response.redirect(url_for('search_by_name'))

	CallState.set_data(inbound_sid, started_at=datetime.datetime.utcnow().isoformat())


def attempt_outbound_call(inbound_sid, from_, to):
	'''
	Create an outbound call via Twilio API. Capture outbound number with inbound SID.
	Link inbound SID to outbound SID.
	'''

	app.logger.info('from %s', from_)
	outbound_call = TRC.calls.create(
		url=url_for('connect_outbound', _external=True),
		#from_=app.config['TWILIO_DEFAULT_FROM'] if from_ == '' else from_,
		from_=app.config['TWILIO_DEFAULT_FROM'],
		to=to,
		timeout=600, # use Twilio's maximum timeout because some calls can ring for quite some time
		status_callback=url_for('ping_outbound', _external=True),
		status_callback_method='POST',
		status_events=['initiated', 'ringing', 'answered', 'completed']
	)
	CallState.log_new_attempt(inbound_sid, outbound_call)

def zip_pad(zip_code):
	return " ".join(list(zip_code))

@app.route("/", methods=['POST'])
def greet_caller():
	'''
	Answer an inbound call.
	'''
	call_data = {
		'from': request.form['From'],
		'received_at': datetime.datetime.utcnow().isoformat()
	}

	CallState.set_data(request.form['CallSid'], **call_data)
	response = twilio.twiml.Response()
	response.say("Hello fellow American!", voice=TWILIO_VOICE)

	caller_data = CallState.get_caller_data(request.form['From'])
	if caller_data and 'zip' in caller_data:
		with response.gather(numDigits=1, timeout=1, action=url_for('set_zip_code')) as g:
			g.say("I see you've called before from zip code {0}. Press star to enter a different zip code.".format(zip_pad(caller_data['zip'])), voice=TWILIO_VOICE)
		response.redirect(url_for('select_member'))
	else:
		response.redirect(url_for('set_zip_code'))

	return str(response)

@app.route("/set_zip_code", methods=['POST'])
def set_zip_code():
	'''
	Search for members of Congress by entering a ZIP code
	'''
	inbound_sid = request.form['CallSid']
	response = twilio.twiml.Response()
	gather_kwargs = {'numDigits': 5, 'timeout': 15, 'finishOnKey': '*', 'action': url_for('set_zip_code')}

	if 'Digits' not in request.form:
		# Start new search if no dialpad digits POSTed on this request
		with response.gather(**gather_kwargs) as g:
			g.say("Please enter your zip code. Press star to start over.", voice=TWILIO_VOICE)
	elif len(request.form['Digits']) < 5:
		# Start over
		response.redirect(url_for('set_zip_code'))
	else:
		zip_code = request.form['Digits']

		results = congress.search_by_zip(zip_code)

		if len(results) == 0:
			# start over
			response.say("I can't find any members of Congress for zip code {0}. Let's try again.".format(zip_pad(zip_code)), voice=TWILIO_VOICE)
			response.redirect(url_for('set_zip_code'))
		else:
			# set zip and redirect to listing of members
			CallState.set_caller_data(request.form['From'], zip=zip_code)
			response.redirect(url_for('select_member'))

	return str(response)

@app.route("/select_member", methods=['POST'])
def select_member():
	'''
	List members of Congress for the current zipcode
	'''
	inbound_sid = request.form['CallSid']
	caller_data = CallState.get_caller_data(request.form['From'])
	zip_code = caller_data['zip']
	results = congress.search_by_zip(zip_code)

	response = twilio.twiml.Response()

	if 'Digits' not in request.form:
		# Offer user menu of result options to select from.
		digits_to_gather = int(math.floor(math.log10(len(results)))+1)
		response.say("I've found {0} members of Congress for zip code {1}.".format(len(results), zip_pad(zip_code)), voice=TWILIO_VOICE)
		with response.gather(numDigits=digits_to_gather, timeout=20, action=url_for('select_member')) as g:
			for i, member in enumerate(results):
				g.say("Press {0} for {1}.".format(i + 1, member['label']), voice=TWILIO_VOICE)
			g.say("Or press star to enter a new zip code.", voice=TWILIO_VOICE)
	else:
		if request.form['Digits'] in '*#':
			response.redirect(url_for('set_zip_code'))	
			return str(response)

		try:
			selection_index = int(request.form['Digits']) - 1

			member = results[selection_index]
			start_outbound_call(
				response=response,
				inbound_sid=request.form['CallSid'],
				from_=request.form['To'],
				to=member['phone'],
				label=member['label']
			)
		except IndexError:
			response.say("Sorry, your entry doesn't match any of the available options. Let's try again.", voice=TWILIO_VOICE)
			response.redirect(url_for('select_member'))

	return str(response)

@app.route("/outbound/connect", methods=['POST'])
def connect_outbound():
	'''
	Bridge an outbound call to the inbound call by joining the inbound call's conference
	when the outbound call successfully connects.
	'''
	outbound_sid = request.form['CallSid']
	inbound_sid = CallState.get_origin(outbound_sid)
	CallState.set_data(inbound_sid, connected_at=datetime.datetime.utcnow().isoformat())
	response = twilio.twiml.Response()
	with response.dial() as d:
		d.conference(inbound_sid, endConferenceOnExit=True, beep=True, waitUrl='')
	return str(response)


@app.route("/outbound/ping", methods=['POST'])
def ping_outbound():
	'''
	Check status of outbound call from Twilio webhook.
	Retry outbound call if previous attempt failed,
	but only if originating call is still connected.
	'''
	app.logger.info('status %s', request.form['CallStatus'])

	outbound_sid = request.form['CallSid']
	inbound_sid = CallState.get_origin(outbound_sid)
	retry=False

	if request.form['CallStatus'] in ["canceled", "busy", "no-answer"]:
		inbound_call = TRC.calls.get(inbound_sid)
		retry = (inbound_call.status == 'in-progress')
	elif request.form['CallStatus'] in ['completed']:
		outbound_call = TRC.calls.get(outbound_sid)
		CallState.add_cost(inbound_sid, outbound_call.price)

	if retry:
		app.logger.info('retrying %s', request.form['To'])
		attempt_outbound_call(
			inbound_sid=inbound_sid,
			from_=request.form['From'],
			to=request.form['To']
		)

	return ('', 204)

@app.route("/inbound/ping", methods=['POST'])
def ping_inbound():
	'''
	Configured status endpoint for inbound calls.
	Log data at inbound call completion, and end
	any active outbound calls.
	'''
	if request.form['CallStatus'] in ['completed', 'canceled', 'failed']:

		inbound_call = TRC.calls.get(request.form['CallSid'])

		call_data = {
			'duration': request.form['Duration'],
			'ended_at': datetime.datetime.utcnow().isoformat(),
		}

		CallState.add_cost(inbound_call.sid, inbound_call.price)
		CallState.set_data(inbound_call.sid, **call_data)

		outbound_sid = CallState.get_last_attempt(inbound_call.sid)
		if outbound_sid:
			outbound_call = TRC.calls.get(outbound_sid)
			if outbound_call.status in ['queued', 'ringing', 'in-progress']:
				outbound_call.hangup()

	return ('', 204)

@app.route("/inbound/wait", methods=['POST'])
def wait_for_outbound():
	'''
	Announcement callback for inbound call
	when it is parked in the conference
	while waiting for the outbound call.
	'''
	response = twilio.twiml.Response()
	response.say("Please hold and I will keep trying if the line is busy.", voice=TWILIO_VOICE)
	return str(response)

if __name__ == "__main__":
	app.run()
