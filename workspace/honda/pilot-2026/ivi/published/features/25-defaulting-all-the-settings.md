<!-- GENERATED:START function=32f7d7d9f4d3 (generated; edits inside this block are overwritten by the next publish — write your own notes outside it) -->
# 25. Defaulting All the Settings

<div class="fn-meta"><b>Function path:</b> Customized Features / Defaulting All the Settings<br><b>Source:</b> printed page 368<br><b>Test-ready:</b> <span class="test-ready-yes">yes — no unfilled thresholds and a procedure is present</span></div>

<p class="fn-disclaimer">Every "Presumed requirement" row below is machine-derived from the Owner's Manual text by rule-based extraction — not AI-written — and traceable to the printed page in its Source column.</p>

## Procedure (2 sequences; the manual restarts the numbering)
```mermaid
flowchart TD
    subgraph SEQ1["Sequence 1"]
    direction TB
    S1_1["1. Select Home."]
    S1_2["2. Select General Settings."]
    S1_3["3. Select System."]
    S1_4["4. Select Factory Data Reset."]
    S1_5["5. Select Continue."]
    S1_6["6. Select Reset again to reset the settings."]
    S1_1 --> S1_2
    S1_2 --> S1_3
    S1_3 --> S1_4
    S1_4 --> S1_5
    S1_5 --> S1_6
    end
    subgraph SEQ2["Sequence 2"]
    direction TB
    S2_1["1. Select Home."]
    S2_2["2. Select Vehicle Settings."]
    S2_3["3. Select Menu."]
    S2_4["4. Select Default All."]
    S2_5["5. Select Yes."]
    S2_1 --> S2_2
    S2_2 --> S2_3
    S2_3 --> S2_4
    S2_4 --> S2_5
    end
```

| Seq | Step | Operation (Copied from OM) | Source |
|---|---|---|---|
| 1 | 1 | Select Home. | p.368 / step |
| 1 | 2 | Select General Settings. | p.368 / step |
| 1 | 3 | Select System. | p.368 / step |
| 1 | 4 | Select Factory Data Reset. | p.368 / step |
| 1 | 5 | Select Continue. | p.368 / step |
| 1 | 6 | Select Reset again to reset the settings. | p.368 / step |
| 2 | 1 | Select Home. | p.368 / step |
| 2 | 2 | Select Vehicle Settings. | p.368 / step |
| 2 | 3 | Select Menu. | p.368 / step |
| 2 | 4 | Select Default All. | p.368 / step |
| 2 | 5 | Select Yes. | p.368 / step |

## 25-2-1. Service overview

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Defaulting All the Settings</span>Defaulting All the Settings. | capability | p.368 / text |
| 2 | <span class="req-label">Defaulting All the Settings</span>Reset all the menu and customized settings as the factory defaults. | capability | p.368 / text |
| 3 | <span class="req-label">Defaulting All the Settings</span>Defaulting System Settings. | capability | p.368 / text |
| 4 | <span class="req-label">Defaulting All the Settings</span>Only the Owner user can execute this command. If current profile is not the Owner user, please switch users. 2 Switching Users P.322. | constraint | p.368 / text |

## 25-2-2. Service requirements

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>A confirmation message appears on the screen. | capability | p.368 / bullet |
| 2 | <span class="req-label">Step -</span>The system will reboot. | capability | p.368 / bullet |
| 3 | <span class="req-label">Defaulting All the Settings</span>Defaulting Vehicle Settings. | capability | p.368 / text |
| 4 | <span class="req-label">Defaulting All the Settings</span>1Defaulting All the Settings When you transfer the vehicle to a third-party, reset all settings to default and delete all personal data. | constraint | p.368 / text |
| 5 | <span class="req-label">Defaulting All the Settings</span>If you perform Factory Data Reset, it will reset the preinstalled apps to their factory default. | capability | p.368 / text |

## 25-5. Exception operation

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Defaulting All the Settings</span>If you perform Factory Data Reset, you cannot use the HondaLink® because it goes offline. 2 HondaLink® P.300. | constraint | p.368 / text |
<!-- GENERATED:END function=32f7d7d9f4d3 -->







