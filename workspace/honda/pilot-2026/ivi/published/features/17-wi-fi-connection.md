<!-- GENERATED:START function=cb52882e923b (generated; edits inside this block are overwritten by the next publish — write your own notes outside it) -->
# 17. Wi-Fi Connection

<div class="fn-meta"><b>Function path:</b> Audio System Basic Operation / Wi-Fi Connection<br><b>Source:</b> printed page 306, 307<br><b>Test-ready:</b> <span class="test-ready-yes">yes — no unfilled thresholds and a procedure is present</span></div>

<p class="fn-disclaimer">Every "Presumed requirement" row below is machine-derived from the Owner's Manual text by rule-based extraction — not AI-written — and traceable to the printed page in its Source column.</p>

## Procedure (2 sequences; the manual restarts the numbering)
```mermaid
flowchart TD
    subgraph SEQ1["Sequence 1"]
    direction TB
    S1_1["1. Select Home."]
    S1_2["2. Select General Settings."]
    S1_3["3. Select Connections."]
    S1_4["4. Select Wi-Fi."]
    S1_5["5. Select the access point you want to connect to the syste…"]
    S1_6["6. Select Connect."]
    S1_7["7. Select Home to go back to the home screen."]
    S1_1 --> S1_2
    S1_2 --> S1_3
    S1_3 --> S1_4
    S1_4 --> S1_5
    S1_5 --> S1_6
    S1_6 --> S1_7
    end
    subgraph SEQ2["Sequence 2"]
    direction TB
    S2_1["1. Select Home."]
    S2_2["2. Select General Settings."]
    S2_3["3. Select Connections."]
    S2_4["4. Select Data Connection Options."]
    S2_5["5. Select Set Up Wi-Fi."]
    S2_6["6. Select Options."]
    S2_7["7. Select Add Network."]
    S2_1 --> S2_2
    S2_2 --> S2_3
    S2_3 --> S2_4
    S2_4 --> S2_5
    S2_5 --> S2_6
    S2_6 --> S2_7
    end
```

| Seq | Step | Operation (Copied from OM) | Source |
|---|---|---|---|
| 1 | 1 | Select Home. | p.306 / step |
| 1 | 2 | Select General Settings. | p.306 / step |
| 1 | 3 | Select Connections. | p.306 / step |
| 1 | 4 | Select Wi-Fi. | p.306 / step |
| 1 | 5 | Select the access point you want to connect to the system. | p.306 / step |
| 1 | 6 | Select Connect. | p.306 / step |
| 1 | 7 | Select Home to go back to the home screen. | p.306 / step |
| 2 | 1 | Select Home. | p.307 / step |
| 2 | 2 | Select General Settings. | p.307 / step |
| 2 | 3 | Select Connections. | p.307 / step |
| 2 | 4 | Select Data Connection Options. | p.307 / step |
| 2 | 5 | Select Set Up Wi-Fi. | p.307 / step |
| 2 | 6 | Select Options. | p.307 / step |
| 2 | 7 | Select Add Network. | p.307 / step |

## 17-2-1. Service overview

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Wi-Fi Connection</span>Wi-Fi Connection. | capability | p.306 / text |
| 2 | <span class="req-label">Wi-Fi Connection</span>This vehicle is equipped with Wi-Fi connectivity. You can connect to an external Wi- 1Wi-Fi Connection Fi hotspot or communication device. In addition, the vehicle can be used by other communication devices as a Wi-Fi hotspot via the telematics unit (TCU). | capability | p.306 / text |

## 17-2-2. Service requirements

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>Connect the vehicle to a Wi-Fi hotspot. | capability | p.306 / bullet |
| 2 | <span class="req-label">Step -</span>Use Wi-Fi inside the vehicle. | capability | p.306 / bullet |
| 3 | <span class="req-label">Wi-Fi Connection</span>Connect the vehicle to a Wi-Fi hotspot. | capability | p.306 / text |
| 4 | <span class="req-label">Step -</span>To change the Wi-Fi settings, select Options. | capability | p.306 / bullet |
| 5 | <span class="req-label">Step -</span>When the connection is successful, the status text Connected next to the network name is displayed on the list. | capability | p.306 / bullet |
| 6 | <span class="req-label">Wi-Fi Connection</span>Wi-Fi and Wi-Fi Direct are registered trademarks of Wi-Fi Alliance®. | capability | p.306 / text |
| 7 | <span class="req-label">Wi-Fi Connection</span>Some cell phone carriers charge for tethering and smartphone data use. Check your phone’s data subscription package. | capability | p.306 / text |
| 8 | <span class="req-label">Wi-Fi Connection</span>Check your phone manual to find out if the phone has Wi-Fi connectivity. | constraint | p.306 / text |
| 9 | <span class="req-label">Wi-Fi Connection</span>You can confirm whether Wi-Fi connection is on or off with the icon on the Wi-Fi network list. Transmission speed and others will not be displayed on this screen. | capability | p.306 / text |
| 10 | <span class="req-label">Wi-Fi Connection</span>In case of Wi-Fi connection with your phone, make sure your phone’s Wi-Fi setting is in access point (tethering) mode. | capability | p.306 / text |
| 11 | <span class="req-label">Wi-Fi Connection</span>Use Wi-Fi inside the vehicle. | capability | p.307 / text |
| 12 | <span class="req-label">Wi-Fi Connection</span>You can set the network as a Wi-Fi hotspot of this audio system. Use the following steps to set up. | capability | p.307 / text |
| 13 | <span class="req-label">Wi-Fi Connection</span>The following options are available for the setup. | capability | p.307 / text |
| 14 | <span class="req-label">Step -</span>Network SSID: Set this network name. | capability | p.307 / bullet |
| 15 | <span class="req-label">Step -</span>Security: Set a password to be required when connecting a Wi-Fi device to this network. | constraint | p.307 / bullet |

## 17-4. User settings

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Wi-Fi Connection</span>When you select Access Point, you can set up a wireless connection from the phone to the vehicle. 2 Customized Features P.346. | capability | p.306 / text |

## 17-5. Exception operation

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Wi-Fi Connection</span>1Connect the vehicle to a Wi-Fi hotspot You cannot go through the setting procedure while the vehicle is moving. Park in a safe place to set the audio system in Wi-Fi mode. | constraint | p.306 / text |
<!-- GENERATED:END function=cb52882e923b -->








