##
# TRACK 1
# One Train Two Tracks (datadrivendj.com/tracks/subway)
# Brian Foo (brianfoo.com)
# This file builds the sequence file for use with ChucK from the data supplied
##

# Library dependancies
import csv
import math
import os
import random
import re
import time

# Config
BPM = 90
METERS_PER_BEAT = 40
INSTRUMENTS_INPUT_FILE = 'data/instruments.csv'
STATIONS_INPUT_FILE = 'data/stations.csv'
SUMMARY_OUTPUT_FILE = 'data/ck_summary.csv'
INSTRUMENTS_OUTPUT_FILE = 'data/ck_instruments.csv'
SEQUENCE_OUTPUT_FILE = 'data/ck_sequence.csv'
INSTRUMENTS_DIR = 'instruments/'
WRITE_SEQUENCE = True
WRITE_SUMMARY = True

# Calculations
BEAT_MS = round(60.0 / BPM * 1000)

print('Building sequence at '+str(BPM)+' BPM ('+str(BEAT_MS)+'ms per beat)')

# Initialize Variables
instruments = []
stations = []
sequence = []

# Find index of first item that matches value
def findInList(list, key, value):
	found = -1
	for index, item in enumerate(list):
		if item[key] == value:
			found = index
			break
	return found

# Read instruments from file
with open(INSTRUMENTS_INPUT_FILE, 'rb') as f:
	r = csv.reader(f, delimiter='\t')
	next(r, None) # remove header
	for name,type,price,file,gain_min,gain_max,tempo,beats_per_phase,borough,active in r:
		if file and int(active):
			index = len(instruments)
			# build instrument object
			instrument = {
				'index': index,
				'name': name,
				'type': type.lower().replace(' ', '_'),
				'price': int(price),
				'file': INSTRUMENTS_DIR + file,
				'gain_min': round(float(gain_min), 1),
				'gain_max': round(float(gain_max), 1),
				'tempo': float(tempo),
				'borough': borough.lower(),
				'beats_per_phase': int(beats_per_phase),
				'beat_ms': int(round(BEAT_MS/float(tempo)))
			}
			# check gain bounds
			if instrument['gain_min'] > instrument['gain_max']:
				instrument['gain_min'],instrument['gain_max'] = instrument['gain_max'],instrument['gain_min']
			# add instrument to instruments
			instruments.append(instrument)

# Read stations from file
with open(STATIONS_INPUT_FILE, 'rb') as f:
	r = csv.reader(f, delimiter='\t')
	next(r, None) # remove header
	for name,income_annual,income,lat,lng,borough in r:
		stations.append({
			'name': name,
			'budget': float(re.sub(r'[\$|,]', '', income)),
			'lat': float(lat),
			'lng': float(lng),
			'beats': 0,
			'distance': 0,
			'duration': 0,
			'borough': borough.lower(),			
			'instruments': []
		})

# For calculating distance between two coords(lat, lng)
def distBetweenCoords(lat1, lng1, lat2, lng2):
	earthRadius = 6371000 # meters
	dLat = math.radians(lat2-lat1)
	dLng = math.radians(lng2-lng1)
	a = math.sin(dLat/2) * math.sin(dLat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLng/2) * math.sin(dLng/2)
	c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
	dist = float(earthRadius * c)
	return dist

# Buy instruments based on a specified budget
def buyInstruments(instruments_shelf, budget):
	instruments_cart = []
	for i in instruments_shelf:
		if i['price'] < budget:
			budget -= i['price']		
			instruments_cart.append(i)
		else:
			break
	return instruments_cart

# Pre-process stations
min_distance = 0
max_distance = 0
total_distance = 0
total_beats = 0
total_ms = 0
for index, station in enumerate(stations):
	# determine the station's budget
	stations[index]['instruments'] = buyInstruments(instruments, station['budget'])
	if index > 0:
		# determine distance between last station
		distance = distBetweenCoords(station['lat'], station['lng'], stations[index-1]['lat'], stations[index-1]['lng'])
		beats = int(round(distance / METERS_PER_BEAT))
		duration = beats * BEAT_MS
		stations[index-1]['distance'] = distance
		stations[index-1]['beats'] = beats
		stations[index-1]['duration'] = duration
		total_distance += distance
		total_beats += beats
		total_ms += duration
		if distance > max_distance:
			max_distance = distance
		if distance < min_distance or min_distance == 0:
			min_distance = distance

# Calculate how many beats
station_count = len(stations)-1
total_seconds = int(1.0*total_ms/1000)
seconds_per_station = int(1.0*total_seconds/station_count)

print('Total distance in meters: '+str(round(total_distance)))
print('Distance range in meters: ['+str(min_distance)+','+str(max_distance)+']')
print('Total beats: '+str(total_beats))
print('Average beats per station: '+str(1.0*total_beats/station_count))
print('Total time: '+time.strftime('%M:%S', time.gmtime(total_seconds)) + '(' + str(total_seconds) + 's)')
print('Average time per station: '+time.strftime('%M:%S', time.gmtime(seconds_per_station)))

