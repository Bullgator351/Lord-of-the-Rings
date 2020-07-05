# -*- coding: utf-8 -*-
import time
import re
from collections import namedtuple

# for XML parsing in loadDeckFromRingsDB
import clr
clr.AddReference("System.Xml")
from System.Xml import XmlDocument

Resource = ("Resource", "62a2ba76-9872-481b-b8fc-ec35447ca640")
Damage = ("Damage", "38d55f36-04d7-4cf9-a496-06cb84de567d")
Progress = ("Progress", "e9a419ff-5154-41cf-b84f-95149cc19a2a")
WillpowerToken = ("WillpowerToken", "f24eb0c4-8405-4599-ba80-95bc009ae9fb")
AttackToken = ("AttackToken", "53f20b83-6292-4017-abd0-511efdaf710d")
DefenseToken = ("DefenseToken", "6987d1a6-55ab-4ced-bbec-4e5b3490a40e")
ThreatToken = ("ThreatToken", "39df75f2-141d-425f-b651-d572b4885004")
TimeToken = ("TimeToken", "31627422-f546-4a69-86df-ca0a028f3138")
Lock = ("Lock", "04d7b7bb-13ee-499c-97c0-c1b96a897560")
Turn = ("Turn", "e0a54bea-6e30-409d-82cd-44a944e591dc")
phases = [  "5b015ce5-9282-402f-8fae-2ee819bd1545",
			"947e9e24-08bb-4193-98dc-88eb72107b7c",
			"656f896c-f45f-4ee4-bc44-aa8fd1eada55",
			"40046ed1-70c5-4a0e-914a-0a897f6cd644",
			"04fbf669-68c4-40c5-ae4d-0e06539497f1",
			"95fd357a-c0f1-4046-8b7a-4baf9abf36fc",
			"fbc17c02-086a-45d5-897b-d3732818b42f",
			"9c0f0325-4262-4a1d-8b1d-f415a6910f03",
			"b3ecfc10-176d-4971-820d-6d1227697d23",
			"aa8cd34c-cf6a-440e-a05f-c05f84446a72",
			"700e2c2e-bb49-40a9-a9ea-f51be3ffe5b4" ]
BoardWidth = 1100
Spacing = 92
HeroY = 70
StagingStart = -530
StagingWidth = 750
StagingY = -224
StagingSpace = 82
QuestStartX = 331
QuestStartY = -246
DoneColour = "#D8D8D8" # Grey
WaitingColour = "#FACC2E" # Orange
ActiveColour = "#82FA58" # Green
EliminatedColour = "#FF0000" # Red
showDebug = False #Can be changed to turn on debug - we don't care about the value on game reconnect so it is safe to use a python global

def debug(str):
	if showDebug:
		whisper(str)

def toggleDebug(group, x=0, y=0):
	global showDebug
	showDebug = not showDebug
	if showDebug:
		notify("{} turns on debug".format(me))
	else:
		notify("{} turns off debug".format(me))

#Return the default x coordinate of the players hero
def heroX(player, hero=0):
	return hero*Spacing + (BoardWidth * player / len(getPlayers())) - BoardWidth / 2

def num(s):
   if not s: return 0
   try:
      return int(s)
   except ValueError:
      return 0

def moveCard(model, x, y):
	for c in table:
		if c.model == model:
			c.moveToTable(x, y)
			return c
	return table.create(model, x, y)

def moveFirstPlayerToken(x=0, y=0):
	return moveCard("15e40d4f-b763-4dcc-aa52-e32b64a992dd", x, y)

def getFirstPlayerToken():
	for c in table:
		if c.model == "15e40d4f-b763-4dcc-aa52-e32b64a992dd":
			return c
	return None

def automationCard(x=0, y=0):
	return moveCard("72e54fdf-17b1-4358-b696-6c195e9696d1", x, y)

def isSpecialCard(card):
	return card.Sphere == 'Special'

#Find and return this players left most hero card
def firstHero(player):
	first = None
	for h in table:
		if h.controller == player and h.Type == "Hero" and h.isFaceUp:
			if first is None:
				first = h
			else:
				x,y = h.position
				minx, miny = first.position
				if x < minx:
					first = h
	return first

def getPlayer(id):
	for p in getPlayers():
		if playerID(p) == id:
			return p
	return None

def countHeroes(p):
	heroes = 0
	for card in table:
		if card.controller == p and card.Type == "Hero":
			heroes += 1
	return heroes

#Work out if the player is still in the game (threat < 50 and has heroes on the table)
def eliminated(p):
	if not p:
		return False

	if p.counters['Threat_Level'].value >= 50:
		debug("eliminated({}) = True (Threat)".format(p))
		return True

	heroes = countHeroes(p)
	if heroes == 0:
		debug("eliminated({}) = True (No Heroes)".format(p))
		return True

	return False

def activePlayers():
	count=0
	for p in getPlayers():
		if not eliminated(p):
			count+=1
	return count

def nextPlayer(current):
	if not eliminated(me):
		fp = getFirstPlayerToken()
		if fp is not None and isLocked(fp):
			return me

	np = me
	tries = 0
	while tries < len(getPlayers()):
		current = (current + 1) % len(getPlayers())
		p = getPlayer(current)
		if not eliminated(p):
			np = p
			break
		tries += 1
	return np

def questCount(group):
	count = 0
	nightmare = 0
	for c in group:
		if c.Type == "Quest":
			count += 1
		if c.Type == "Nightmare" or c.Type == "Campaign":
			nightmare += 1
	return (nightmare, count)

#Check see if a card at x1,y1 overlaps a card at x2,y2
#Both have size w, h
def overlaps(x1, y1, x2, y2, w, h):
	#Four checks, one for each corner
	if x1 >= x2 and x1 <= x2 + w and y1 >= y2 and y1 <= y2 + h: return True
	if x1 + w >= x2 and x1 <= x2 and y1 >= y2 and y1 <= y2 + h: return True
	if x1 >= x2 and x1 <= x2 + w and y1 + h >= y2 and y1 <= y2: return True
	if x1 + w >= x2 and x1 <= x2 and y1 + h >= y2 and y1 <= y2: return True
	return False

def cardHere(x, y, checkOverlap=True):
	cw = 0
	ch = 0
	for c in table:
		cx, cy = c.position
		if checkOverlap:
			cw = c.width()
			ch = c.height()
		if overlaps(x, y, cx, cy, cw, ch):
			return c
	return None

def cardX(card):
	x, y = card.position
	return x

def cardY(card):
	x, y = card.position
	return y

#Move the given card in the staging area to the first available space on the left of the Staging Area
#If there is no room then we compress all the cards in the staging area to make room
def layoutStage(card=None):
	x = StagingStart
	y = StagingY
	s = StagingSpace
	while x < StagingStart + StagingWidth - s:
		if cardHere(x, y) is None:
			card.moveToTable(x, y)
			return
		x += s
	card.moveToTable(x - s, y)
	#There was no room - we neeed to move all the cards to make space
	staged = []
	for c in table:
		if overlaps(cardX(c), cardY(c), StagingStart, StagingY, StagingWidth, 100):
			staged.append(c)

	for c in staged:
		cx, cy = c.position
		shift = (cx - StagingStart) // len(staged)
		c.moveToTable(cx - shift, cy)

def clearTargets(group=table, x=0, y=0):
	for c in group:
		if c.controller == me or (c.targetedBy is not None and c.targetedBy == me):
			c.target(False)

def clearHighlights(group=table, x=0, y=0):
	for c in group: # Safe to do on all cards, not just ones we control
		c.highlight = None

def findCard(group, model):
	for c in group:
		if c.model == model:
			return c
	return None

def encounterDeck():
	return shared.piles['Encounter']

def encounterDiscard():
	return shared.piles['Encounter Discard Pile']

def specialDeck():
	return shared.piles['Special']

def specialDiscard():
	return shared.piles['Special Discard Pile']

def questDeck():
	return shared.piles['Quest']

def questDiscard():
	return shared.piles['Quest Discard Pile']

def setupDeck():
	return shared.piles['Setup']

def stagingSetupDeck():
	return shared.piles['Staging Setup']

def activeSetupDeck():
	return shared.piles['Active Setup']

def isPlayerCard(card):
	return card.owner in getPlayers()

def isEncounterCard(card):
	return card.type in ['Enemy','Treachery','Location','Objective','Objective Ally'] or 'Encounter' in card.Keywords

def isSetupCard(card):
	return card.Name in ['Mirlonde','Folco Boffin','Thurindir'] or (card.Name == 'Éowyn' and card.Sphere == 'Tactics') or (card.Name == 'Denethor' and card.Sphere == 'Leadership')
#------------------------------------------------------------
# Global variable manipulations function
#------------------------------------------------------------

def getLock():
	lock = getGlobalVariable("lock")
	if lock == str(me._id):
		return True

	if len(lock) > 0: #Someone else has the lock
		return False

	setGlobalVariable("lock", str(me._id))
	if len(getPlayers()) > 1:
		update()
	return getGlobalVariable("lock") == str(me._id)

def clearLock():
	lock = getGlobalVariable("lock")
	if lock == str(me._id):
		setGlobalVariable("lock", "")
		update()
		return True
	debug("{} id {} failed to clear lock id {}".format(me, me._id, lock))
	return False


#Store this player's starting position (his ID for this game)
#The first player is 0, the second 1 ....
#These routines set global variables so should be called within getLock() and clearLock()
#After a reset, the game count will be updated by the first player to setup again which invalidates all current IDs
def myID():
	if me.getGlobalVariable("game") == getGlobalVariable("game") and len(me.getGlobalVariable("playerID")) > 0:
		return playerID(me) # We already have a valid ID for this game

	g = getGlobalVariable("playersSetup")
	if len(g) == 0:
		id = 0
	else:
		id = num(g)
	me.setGlobalVariable("playerID", str(id))
	game = getGlobalVariable("game")
	me.setGlobalVariable("game", game)
	setGlobalVariable("playersSetup", str(id+1))
	setGlobalVariable("cardsDrawn{}".format(id), str(1))
	update()
	debug("Player {} sits in position {} for game {}".format(me, id, game))
	return id

def playerID(p):
	return num(p.getGlobalVariable("playerID"))

#FirstPlayer - the default value is the controller of the first player token
#If there isn't one on the table the use the value stored in the global variable
def getFirstPlayerID():
	token = getFirstPlayerToken()
	var = getGlobalVariable("firstPlayer")
	if var is None or len(var) == 0:
		id = -1
	else:
		id = num(var)

	if token is None:
		return id

	result = playerID(token.controller)
	if id != result: #Ensure global is the in sync with controller of token
		setGlobalVariable("firstPlayer", str(result))
		update()
	return result

