<!-- GENERATED:START function=ed6bea1285ce (generated; edits inside this block are overwritten by the next publish — write your own notes outside it) -->
# 21. Limitations Of The Navigation System

<div class="fn-meta"><b>Function path:</b> Navigation System (If equipped) / Limitations Of The Navigation System<br><b>Source:</b> printed page 221, 222<br><b>Test-ready:</b> <span class="test-ready-no">no — procedure missing or thresholds unfilled</span></div>

<p class="fn-disclaimer">Every "Presumed requirement" row below is machine-derived from the Owner's Manual text by rule-based extraction — not AI-written — and traceable to the printed page in its Source column.</p>

## Numeric thresholds (filled in by a tester)
Filled: 1 / unfilled: 3

| Threshold | Matching text (Copied from OM) | Kind | Unit | Value | Status | Evidence | Filled by |
|---|---|---|---|---|---|---|---|
| 99e4c6901789 | a few seconds | duration | seconds | **unfilled** | unfilled | — | — |
| 236284653a08 | a certain level of inaccuracy | quantity | as stated | 100 m | from_manual | Stated in the OM: "100 m" | — |
| 7f5b88cd5a44 | high speed | speed | speed | **unfilled** | unfilled | — | — |
| 59429d5bddf1 | high speed | speed | speed | **unfilled** | unfilled | — | — |

## 21-2-1. Service overview

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Limitations Of The Navigation System</span>This navigation system calculates the current position using satellite signals, various vehicle signals, map data, etc. However, an accurate position may not be shown depending on satellite conditions, road configuration, vehicle condition or other circumstances. | capability | p.221 / text |
| 2 | <span class="req-label">Limitations Of The Navigation System</span>The Global Positioning System (GPS) developed and operated by the U.S. Department of Defense provides an accurate current position, normally using 4 or more satellites, and in some case 3 satellites. The GPS system has a certain level of inaccuracy. While the navigation system compensates for this most of the time, occasional positioning errors of up to 300 feet (100 m) can and should be expected. Generally, position errors will be corrected within a few seconds. The GPS signal may be physically obstructed, leading to inaccurate vehicle position on the map screen. Tunnels, tall buildings, trucks, or even the placement of objects on the instrument panel may obstruct the GPS signals. The GPS satellites may not send signals due to repairs or improvements being made to them. Even when the navigation system is receiving clear GPS signals, the vehicle position may not be shown accurately or inappropriate route guidance may occur in some cases. | constraint | p.221 / text |
| 3 | <span class="req-label">Limitations Of The Navigation System</span>l The installation of window tinting may obstruct the GPS signals. Most window tinting contains some metallic content that will interfere with GPS signal reception of the antenna in the instrument panel. We advise against the use of window tinting on vehicles equipped with navigation systems. | capability | p.221 / text |
| 4 | <span class="req-label">Limitations Of The Navigation System</span>following cases:. | capability | p.222 / text |

## 21-2-2. Service requirements

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>When driving on a small angled Y-shaped road. | capability | p.222 / bullet |
| 2 | <span class="req-label">Step -</span>When driving on a winding road. | capability | p.222 / bullet |
| 3 | <span class="req-label">Step -</span>When driving on a slippery road such as in sand, gravel, snow, etc. | capability | p.222 / bullet |
| 4 | <span class="req-label">Step -</span>When driving on a long straight road. | capability | p.222 / bullet |
| 5 | <span class="req-label">Step -</span>When freeway and surface streets run in parallel. | capability | p.222 / bullet |
| 6 | <span class="req-label">Step -</span>After moving by ferry or vehicle carrier. | capability | p.222 / bullet |
| 7 | <span class="req-label">Step -</span>When a long route is searched during high speed driving. | capability | p.222 / bullet |
| 8 | <span class="req-label">Step -</span>After repeating a change of direction by going forward and backward, or turning on a turntable in a parking lot. | capability | p.222 / bullet |
| 9 | <span class="req-label">Step -</span>When leaving a covered parking lot or parking garage. | capability | p.222 / bullet |
| 10 | <span class="req-label">Step -</span>When a roof carrier is installed. | capability | p.222 / bullet |
| 11 | <span class="req-label">Step -</span>When driving with tire chains installed. | capability | p.222 / bullet |
| 12 | <span class="req-label">Step -</span>When the tires are worn. | capability | p.222 / bullet |
| 13 | <span class="req-label">Step -</span>After replacing a tire or tires. | capability | p.222 / bullet |
| 14 | <span class="req-label">Step -</span>When using tires that are smaller or larger than the factory specifications. | capability | p.222 / bullet |
| 15 | <span class="req-label">Step -</span>When the tire pressure in any of the 4 tires is not correct. | capability | p.222 / bullet |
| 16 | <span class="req-label">Step -</span>When turning at an intersection off the designated route guidance. | capability | p.222 / bullet |
| 17 | <span class="req-label">Step -</span>If you set more than 1 destination but skip any of them, auto reroute will display a route returning to the destination on the previous route. | capability | p.222 / bullet |
| 18 | <span class="req-label">Step -</span>When turning at an intersection for which there is no route guidance. | capability | p.222 / bullet |
| 19 | <span class="req-label">Step -</span>When passing through an intersection for which there is no route guidance. | capability | p.222 / bullet |
| 20 | <span class="req-label">Step -</span>During high speed driving, it may take a long time for auto reroute to operate. In auto reroute, a detour route may be shown. | capability | p.222 / bullet |
| 21 | <span class="req-label">Step -</span>If an unnecessary U-turn is shown or announced. | capability | p.222 / bullet |
| 22 | <span class="req-label">Step -</span>If a location has multiple names and the system announces 1 or more of them. | capability | p.222 / bullet |
| 23 | <span class="req-label">Step -</span>Your destination point might be shown on the opposite side of the street. | capability | p.222 / bullet |

## 21-5. Exception operation

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>During auto reroute, the route guidance may not be available for the next turn to the right or left. | capability | p.222 / bullet |
| 2 | <span class="req-label">Step -</span>After auto reroute, the route may not be changed. | capability | p.222 / bullet |
| 3 | <span class="req-label">Step -</span>When a route cannot be searched. | constraint | p.222 / bullet |
| 4 | <span class="req-label">Step -</span>If the route to your destination includes gravel, unpaved roads or alleys, the route guidance may not be shown. | capability | p.222 / bullet |
<!-- GENERATED:END function=ed6bea1285ce -->






