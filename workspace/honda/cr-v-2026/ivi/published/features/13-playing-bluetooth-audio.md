<!-- GENERATED:START function=bfae0f3ebe54 (generated; edits inside this block are overwritten by the next publish — write your own notes outside it) -->
# 13. Playing Bluetooth® Audio

<div class="fn-meta"><b>Function path:</b> Features / Playing Bluetooth® Audio<br><b>Source:</b> printed page 273, 274, 275<br><b>Test-ready:</b> <span class="test-ready-no">no — procedure missing or thresholds unfilled</span></div>

<p class="fn-disclaimer">Every "Presumed requirement" row below is machine-derived from the Owner's Manual text by rule-based extraction — not AI-written — and traceable to the printed page in its Source column.</p>

## Figures (areas of the original PDF; the OM has no figure numbers or captions)
![figure](../figures/FIG-0b8defe3f7bb.png)
- Figure 13-1 source: p.273
- (Copied from OM) Shuffle Icon


## Procedure (2 sequences; the manual restarts the numbering)
```mermaid
flowchart TD
    subgraph SEQ1["Sequence 1"]
    direction TB
    S1_1["1. Make sure that your phone is paired and connected to HFL."]
    S1_2["2. Select Audio Source and then Bluetooth Audio."]
    S1_1 --> S1_2
    end
    subgraph SEQ2["Sequence 2"]
    direction TB
    S2_1["1. Select Music Library."]
    S2_2["2. Select a search category (e.g., Albums)."]
    S2_3["3. Select an item."]
    S2_1 --> S2_2
    S2_2 --> S2_3
    end
```

| Seq | Step | Operation (Copied from OM) | Source |
|---|---|---|---|
| 1 | 1 | Make sure that your phone is paired and connected to HFL. | p.274 / step |
| 1 | 2 | Select Audio Source and then Bluetooth Audio. | p.274 / step |
| 2 | 1 | Select Music Library. | p.274 / step |
| 2 | 2 | Select a search category (e.g., Albums). | p.274 / step |
| 2 | 3 | Select an item. | p.274 / step |

## Numeric thresholds (filled in by a tester)
Filled: 0 / unfilled: 2

| Threshold | Matching text (Copied from OM) | Kind | Unit | Value | Status | Evidence | Filled by |
|---|---|---|---|---|---|---|---|
| f552b01f7910 | repeatedly until | count | times | **unfilled** | unfilled | — | — |
| 6136d616e7c2 | Repeatedly select shuffle or repeat icon until | count | times | **unfilled** | unfilled | — | — |

## 13-2-1. Service overview

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Playing Bluetooth® Audio</span>Your audio system allows you to listen to music from your Bluetooth-compatible phone. This function is available when the phone is paired and connected to the vehicle’s Bluetooth® HandsFreeLink® (HFL) system. 2 Phone Setup P.315. | constraint | p.273 / text |
| 2 | <span class="req-label">Playing Bluetooth® Audio</span>Repeat Icon Select to repeat the current track. | capability | p.273 / text |
| 3 | <span class="req-label">Playing Bluetooth® Audio</span>1Playing Bluetooth® Audio Not all Bluetooth-enabled phones with streaming audio capabilities are compatible with the system. For a list of compatible phones:. | capability | p.273 / text |