# Multiplier based on sine curve
def getMultiplier(percent_complete):
	radians = percent_complete * math.pi
	multiplier = math.sin(radians)
	if multiplier < 0:
		multiplier = 0.0
	elif multiplier > 1:
		multplier = 1.0
	return multiplier

# Retrieve gain based on current beat
def getGain(instrument, beat):
	percent_complete = float(beat % instrument['beats_per_phase']) / instrument['beats_per_phase']
	multiplier = getMultiplier(percent_complete)
	min = instrument['gain_min']
	max = instrument['gain_max']
	gain = multiplier * (max - min) + min
	return gain

def getBeatMs(elapsed_duration, total_duration, beat_ms, base_beat_ms):
	percent_complete = 1.0 * elapsed_duration / total_duration
	multiplier = getMultiplier(percent_complete)
	min = base_beat_ms if base_beat_ms < beat_ms else beat_ms
	max = beat_ms if base_beat_ms < beat_ms else base_beat_ms
	ms = multiplier * (max - min) + min
	return ms

# Add beats to sequence
def addBeatsToSequence(instrument, duration, ms, beat_ms, base_beat_ms):
	global sequence
	min_ms = base_beat_ms if base_beat_ms < beat_ms else beat_ms
	remaining_duration = int(duration)
	elapsed_duration = 0
	while remaining_duration >= min_ms:
		this_beat_ms = getBeatMs(elapsed_duration, duration, beat_ms, base_beat_ms)
		elapsed_ms = int(ms + this_beat_ms)
		elapsed_beat = int(elapsed_ms / beat_ms)
		sequence.append({
			'instrument_index': instrument['index'],
			'position': 0,
			'gain': getGain(instrument, elapsed_beat),
			'rate': 1,
			'elapsed_ms': elapsed_ms
		})
		remaining_duration -= this_beat_ms
		elapsed_duration += this_beat_ms
		ms += this_beat_ms

# Build sequence
for instrument in instruments:
	ms = 0
	beat_ms = instrument['beat_ms']
	station_queue_duration = 0
	# Each station in stations
	for station in stations:
		# Check if instrument is in this station
		instrument_index = findInList(station['instruments'], 'index', instrument['index'])
		# Instrument not here, just add the station duration and continue
		if instrument_index < 0 and station_queue_duration > 0:
			addBeatsToSequence(instrument, station_queue_duration, ms, beat_ms, BEAT_MS)
			ms += station_queue_duration
			station_queue_duration = 0
		elif instrument_index < 0:
			ms += station['duration']
		else:
			station_queue_duration += station['duration']
	if station_queue_duration > 0:
		addBeatsToSequence(instrument, station_queue_duration, ms, beat_ms, BEAT_MS)
		
# Sort sequence
sequence = sorted(sequence, key=lambda k: k['elapsed_ms'])

# Add milliseconds to sequence
elapsed = 0
for index, step in enumerate(sequence):
	sequence[index]['milliseconds'] = step['elapsed_ms'] - elapsed
	elapsed = step['elapsed_ms']

# Write instruments to file
if WRITE_SEQUENCE:
	with open(INSTRUMENTS_OUTPUT_FILE, 'wb') as f:
		w = csv.writer(f)	
		for index, instrument in enumerate(instruments):
			w.writerow([index])
			w.writerow([instrument['file']])
		f.seek(-2, os.SEEK_END) # remove newline
		f.truncate()
		print('Successfully wrote instruments to file.')

# Write sequence to file
if WRITE_SEQUENCE:
	with open(SEQUENCE_OUTPUT_FILE, 'wb') as f:
		w = csv.writer(f)	
		for step in sequence:
			w.writerow([step['instrument_index']])
			w.writerow([step['position']])
			w.writerow([step['gain']])
			w.writerow([step['rate']])
			w.writerow([step['milliseconds']])
		f.seek(-2, os.SEEK_END) # remove newline
		f.truncate()
		print('Successfully wrote sequence to file.')

# Write summary file
if WRITE_SUMMARY:
	with open(SUMMARY_OUTPUT_FILE, 'wb') as f:
		w = csv.writer(f)
		w.writerow(['Time', 'Name', 'Distance', 'Duration', 'Beats', 'Instruments'])
		elapsed = 0
		for station in stations:
			duration = int(station['duration']/1000)
			duration_f = time.strftime('%M:%S', time.gmtime(duration))
			elapsed_f = time.strftime('%M:%S', time.gmtime(elapsed))
			elapsed += duration
			w.writerow([elapsed_f, station['name'], station['distance'], duration_f, station['beats'], ' '.join([i['name'] for i in station['instruments']])])
		print('Successfully wrote summary file.')
