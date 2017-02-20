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
	response.redirect(url_for('search_by_name'))
	return str(response)


@app.route("/search_by_name", methods=['POST'])
def search_by_name():
	'''
	Search for members of Congress by entering a name on a telephone dialpad.
	'''
	inbound_sid = request.form['CallSid']
	response = twilio.twiml.Response()
	gather_kwargs = {'numDigits': 1, 'timeout': 30, 'action': url_for('search_by_name')}

	if 'Digits' not in request.form:
		# Start new search if no dialpad digits POSTed on this request
		CallState.clear_query(inbound_sid)
		with response.gather(**gather_kwargs) as g:
			g.say("Please enter the last name of the member of Congress you want to call. Press star to start over.", voice=TWILIO_VOICE)
	else:
		# Continue existing search if there are dialpad digits attached to this request.
		# Append current digits to existing query, and search for results.
		CallState.append_to_query(inbound_sid, request.form['Digits'])
		query = CallState.get_query(inbound_sid)

		results = congress.search_by_dialpad(query)

		if request.form['Digits'] in '*#':
			# Start over
			response.redirect(url_for('search_by_name'))
		elif len(results) == 0:
			# start over
			response.say("I can't find anyone whose last name matches your entry. Let's try again.", voice=TWILIO_VOICE)
			response.redirect(url_for('search_by_name'))
		elif len(results) == 1:
			# Dial single remaining result
			start_outbound_call(
				response=response,
				inbound_sid=request.form['CallSid'],
				from_=request.form['To'],
				to=results[0]['phone'],
				label=results[0]['label']
			)
		elif len(results) < 10 and len(results) > len(set([m['search_dial'] for m in results])):
			# Short list of remaining results with some duplication of dialpad mapping
			# Offer user menu of result options to select from.
			digits_to_gather = int(math.floor(math.log10(len(results)))+1)
			response.say("I've found {0} options for you.".format(len(results)), voice=TWILIO_VOICE)
			with response.gather(numDigits=digits_to_gather, timeout=20, action=url_for('pick_search_result')) as g:
				for i, member in enumerate(results):
					g.say("Dial {0} for {1}.".format(i + 1, member['label']), voice=TWILIO_VOICE)
				g.say("Or press star to start over", voice=TWILIO_VOICE)
		else:
			# Continue refining the query
			response.gather(**gather_kwargs)

	return str(response)

@app.route("/pick_search_result", methods=['POST'])
def pick_search_result():
	'''
	Connect an outbound call based on the user-selected search result choice.
	'''
	inbound_sid = request.form['CallSid']
	query = CallState.get_query(inbound_sid)
	results = congress.search_by_dialpad(query)

	response = twilio.twiml.Response()

	if request.form['Digits'] in '*#':
		response.redirect(url_for('search_by_name'))	
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
		response.redirect(url_for('search_by_name'))

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