## 13-2-2. Service requirements

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>U.S.: Visit https://mygarage.honda.com/s/hondahandsfreelink-compatibility-check, or call 1-888- 528-7876. | capability | p.273 / bullet |
| 2 | <span class="req-label">Step -</span>Canada: Call 1-855-490-7351. Audio/Information Screen. | capability | p.273 / bullet |
| 3 | <span class="req-label">Playing Bluetooth® Audio</span>In some states, it may be illegal to perform some data Bluetooth Indicator device functions while driving. Appears when your phone is connected to HFL. Only one phone can be used with HFL at a time. When there is more than one paired phone in the vehicle, the system automatically connects to the prioritized phone. You can assign priority to a phone Music Library Icon in the Priority Device menu. Select to display the 2 HFL Menus P.313 music search screen. | constraint | p.273 / text |
| 4 | <span class="req-label">Playing Bluetooth® Audio</span>Play/Pause Icon. | capability | p.273 / text |
| 5 | <span class="req-label">Playing Bluetooth® Audio</span>To Play Bluetooth® Audio Files. | capability | p.274 / text |
| 6 | <span class="req-label">Playing Bluetooth® Audio</span>If the phone is not recognized, another HFL-compatible phone, which is not compatible for Bluetooth® Audio, may already be connected. | capability | p.274 / text |
| 7 | <span class="req-label">Playing Bluetooth® Audio</span>To pause or resume a file. | capability | p.274 / text |
| 8 | <span class="req-label">Playing Bluetooth® Audio</span>Select the play/pause icon. | capability | p.274 / text |
| 9 | <span class="req-label">Playing Bluetooth® Audio</span>How to Select a Song from the Music Search List. | capability | p.274 / text |
| 10 | <span class="req-label">Step -</span>Select an item repeatedly until a desired item you want to listen to is displayed. | capability | p.274 / bullet |
| 11 | <span class="req-label">Playing Bluetooth® Audio</span>1To Play Bluetooth® Audio Files To play the audio files, you may need to operate your phone. If so, follow the phone manufacturer's operating instructions. | constraint | p.274 / text |
| 12 | <span class="req-label">Playing Bluetooth® Audio</span>Switching to another mode pauses the music playing from your phone. | capability | p.274 / text |
| 13 | <span class="req-label">Playing Bluetooth® Audio</span>If any audio device is connected to the USB port, you may need to select Audio Source to select Bluetooth Audio. | capability | p.274 / text |
| 14 | <span class="req-label">Playing Bluetooth® Audio</span>You can change the connected phone by selecting Change Devices. 2 Phone Setup P.315. | capability | p.274 / text |
| 15 | <span class="req-label">Playing Bluetooth® Audio</span>How to Select a Play Mode. | capability | p.275 / text |
| 16 | <span class="req-label">Playing Bluetooth® Audio</span>You can select repeat and shuffle modes when playing a song. | constraint | p.275 / text |
| 17 | <span class="req-label">Playing Bluetooth® Audio</span>Shuffle/Repeat. | capability | p.275 / text |
| 18 | <span class="req-label">Playing Bluetooth® Audio</span>Play Mode Menu Items Shuffle Shuffle off: Shuffle mode to off. Shuffle All Songs: Plays all available songs in a selected list in random order. | capability | p.275 / text |
| 19 | <span class="req-label">Playing Bluetooth® Audio</span>Repeat Repeat off: Repeat mode to off. Repeat all: Repeats all songs. Repeat Song: Repeats the current song. | capability | p.275 / text |

## 13-4. User settings

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Playing Bluetooth® Audio</span>Repeatedly select shuffle or repeat icon until you find a play mode option of your preference. | capability | p.275 / text |

## 13-5. Exception operation

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Playing Bluetooth® Audio</span>Track Icons If a phone is currently connected via Apple CarPlay or or to Select Android Auto, Bluetooth® Audio from that phone is change track. unavailable. 2 Phone Setup P.315 Shuffle Icon Select to play all tracks in the current category in random order. | constraint | p.273 / text |
| 2 | <span class="req-label">Playing Bluetooth® Audio</span>1How to Select a Song from the Music Search List Depending on the Bluetooth® device you connect, some or all of the categories may not be displayed. | capability | p.274 / text |
| 3 | <span class="req-label">Playing Bluetooth® Audio</span>1How to Select a Play Mode Depending on the Bluetooth® device you connect, some or all of the functions may not be displayed. | capability | p.275 / text |
<!-- GENERATED:END function=bfae0f3ebe54 -->








