<!-- GENERATED:START function=35b7539e28da (generated; edits inside this block are overwritten by the next publish — write your own notes outside it) -->
# 11. Playing AM/FM Radio

<div class="fn-meta"><b>Function path:</b> Audio System Basic Operation / Playing AM/FM Radio<br><b>Source:</b> printed page 287, 288, 289, 290<br><b>Test-ready:</b> <span class="test-ready-yes">yes — no unfilled thresholds and a procedure is present</span></div>

<p class="fn-disclaimer">Every "Presumed requirement" row below is machine-derived from the Owner's Manual text by rule-based extraction — not AI-written — and traceable to the printed page in its Source column.</p>

## Figures (areas of the original PDF; the OM has no figure numbers or captions)
![figure](../figures/FIG-7fb40ab4b23f.png)
- Figure 11-1 source: p.287
- (Copied from OM) Audio/Information Screen

## Procedure (7 sequences; the manual restarts the numbering)
```mermaid
flowchart TD
    subgraph SEQ1["Sequence 1"]
    direction TB
    S1_1["1. Tune to the selected station."]
    S1_2["2. Select and hold Press & Hold to Add."]
    S1_1 --> S1_2
    end
    subgraph SEQ2["Sequence 2"]
    direction TB
    S2_1["1. Select Station List to display a list."]
    S2_2["2. Select the station."]
    S2_1 --> S2_2
    end
    subgraph SEQ3["Sequence 3"]
    direction TB
    S3_1["1. Select Station List to display a list."]
    S3_2["2. Select Refresh."]
    S3_1 --> S3_2
    end
    subgraph SEQ4["Sequence 4"]
    direction TB
    S4_1["1. Select Station List to display a list while listening to…"]
    S4_2["2. Select the station."]
    S4_1 --> S4_2
    end
    subgraph SEQ5["Sequence 5"]
    direction TB
    S5_1["1. Select Station List to display a list while listening to…"]
    S5_2["2. Select Refresh."]
    S5_1 --> S5_2
    end
    subgraph SEQ6["Sequence 6"]
    direction TB
    S6_1["1. Select Station List."]
    S6_2["2. Select the channel number."]
    S6_1 --> S6_2
    end
    subgraph SEQ7["Sequence 7"]
    direction TB
    S7_1["1. Select Menu."]
    S7_2["2. Select an option."]
    S7_1 --> S7_2
    end
```

| Seq | Step | Operation (Copied from OM) | Source |
|---|---|---|---|
| 1 | 1 | Tune to the selected station. | p.288 / step |
| 1 | 2 | Select and hold Press &amp; Hold to Add. | p.288 / step |
| 2 | 1 | Select Station List to display a list. | p.288 / step |
| 2 | 2 | Select the station. | p.288 / step |
| 3 | 1 | Select Station List to display a list. | p.288 / step |
| 3 | 2 | Select Refresh. | p.288 / step |
| 4 | 1 | Select Station List to display a list while listening to an FM station. | p.289 / step |
| 4 | 2 | Select the station. | p.289 / step |
| 5 | 1 | Select Station List to display a list while listening to an FM station. | p.289 / step |
| 5 | 2 | Select Refresh. | p.289 / step |
| 6 | 1 | Select Station List. | p.290 / step |
| 6 | 2 | Select the channel number. | p.290 / step |
| 7 | 1 | Select Menu. | p.290 / step |
| 7 | 2 | Select an option. | p.290 / step |

## Numeric thresholds (filled in by a tester)
Filled: 1 / unfilled: 0

| Threshold | Matching text (Copied from OM) | Kind | Unit | Value | Status | Evidence | Filled by |
|---|---|---|---|---|---|---|---|
| f6e829c5d602 | for 10 seconds | duration | seconds | 10 | from_manual | Stated in the OM: "10" | — |

