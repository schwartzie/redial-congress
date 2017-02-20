from unidecode import unidecode
import re
import csv
import urllib2

def csv_url_to_dicts(url):
	'''
	Retrieve CSV from URL. Parse into an array of dicts,
	assuming headers are on first line.
	'''
	lines = urllib2.urlopen(url).read().rstrip().split("\n")

	line_iter = csv.reader(lines)

	headers = None

	rows = []

	for line in line_iter:
		if headers == None:
			headers = line
		else:
			rows.append(dict(zip(headers, line)))

	return rows

def remove_diacritics(value):
	'''
	Strip accents and other diacritical marks from a multibyte string
	'''
	return unidecode(value.decode('utf-8'))

def sanitize_for_dialpad(value):
	'''
	Sanitize a string for entry via telephone dialpad.
	'''
	return re.sub(r'[^A-Z]', '', remove_diacritics(value).upper())

def str_to_dialpad(value):
	'''
	Convert a string to its telephone dialpad equivalent
	'''
	dial_map = dict(zip(list('ABCDEFGHIJKLMNOPQRSTUVWXYZ'), list('22233344455566677778889999')))
	return "".join([dial_map[c] for c in sanitize_for_dialpad(value)])