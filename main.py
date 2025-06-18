import requests
import os
from dotenv import load_dotenv

import time
import datetime

import json

load_dotenv()

authHeaders = {
	"X-Riot-Token": os.getenv("RIOT_API_KEY")
}

# Settings
riotAccountRegion = "europe"
#leagueAccountRegion = "euw1"

CACHE_FILE="cache.json"
PUUID_BY_SUMMONER="puuidBySummoner"
MATCHES_BY_PUUID="matchesByPuuid"
MATCH_INFOS="matchInfos"

def loadCache():
	try:
		with open(CACHE_FILE, "r") as f:
			return json.load(f)
	except FileNotFoundError:
		data = { PUUID_BY_SUMMONER: {}, MATCHES_BY_PUUID: {}, MATCH_INFOS: {} }
		#writeMatchMap(data)
		return data

def writeCache(cache):
	with open(CACHE_FILE, "w") as f:
		json.dump(cache, f, indent=4)

def fetchPuuid(gameName, tagLine):
	data = loadCache()

	summonerName = f"{gameName}#{tagLine}"

	if summonerName in data[PUUID_BY_SUMMONER]:
		return data[PUUID_BY_SUMMONER][summonerName]

	r = requests.get(f"https://{riotAccountRegion}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}", headers=authHeaders)
	json = r.json()
	puuid = json["puuid"]

	data[PUUID_BY_SUMMONER][summonerName] = puuid
	writeCache(data)

	return puuid

def fetchMatchIds(puuid):
	#startTimestamp = int(time.mktime(datetime.date.today().timetuple()))
	matchType = "ranked"

	#print(startTimestamp)

	# startTime={startTimestamp}&
	r = requests.get(f"https://{riotAccountRegion}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?type={matchType}&start=0&count=10", headers=authHeaders)
	json = r.json()

	#print(json)

	return json

def getLatestMatchIds(puuid, matchIds):
	data = loadCache()

	if puuid in data[MATCHES_BY_PUUID]:
		cachedMatches = data[MATCHES_BY_PUUID][puuid]
		latestMatchIds = [m for m in matchIds if m not in cachedMatches]
	else:
		latestMatchIds = matchIds

	data[MATCHES_BY_PUUID][puuid] = matchIds
	writeCache(data)

	return latestMatchIds

def fetchMatch(matchId):
	data = loadCache()

	if matchId in data[MATCH_INFOS]:
		return data[MATCH_INFOS][matchId]

	r = requests.get(f"https://{riotAccountRegion}.api.riotgames.com/lol/match/v5/matches/{matchId}", headers=authHeaders)
	json = r.json()

	data[MATCH_INFOS][matchId] = json
	writeCache(data)

	return json

def getMatchParticipant(matchInfo, puuid):
	return next(
		(participant for participant in matchInfo["info"]["participants"] if participant["puuid"] == puuid),
		None
	)

def getMatchTeam(matchInfo, teamId):
	return next(
		(team for team in matchInfo["info"]["teams"] if team["teamId"] == teamId),
		None
	)

def isMatchWinForPlayer(matchInfo, puuid):
	part = getMatchParticipant(matchInfo, puuid)
	team = getMatchTeam(matchInfo, part["teamId"])

	return team["win"]

def getStreak(matchIds, puuid, shouldWin, idx=0):
	streak = 0

	for matchId in matchIds[idx:]:
		matchInfo = fetchMatch(matchId)
		isWin = isMatchWinForPlayer(matchInfo, puuid)

		if isWin != shouldWin:
			break

		streak += 1
	
	return streak

def sendMessage(message):
	r = requests.post(
		os.getenv("WEBHOOK_URL"),
		headers={ "Content-Type": "application/json" },
		data=json.dumps({ "content": message })
	)

	#print(r.json())
	#print(r.request.body)

def main():
	for [gameName, tagLine] in map(lambda s: s.split("-"), os.getenv("WATCHED_USERS").split(",")):
		print(f"Processing {gameName}#{tagLine}")

		puuid = fetchPuuid(gameName, tagLine)
		print(f"  puuid={puuid}")


		matchIds = fetchMatchIds(puuid)
		latestMatchIds = getLatestMatchIds(puuid, matchIds)

		print(f"  latestMatchIds={latestMatchIds}")

		if len(latestMatchIds) == 0:
			continue

		if (streak := getStreak(matchIds, puuid, True, 1)) > getStreak(matchIds, puuid, True) and streak > 2:
			sendMessage(f"{gameName}#{tagLine} just ended a {streak}x win streak by losing")
		elif (streak := getStreak(matchIds, puuid, True)) > 0:
			print("xd")
			sendMessage(f"{gameName}#{tagLine} has a {streak}x win streak")
		elif (streak := getStreak(matchIds, puuid, False)) > 0:
			print("xde2")
			sendMessage(f"{gameName}#{tagLine} has a {streak}x losing streak")

		#for matchId in matchIds:
		#	matchInfo = fetchMatch(matchId)
		#	isWin = isMatchWinForPlayer(matchInfo, puuid)
		#	print(f"Match '{matchId}': isWin={isWin}")

main()