def setFirstPlayer(id):
	setGlobalVariable("firstPlayer", str(id))

#In phase management this represents the player highlighted in green
def setActivePlayer(p):
	if p is None:
		setGlobalVariable("activePlayer", "-1")
	else:
		setGlobalVariable("activePlayer", str(playerID(p)))
	update()

def getActivePlayer():
	return getPlayer(num(getGlobalVariable("activePlayer")))

def setPlayerDone(phase=-1, step=-1):
	if phase == -1:
		phase = shared.counters['Phase'].value
	if step == -1:
		step = shared.counters['Step'].value
	me.setGlobalVariable("done", "{}.{}.{}.{}".format(getGlobalVariable("game"), shared.counters['Round'].value, phase, step))
	updatePhase()
	update()

def clearPlayerDone():
	me.setGlobalVariable("done", "")
	updatePhase()
	update()

def isPlayerDone(p, phase=-1, step=-1):
	debug("isPlayerDone({}): {}".format(p, p.getGlobalVariable("done")))
	when = p.getGlobalVariable("done").split('.')
	if len(when) != 4: return False
	game = num(getGlobalVariable("game"))
	if num(when[0]) > game: return True
	if num(when[0]) < game: return False
	if num(when[1]) > shared.counters['Round'].value: return True
	if num(when[1]) < shared.counters['Round'].value: return False
	if phase == -1:
		phase = shared.counters['Phase'].value
	if num(when[2]) > phase: return True
	if num(when[2]) < phase: return False
	if step == -1:
		step = shared.counters['Step'].value
	return num(when[3]) >= step

def deckLocked():
	return me.getGlobalVariable("deckLocked") == "1"

def lockDeck():
	me.setGlobalVariable("deckLocked", "1")

def unlockDeck():
	me.setGlobalVariable("deckLocked", "0")

#---------------------------------------------------------------------------
# Workflow routines
#---------------------------------------------------------------------------

#Triggered event OnGameStart
def startOfGame():
	unlockDeck()
	setActivePlayer(None)
	if me._id == 1:
		setGlobalVariable("playersSetup", "")
		setGlobalVariable("game", str(num(getGlobalVariable("game"))+1))
		notify("Starting Game {}".format(getGlobalVariable("game")))

	#---------------------------------------------------------------------------
	# NEW
	#---------------------------------------------------------------------------
	setGlobalVariable("currentPlayers",str([]))
	setGlobalReminders()

# Try to unload a player deck
def unloadDeck(group, x = 0, y = 0):
	mute()
	for p in me.piles:
		notify("{} removes cards from {}.".format(me,p))
		for c in me.piles[p]:
			if c.owner == me:
				c.delete()
	notify("{} removes cards from hand.".format(me))
	for c in me.hand:
		if c.owner == me:
			c.delete()
	notify("{} removes cards from table.".format(me))
	for c in group:
		if c.owner == me and c.model != "15e40d4f-b763-4dcc-aa52-e32b64a992dd":
			c.delete()
	me.counters['Threat_Level'].value = 0
	notify("{} sets threat counter to {}.".format(me,me.counters['Threat_Level'].value))

#Triggered event OnLoadDeck
# It is also explicitly called from loadDeckFromRingsDB so the same setup happens whether the player
# deck was loaded from the menu bar or from RingsDB directly
def deckLoaded(args):
	mute()
	player = args.player
	groups = args.groups
	if player != me:
		return

	isShared = False
	isPlayer = False
	for p in groups:
		if p.name == 'Hand':
			isPlayer = True
		elif p.name in shared.piles:
			isShared = True
		elif p.name in me.piles:
			isPlayer = True

	#If we are loading into the shared piles we need to become the controller of all the shared piles
	if isShared:
		notify("{} Takes control of the encounter deck".format(me))
		for p in shared.piles:
			if shared.piles[p].controller != me:
				shared.piles[p].setController(me)
		rnd(1,2) # This causes OCTGN to sync the controller changes!

	# Wizard's Quest and Woodland Realm
	for p in groups:
		for card in p:
			# Look for the Rhosgobel or Spider Den card, which will determine that the Wizard's Quest or Woodland Realm was loaded.
			if card.model == '1a3c69f9-c973-4e4e-aa00-435c1f615393' or card.model == '35fb5564-b4a1-4730-9e4d-65bd2e6d43c4':
				notify("Setting up The Wizard's Quest / The Woodland Realm.")
				setupWizardsQuest(groups)
				update()
				playerSetup(table, 0, 0, isPlayer, isShared)
				return

	#Cards for the encounter deck and player deck are loaded into the discard pile because this has visibility="all"
	#Check for cards with a Setup effects and move other cards back into the correct pile
	for p in groups:
		for card in p:
			if card.Setup == 't' and card.Type not in [ 'Quest' , 'Nightmare', 'Campaign' ]:
				addToTable(card)
			elif card.Setup == 's' and card.Type not in [ 'Quest' , 'Nightmare', 'Campaign' ]:
				addToStagingArea(card)
			elif p == encounterDiscard():
				card.moveTo(encounterDeck())
			elif p == me.piles['Discard Pile']:
				card.moveTo(me.deck)

	#Temple of the Decieved
	for p in groups:
		for card in p:
			if card.model == 'f3bc3759-1f94-4983-bebb-66c7d9e3e0b3':
				whisper('Setting up map.')
				setupTotDMap(p)



	update()
	playerSetup(table, 0, 0, isPlayer, isShared)
	#if automate():			<-----Turning off Automation by default for ScriptVersion updates, but still want playerSetup to run
	#	playerSetup(table, 0, 0, isPlayer, isShared)

#Triggered event OnChangeCounter
def counterChanged(args):
        player = args.player
        counter = args.counter
        oldV = args.value
	if counter == shared.counters['Round']:
		fp = getFirstPlayerToken()
		if fp is not None and fp.controller == me:
			fp.markers[Turn] = shared.counters['Round'].value

#Triggered event OnPlayerGlobalVariableChanged
#We use this to manage turn and phase management by tracking changes to the player "done" variable
def globalChanged(args):
	player = args.player
        var = args.name
	oldV = args.oldValue
	newV = args.value
	debug("globalChanged(player {}, Variable {}, from {}, to {})".format(player, var, oldV, newV))
	if var == "done":
		updatePhase(player)

def numDone(phase=-1, step=-1):
	count = 0
	for p in getPlayers():
		if isPlayerDone(p, phase, step): count += 1
	debug("numDone() == {}".format(count))
	return count

def highlightPlayer(p, state):
	if len(getPlayers()) <= 1:
		return
	debug("highlightPlayer {} = {}".format(p, state))
	for card in table:
		if card.Type == "Hero" and card.controller == p and card.isFaceUp:
			card.highlight = state

#Highlight all players to show his status
def highlightPlayers():
	mute()
	active = getActivePlayer()
	debug("highlightPlayers: active = {}".format(active))
	for p in getPlayers():
		c = None
		if eliminated(p):
			c = EliminatedColour
		elif isPlayerDone(p):
			c = DoneColour
		elif active is None or p == active:
			c = ActiveColour
		else:
			c = WaitingColour
		highlightPlayer(p, c)

def nextPhase():
	shared.counters['Phase'].value += 1
	shared.counters['Step'].value = 1

def nextStep():
	shared.counters['Step'].value += 1

def showPhase():
	mute()
	phaseID = [ [0], [1], [2, 3, 4], [5], [6], [7, 8, 9], [10] ]
	phase = shared.counters['Phase'].value
	step = shared.counters['Step'].value
	x = StagingStart + StagingWidth / 2 - 36
	y = StagingY + 113

	debug("showPhase: {} {}".format(phase, step))

	if phase == 0:
		notify("Player Setup")
		idx = -1
	else:
		idx = phaseID[phase-1][step-1]

	phaseCard = None
	for c in table:
		if c.model in phases:
			if idx >= 0 and phaseCard is None and c.model == phases[idx]:
				phaseCard = c
			else:
				c.moveTo(me.piles['Discard Pile'])

	if idx >= 0:
		if phaseCard is None:
			phaseCard = table.create(phases[idx], x, y)
			notify("{} - {}".format(phaseCard, phaseCard.properties['Text']))
		else:
			phaseCard.moveToTable(x, y)

def clearPhase():
	#Delete current phase card
	for c in table:
		if c.model in phases:
			c.moveTo(me.piles['Discard Pile'])

#playerDone - called when player presses the Done button
#Calls the setPlayerDone function to mark the player as ready (stored in their global variables)
#Updating the Global variable will trigger an event that will then check to see if all players are ready to move to the next phase (see updatePhase())
def playerDone(group, x=0, y=0):
	mute()
	if not phaseManagement():
		notify("<{}> done".format(me))
		return

	#The game state is defined by the phase and step we are in.
	#Some states allow any player to act (False), others restrict actions to the current active player (True)
	phaseState = [ [False], #Setup
					[False], #Resource
					[True], #Planning
					[True, True, False], #Quest (Commit, Reveal, Resolve)
					[False], #Travel
					[False], #Encounter
					[True, True, False], #Combat (Defend, Attack, Actions)
					[False] ] #Refresh
	phase = shared.counters['Phase'].value
	step = shared.counters['Step'].value
	debug("{} playerDone: Phase {} Step {} activeOnly {} Active Player {}".format(me, phase, step, phaseState[phase][step-1], getActivePlayer()))

	if phaseState[phase][step-1] == False or getActivePlayer() == me:
		setPlayerDone()

