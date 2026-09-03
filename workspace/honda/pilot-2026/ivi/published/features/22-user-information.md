<!-- GENERATED:START function=21db6d0177b4 (generated; edits inside this block are overwritten by the next publish — write your own notes outside it) -->
# 22. User Information

<div class="fn-meta"><b>Function path:</b> Audio System Basic Operation / User Information<br><b>Source:</b> printed page 319, 320, 321, 322<br><b>Test-ready:</b> <span class="test-ready-yes">yes — no unfilled thresholds and a procedure is present</span></div>

<p class="fn-disclaimer">Every "Presumed requirement" row below is machine-derived from the Owner's Manual text by rule-based extraction — not AI-written — and traceable to the printed page in its Source column.</p>

## Figures (areas of the original PDF; the OM has no figure numbers or captions)
![figure](../figures/FIG-ffafea031ad3.png)
- Figure 22-1 source: p.319
- (Copied from OM) a User Information
![figure](../figures/FIG-12a422d64ddf.png)
- Figure 22-2 source: p.320
- (Copied from OM) website.

## Procedure (3 sequences; the manual restarts the numbering)
```mermaid
flowchart TD
    subgraph SEQ1["Sequence 1"]
    direction TB
    S1_1["1. Select User Info."]
    S1_2["2. Select Change Profile."]
    S1_3["3. Select the +Add User."]
    S1_4["4. Enter User Information. 2 Start Up P.271"]
    S1_1 --> S1_2
    S1_2 --> S1_3
    S1_3 --> S1_4
    end
    subgraph SEQ2["Sequence 2"]
    direction TB
    S2_1["1. Select User Info."]
    S2_2["2. Select Change Profile."]
    S2_3["3. Select the user you want to use."]
    S2_1 --> S2_2
    S2_2 --> S2_3
    end
    subgraph SEQ3["Sequence 3"]
    direction TB
    S3_1["1. Select Profile Settings."]
    S3_2["2. Select Manage Profile."]
    S3_3["3. Select Your Profile."]
    S3_4["4. Select Delete."]
    S3_1 --> S3_2
    S3_2 --> S3_3
    S3_3 --> S3_4
    end
```

| Seq | Step | Operation (Copied from OM) | Source |
|---|---|---|---|
| 1 | 1 | Select User Info. | p.321 / step |
| 1 | 2 | Select Change Profile. | p.321 / step |
| 1 | 3 | Select the +Add User. | p.321 / step |
| 1 | 4 | Enter User Information. 2 Start Up P.271 | p.321 / step |
| 2 | 1 | Select User Info. | p.322 / step |
| 2 | 2 | Select Change Profile. | p.322 / step |
| 2 | 3 | Select the user you want to use. | p.322 / step |
| 3 | 1 | Select Profile Settings. | p.322 / step |
| 3 | 2 | Select Manage Profile. | p.322 / step |
| 3 | 3 | Select Your Profile. | p.322 / step |
| 3 | 4 | Select Delete. | p.322 / step |

## 22-2-1. Service overview

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">User Information</span>User Information. | capability | p.319 / text |
| 2 | <span class="req-label">User Information</span>a User Information. | capability | p.319 / text |
| 3 | <span class="req-label">User Information</span>1User Information This feature cannot be used while driving. | constraint | p.319 / text |
| 4 | <span class="req-label">User Information</span>You can customize settings individually for each user. 2 Profile Settings P.323. | capability | p.319 / text |
| 5 | <span class="req-label">User Information</span>You can customize security settings for each user. If you have forgotten security settings, you will need to delete the user and create a new one. If you have forgotten security settings for the Owner user, please contact a dealer or Honda Customer Service. 2 Customer Service Information P.682. | constraint | p.319 / text |
| 6 | <span class="req-label">User Information</span>Certain features are unavailable when using a newly created user or the Guest user. | constraint | p.319 / text |
| 7 | <span class="req-label">User Information</span>You can add and change users, as well as customize user settings. By registering a user, you can personalize your vehicle settings. You can select a user when the audio/information screen loads, even when the doors are open or unlocked. | constraint | p.320 / text |
| 8 | <span class="req-label">User Information</span>By linking your profile with your Google Account, you can enjoy a more personalized Google built-in experience. For more assistance on account linking, visit the Google website. | capability | p.320 / text |
| 9 | <span class="req-label">User Information</span>Registering a User. | capability | p.321 / text |

## 22-2-2. Service requirements

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>You can also add users when Profile Settings Change Profile is selected. 2 Profile Settings P.323. | constraint | p.321 / bullet |
| 2 | <span class="req-label">Step -</span>You can add users even when the doors are open and unlocked. | constraint | p.321 / bullet |
| 3 | <span class="req-label">User Information</span>1Registering a User Profile can be changed only when the vehicle is parked. | constraint | p.321 / text |
| 4 | <span class="req-label">User Information</span>You can add up to 4 users other than the Owner user and the Guest user. | capability | p.321 / text |
| 5 | <span class="req-label">User Information</span>When you add a user, the audio/information screen is loaded under that user. | capability | p.321 / text |
| 6 | <span class="req-label">User Information</span>Switching Users. | capability | p.322 / text |
| 7 | <span class="req-label">Step -</span>You can also change users when Profile Settings Change Profile is selected. 2 Profile Settings P.323. | constraint | p.322 / bullet |
| 8 | <span class="req-label">Step -</span>You can switch users even when the doors are open and unlocked. | constraint | p.322 / bullet |
| 9 | <span class="req-label">User Information</span>Deleting Users. | capability | p.322 / text |
| 10 | <span class="req-label">User Information</span>1Switching Users Profile can be changed only when the vehicle is parked. | constraint | p.322 / text |
| 11 | <span class="req-label">User Information</span>1Deleting Users When the profile currently being used is deleted, the audio/information screen is loaded under the Guest user. | constraint | p.322 / text |
| 12 | <span class="req-label">User Information</span>Depending on the version of your OS, the steps for deleting a user may differ from the instructions on this page. Follow the on-screen prompts. | capability | p.322 / text |

## 22-4. User settings

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">User Information</span>Users with customized security settings can restrict screen operations by selecting the Screen Lock shortcut. | capability | p.322 / text |
| 2 | <span class="req-label">User Information</span>While using the Owner user, you can delete other users via General Settings Advanced Settings. 2 Customized Features P.346. | capability | p.322 / text |

## 22-5. Exception operation

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">User Information</span>The transmitter settings may not be switched when you change the Owner user. If this happens, change to a different user and then try switching to the desired user again. | constraint | p.322 / text |
<!-- GENERATED:END function=21db6d0177b4 -->







