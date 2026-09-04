<!-- GENERATED:START function=d20c0260d90f (generated; edits inside this block are overwritten by the next publish — write your own notes outside it) -->
# 15. Android AutoTM

<div class="fn-meta"><b>Function path:</b> Features / Android AutoTM<br><b>Source:</b> printed page 280, 281, 282, 283, 284<br><b>Test-ready:</b> <span class="test-ready-yes">yes — no unfilled thresholds and a procedure is present</span></div>

<p class="fn-disclaimer">Every "Presumed requirement" row below is machine-derived from the Owner's Manual text by rule-based extraction — not AI-written — and traceable to the printed page in its Source column.</p>

## Figures (areas of the original PDF; the OM has no figure numbers or captions)
![figure](../figures/FIG-3e9406772329.png)
- Figure 15-1 source: p.280
- (Copied from OM) Android Auto Icon


## Procedure (2 sequences; the manual restarts the numbering)
```mermaid
flowchart TD
    subgraph SEQ1["Sequence 1"]
    direction TB
    S1_1["1. Connect the Android phone to the USB port using the USB …"]
    S1_2["2. Select Yes."]
    S1_1 --> S1_2
    end
    subgraph SEQ2["Sequence 2"]
    direction TB
    S2_1["1. Press the button."]
    S2_2["2. Select Android Auto."]
    S2_3["3. Select Connect New Device."]
    S2_4["4. Pair the Android phone to the vehicle’s Bluetooth® Hands…"]
    S2_5["5. Select Yes."]
    S2_1 --> S2_2
    S2_2 --> S2_3
    S2_3 --> S2_4
    S2_4 --> S2_5
    end
```

| Seq | Step | Operation (Copied from OM) | Source |
|---|---|---|---|
| 1 | 1 | Connect the Android phone to the USB port using the USB cable. 2 USB Ports P.253 | p.282 / step |
| 1 | 2 | Select Yes. | p.282 / step |
| 2 | 1 | Press the button. | p.282 / step |
| 2 | 2 | Select Android Auto. | p.282 / step |
| 2 | 3 | Select Connect New Device. | p.282 / step |
| 2 | 4 | Pair the Android phone to the vehicle’s Bluetooth® HandsFreeLink® (HFL) system. 2 Phone Setup P.315 | p.282 / step |
| 2 | 5 | Select Yes. | p.282 / step |

## 15-2-1. Service overview

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Android AutoTM</span>If you connect an AndroidTM phone to the system via USB port or wirelessly, and the 1Android AutoTM (Connect) button is pressed or the Android Auto icon is selected, you can operate Android Auto on the audio/information screen. We recommend that you complete this tutorial while safely parked before using Android Auto. 2 USB Ports P.253. | capability | p.280 / text |
| 2 | <span class="req-label">Android AutoTM</span>Android Auto Icon. | capability | p.280 / text |
| 3 | <span class="req-label">Android AutoTM</span>We recommend that you update Android OS to the latest version when using Android Auto. Bluetooth A2DP cannot be used while your phone is connected to Android Auto. | constraint | p.280 / text |
| 4 | <span class="req-label">Android AutoTM</span>To use Android Auto on a smartphone with Android 9.0 (Pie) or earlier, you need to download the Android Auto app from Google Play to your smartphone. | capability | p.280 / text |
| 5 | <span class="req-label">Android AutoTM</span>Park in a safe place before connecting your Android phone to Android Auto and when launching any compatible apps. | constraint | p.280 / text |
| 6 | <span class="req-label">Android AutoTM</span>When your Android phone is connected to Android Auto, it is not possible to use the Bluetooth® Audio or Bluetooth® HandsFreeLink®. However, other previously paired phones can stream audio via Bluetooth® while Android Auto is connected. 2 Phone Setup P.315. | capability | p.280 / text |
| 7 | <span class="req-label">Android AutoTM</span>Apple CarPlay and Android Auto cannot run at the same time. | constraint | p.280 / text |
| 8 | <span class="req-label">Android AutoTM</span>Android and Android Auto are trademarks of Google LLC. | capability | p.280 / text |
| 9 | <span class="req-label">Android AutoTM</span>Android Auto Menu. | capability | p.281 / text |
| 10 | <span class="req-label">Android AutoTM</span>For details on available applications, please refer to the Android Auto homepage. Apps displayed on your screen can be changed with your smartphone. Select the Honda icon on the Android Auto menu screen to go back to the home screen. | capability | p.281 / text |
| 11 | <span class="req-label">Android AutoTM</span>1Android AutoTM For details on countries and regions where Android Auto is available, as well as information pertaining to function, refer to the Android Auto homepage. | capability | p.281 / text |
| 12 | <span class="req-label">Android AutoTM</span>Screens may differ depending on the version of the Android Auto app you are using. | capability | p.281 / text |
| 13 | <span class="req-label">Android AutoTM</span>Android Auto Operating Requirements &amp; Limitations Android Auto requires a compatible Android phone with an active mobile connection and data plan. Your carrier’s rate plans will apply. | capability | p.281 / text |
| 14 | <span class="req-label">Android AutoTM</span>Changes in operating systems, hardware, software, and other technology integral to providing Android Auto functionality, as well as new or revised governmental regulations, may result in a decrease or cessation of Android Auto functionality and services. Honda cannot and does not provide any warranty or guarantee of future Android Auto performance or functionality. | constraint | p.281 / text |
| 15 | <span class="req-label">Android AutoTM</span>It is possible to use 3rd party apps if they are compatible with Android Auto. Refer to the Android Auto homepage for information on compatible apps. | constraint | p.281 / text |
| 16 | <span class="req-label">Android AutoTM</span>Connecting Android Auto Using the USB Cable. | capability | p.282 / text |