## 11-2-1. Service overview

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Playing AM/FM Radio</span>Playing AM/FM Radio. | capability | p.287 / text |
| 2 | <span class="req-label">Playing AM/FM Radio</span>Icon Select to display the subchannel list screen. | capability | p.287 / text |
| 3 | <span class="req-label">Playing AM/FM Radio</span>Tune Icon Select to use the on-screen keyboard for entering the radio frequency directly. | capability | p.287 / text |
| 4 | <span class="req-label">Playing AM/FM Radio</span>Seek Icons Select or to search up and down on the selected band for a station with a strong signal. | capability | p.287 / text |
| 5 | <span class="req-label">Playing AM/FM Radio</span>Audio/Information Screen. | capability | p.287 / text |
| 6 | <span class="req-label">Playing AM/FM Radio</span>Scan Icon Select to scan each station with a strong signal. | capability | p.287 / text |
| 7 | <span class="req-label">Playing AM/FM Radio</span>Menu Select to display the menu screen. | capability | p.287 / text |
| 8 | <span class="req-label">Playing AM/FM Radio</span>Station List Select to display the station list screen. | capability | p.287 / text |
| 9 | <span class="req-label">Playing AM/FM Radio</span>Favorite Station Icons, Add Favorite Tune the radio frequency for a favorite station. Press and hold + Press &amp; Hold to Add to store the station. Swipe left or right on the screen to move to the next or previous favorite station list. | capability | p.287 / text |
| 10 | <span class="req-label">Playing AM/FM Radio</span>Favorite Station. | capability | p.288 / text |
| 11 | <span class="req-label">Playing AM/FM Radio</span>To add a station:. | capability | p.288 / text |
| 12 | <span class="req-label">Playing AM/FM Radio</span>Editing a favorite station. | capability | p.288 / text |
| 13 | <span class="req-label">Playing AM/FM Radio</span>Select and hold the desired favorite station icon. The following items are available:. | capability | p.288 / text |

## 11-2-2. Service requirements

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>Remove Favorite: Delete the favorite station icon from the favorite station list. | capability | p.288 / bullet |
| 2 | <span class="req-label">Step -</span>Replace with (number): Replace the stored favorite station icon. | capability | p.288 / bullet |
| 3 | <span class="req-label">Step -</span>Add to Home: Add the shortcut icon of the stored favorite station to the home screen. | capability | p.288 / bullet |
| 4 | <span class="req-label">Playing AM/FM Radio</span>Station List. | capability | p.288 / text |
| 5 | <span class="req-label">Playing AM/FM Radio</span>Lists the strongest stations on the selected band. | capability | p.288 / text |
| 6 | <span class="req-label">Playing AM/FM Radio</span>Manual update. | capability | p.288 / text |
| 7 | <span class="req-label">Playing AM/FM Radio</span>Updates your available station list at any time. | capability | p.288 / text |
| 8 | <span class="req-label">Playing AM/FM Radio</span>1Favorite Station Switching the Audio Mode Roll the left selector wheel or select the audio source icon on the screen. 2 Audio Remote Controls P.268. | capability | p.288 / text |
| 9 | <span class="req-label">Playing AM/FM Radio</span>You can store 12 AM/FM stations into preset memory. | capability | p.288 / text |
| 10 | <span class="req-label">Playing AM/FM Radio</span>Samples each of the strongest stations on the selected band for 10 seconds. To turn off scan, select Stop or Back. | capability | p.289 / text |
| 11 | <span class="req-label">Playing AM/FM Radio</span>Radio Data System (RDS). | capability | p.289 / text |
| 12 | <span class="req-label">Playing AM/FM Radio</span>Provides text data information related to your selected RDS-capable FM station. | capability | p.289 / text |
| 13 | <span class="req-label">Playing AM/FM Radio</span>To find an RDS station from Station List. | capability | p.289 / text |
| 14 | <span class="req-label">Playing AM/FM Radio</span>Manual update. | capability | p.289 / text |
| 15 | <span class="req-label">Playing AM/FM Radio</span>Updates your available station list at any time. | capability | p.289 / text |
| 16 | <span class="req-label">Playing AM/FM Radio</span>1Radio Data System (RDS) When you select an RDS-capable FM station, the RDS automatically turns on, and the frequency display changes to the station name. However, when the signals of that station become weak, the display changes from the station name to the frequency. | constraint | p.289 / text |
| 17 | <span class="req-label">Playing AM/FM Radio</span>HD Subchannel. | capability | p.290 / text |
| 18 | <span class="req-label">Playing AM/FM Radio</span>Displays the subchannel list when an HD RadioTM station is selected while listening to an FM station. | constraint | p.290 / text |
| 19 | <span class="req-label">Playing AM/FM Radio</span>AM/FM Settings. | capability | p.290 / text |
| 20 | <span class="req-label">Playing AM/FM Radio</span>Changes the AM/FM settings. | capability | p.290 / text |
| 21 | <span class="req-label">Step -</span>HD Radio: Automatically choose a digital or an analog channel, or listen to analog only. | capability | p.290 / bullet |
| 22 | <span class="req-label">Step -</span>Artwork: Turns the artwork display on and off. | capability | p.290 / bullet |
<!-- GENERATED:END function=35b7539e28da -->







