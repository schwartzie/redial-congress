import json
import re
import utils
import geo_data

# A convenient list of members of Congress in CSV form
DATA_CSV = 'http://unitedstates.sunlightfoundation.com/legislators/legislators.csv'

# Map of title abbreviations to full names for spoken prompts
title_map = {'Rep': 'Representative', 'Sen': 'Senator', 'Del': 'Delegate', 'Com': 'Commissioner'}

# Map of title abbreviations and their relative rank/order of priority in sorted lists
title_rank_map = {'Sen': 'A', 'Rep': 'B', 'Com': 'C', 'Del': 'D'}

# capture output in a global var
current_members = None

def get_first_name(firstname, middlename, nickname):
	'''
	Choose the most sensible first name for a member
	'''
	if nickname != '':
		# If a nickname is specified, just use that
		return nickname
	elif middlename != '' and firstname.rstrip().endswith('.'):
		# For "F. James Sensenbrenner", use "James"
		return middlename
	else:
		return firstname

def get_current_members():
	'''
	Get current members of Congress as a list of standardized dicts.
	'''
	global current_members

	state_map = geo_data.get_state_name_map()

	if current_members != None:
		return current_members

	members = []

	for member in utils.csv_url_to_dicts(DATA_CSV):
		if member['in_office'] == '1' and member['phone'] != '':
			# only include members currently in office
			firstname = get_first_name(member['firstname'], member['middlename'], member['nickname'])
			members.append({
				'label': " ".join([
					title_map[member['title']],
					utils.remove_diacritics(firstname),
					utils.remove_diacritics(member['lastname'])
				]),
				'state': member['state'],
				'search_district': "{0}{1}".format(member['state'], member['district'].zfill(2) if 'Seat' not in member['district'] else ''),
				'search_dial': utils.str_to_dialpad(member['lastname']),
				'phone': "+1{0}".format(re.sub(r'[^0-9]', '', member['phone'])),
				'sort': utils.remove_diacritics("{0}|{1}|{2}".format(title_rank_map[member['title']], member['lastname'], firstname))
			})
	current_members = members
	return members

def search_by_dialpad(digits):
	'''
	Search for members by telephone dialpad entry. Rely on precomputed dialpad equivalents for speed/simplicity.
	'''
	subset = [member for member in get_current_members() if member['search_dial'].startswith(re.sub(r'[^2-9]', '', digits))]
	return sorted(subset, cmp=lambda a, b: cmp(a['sort'], b['sort']))

def search_by_zip(query):
	normalized_query = re.sub(r'[^0-9]', '', str(query))
	zip_tuples = [z for z in geo_data.get_zip_state_cd_tuples() if z['zip'].startswith(normalized_query)]
	districts = list(set(
		[z['state'] for z in zip_tuples]
		+ ["{0}{1}".format(z['state'], z['cd']) for z in zip_tuples]
	))
	subset = [member for member in get_current_members() if member['search_district'] in districts]
	return sorted(subset, cmp=lambda a, b: cmp(a['sort'], b['sort']))

if __name__ == "__main__":
	print(json.dumps(get_current_members(), indent=2))