## 15-2-2. Service requirements

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Step -</span>The confirmation screen will be displayed. | capability | p.282 / bullet |
| 2 | <span class="req-label">Step -</span>If you do not want to connect Android Auto, select No. | capability | p.282 / bullet |
| 3 | <span class="req-label">Android AutoTM</span>You may change the consent settings under the Connections menu. | capability | p.282 / text |
| 4 | <span class="req-label">Android AutoTM</span>Connecting Android Auto Wirelessly. | capability | p.282 / text |
| 5 | <span class="req-label">Step -</span>If your Android phone asks for permission to accept an Android Auto connection, accept to connect. | capability | p.282 / bullet |
| 6 | <span class="req-label">Android AutoTM</span>1Connecting Android Auto Using the USB Cable Only initialize Android Auto when you are safely parked. When Android Auto first detects your phone, you will need to set up your phone so that auto pairing is possible. Refer to the instruction manual that came with your phone. | constraint | p.282 / text |
| 7 | <span class="req-label">Android AutoTM</span>You can use the following procedure to disconnect or delete the devices connecting Android Auto after you have completed the initial setup: Press the button Select General Settings Connections Select device. | capability | p.282 / text |
| 8 | <span class="req-label">Android AutoTM</span>Use of user and vehicle information The use and handling of user and vehicle information transmitted to/from your phone by Android Auto is governed by Google’s Privacy Policy. | capability | p.282 / text |
| 9 | <span class="req-label">Android AutoTM</span>Operating Android Auto with Google Assistant. | capability | p.283 / text |
| 10 | <span class="req-label">Android AutoTM</span>Press the (talk) button to talk to Google Assistant. Press again to deactivate voice recognition. | capability | p.283 / text |
| 11 | <span class="req-label">Android AutoTM</span>1Operating Android Auto with Google Assistant Below are examples of commands you can give with voice recognition:. | capability | p.283 / text |
| 12 | <span class="req-label">Step -</span>Reply to text. | capability | p.283 / bullet |
| 13 | <span class="req-label">Step -</span>Call my wife. | capability | p.283 / bullet |
| 14 | <span class="req-label">Step -</span>Navigate to Honda. | capability | p.283 / bullet |
| 15 | <span class="req-label">Step -</span>Play my music. | capability | p.283 / bullet |
| 16 | <span class="req-label">Step -</span>Send a text message to my wife. | capability | p.283 / bullet |
| 17 | <span class="req-label">Step -</span>Call flower shop. | capability | p.283 / bullet |
| 18 | <span class="req-label">Android AutoTM</span>For more information, please refer to the Android Auto homepage. | capability | p.283 / text |

## 15-5. Exception operation

| # | Presumed requirement | Strength | Source |
|---|---|---|---|
| 1 | <span class="req-label">Android AutoTM</span>The following error messages are just examples. If you see an error message not listed below, follow the on-screen instructions to clear it. | constraint | p.284 / text |
<!-- GENERATED:END function=d20c0260d90f -->








