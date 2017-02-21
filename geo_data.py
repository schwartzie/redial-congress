import utils
import json
import os.path

# US Census data often uses FIPS codes to identify states instead of the usual
# abbreviations. Need to map from the codes to the abbreviations
# https://en.wikipedia.org/wiki/Federal_Information_Processing_Standard_state_code
# From https://www.census.gov/geo/reference/ansi_statetables.html
STATE_FIPS_CODE_FILE = 'http://www2.census.gov/geo/docs/reference/state.txt'

# Zip code data is always a hassle. The US Census has a data set with all ZCTAs and their 
# equivalent CDs, but it's the data from before the reapportionment following the 2010
# Census! There's a newer file, but it doesn't contain ZCTAs for states with only a single
# CD. We need to combine these files to get all the data needed.

# From https://www.census.gov/geo/maps-data/data/zcta_rel_download.html
ZCTA_TO_CD_FILE_ALL = 'http://www2.census.gov/geo/docs/maps-data/data/rel/zcta_cd111_rel_10.txt'

# https://www.census.gov/geo/maps-data/data/cd_national.html
ZCTA_TO_CD_FILE_CURRENT = 'http://www2.census.gov/geo/relfiles/cdsld13/natl/natl_zccd_delim.txt'

# Path to local cache of ZIP data so we don't always have to regenerate this
LOCAL_ZIPS_FILE = 'zip_codes.json'

state_fips_codes = None
zips = None

def get_state_fips_codes():
  '''
  Get listing of state FIPS codes
  '''
  global state_fips_codes

  if not state_fips_codes:
    state_fips_codes = utils.csv_url_to_dicts(STATE_FIPS_CODE_FILE, delimiter='|')

  return state_fips_codes

def get_fips_to_state_map():
  '''
  Get a hash of FIPS codes to standard state abbreviations.
  '''
  state_fips_codes = get_state_fips_codes()
  return {code['STATE']: code['STUSAB'] for code in state_fips_codes}

def get_state_name_map():
  '''
  Get a hash of state abbreviation to name maps
  '''
  state_fips_codes = get_state_fips_codes()
  return {code['STUSAB']: code['STATE_NAME'] for code in state_fips_codes}


def get_zip_state_cd_tuples():
  '''
  Get a list of Zip/State/Congressional District objects
  '''
  global zips

  # use the data in the global var if it's set
  if zips:
    return zips

  # use the local cache if it's present
  if os.path.isfile(LOCAL_ZIPS_FILE):
    zips_file = open(LOCAL_ZIPS_FILE, 'r') 
    zips = json.loads(zips_file.read())
    return zips

  # load the data from the US Census if all else fails
  state_fips_map = get_fips_to_state_map()
  current_zctas = utils.csv_url_to_dicts(ZCTA_TO_CD_FILE_CURRENT, ignore_first=1)
  current_zcta_zips = [z['ZCTA'] for z in current_zctas]

  # first portion of the list are the tuples from the current ZCTA file
  # second portion are the tuples from states with only a single CD from the old ZCTA file
  zips = [{
    'zip': zcta['ZCTA'],
    'state': state_fips_map[zcta['State']],
    'cd': zcta['Congressional District'].zfill(2)
  } for zcta in current_zctas] + [{
    'zip': zcta['ZCTA5'],
    'state': state_fips_map[zcta['STATE']],
    'cd': '00'
  } for zcta in utils.csv_url_to_dicts(ZCTA_TO_CD_FILE_ALL)
  if zcta['ZCTA5'] not in current_zcta_zips]

  return zips

if __name__ == "__main__":
  print(json.dumps(get_zip_state_cd_tuples(), indent=2))
