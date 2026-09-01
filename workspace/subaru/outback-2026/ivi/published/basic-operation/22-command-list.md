<!-- GENERATED:START function=1f76c1dbfa2c (generated; edits inside this block are overwritten by the next publish — write your own notes outside it) -->
# 22. Command list

<div class="fn-meta"><b>Function path:</b> Basic operation / Command list<br><b>Source:</b> printed page 34, 35, 36, 37, 38<br><b>Test-ready:</b> <span class="test-ready-no">no — procedure missing or thresholds unfilled</span></div>

<p class="fn-disclaimer">Every "Presumed requirement" row below is machine-derived from the Owner's Manual text by rule-based extraction — not AI-written — and traceable to the printed page in its Source column.</p>

## 22-2-1. Service overview

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Command list</span>Recognizable voice commands and their actions are shown below. | capability | p.34 / text |

## 22-2-2. Service requirements

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>Frequently used commands are listed in the following tables. | capability | p.34 / bullet |
| 2 | <span class="req-label">Step -</span>The functions available may vary according to the system installed. | capability | p.34 / bullet |
| 3 | <span class="req-label">Step -</span>If the system language is changed on the display settings screen, the language of the voice assistance function will also change. Refer to the vehicle Owner’s Manual for details. | capability | p.34 / bullet |
| 4 | <span class="req-label">Step -</span>&lt;○○○&gt; descriptions in the command lists below signify numbers/titles/names to be spoken. | capability | p.34 / bullet |
| 5 | <span class="req-label">Command list</span>Phone commands. | capability | p.35 / text |
| 6 | <span class="req-label">Command list</span>*: When speaking the name of registered points, be sure to say it as it is registered. | constraint | p.36 / text |
| 7 | <span class="req-label">Command list</span>Music commands. | capability | p.36 / text |
| 8 | <span class="req-label">Command list</span>Climate commands. | capability | p.37 / text |
| 9 | <span class="req-label">Command list</span>*: If equipped. | constraint | p.38 / text |
| 10 | <span class="req-label">Command list</span>Apps commands. | capability | p.38 / text |
| 11 | <span class="req-label">Command list</span>Vehicle commands. | capability | p.38 / text |

