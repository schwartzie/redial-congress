import json
import re
import utils

# A convenient list of members of Congress in CSV form
DATA_CSV = 'http://unitedstates.sunlightfoundation.com/legislators/legislators.csv'

# Map of state codes to full names for spoken prompts
state_map = {'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
             'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'DC': 'District of Columbia',
             'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois',
             'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
             'ME': 'Maine', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire',
             'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina',
             'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'MD': 'Maryland',
             'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
             'MO': 'Missouri', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
             'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
             'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin',
             'WY': 'Wyoming', 'AS': 'American Samoa', 'FM': 'Federated States of Micronesia',
             'GU': 'Guam', 'MH': 'Marshall Islands', 'MP': 'Northern Mariana Islands',
             'PW': 'Palau', 'PR': 'Puerto Rico', 'VI': 'Virgin Islands'}

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

	if current_members != None:
		return current_members

	members = []

	for member in utils.csv_url_to_dicts(DATA_CSV):
		if member['in_office'] == '1' and member['phone'] != '':
			# only include members currently in office
			firstname = get_first_name(member['firstname'], member['middlename'], member['nickname'])
			members.append({
				'label': "{0} {1} {2} of {3}".format(
					title_map[member['title']],
					utils.remove_diacritics(firstname),
					utils.remove_diacritics(member['lastname']),
					state_map[member['state']]
				),
				'state': member['state'],
				'state_label': state_map[member['state']],
				'search_term': member['lastname'],
				'search_dial': utils.str_to_dialpad(member['lastname']),
				'phone': "+1{0}".format(re.sub(r'[^0-9]', '', member['phone'])),
				'sort': "{0}|{1}|{2}".format(title_rank_map[member['title']], member['lastname'], firstname)
			})
	current_members = members
	return members

def search_by_dialpad(digits):
	'''
	Search for members by telephone dialpad entry. Rely on precomputed dialpad equivalents for speed/simplicity.
	'''
	subset = [member for member in get_current_members() if member['search_dial'].startswith(re.sub(r'[^2-9]', '', digits))]
	return sorted(subset, cmp=lambda a, b: cmp(a['sort'], b['sort']))

if __name__ == "__main__":
	print(json.dumps(get_current_members(), indent=2))