#Called when the "done" global variable is changed by one of the players
#We use this check to see if all players are ready to advance to the next phase
#Note - all players get called whenever any player changes state. To ensure we don't all do the same thing multiple times
#       only the Encounter player is allowed to change the phase or step and only the player triggering the event is allowed to change the highlights
def updatePhase(who=me):
	mute()
	if not automate():
		return

	#Depending on current game state we either
	# Advance to next player
	# Advance to next step of this phase
	# Advance to next phase
	# Advance to next round

	isActive = (getActivePlayer() == me and who == me)
	isEncounterPlayer = (encounterDeck().controller == me)

	if turnManagement() and shared.counters['Phase'].value > 0 and shared.counters['Phase'].value < 6:
		#The phase and step will not have been updated in turn management mode so we skip straight to the end of combat (ready for refresh)
		if isEncounterPlayer:
			shared.counters['Phase'].value = 6
			shared.counters['Step'].value = 3
		phase = 6
		step = 3
	else:
		phase = shared.counters['Phase'].value
		step = shared.counters['Step'].value
	debug("me = {} updatePhase({}): Phase {} Step {}".format(me, who, phase, step))

	ready = (numDone(phase, step) >= activePlayers())

	if phase == 1: #Resource
		if ready and isEncounterPlayer:
			nextPhase()
			np = getPlayer(getFirstPlayerID())
			if eliminated(np):
				np = nextPlayer(playerID(np))
			setActivePlayer(np)
			if phaseManagement():
				highlightPlayers()
		elif phaseManagement() and who == me:
			highlightPlayers()
	elif phase == 2: #Planning
		if ready:
			if isEncounterPlayer:
				nextPhase()
				setActivePlayer(getPlayer(getFirstPlayerID()))
				if phaseManagement:
					highlightPlayers()
		elif isActive:
			setActivePlayer(nextPlayer(playerID(me)))
			if phaseManagement():
				highlightPlayers()
	elif phase == 3: #Quest
		if step == 1: #Commit
			if ready:
				if isEncounterPlayer:
					nextStep()
					setActivePlayer(me)
					if phaseManagement():
						highlightPlayers()
			elif isActive:
				setActivePlayer(nextPlayer(playerID(me)))
				if phaseManagement():
					highlightPlayers()
		elif step == 2: #Reveal Encounter cards
			if isActive:
				nextStep()
				setActivePlayer(None)
				if phaseManagement():
					highlightPlayers()
		else: #Resolve questing
			if ready and isEncounterPlayer:
				nextPhase()
				setActivePlayer(None)
				if phaseManagement():
					highlightPlayers()
			elif phaseManagement() and who == me:
				highlightPlayers()
	elif phase == 4: #Travel
		if ready and isEncounterPlayer:
			nextPhase()
			if phaseManagement():
				highlightPlayers()
		elif phaseManagement() and who == me:
			highlightPlayers()
	elif phase == 5: #Encounter
		if ready and isEncounterPlayer:
			nextPhase()
			np = getPlayer(getFirstPlayerID())
			if eliminated(np):
				np = nextPlayer(playerID(np))
			setActivePlayer(np)
			if phaseManagement():
				highlightPlayers()
		elif phaseManagement() and who == me:
			highlightPlayers()
	elif phase == 6: #Combat
		if step == 1: #Defend
			if ready:
				if isEncounterPlayer:
					nextStep()
					#First player to defend is first surviving player!
					np = getPlayer(getFirstPlayerID())
					if eliminated(np):
						np = nextPlayer(playerID(np))
					setActivePlayer(np)
					if phaseManagement():
						highlightPlayers()
			elif isActive:
				setActivePlayer(nextPlayer(playerID(me)))
				if phaseManagement():
					highlightPlayers()
		elif step == 2: #Attack
			if ready:
				if isEncounterPlayer:
					nextStep()
					setActivePlayer(None)
					if phaseManagement():
						highlightPlayers()
			elif isActive:
				setActivePlayer(nextPlayer(playerID(me)))
				if phaseManagement():
					highlightPlayers()
		else:
			if ready: # Trigger refresh
				doRestoreAll()
				me.counters['Threat_Level'].value += 1
				notify("{} increases threat to {}.".format(me, me.counters['Threat_Level'].value))

				#The first player token needs to move on in the refresh phase
				if getFirstPlayerID() == playerID(me):
					advanceFirstPlayer()
				if me.isActivePlayer: # Anyone can act in the refresh phase
					setActivePlayer(None)
				if turnManagement() and not isPlayerDone(me, 7, 1): # Clear my refresh highlight if I'm not ready for phase 7
					highlightPlayer(me, None)
				if isEncounterPlayer:
					nextPhase()
					refreshReminders()

				#We need to check if we are ready to complete phase 7
				ready = (numDone(7, 1) >= activePlayers())
				if ready:
					phase = 7
			if phaseManagement() and isEncounterPlayer:
				highlightPlayers()
	if phase == 7 or phase <= 0: #Refresh or Setup
		if ready:
			if me.isActivePlayer:
				if shared.counters['Round'].value > 0: # Skip this on the first game because we did it during player setup
					getPlayer(getFirstPlayerID()).setActivePlayer()
				setActivePlayer(None)
			if isEncounterPlayer:
				# We really want all the other players to have completed running their call to this function before we advance the round
				# There is no official way to sync but calling rnd then update seems to do the trick
				rnd(1,2)
				update()
				shared.counters['Round'].value += 1
				shared.counters['Phase'].value = 1
				shared.counters['Step'].value = 1
				if phaseManagement():
					highlightPlayers()
			doNextRound()
		elif phaseManagement() and who == me:
			highlightPlayers()

	#Show the updated game state by updating the phase card
	if phaseManagement() and isEncounterPlayer:
		showPhase()

#---------------------------------------------------------------------------
# Table menu options
#---------------------------------------------------------------------------
def isLocation(cards,x,y):
	for c in cards:
		if c.Type != 'Location':
			return False
	return True

def isHero(cards,x=0,y=0):
	for c in cards:
		if c.Type != 'Hero':
			return False
	return True

def isAlly(cards,x=0,y=0):
	for c in cards:
		if c.Type != 'Ally':
			return False
	return True

def isEnemy(cards,x,y):
	for c in cards:
		if c.isFaceUp and (c.type != "Enemy" or c.orientation == Rot90):
			return False
	return True

def isFirstPlayerToken(cards,x,y):
	for c in cards:
		if c.model != "15e40d4f-b763-4dcc-aa52-e32b64a992dd":
			return False
	return True

#---------------------------------------------------------------------------
# Table group actions
#---------------------------------------------------------------------------

def turnManagementOn(group, x=0, y=0):
	mute()
	setGlobalVariable("Automation", "Turn")
	clearHighlights(group)
	if me == encounterDeck().controller:
		clearPhase()
	else:
		remoteCall(encounterDeck().controller, "clearPhase", [])
	notify("{} enables Turn Management for all players".format(me))
	notify("Use ctrl+N to advance the turn")

def phaseManagementOn(group, x = 0, y = 0):
	mute()
	setGlobalVariable("Automation", "Phase")
	highlightPlayers()
	if me == encounterDeck().controller:
		showPhase()
	else:
		remoteCall(encounterDeck().controller, "showPhase", [])
	notify("{} enables Phase Management for all players".format(me))
	notify("Use ctrl+Right Arrow to advance the phase/step")

def automationOff(group, x = 0, y = 0):
	mute()
	setGlobalVariable("Automation", "Off")
	clearHighlights(group)
	if me == encounterDeck().controller:
		clearPhase()
	else:
		remoteCall(encounterDeck().controller, "clearPhase", [])
	notify("{} disables all turn management".format(me))

def automationHelp(group, x = 0, y = 0):
	mute()
	automationCard(x, y)
	if phaseManagement():
		whisper("Phase Management is on")
		highlightPlayers()
		if me == encounterDeck().controller:
			showPhase()
		else:
			remoteCall(encounterDeck().controller, "showPhase", [])
	elif turnManagement():
		whisper("Turn Management is on")
	else:
		whisper("Turn Management is turned off")

def phaseManagement():
	mute()
	return getGlobalVariable("Automation") == "Phase"

def turnManagement():
	mute()
	auto = getGlobalVariable("Automation")
	return auto == "Turn" or len(auto) == 0

def automate():
	mute()
	return getGlobalVariable("Automation") != "Off"

def createDoneButton(group, x=0, y=0):
	for c in group:
		if c.owner == me and c.model == "4a4206d6-2ede-4d4a-bb11-c97cceaa7665":
			c.moveToTable(x, y)
			return
	group.create("4a4206d6-2ede-4d4a-bb11-c97cceaa7665", x, y, 1, False)

def createFirstPlayerToken(group, x=0, y=0):
	moveFirstPlayerToken(x, y)

def flipCoin(group, x = 0, y = 0):
    mute()
    n = rnd(1, 2)
    if n == 1:
        notify("{} flips heads.".format(me))
    else:
        notify("{} flips tails.".format(me))

def randomPlayer(group, x=0, y=0):
	mute()
	players = getPlayers()
	if len(players) <= 1:
		notify("{} randomly selects {}".format(me, me))
	else:
		n = rnd(0, len(players)-1)
		notify("{} randomly selects {}".format(me, players[n]))

def randomAlly(group, x=0, y=0):
	mute()
	randomCard(table, "Ally")

def randomHero(group, x=0, y=0):
	mute()
	randomCard(table, "Hero")

def randomCard(group, type):
	n = 0
	for card in group:
		if card.controller == me and card.Type == type:
			n = n + 1
	if n == 0:
		whisper("You have no cards of that type")
	else:
		c = rnd(1, n)
		n = 0
		for card in group:
			if card.controller == me and card.Type == type:
				n = n + 1
				if n == c:
					notify("{} randomly selects {}".format(me, card))
					card.select()

def randomNumber(group, x=0, y=0):
	mute()
	max = askInteger("Random number range (1 to ....)", 6)
	if max == None: return
	notify("{} randomly selects {} (1 to {})".format(me, rnd(1,max), max))

def readyForRefresh(group, x = 0, y = 0):
	mute()
	if phaseManagement():
		whisper("Phase Management will automate this operation")
		return

	if turnManagement():
		if shared.counters['Phase'].value < 7:
			highlightPlayer(me, WaitingColour)
			setPlayerDone(6, 3) # Mark step 6 (combat) as done - i.e. ready to refresh
		return

	doRestoreAll(group)
	me.counters['Threat_Level'].value += 1
	notify("{} increases threat to {}.".format(me, me.counters['Threat_Level'].value))

def doRestoreAll(group=table):
	mute()

	debug("doRestoreAll({})".format(group))
	myCards = (card for card in group
				if card.controller == me)
	for card in myCards:
		if not isLocked(card) and card.model != "ce1cf93c-68d9-4613-af3a-a08671152358":
			card.orientation &= ~Rot90
	notify("{} readies all his cards.".format(me))

#Advance the first player token to the next player but don't change the OCTGN active player (yet)
#This will be done at the end of the refresh phase
def advanceFirstPlayer():
	mute()
	current = getFirstPlayerID() #This is the position (ID) of the current first player
	first = nextPlayer(current)
	debug("New first player will be {}".format(first))

	if len(getPlayers()) > 1: #Put the first player token onto the table
		x, y = firstHero(first).position
		c = moveFirstPlayerToken(x, y+Spacing)
		c.setController(first)