## 22-3. Requirements for HMI

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Command list</span>Voice command Function Places a call to the spoken contact name and phone type of the “Call a Contact” contact from the phonebook Places a call to the spoken contact name and phone type of the “Call &lt;Name&gt; &lt;Phone Type&gt;” contact from the phonebook “Pair Phone” Displays manage devices screen Sends the preset message to the spoken contact name and 1 “Send a Text to Contact” phone type of the contact from the phonebook “Dial a Number” Places a call to the spoken phone number “Dial &lt;Number&gt;” Places a call to the spoken phone number “Call Back” Places a call to the phone number of the latest incoming call “Redial” Places a call to the phone number of the latest outgoing call “Show Messages” Displays received text messages “Show Recent Calls” Displays the call history screen “Send a Text to &lt;Number&gt;” Sends a text message to the spoken phone number “Send a Text to Recent Call” Sends a text message by the recent call list “Send a Text to &lt;Name&gt; Sends a text message to the spoken contact name and phone &lt;Phone Type&gt;” type of the contact from the phonebook. | capability | p.35 / text |
| 2 | <span class="req-label">Command list</span>Navigation commands* *: If equipped Voice command Function Enables setting a destination by saying the address with city and “Enter an Address” state Enables setting a destination by saying the address with city and “Navigate to &lt;Address&gt;” state “Find &lt;POI&gt;” Displays a list of POI category near the current position “Go Home” Displays the route to home “Go to Work” Displays the route to work “Cancel Route” Cancels route guidance “Navigate to Favorite” Displays the favorite location “Navigate to Favorite &lt;Favor- Displays the favorite location ite Name&gt;”* “Previous Destination” Displays the previous destinations “Delete Destination” Cancels route guidance “Show Map” Displays the map screen. | constraint | p.35 / text |
| 3 | <span class="req-label">Command list</span>Voice command Function “Find &lt;POI&gt; in a City” Displays a list of POI category near the current position “Change Country to &lt;Coun- Changes a country try&gt;” Enables setting a destination by saying three words hit by “Navigate to What3words” “what3words” search. | capability | p.36 / text |
| 4 | <span class="req-label">Command list</span>Voice command Function “Turn on the Music” Turns music on “Turn off the Music” Turns music off “Play Song &lt;Name&gt;” Plays the selected song “Play Artist &lt;Name&gt;” Plays tracks from the selected artist “Play Playlist &lt;Name&gt;” Plays tracks from the selected playlist “Turn on FM” Switches to FM radio “Turn on AM” Switches to AM radio “Tune to satellite radio” Switches to satellite radio “Radio Frequency” Tunes radio frequency “Tune to a Preset” Selects a preset “Channel &lt;Name&gt;” Switches to a selected satellite radio channel “Play Album &lt;Name&gt;” Plays tracks from the selected album “Browse Artist &lt;Name&gt;” Displays the list of albums of the artist “Browse Playlist &lt;Name&gt;” Displays the list of playlist “Browse Songs” Displays the list of songs “Play USB” Switches source to USB “Play Bluetooth” Switches source to Bluetooth audio “Tune to &lt;Frequency&gt; AM” Tunes AM radio frequency “Tune to &lt;Frequency&gt; FM” Tunes FM radio frequency “Tune to FM &lt;Frequency&gt; HD Tunes FM radio frequency &lt;Subchannel&gt;” “Listen to a Radio Genre - FM Selects a radio genre Radio -” “Listen to a Radio Genre Selects a radio genre &lt;Genre&gt;” “Tune to Preset &lt;Number&gt;” Selects a preset “Tune to Channel Number” Selects a satellite radio channel. | capability | p.36 / text |
| 5 | <span class="req-label">Command list</span>Voice command Function “Tune to Channel Number Selects a satellite radio channel &lt;Number&gt;”. | capability | p.37 / text |
| 6 | <span class="req-label">Command list</span>Voice command Function 1 “Auto AC On” Switches on the auto AC mode on “Increase Temperature the Increases the temperature the driver side Driver Side” “Increase Temperature the Increases the temperature the passenger side Passenger Side” “Decrease temperature the Decreases the temperature the driver side Driver Side” “Decrease temperature the Decreases the temperature the passenger side Passenger Side” “Increase the Fan Speed” Increases the fan speed “Decrease the Fan Speed” Decreases the fan speed “Set Driver Side Temperature Sets the driver side temperature to the spoken temperature to &lt;Temperature&gt;” “Set Passenger Side Tem- Sets the passenger side temperature to the spoken temperature perature to &lt;Temperature&gt;” “Change Driver Side Tempera- Sets the driver side temperature to the spoken temperature ture” “Change Passenger Side Sets the passenger side temperature to the spoken temperature Temperature” “Fan Speed” Sets the fan speed to the spoken fan speed “Turn on Driver Heated Seat” Turns the driver seat heater on “Turn on Passenger Heated Turns the passenger seat heater on Seat” “Turn off Driver Heated Seat” Turns the driver seat heater off “Turn off Passenger Heated Turns the passenger seat heater off Seat” “Set Driver Heated Seat to Sets the level of the driver seat heater intensity &lt;High - Low&gt;” “Set Passenger Heated Seat Sets the level of the passenger seat heater intensity to &lt;High - Low&gt;” “Turn on Driver Ventilated Turns the driver seat ventilator on Seat”*. | capability | p.37 / text |
| 7 | <span class="req-label">Command list</span>Voice command Function “Turn on Passenger Venti- Turns the passenger seat ventilator on lated Seat”* “Turn off Driver Ventilated Turns the driver seat ventilator off Seat”* “Turn off Passenger Venti- Turns the passenger seat ventilator off lated Seat”* “Set Driver Ventilated Seat to Sets the level of the driver seat ventilator intensity &lt;High - Low&gt;”* “Set Passenger Ventilated Sets the level of the passenger seat ventilator intensity Seat to &lt;High - Low&gt;”*. | capability | p.38 / text |
| 8 | <span class="req-label">Command list</span>Voice command Function “Launch &lt;App Name&gt;” Changes screen to selected application “Go to CarPlay” Changes screen to Apple CarPlay “Go to Android Auto” Changes screen to Android Auto. | capability | p.38 / text |
| 9 | <span class="req-label">Command list</span>Voice command Function “Lane Departure Options” Changes the settings of the Lane Departure function “Cruise Control Options” Changes the settings of the Cruise Control function. | capability | p.38 / text |

## 22-5. Exception operation

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>For devices that are not installed in the vehicle, the related commands will not be displayed in the screen. Also, according to conditions, other commands may not be displayed in the screen. | capability | p.34 / bullet |
<!-- GENERATED:END function=1f76c1dbfa2c -->







