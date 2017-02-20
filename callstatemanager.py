import redis

class CallStateManager(object):
	
	KEY_DATA = 'call:{0}:data'
	KEY_ATTEMPTS = 'call:{0}:attempts'
	KEY_ORIGIN = 'call:{0}:origin'
	KEY_QUERY = 'call:{0}:query'

	def __init__(self, conn_args={}, ttl=3600):
		self.conn_args = conn_args
		self.ttl = ttl

		self.cache = redis.StrictRedis(**self.conn_args)

	def get_data_key(self, inbound_sid):
		'''
		Return the key for the data cache entry
		'''
		return self.__class__.KEY_DATA.format(inbound_sid)

	def get_attempts_key(self, inbound_sid):
		'''
		Return the key for the attempts cache entry
		'''
		return self.__class__.KEY_ATTEMPTS.format(inbound_sid)

	def set_data(self, inbound_sid, **fields):
		'''
		Store the outbound destination number for an inbound SID
		'''
		key = self.get_data_key(inbound_sid)
		self.cache.hmset(key, fields)

	def get_origin_key(self, outbound_sid):
		'''
		Return the key for the origin cache entry
		'''
		return self.__class__.KEY_ORIGIN.format(outbound_sid)

	def get_origin(self, outbound_sid):
		'''
		Get the inbound SID for an outbound SID
		'''
		key = self.get_origin_key(outbound_sid)
		return self.cache.get(key)

	def set_origin(self, outbound_sid, inbound_sid):
		'''
		Store the inbound origin call SID of an outbound call SID.
		'''
		key = self.get_origin_key(outbound_sid)
		self.cache.set(key, inbound_sid, ex=self.ttl)


	def get_query_key(self, inbound_sid):
		'''
		Return the key for the inbound SID search query
		'''
		return self.__class__.KEY_QUERY.format(inbound_sid)

	def get_query(self, inbound_sid):
		'''
		Get the the inbound SID search query
		'''
		key = self.get_query_key(inbound_sid)
		return self.cache.get(key)

	def set_query(self, inbound_sid, query=None):
		'''
		Set current search query for the inbound SID
		'''
		key = self.get_query_key(inbound_sid)
		if query == None: query = ''
		self.cache.set(key, query, ex=self.ttl)

	def clear_query(self, inbound_sid):
		'''
		Clear any current search query for the inbound SID
		'''
		self.set_query(inbound_sid, None)

	def append_to_query(self, inbound_sid, to_append):
		'''
		Refine current query by appending additional digits to it
		'''
		key = self.get_query_key(inbound_sid)
		return self.cache.append(key, to_append)

	def log_new_attempt(self, inbound_sid, outbound_call):
		'''
		Log a new outbound call attempt.
		'''
		data_key = self.get_data_key(inbound_sid)
		attempts_key = self.get_attempts_key(inbound_sid)
		self.cache.hmset(data_key, {'to': outbound_call.to, 'last_attempt': outbound_call.sid})
		self.cache.hincrby(data_key, 'attempts', 1)
		self.cache.lpush(attempts_key, outbound_call.sid)
		self.set_origin(outbound_call.sid, inbound_sid)

	def add_cost(self, inbound_sid, cost_usd):
		'''
		Capture cost data
		'''
		if cost_usd is None:
			return
		try:
			cost_cents = int(100 * float(cost_usd))
			key = self.get_data_key(inbound_sid)
			self.cache.hincrby(key, 'cost', cost_cents)
		except ValueError as e:
			pass

	def get_last_attempt(self, inbound_sid):
		'''
		Get most recent outbound call attempt
		'''
		attempts_key = self.get_attempts_key(inbound_sid)
		return self.cache.lindex(attempts_key, 0)