def resetEncounterDeck(group):
	if group == specialDeck():
		discard = specialDiscard()
	else:
		discard = encounterDiscard()
	if len(discard) == 0: return
	for c in discard:
		c.moveTo(group)
	notify("{} moves all cards from {} to {}".format(me, discard.name, group.name))
	shuffle(group)

def addHidden(group=None, x=0, y=0):
	nextEncounter(encounterDeck(), x, y, True)

def addHiddenSpecial(group, x=0, y=0):
	nextEncounter(specialDeck(), x, y, True)

def addEncounter(group=None, x=0, y=0):
	nextEncounter(encounterDeck(), x, y, False)
	if me == encounterDeck().controller:
		questReminders()

def addEncounterSpecial(group=None, x=0, y=0):
	nextEncounter(specialDeck(), x, y, False)

def addToStagingArea(card, facedown=False, who=me):
	#Check to see if there is already an encounter card here.
	#If so shuffle it left to make room
	ex = StagingStart + StagingWidth - card.width()
	ey = StagingY
	move = cardHere(ex, ey)
	while move is not None:
		layoutStage(move)
		move = cardHere(ex, ey)
	card.moveToTable(ex, ey, facedown)
	layoutStage(card)
	notify("{} adds '{}' to the staging area.".format(who, card))

def nextEncounter(group, x, y, facedown, who=me):
	mute()

	if group.controller != me:
		remoteCall(group.controller, "nextEncounter", [group, x, y, facedown, me])
		return

	if len(group) == 0:
		resetEncounterDeck(group)
	if len(group) == 0: # No cards
		return

	clearTargets()
	card = group.top()
	if x == 0 and y == 0:  #Move to default position in the staging area
		addToStagingArea(card, facedown, who)
	else:
		card.moveToTable(x-card.width()/2, y-card.height()/2, facedown)
		notify("{} places '{}' on the table.".format(who, card))
	card.setController(who)
	setReminders(card)
	if len(group) == 0:
		resetEncounterDeck(group)

def nextQuestStage(group=None, x=0, y=0):
	mute()

	#If the current quest card has side A showing it is simply flipped and we are done
	for c in table:
		if c.Type in ("Quest", "Nightmare") and c.alternates is not None and "B" in c.alternates and c.alternate != "B":
			flipcard(c)
			return

	#We need a new quest card
	if group is None or group == table:
		group = questDeck()
	if len(group) == 0: return

	if group.controller != me:
		remoteCall(group.controller, "nextQuestStage", [group, x, y])
		return

	if x == 0 and y == 0: #The keyboard shortcut was used
		#Count quest cards already on table to work out where to put this one
		n, count = questCount(table)
		x = QuestStartX + 89*(count // 2) + 64*n
		y = QuestStartY + 64*(count % 2)

	# card = group.top()
	# card.moveToTable(x, y)
	# setReminders(card)
	# if card.Type in ("Nightmare", "Campaign"):
		# card.moveToTable(x, y)
		# notify("{} begins a {} quest '{}'".format(me, card.Type, card))
		# questSetup(card)
		# if card.Type == "Nightmare":
			# flipcard(card)
		# #Reveal and place the real quest card
		# if len(group) > 0:
			# card = group[0]
			# card.moveToTable(x+64, y)
			# #If next card was a nightmare/campaign card, still need to reveal the actual quest card
			# if card.Type in ("Nightmare", "Campaign"):
				# if len(group) > 0:
					# card = group[0]
					# card.moveToTable(x+2*64, y)


	card = group.top()
	card.moveToTable(x, y)
	questSetup(card) # Look for special setup rules on the first card in the quest pile
	setReminders(card)
	notify("Setting up {}".format(card))
	i=1
	# Keep putting cards on the table until a quest card is found
	while card.Type != "Quest":
		notify("Setting up {}".format(card))
		card = group[0]
		if card is None: break
		card.moveToTable(x+i*64, y)
		setReminders(card)
		i +=1

	questSetup(card)
	notify("{} advances quest to '{}'".format(me, card))

def addToTable(card):
	x = QuestStartX - 80
	y = -96
	blocked = cardHere(x, y, False)
	while blocked is not None:
		x += 16
		blocked = cardHere(x, y, False)
	card.moveToTable(x, y)

def questSetup(card):
	if len(card.Setup) + len(setupDeck()) + len(stagingSetupDeck()) + len(activeSetupDeck()) > 0:
		cardsToStage = card.Setup.count('s')
		i = 0
		for c in setupDeck():
			if i >= len(card.Setup) or card.Setup[i] == 't':
				addToTable(c)
			elif card.Setup[i] == 's':
				addToStagingArea(c)
				setReminders(c)
			elif card.Setup[i] == 'l':
				makeActive(c)
				setReminders(c)
			i += 1
		for c in stagingSetupDeck():
			addToStagingArea(c)
		for c in activeSetupDeck():
			makeActive(c)

def readyForNextRound(group=table, x=0, y=0):
	mute()
	if phaseManagement():
		whisper("Phase Management will automate this operation")
		return

	if turnManagement():
		highlightPlayer(me, DoneColour)
		setPlayerDone(7, 1) # Mark phase 7 (Refresh) as complete - i.e. ready for next round
		return

	clearTargets()
	resourcePhaseDraw()
	for card in group:
		if card.Type == "Hero" and card.controller == me and not isLocked(card):
			addResource(card)


#doNextRound
#Draw a card and add a resource to each hero
def doNextRound():
	mute()
	debug("doNextRound()")

#	if activePlayers() == 0:
#		whisper("All players have been eliminated: You have lost the game")
#		return
#	if eliminated(me):
#		whisper("You have been eliminated from the game")
#		return

	clearTargets()
	if me.Willpower <> 0:
		me.Willpower = 0

	resourcePhaseDraw()

	for card in table:
		if card.Type == "Hero" and card.controller == me and not isLocked(card) and card.isFaceUp:
			addResource(card)
	# Additional resources per round
		if card.controller == me and not isLocked(card) and card.isFaceUp:
			try:
				resPerRound = int(card.properties['Resource Tokens Per Round'])
			except:
				resPerRound = 0
			for i in xrange(resPerRound):
				addResource(card)

	if not phaseManagement():
		clearHighlights()

	if me == encounterDeck().controller:
		resourceReminders()

def playerSetup(group=table, x=0, y=0, doPlayer=True, doEncounter=False):

	if not getLock():
		whisper("Others players are setting up, please try manual setup again (Ctrl+Shift+S)")
		return

	unlockDeck()
	if doPlayer:
		id = myID() #This ensures we have a unique ID based on our position in the setup order
		heroCount = countHeroes(me)
		if shared.counters['Round'].value == 0 and id == 0 and heroCount == 0: #First time actions
			me.setActive()
			setFirstPlayer(id)

		#Move Heroes to the table
		newHero = False
		lore = 0
		hobbits = 0
		setupCards = []
		for card in me.hand:
			if card.Type == "Contract":
				card.moveToTable(heroX(id, heroCount), HeroY)
				heroCount += 1
				
			if card.Type == "Ally":
				card.delete()
				continue
			
			if card.Type == "Hero":
					
				card.moveToTable(heroX(id, heroCount), HeroY)
				heroCount += 1
				newHero = True
				me.counters['Threat_Level'].value += num(card.Cost)
				if isSetupCard(card):
					setupCards.append(card.Name)

					#Leadership Denethor starts with 2 extra resources
					if card.Name == 'Denethor':
						addResource(card)
						addResource(card)

				if card.Sphere == 'Lore':
					lore += 1
				if 'Hobbit' in card.Traits:
					hobbits += 1

		# Tactics Éowyn - reduces your starting threat by 3
		if 'Éowyn' in setupCards:
			me.counters['Threat_Level'].value -= 3

		# Mirlonde - reduces your starting threat by 1 for each Lore hero you control
		if 'Mirlonde' in setupCards:
			me.counters['Threat_Level'].value -= lore

		# Folco Boffin - reduces your starting threat by 1 for each Hobbit hero you control
		if 'Folco Boffin' in setupCards:
			me.counters['Threat_Level'].value -= hobbits

		drawStartingHand = True
		# The One Ring
		masterCards = []
		for card in me.deck:
			if card.Name == 'The One Ring':
				card.moveToTable(heroX(id, heroCount), HeroY)
				heroCount += 1
				for card in me.deck:
					if 'Master.' in card.Traits and card.Name not in masterCards:
						card.moveToTable(heroX(id, heroCount), HeroY)
						heroCount += 1
						masterCards.append(card.Name)
		if len(masterCards) > 1: drawStartingHand = False # Need to decide first

		# Thurindir - place all your side quests on the table to choose one
		sideQuests = []
		if 'Thurindir' in setupCards:
			for card in me.deck:
				if card.Type == 'Side Quest' and card.Name not in sideQuests:
					card.moveToTable(heroX(id, len(sideQuests)), -36 )
					sideQuests.append(card.Name)
		if len(sideQuests) > 1: drawStartingHand = False # Need to decide first


		if newHero:
			notify("{} places his Heroes on the table and sets his starting Threat to {}".format(me,me.counters['Threat_Level'].value))
			if len(me.hand) == 0:
				shuffle(me.deck)
				if drawStartingHand: drawMany(me.deck, shared.HandSize)
			if len(getPlayers()) > 1 and getFirstPlayerID() == playerID(me): #Put the first player token onto the table
				x, y = firstHero(me).position
				c = moveFirstPlayerToken(x, y+Spacing)
				c.setController(me)

	#If we loaded the encounter deck - add the first quest card to the table
	if doEncounter or encounterDeck().controller == me:
		n, count = questCount(table)
		if n+count == 0:
			nextQuestStage()
			shuffle(encounterDeck())
			shuffle(specialDeck())

	if phaseManagement():
		highlightPlayers()

	if not clearLock():
		notify("Players performed setup at the same time causing problems, please reset and try again")

def calcScore(group=None, x=0, y=0):
	mute()
	scoreTotal = 0
	scoreRound = 0
	scoreDamage = 0
	scoreDeadHeroes = 0
	scoreThreat = 0
	completedRounds = shared.counters['Round'].value - 1
	if completedRounds < 0:
		completedRounds = turnNumber() - 1
	if completedRounds < 0:
		notify("Set the global Round counter to the current round before calculating score!")
		return
	notify(":::Calculating Score...:::")
	scoreRound = completedRounds * 10
	notify("{} completed rounds = {}".format(completedRounds,scoreRound))
	for player in getPlayers():
		scoreThreat += player.counters['Threat_level'].value
		for card in player.piles['Discard Pile']:
			if card.Type == "Hero": scoreDeadHeroes += num(card.Cost)
	notify("Total combined Threat = {}".format(scoreThreat))
	for card in table:
		if card.Type == "Hero": scoreDamage += card.markers[Damage]
	notify("Total damage on Heroes = {}".format(scoreDamage))
	notify("Cost of dead Heroes = {}".format(scoreDeadHeroes))
	sumVictory()
	notify("Victory points = {}".format(shared.VictoryPoints))
	scoreTotal = scoreRound + scoreThreat + scoreDamage + scoreDeadHeroes - shared.VictoryPoints
	notify("TOTAL SCORE = {}".format(scoreTotal))

def toggleLock(group, x=0, y=0):
	if deckLocked():
		unlockDeck()
		if len(me.deck) > 0:
			if isLocked(me.deck.top()):
				lockCard(me.deck.top())
		notify("{} Unlocks his deck".format(me))
	else:
		lockDeck()
		if len(me.deck) > 0:
			lockCard(me.deck.top())
		notify("{} Locks his deck".format(me))

#---------------------------------------------------------------------------
# Table card actions
#---------------------------------------------------------------------------
def changeCardType(card, x=0, y=0):
	if card.Type == 'Hero':
		card.Type = 'Ally'
	elif card.Type == 'Ally':
		card.Type = 'Hero'
	else:
		return
	notify("{} changed type of {} to {}.".format(me, card.Name, card.Type))

def defaultAction(card, x = 0, y = 0):
	mute()
	# Default for Done button is playerDone
	if card.Type == "Internal": #No action - unless it is the done button
		if card.model == "4a4206d6-2ede-4d4a-bb11-c97cceaa7665":
			playerDone(table, x, y)
	elif not card.isFaceUp: #Face down card - flip
		flipcard(card, x, y)
	elif card.orientation & Rot90 == Rot90: #Rotated card - refresh
		kneel(card, x, y)
	elif card.Type == "Quest":
		if len(card.properties['Quest Points']) == 0:
			flipcard(card)
		elif card.markers[Progress] >= num(card.properties['Quest Points']):
			discard(card)
		else:
			addProgress(card, x, y)
	elif card.Type == "Nightmare" or card.type == "Campaign":
		flipcard(card)
	elif card.Type == "Location" or card.Type == "Side Quest": #Add a progress token
		addProgress(card, x, y)
	elif card.Type == "Enemy": #Add damage
		addDamage(card, x, y)
	else:
		kneel(card, x, y)

def kneel(card, x = 0, y = 0):
    mute()
    card.orientation ^= Rot90
    if card.orientation & Rot90 == Rot90:
        notify("{} exhausts '{}'".format(me, card))
    else:
        notify("{} readies '{}'".format(me, card))

def inspectCard(card, x = 0, y = 0):
    whisper("{} - model {}".format(card, card.model))
    for k in card.properties:
        if len(card.properties[k]) > 0:
            whisper("{}: {}".format(k, card.properties[k]))

def flipcard(card, x = 0, y = 0):
	mute()

	if card.controller != me:
		notify("{} gets {} to flip card".format(me, card.controller()))
		remoteCall(card.controller, "flipcard", card)
		return

	cardx, cardy = card.position

	#Treachery of Rhudaur double-sided objective card swap (TEMP until OCTGN supports cardsize for Alternates)
	if card.model == "6709bafa-87b5-483e-9895-0f2edea7e47a":
		notify("{} flips '{}'.".format(me, card))
		card.delete()
		table.create('87c33692-599d-4914-a513-4353906fc6d4', cardx, cardy, quantity = 1, persist = True)
		return

	if card.model == "87c33692-599d-4914-a513-4353906fc6d4":
		notify("{} flips '{}'.".format(me, card))
		card.delete()
		table.create('6709bafa-87b5-483e-9895-0f2edea7e47a', cardx, cardy, quantity = 1, persist = True)
		return

	if card.model == "bf925a7c-b427-4fb6-ba6b-dbc86304a69f":
		notify("{} flips '{}'.".format(me, card))
		card.delete()
		table.create('2e5e6e97-003b-4500-8372-495f5ee86051', cardx, cardy, quantity = 1, persist = True)
		return

	if card.model == "2e5e6e97-003b-4500-8372-495f5ee86051":
		notify("{} flips '{}'.".format(me, card))
		card.delete()
		table.create('bf925a7c-b427-4fb6-ba6b-dbc86304a69f', cardx, cardy, quantity = 1, persist = True)
		return

	if card.model == "768bab66-1707-41a4-adf3-3baad2e7daad":
		notify("{} flips '{}'.".format(me, card))
		card.delete()
		table.create('d9c04b71-93cd-455d-9f6e-4ee16cf7d1b4', cardx, cardy, quantity = 1, persist = True)
		return

	if card.model == "d9c04b71-93cd-455d-9f6e-4ee16cf7d1b4":
		notify("{} flips '{}'.".format(me, card))
		card.delete()
		table.create('768bab66-1707-41a4-adf3-3baad2e7daad', cardx, cardy, quantity = 1, persist = True)
		return
	#END Treachery of Rhudaur WORKAROUND
	#Quest cards have a different back - defined by the alternate (B) property
	if card.alternates is not None and "B" in card.alternates:
		if card.alternate == "B":
			card.switchTo("")
		else:
			card.switchTo("B")
		if card.Type != "Location": questSetup(card) #Don't do setup for double-sided locations
		notify("{} turns '{}' face up.".format(me, card))
	elif card.isFaceUp:
		card.isFaceUp = False
		notify("{} turns '{}' face down.".format(me, card))
	else:
		card.isFaceUp = True
		notify("{} turns '{}' face up.".format(me, card))


def rotateRight(card, x = 0, y = 0):
	# Rot90, Rot180, etc. are just aliases for the numbers 0-3
	mute()
	if card.controller == me:
		card.orientation = (card.orientation + 1) % 4
		if card.isFaceUp:
			notify("{} Rotates '{}'".format(me, card.Name))
		else:
			notify("{} Rotates a card".format(me))
	#mute()
	#if card.orientation == Rot0:
	#	card.orientation = Rot90
	#elif card.orientation == Rot90:
	#	card.orientation = Rot180
	#elif card.orientation == Rot180:
	#	card.orientation = Rot270
	#else:
	#	card.orientation = Rot0

def rotateLeft(card, x = 0, y = 0):
	# Rot90, Rot180, etc. are just aliases for the numbers 0-3
	mute()
	if card.controller == me:
		card.orientation = (card.orientation - 1) % 4
		if card.isFaceUp:
			notify("{} Rotates '{}'".format(me, card.Name))
		else:
			notify("{} Rotates a card".format(me))
	#mute()
	#if card.orientation == Rot0:
	#	card.orientation = Rot270
	#elif card.orientation  == Rot270:
	#	card.orientation = Rot180
	#elif card.orientation == Rot180:
	#	card.orientation = Rot90
	#else:
	#	card.orientation = Rot0

def makeActive(card, x=0, y=0):
	mute()
	if card.Type != "Location": return
	card.moveToTable(252, -229)

def addResource(card, x = 0, y = 0):
    addToken(card, Resource)

def addDamage(card, x = 0, y = 0):
    addToken(card, Damage)

def addProgress(card, x = 0, y = 0):
    addToken(card, Progress)

def addWillpower(card, x = 0, y = 0):
    addToken(card, WillpowerToken)

def addAttack(card, x = 0, y = 0):
    addToken(card, AttackToken)

def addDefense(card, x = 0, y = 0):
    addToken(card, DefenseToken)

def addThreat(card, x = 0, y = 0):
    addToken(card, ThreatToken)

def addTime(card, x=0, y=0):
    addToken(card, TimeToken)

def addTurn(card, x=0, y=0):
	if isFirstPlayerToken([card]):
		shared.counters['Round'].value += 1

def addToken(card, tokenType):
	mute()
	card.markers[tokenType] += 1
	notify("{} adds a {} to '{}'".format(me, tokenType[0], card))

def subResource(card, x = 0, y = 0):
    subToken(card, Resource)

def subDamage(card, x = 0, y = 0):
    subToken(card, Damage)

def subProgress(card, x = 0, y = 0):
    subToken(card, Progress)

def subWillpower(card, x = 0, y = 0):
    subToken(card, WillpowerToken)

def subAttack(card, x = 0, y = 0):
    subToken(card, AttackToken)

def subDefense(card, x = 0, y = 0):
    subToken(card, DefenseToken)

def subThreat(card, x = 0, y = 0):
    subToken(card, ThreatToken)

def subTime(card, x=0, y=0):
    subToken(card, TimeToken)

def subTurn(card, x=0, y=0):
	if isFirstPlayerToken([card]) and shared.counters['Round'].value > 0:
		shared.counters['Round'].value -= 1

def subToken(card, tokenType):
    mute()
    card.markers[tokenType] -= 1
    notify("{} removes a {} from '{}'".format(me, tokenType[0], card))

def lockCard(card, x=0, y=0):
	mute()
	if isLocked(card):
		card.markers[Lock] = 0
	else:
		card.markers[Lock] = 1

def isLocked(card):
	return card.markers[Lock] > 0

def shadowCardAt(sx, sy):
	for c in table:
		x, y = c.position
		if x == sx and y == sy and c.orientation == Rot90:
			return True
	return False

def addShadow(card, x=0, y=0):
	mute ()

	if not card.isFaceUp and card.orientation == Rot90: #This is a shadow card - reveal it
		card.isFaceUp = True
		if card.Type == "Side Quest":
			indx = card.getIndex
			card.orientation &= ~Rot90
			shadx, shady = card.position
			card.moveToTable(shadx, shady+25)
			card.setIndex(indx)
		notify("{} reveals shadow card '{}'".format(me, card))
		return

	#Only enemy cards or facedown player cards (Orc Guards) are valid targets
	if card.isFaceUp and (card.type != "Enemy" or card.orientation == Rot90):
		return

	if len(encounterDeck()) == 0:
		whisper("There are no cards left in the encounter deck")
		return

	posx, posy = card.position
	xoff = (card.width() - card.height())/2
	yoff = card.width() - card.height()/2
	if table.isTwoSided() and posy + card.height()/2 < 0 :
		x = posx - xoff
		y = posy - yoff
		skip = -8
	else:
		x = posx + xoff
		y = posy + yoff
		skip = 8

	while shadowCardAt(x, y):
		x += skip
		y += skip

	notify("{} adds a shadow card to '{}'".format(me, card))
	dealShadow(card.controller, x, y)
	if me == encounterDeck().controller:
		combatReminders()
def dealShadow(who, x, y):
	if encounterDeck().controller != me:
		remoteCall(encounterDeck().controller, "dealShadow", [who, x, y])
		return

	deck = encounterDeck()
	if len(deck) == 0:
		return
	sc = deck.top()
	#if sc.Type != "Side Quest":  #Hopefully just a temp "fix" for landscape shadow cards
	#	sc.moveToTable(x, y, True)
	#	sc.orientation = Rot90
	#else:
	#	sc.moveToTable(x, y+25, True)
	sc.moveToTable(x, y, True)
	sc.orientation = Rot90
	sc.sendToBack()
	sc.setController(who)


def discard(card, x=0, y=0):
	mute()
	if card.controller != me:
		whisper("{} does not control '{}' - discard cancelled".format(me, card))
		return

	if card.Type == "Quest": #If we remove the only quest card then we reveal the next one
		card.moveToBottom(questDiscard())
		notify("{} discards '{}'".format(me, card))
		n, c = questCount(table)
		if c == 0:
			nextQuestStage()
		return

	if isEncounterCard(card):
		pile = encounterDiscard()
	elif isPlayerCard(card):
		pile = card.owner.piles['Discard Pile']
	elif isSpecialCard(card):
		pile = specialDiscard()
	else:
		pile = encounterDiscard()

	who = pile.controller
	notify("{} discards '{}'".format(me, card))
	if who != me:
		card.setController(who)
		remoteCall(who, "doDiscard", [me, card, pile])
	else:
		doDiscard(who, card, pile)

def discardSpecial(card, x=0, y=0):
	mute()
	if card.controller != me:
		whisper("{} does not control '{}' - discard cancelled".format(me, card))
		return

	if card.Type == "Quest": #If we remove the only quest card then we reveal the next one
		card.moveToBottom(questDiscard())
		notify("{} discards '{}'".format(me, card))
		n, c = questCount(table)
		if c == 0:
			nextQuestStage()
		return

	if isPlayerCard(card):
		pile = specialDiscard()
	elif isSpecialCard(card):
		pile = specialDiscard()
	else:
		pile = specialDiscard()

	who = pile.controller
	notify("{} discards '{}'".format(me, card))
	if who != me:
		card.setController(who)
		remoteCall(who, "doDiscard", [me, card, pile])
	else:
		doDiscard(who, card, pile)


def doDiscard(player, card, pile):
	card.moveTo(pile)

def shuffleIntoDeck(card, x=0, y=0, player=me):
	mute()
	if card.controller != me:
		whisper("{} does not control '{}' - shuffle cancelled".format(me, card))
		return

	if card.Type == "Quest":
		whisper("Invalid operation on a {} card".format(card.Type))
		return

	if isPlayerCard(card) and 'Encounter' not in card.Keywords:
		pile = card.owner.deck
	elif isSpecialCard(card):
		pile = specialDeck()
	else:
		pile = encounterDeck()

	who=pile.controller
	notify("{} moves '{}' to '{}'".format(me, card, pile.name))
	if who != me:
		card.setController(who)
		remoteCall(who, "doMoveShuffle", [me, card, pile])
	else:
		doMoveShuffle(me, card, pile)

def doMoveShuffle(player, card, pile):
	card.moveTo(pile)
	shuffle(pile)

def playCard(card, x=0, y=0):
	if x == 0 and y == 0 and not eliminated(me):
		x, y = firstHero(me).position
		x += Spacing
		y += Spacing
	card.moveToTable(x, y)
	card.select()

def swapCard(card):
	draw(me.deck)
	card.moveTo(me.deck)
	notify("{} returns {} to the top of the deck.".format(me, card))

def sumVictory():
	v = 0
	for c in shared.piles['Victory Display']:
		v += num(c.properties['Victory Points'])
	shared.VictoryPoints = v

def moveToVictory(card, x=0, y=0):
	mute()
	card.moveTo(shared.piles['Victory Display'])
	v = num(card.properties['Victory Points'])
	sumVictory()
	notify("{} adds '{}' (+{}) to the Global Victory Display (Total = {})".format(me, card, v, shared.VictoryPoints))


#---------------------------
#movement actions
#---------------------------

#------------------------------------------------------------------------------
# Hand Actions
#------------------------------------------------------------------------------

def randomDiscard(group):
	mute()
	card = group.random()
	if card is None: return
	notify("{} randomly discards '{}'.".format(me, card))
	card.moveTo(me.piles['Discard Pile'])

def mulligan(group, x = 0, y = 0):
	mute()
	if shared.HandSize <= 0:
		whisper("Invalid hand size specified in global counter")
		return
	if not confirm("Are you sure you want to Mulligan?"): return
	for card in group:
		card.moveToBottom(me.deck)
	shuffle(me.deck)
	for card in me.deck.top(shared.HandSize):
		card.moveTo(me.hand)
	notify("{} draws {} new cards.".format(me, shared.HandSize))

#------------------------------------------------------------------------------
# Pile Actions
#------------------------------------------------------------------------------

def draw(group, x = 0, y = 0):
	mute()
	if len(group) == 0: return
	if deckLocked():
		whisper("Your deck is locked, you cannot draw a card at this time")
		return
	card = group[0]
	card.moveTo(me.hand)
	notify("{} draws '{}'".format(me, card))

def shuffle(group):
	mute()
	if len(group) > 0:
		update()
		group.shuffle()
		notify("{} shuffles {}".format(me, group.name))

def drawMany(group, count = None):
	mute()
	if len(group) == 0: return
	if deckLocked():
		whisper("Your deck is locked, you cannot draw cards at this time")
		return
	if count is None:
		count = askInteger("Draw how many cards?", 6)
	if count is None or count <= 0:
		whisper("drawMany: invalid card count")
		return
	for c in group.top(count):
		c.moveTo(me.hand)
		notify("{} draws '{}'".format(me, c))

def lookAtAllEncounterDeck(group, x = 0, y = 0):
	mute()
	notify("{} looks at Global's Encounter.".format(me))
	encounterDeck().lookAt(-1,True)

def lookAtAllEncounterDiscard(group, x = 0, y = 0):
	mute()
	encounterDiscard().lookAt(-1,True)

def lookAtTop5Deck(group, x = 0, y = 0):
	mute()
	notify("{} looks at {}'s Deck.".format(me, me))
	me.deck.lookAt(5,True)

def lookAtTop10Deck(group, x = 0, y = 0):
	mute()
	notify("{} looks at {}'s Deck.".format(me, me))
	me.deck.lookAt(10,True)

def search(group, count = None):
	mute()
	if len(group) == 0: return
	if count is None:
		count = askInteger("Search how many cards?", 5)
	if count is None or count <= 0:
		whisper("search: invalid card count")
		return

	notify("{} searches top {} cards".format(me, count))
	moved = 0
	for c in group.top(count):
		c.moveTo(me.piles['Discard Pile'])
		moved += 1
	me.piles['Discard Pile'].lookAt(moved)

def moveMany(group, count = None):
	if len(group) == 0: return
	mute()
	if count is None:
		count = askInteger("Move how many cards to secondary deck?", 1)
		if count is None or count <= 0: return

	moved = 0

	if group == me.deck:
		pile = me.piles['Secondary Deck']
	else:
		pile = specialDeck()

	for c in group.top(count):
		c.moveTo(pile)
		moved += 1
	notify("{} moves {} cards to the secondary deck".format(me, moved))
	if pile.collapsed:
		pile.collapsed = False

def discardMany(group, count = None):
	if len(group) == 0: return
	mute()
	if count is None:
		count = askInteger("Discard how many cards?", 1)
		if count is None or count <= 0: return

	if group == me.deck:
		pile = me.piles['Discard Pile']
		fr = "his deck"
	else:
		pile = encounterDiscard()
		fr = "the Encounter Deck"

	for c in group.top(count):
		c.moveTo(pile)
		notify("{} discards '{}' from {}".format(me, c, fr))

def moveAllToEncounter(group):
	mute()
	if confirm("Shuffle all cards from {} to Encounter Deck?".format(group.name)):
		for c in group:
			c.moveTo(encounterDeck())
		notify("{} moves all cards from {} to the Encounter Deck".format(me, group.name))
		shuffle(encounterDeck())

def moveAllToEncounterBottom(group):
	mute()
	if confirm("Move all cards from {} to the bottom of the Encounter Deck?".format(group.name)):
		for c in group:
			c.moveToBottom(encounterDeck())
		notify("{} moves all cards from {} to the bottom of the Encounter Deck".format(me, group.name))


def moveAllToSpecial(group):
	mute()
	if confirm("Shuffle all cards from {} to Special Deck?".format(group.name)):
		for c in group:
			c.moveTo(specialDeck())
		notify("{} moves all cards from {} to the Special Deck".format(me, group.name))
		shuffle(specialDeck())

def moveAllToPlayer(group):
	mute()
	if confirm("Shuffle all cards from {} to Player Deck?".format(group.name)):
		for c in group:
			if c.Type != "Hero" and len(c.Setup) == 0:
				c.moveTo(c.owner.piles['Deck'])
		notify("{} moves all cards from {} to the Player Deck".format(me, group.name))
		shuffle(me.piles['Deck'])

def swapWithEncounter(group):
  mute()
  if confirm("Swap all cards from {} with those in Encounter Deck?".format(group.name)):
	deck = encounterDeck()
	size = len(deck)
	for c in group:
		c.moveToBottom(deck)
	for c in deck.top(size):
		c.moveToBottom(group)
	notify("{} swaps {} and Encounter Deck.".format(me, group.name))

def captureDeck(group):
	if len(group) == 0: return
	mute()
	if group == me.deck:
		pile = me.piles['Secondary Deck']
	else: return
	if confirm("Create your capture deck?"):
		for c in group:
			if c.Type == "Ally":
				c.moveTo(pile)
			if c.Type == "Attachment":
				if "Item." in c.Traits or "Mount." in c.Traits or "Artifact." in c.Traits:
					c.moveTo(pile)
	notify("{} creates their Capture Deck".format(me))
	if pile.collapsed:
		pile.collapsed = False

def setupTotDMap(group):
	group.shuffle()
	MapStartX = 350
	MapStartY = -90
	i = 0

	map = []
	for c in group:
		c.moveToTable(MapStartX,MapStartX)
		map.append(c)

	for c in map:
		if c.name == "Lost Island":
			x = MapStartX + 64*(i // 3)
			y = MapStartY + 89*(i % 3)
			c.moveToTable(x,y)
			if i==0 or i==2:
				flipcard(c)
			i=i+1

	for c in map:
		if c.name == "Edge of the Temple":
			x = MapStartX + 64*(i // 3)
			y = MapStartY + 89*(i % 3)
			c.moveToTable(x,y)
			i=i+1

	for c in map:
		if c.name == "Temple of the Deceived":
			x = MapStartX + 64*(i // 3)
			y = MapStartY + 89*(i % 3)
			c.moveToTable(x,y)
			i=i+1

		# c.moveToTable(MapStartX,MapStartX)
		# if c.name == "Lost Island":
			# x = MapStartX + 64*(i // 3)
			# y = MapStartY + 89*(i % 3)
			# c.moveToTable(x,y)
			# if i==0 or i==2:
				# flipcard(c)
			# i=i+1
		# if c.name == "Temple of the Deceived":
			# c.moveToTable(MapStartX+64*4,MapStartY+89*j)
			# j=j+1



# Wizard's Quest and Woodland Realm
def setupWizardsQuest(groups):
	offset = [0]*28 # Define Offsets for each of the 28 encounter sets
	StartX = StagingStart - 64 * 3
	StartY = StagingY - 20
	for p in groups:
		for card in p:
			set = card.properties["Encounter Set"]
			setnumstr = set[-2:] # Get last two characters from encounter set, so "Wizard's Quest 15" becomes "15"
			if not setnumstr.isdigit():
				addToTable(card)
				continue
			setnum = int(setnumstr) # Cast to int
			setnum -= 1 # 0 based
			x = StartX + 64 * (setnum % 14)
			y = StartY + 150 * (setnum // 14) + offset[setnum]
			offset[setnum] += 12
			card.moveToTable(x,y)




# Reminders

def enableReminders(group, x=0, y=0):
	setGlobalVariable("Reminders", "On")
	whisper("Reminders enabled.")
def disableReminders(group, x=0, y=0):
	setGlobalVariable("Reminders", "Off")
	whisper("Reminders disabled.")

def isTextInCard(text,card):
	match = re.search(text,card.Text)
	if match: return True
	try:
		match = re.search(text,card.alternateProperty("B","Text"))
		if match: return True
	except:
		pass

def setReminders(card):
	match = re.search('Time ([0-9]+)',card.Text)
	if match:
		for i in range(num(match.group(1))):
			addTime(card)
	try:
		match = re.search('Time ([0-9]+)',card.alternateProperty("B","Text"))
		if match:
			for i in range(num(match.group(1))):
				addTime(card)
	except:
		pass

	if isTextInCard('resource phase',card): setReminderResource(card)
	if isTextInCard('quest phase',card): setReminderQuest(card)
	if isTextInCard('staging step',card): setReminderQuest(card)
	if isTextInCard('combat phase',card): setReminderCombat(card)
	if isTextInCard('refresh phase',card): setReminderRefresh(card)
	if isTextInCard('t the end of the round',card): setReminderRefresh(card)

def resourceReminders():
	if getGlobalVariable("Reminders") == "Off": return;
	clearTargets()
	reminder = getGlobalVariable("reminderResource")
	for c in table:
		if str(c._id) in reminder:
			c.target(True)

def questReminders():
	if getGlobalVariable("Reminders") == "Off": return;
	reminder = getGlobalVariable("reminderQuest")
	for c in table:
		if str(c._id) in reminder:
			c.target(True)

def combatReminders():
	if getGlobalVariable("Reminders") == "Off": return;
	reminder = getGlobalVariable("reminderCombat")
	for c in table:
		if str(c._id) in reminder:
			c.target(True)

def refreshReminders():
	if getGlobalVariable("Reminders") == "Off": return;
	clearTargets()
	reminder = getGlobalVariable("reminderRefresh")
	for c in table:
		if c.markers[TimeToken] >= 1:
			c.target(True)
		if str(c._id) in reminder:
			c.target(True)

def setReminderResource(card,x=0,y=0):
	reminder = getGlobalVariable("reminderResource")
	if not str(card._id) in reminder:
		reminder += str(card._id) + ","
	setGlobalVariable("reminderResource",reminder)
def removeReminderResource(card,x=0,y=0):
	reminder = getGlobalVariable("reminderResource")
	reminder = reminder.replace(str(card._id) + ",","")
	setGlobalVariable("reminderResource",reminder)

def setReminderQuest(card,x=0,y=0):
	reminder = getGlobalVariable("reminderQuest")
	if not str(card._id) in reminder:
		reminder += str(card._id) + ","
	setGlobalVariable("reminderQuest",reminder)
def removeReminderQuest(card,x=0,y=0):
	reminder = getGlobalVariable("reminderQuest")
	reminder = reminder.replace(str(card._id) + ",","")
	setGlobalVariable("reminderQuest",reminder)

def setReminderCombat(card,x=0,y=0):
	reminder = getGlobalVariable("reminderCombat")
	if not str(card._id) in reminder:
		reminder += str(card._id) + ","
	setGlobalVariable("reminderCombat",reminder)
def removeReminderCombat(card,x=0,y=0):
	reminder = getGlobalVariable("reminderCombat")
	reminder = reminder.replace(str(card._id) + ",","")
	setGlobalVariable("reminderCombat",reminder)

def setReminderRefresh(card,x=0,y=0):
	reminder = getGlobalVariable("reminderRefresh")
	if not str(card._id) in reminder:
		reminder += str(card._id) + ","
	setGlobalVariable("reminderRefresh",reminder)
def removeReminderRefresh(card,x=0,y=0):
	reminder = getGlobalVariable("reminderRefresh")
	reminder = reminder.replace(str(card._id) + ",","")
	setGlobalVariable("reminderRefresh",reminder)

def setGlobalReminders():
	setGlobalVariable("Reminders", "Off")
	setGlobalVariable("reminderResource","")
	setGlobalVariable("reminderQuest","")
	setGlobalVariable("reminderCombat","")
	setGlobalVariable("reminderRefresh","")

def tokensPerRoundResource(card,x=0,y=0):
	current = 0
	try:
		current = num(card.properties['Resource Tokens Per Round'])
	except:
		pass

	count = askInteger("How many additional resource tokens per round?", current)
	if count is None or count < 0: return
	newval = count
	card.properties['Resource Tokens Per Round'] = str(newval)
	update()
	whisper("{} is now generating an additional {} resource(s) per round.".format(card.Name,card.properties['Resource Tokens Per Round']))


def createCard(group=None, x=0, y=0):
	cardID, quantity = askCard()
	cards = table.create(cardID, x, y, quantity, True)
	try:
		iterator = iter(cards)
	except TypeError:
		# not iterable
		notify("{} created {}.".format(me, cards))
	else:
		# iterable
		for card in cards:
			notify("{} created {}.".format(me, card))


def resourcePhaseDraw():
	id = playerID(me)
	count = 1
	strcount = getGlobalVariable("cardsDrawn{}".format(id))
	if strcount:
		count=num(strcount)

	for i in range(count):
		draw(me.deck)

def adjustCardsDrawn(group=None, x=0, y=0):
	id = playerID(me)
	current = 1
	strcurrent = getGlobalVariable("cardsDrawn{}".format(id))
	if strcurrent:
		current=num(strcurrent)
	count = askInteger("How many cards do want to draw in the resource phase?", current)
	if count is None or count < 0: return
	setGlobalVariable("cardsDrawn{}".format(id), str(count))

def takeControlOfTargets(group=None, x=0, y=0):
	for c in table:
		if c.targetedBy == me:
			c.setController(me)
			c.target(False)

# The Woodland Realm / The Wizard's Quest Randomization
twqtwr = [
[["3b855783-5b90-4788-802e-e7c1e81461d8",1],["2be47628-65a9-4809-87aa-6251eb68b4bc",2],["473e56fe-31b8-4637-acdb-a72a7138237b",2]],
[["3360d53e-e01b-4d22-b2e3-4e1733a4896d",1],["60057e26-14f3-468c-ba70-4b14aea7d49a",2],["10e74386-4dad-42c1-8f29-bb9e35e044a2",2]],
[["9b01e317-82e5-4f19-9375-917607d54aed",2],["e00490c1-cab9-4f99-ad19-04f7b81e4077",1],["9adddbd0-458a-4810-b0db-502a5e125704",2]],
[["f939f43c-51b5-4d96-9a1e-86f606c7dcc6",3],["fc45fcc9-65b1-4c1f-ac9a-e392d86d93fd",1],["df24263d-f2f9-436c-a62f-4db50e09d283",1]],
[["14304a2f-f6f8-4f78-adc6-5ee35bc9a08e",3],["0daf7bcd-4719-48e6-948a-0230aa96d34c",1],["4cf56614-3155-4a84-85dc-74c6cef00ae3",1]],
[["abf880a9-117c-4c23-8a29-9a152f36c4e9",1],["c2237ebe-c98f-49b1-9e6e-1e33d39f815d",3],["76ceda47-fb5e-48de-8a6d-83feda48d197",1]],
[["c7f4c92b-e593-4c40-9ecb-64d8ab9c6368",2],["4d5a388c-d710-4663-ab96-a3a914da2a24",2],["9221e69b-0649-4585-9ee2-2dd2890531ea",1]],
[["888e1fe6-2fc4-407d-8bb3-df2c020e1e24",2],["4b9d24ad-1ae3-4e49-a675-a27fc84c289b",2],["1e7ccc5d-2f76-4295-add4-c06da3da1516",1]],
[["d97a8405-7c6b-4b27-a705-c165ab2c8977",2],["41928f89-4736-42f9-b789-9ea670d26639",2],["37f0bdca-11d8-40ba-97cd-bbe2b8190cd5",1]],
[["97ee3084-5379-47da-aab0-acd5d4a540af",2],["cbf2984f-cfb8-4cc3-9d5c-fdadd4201451",2],["a8870930-554e-4e94-9188-b454e2a1158a",1]],
[["7f03acd1-41d0-44db-9903-c6030e1548a1",2],["ef719fc5-dddd-4455-87de-96fe22e4ff1a",2],["dde0edf6-bc4d-4f21-8681-3e90098218db",1]],
[["34a6c6ed-1dff-4264-815c-367ff47e73a6",1],["6d012dfd-07bb-40d5-8da7-2e4d9bad9bcd",2],["69c3d8f9-750a-4903-be32-588898fd766e",2]],
[["34635348-ab17-4d00-bc6f-7ced07821168",1],["d2d31f2a-4b80-48b5-b92a-e42d254cfd49",2],["2b10aa08-31ac-4133-b613-f7fde8a2444c",2]],
[["a4e02843-7689-484e-8e58-0b869717aeba",1],["057a8676-b610-4806-aa86-edf9b03060e8",2],["83818038-5291-4d4b-acec-1937c5b787e0",2]],
[["9f29199a-f40a-4198-b355-4d5e75d910e2",1],["ad36bbe2-646e-4ac1-983b-e2d8a651dd0e",2],["60fe85d1-4dae-4c74-8776-424b4a306054",2]],
[["996158ae-41aa-457e-99c4-97640796d6e0",1],["678fe922-7c1f-4270-aaec-002d916fc52a",2],["826b71a9-3f90-454a-8009-24afa9a94ec8",2]],
[["2899ad24-ba7e-4c24-9d20-dabe8f4fce71",2],["a662bccc-025c-48dd-9c13-0eb47a91236c",1],["ad6a6843-b482-43a8-8d1f-771ac69c9ab5",2]],
[["d801e97a-0cb8-44f0-a28f-de9546200967",1],["14a944ab-8301-4006-8e2a-d607eb614fab",3],["15e06e00-8d82-4590-b2ae-6e615330d78a",1]],
[["a880b0ab-79d4-42b4-81b1-5ad9a8054c27",1],["e7100f6a-bdbd-4605-86e2-67d4479d227d",1],["764c89bc-d212-401f-acfa-a971cd0e5e17",2],["3f7b681f-f1c0-4771-8e7b-b6e804d0bf88",1]],
[["79a2b4c2-7d0c-41a5-aa5f-1ec29644caab",1],["1b036c00-55cc-4538-a659-6d86aaf8ce20",1],["e7a6c9c3-9d45-478c-81e5-7811d43deb0e",3]],
[["fd9398a9-9f4f-4134-875b-5527f3533c7d",3],["ac78aadc-9a58-42a6-a328-60dbb1e2191c",1],["e763a539-7fc8-49ab-8f8f-879070aa0e03",1]],
[["058c4067-9b8c-4631-ae6b-6cee784e71df",2],["008bcdb1-bac6-4c45-86c5-6bcfb0bf12cc",1],["85cf554d-25c5-47f4-96bb-c11f4e764155",2]],
[["90c7e192-2a1e-480c-96a2-7c643f0562d1",2],["0b215acb-56e1-4653-9cbf-38171c4af9c9",1],["88efb537-cea8-4c20-8b73-e51f0742f769",2]],
[["93e61cb5-2bde-420e-aebd-79a1c4111838",2],["6c456def-a38c-409c-a085-37f027e9c7b0",1],["59724478-f4c5-4f9b-99bd-288dd8fc1b43",2]],
[["05119d55-73f5-4973-ada5-d0cc73a2eb4b",1],["763643f4-fb17-43d0-a165-ae0b0b10bc46",2],["66391b37-52bb-4461-97e7-e24fd3aaa3d5",2]],
[["c37069a2-1a82-4a67-a08a-d79f5525c547",2],["2108c366-c09a-4952-9920-398f8d84b5a9",2],["2e005552-a0a2-4a70-bd96-9d1b21601261",1]],
[["5c4188a5-5767-4c8c-8dfd-0b3f7c55e4a1",2],["98fe6f91-977f-41a0-b7a4-a89d24836239",2],["5f2bf8db-d56f-4353-b9be-fd25b7b0650e",1]],
[["929a0f96-a029-4327-b8e5-03cb78293bdf",3],["f75180d3-29c9-4184-85ce-8b805b9aa8c6",1],["c4aea786-9987-451a-8924-e63c628be505",1]]
]

def randomSubset(set, n):
	subset = []
	while len(subset) < n:
		randn = rnd(0,len(set)-1)
		if set[randn] in subset: continue
		subset.append(set[randn])
	return subset


def random7Sets(setnums):
	for setnum in setnums:
		notify("Choosing set {}.".format(setnum+1))
		for guid in twqtwr[setnum]:
			encounterDeck().create(guid[0],guid[1])
	shuffle(encounterDeck())

def randomTWQEncounter(group=None, x=0, y=0):
	setnums = randomSubset(range(15,28), 7)
	random7Sets(setnums)


def randomTWREncounter(group=None, x=0, y=0):
	setnums = randomSubset(range(0,14), 7)
	random7Sets(setnums)

def randomTWQTWREncounter(group=None, x=0, y=0):
	setnums = randomSubset(range(0,28), 7)
	random7Sets(setnums)

def randomTWQQuest(group=None, x=0, y=0):
	oneA = "79666b89-ec7b-4bc8-98d9-9c517f8ca6ed"
	twoA = ["35d72889-370e-4ee3-99c0-b7d0a605ec49","4ce7c4e4-c96c-4ee7-ae98-cfb497303cd0","b446fa27-d5f8-40e0-8985-fe15478cd79b"]
	thrA = ["7d71a43e-a7ae-49bb-930c-437101a12d82","b717f5f9-cd1a-4852-aa1d-36acd1f8d3b1","85409c38-e188-46f7-b844-42716266ea83"]
	loc = "1a3c69f9-c973-4e4e-aa00-435c1f615393"

	questDeck().create(oneA)
	questDeck().create(twoA[rnd(0,2)],1)
	questDeck().create(thrA[rnd(0,2)],1)
	nextQuestStage()

	card = stagingSetupDeck().create(loc, 1)
	addToStagingArea(card)

def randomTWRQuest(group=None, x=0, y=0):
	oneA = "4fd47b8b-1132-4e90-967c-b15369215025"
	twoA = ["78689e20-d52f-4495-accc-b2cc39bb9ddc","a7280ef5-7a73-4c34-bc7e-e7aef7e4f3df","13e84f42-66ff-4abb-819d-a4b0ad088bb1"]
	thrA = ["2e4aea1e-abb5-48c6-9f83-abbf9b6bcf72","ba4f0abd-bd8c-4b25-b045-1599e5c92ce7","35924e07-9473-4701-855a-11f69dc83185"]
	loc = "35fb5564-b4a1-4730-9e4d-65bd2e6d43c4"

	questDeck().create(oneA)
	questDeck().create(twoA[rnd(0,2)],1)
	questDeck().create(thrA[rnd(0,2)],1)
	nextQuestStage()

	card = stagingSetupDeck().create(loc, 1)
	addToStagingArea(card)

def randomTWQTWRQuest(group=None, x=0, y=0):
	n = rnd(1,2)
	if n==1:
		randomTWQQuest()
	else:
		randomTWRQuest()

def drinkingSong(group):
	additionalCards = 0
	hobbitFound = '-'
	for card in table:
		if ('Hobbit' in card.Traits) and (card.Unique) and (card.controller == me):
			additionalCards = 1
			hobbitFound = card.Name
			break
	notify("Drinking Song - Found {} unique Hobbits: {}.".format(additionalCards, hobbitFound))
	exchangeCardsInHand(group, additionalCards)

def exchangeCardsInHand(group, additionalCards):
	mute()
	handsize = len(group)
	newHandSize = handsize + additionalCards
	for card in group:
		card.moveToBottom(me.deck)
	shuffle(me.deck)
	for card in me.deck.top(newHandSize):
		card.moveTo(me.hand)
	notify("{} draws {} new cards.".format(me, newHandSize))

def loadDeckFromRingsDB(group, x=0, y=0):
	notify("loadDeckFromRingsDB called successfully")

	url = askString("Please enter the URL of the deck you wish to load.", "")
        if url == None: # cancelled
		return

	if re.match("^https://(www\.)?ringsdb\.com/decklist/view/", url) != None:
		deckid = url.split("/view/")[1].split("/")[0]
		data, code = webRead("https://ringsdb.com/decklist/export/octgn/{}".format(deckid))
	elif re.match("^https://(www\.)?ringsdb\.com/deck/view/", url) != None:
		deckid = url.split("/view/")[1].split("/")[0]
		data, code = webRead("https://ringsdb.com/deck/export/octgn/{}".format(deckid))
        else:
		notify("Error: Invalid RingsDB Deck URL - should look like https://ringsdb.com/*/view/*")
		return

	if code != 200:
		notify("""Error retrieving online deck data, please try again. You may need to enable
'Share my decks' in your RingsDB account if this was a /deck/view/ URL""")
		return

	doc = XmlDocument()
	doc.LoadXml(data)

	# start off by validating the basic structure of the XML - xml node and game node
	if (doc.ChildNodes.Count != 2 or doc.ChildNodes[0].Name != "xml" or
		doc.ChildNodes[1].Name != "deck" or doc.ChildNodes[1].Attributes["game"] == None or
		doc.ChildNodes[1].Attributes["game"].Value != "a21af4e8-be4b-4cda-a6b6-534f9717391f"):
		notify("Illegal XML in OCTGN export")
	else:
		sections = doc.ChildNodes[1].ChildNodes

                # the below is pretty pedantic about checking for well-formed OCTGN exports. I wanted
                # it to be as bulletproof as possible, but that means that if OCTGN export formats change
                # much, this code will likely need to change as well
		for section in sections:
			if section.Name == "section":
				name_attr = section.Attributes["name"]

				if name_attr != None:
					for card in section.ChildNodes:
						if (card.Name == "card" and card.Attributes["qty"] != None and
							card.Attributes["id"] != None and
							re.match("^[0-9]+$", card.Attributes["qty"].Value) != None):

							id = card.Attributes["id"].Value
							qty = int(card.Attributes["qty"].Value)

							# heroes get loaded into hand (based on definition.xml)
							if name_attr.Value == "Hero":
								me.hand.create(id, qty)
							# sideboard cards get loaded as such
							elif name_attr.Value == "Sideboard":
								me.piles['Sideboard'].create(id, qty)
							# other cards get loaded into the discard pile
							else:
								me.piles['Discard Pile'].create(id, qty)

		# call this so that it appears that this was "loaded" from the menu bar items
                Arguments = namedtuple('Arguments', 'player groups')
                args = Arguments(me, [ me.hand, me.piles['Discard Pile'] ])
		deckLoaded(args)
