<!-- GENERATED:START index (generated; edits inside this block are overwritten by the next publish — write your own notes outside it) -->
# 2026 Honda HR-V Owner's Manual (A3V02626OMEN) — features — Presumed specification

> This is a machine-derived estimate, not an official requirements document. Numeric thresholds left blank could not be found in the manual and must be filled in by a tester with evidence.

| Field | Value |
|---|---|
| Maker / Model | Honda / HR-V 2026 |
| Scope | features |
| Markets | US, CA |
| Profile | honda_v3 |
| Manual ID | honda/hr-v-2026/ivi |

## Numeric thresholds

- Thresholds detected: **10**
- Filled: **1** / unfilled: **9**
- Test-ready functions: **8 / 19**

The manual states almost no numbers, so a tester fills the thresholds in. A function that still has an unfilled threshold cannot become a test specification (`is_test_ready=false`). Fill them in `overlay/thresholds.yaml` or on the screen.

```mermaid
pie showData
    "Filled" : 1
    "Unfilled" : 9
```

## Figures in the manual

- Figures: **26** / images rendered: **26**

Each image is a rendering of the corresponding area of the original PDF. **Images are not kept in the repository** (they are copies of another company's manual); `publish` creates them under `../figures/` on the machine that runs it.

## Glossary (registered by a reviewer)

How wording in the manual maps to the in-house term. **The original text is not rewritten** — the mapping is only annotated here. Register terms on the Glossary screen. Evidence (why the mapping holds) is required.

| In-house term | Category | Wording in the manual | Hits | Evidence |
|---|---|---|---:|---|
| AA | abbreviation | `Android Auto` | 60 | Counted by string match over workspace/subaru/**/published/*.md (2026-09-01): outback-2026 31 / outback-2025 24 / ascent-2026 1. Always printed in full ("Android Auto") — no abbreviated form appears in the manual text; "AA" is an in-house-only abbreviation. |
| Hands-free telephone | abbreviation | `HFL` | 26 | Counted by string match over workspace/**/published/*.md (2026-07-30, after re-publishing RAV4): Honda Pilot 85 / HR-V 73, Toyota and GM 0. The abbreviation is not used outside Honda, so it is restricted to maker=honda. |

## Functions

```mermaid
%%{init: {"themeVariables": {"fontSize": "11px"}}}%%
flowchart LR
    ROOT["2026 Honda HR-V Owner's Manual (A3V02626OMEN) — features"]
    ROOT --> A1["Features"]
    A1 --> A1F1["1 About Your Audio System ⚠"]
    A1 --> A1F2["2 USB Ports ⚠"]
    A1 --> A1F3["3 Audio System Theft Protection"]
    A1 --> A1F4["4 Audio Remote Controls ⚠"]
    A1 --> A1F5["5 Audio System Basic Operation ⚠"]
    A1 --> A1F6["6 Start Up ⚠"]
    A1 --> A1F7["7 Reboot Audio ⚠"]
    A1 --> A1F8["8 Audio/Information Screen"]
    A1 --> A1F9["9 Adjusting the Sound"]
    A1 --> A1F10["10 Display Setup"]
    A1 --> A1F11["11 Playing AM/FM Radio"]
    A1 --> A1F12["12 Music Playback via Wired Connection ⚠"]
    A1 --> A1F13["13 Playing Bluetooth® Audio ⚠"]
    A1 --> A1F14["14 Apple CarPlay"]
    A1 --> A1F15["15 Android AutoTM"]
    A1 --> A1F16["16 Audio Error Messages ⚠"]
    A1 --> A1F17["17 System ⚠"]
    A1 --> A1F18["18 Customized Features ⚠"]
    A1 --> A1F19["19 Bluetooth® HandsFreeLink"]
```

| No. | Function | Area | Requirements | Figures | Unfilled thresholds | Test-ready |
|---|---|---|---|---|---|---|
| 1 | [About Your Audio System](/specifications/honda/hr-v-2026/ivi/file/1-about-your-audio-system.md?chapter=features) | Features | 5 | 1 | 0 | - |
| 2 | [USB Ports](/specifications/honda/hr-v-2026/ivi/file/2-usb-ports.md?chapter=features) | Features | 20 | 2 | 0 | - |
| 3 | [Audio System Theft Protection](/specifications/honda/hr-v-2026/ivi/file/3-audio-system-theft-protection.md?chapter=features) | Features | 3 | 0 | 0 | o |
| 4 | [Audio Remote Controls](/specifications/honda/hr-v-2026/ivi/file/4-audio-remote-controls.md?chapter=features) | Features | 10 | 1 | 0 | - |
| 5 | [Audio System Basic Operation](/specifications/honda/hr-v-2026/ivi/file/5-audio-system-basic-operation.md?chapter=features) | Features | 9 | 1 | 0 | - |
| 6 | [Start Up](/specifications/honda/hr-v-2026/ivi/file/6-start-up.md?chapter=features) | Features | 1 | 1 | 0 | - |
| 7 | [Reboot Audio](/specifications/honda/hr-v-2026/ivi/file/7-reboot-audio.md?chapter=features) | Features | 4 | 0 | 1 | - |
| 8 | [Audio/Information Screen](/specifications/honda/hr-v-2026/ivi/file/8-audio-information-screen.md?chapter=features) | Features | 18 | 3 | 0 | o |
| 9 | [Adjusting the Sound](/specifications/honda/hr-v-2026/ivi/file/9-adjusting-the-sound.md?chapter=features) | Features | 7 | 0 | 0 | o |
| 10 | [Display Setup](/specifications/honda/hr-v-2026/ivi/file/10-display-setup.md?chapter=features) | Features | 11 | 2 | 0 | o |
| 11 | [Playing AM/FM Radio](/specifications/honda/hr-v-2026/ivi/file/11-playing-am-fm-radio.md?chapter=features) | Features | 25 | 1 | 0 | o |
| 12 | [Music Playback via Wired Connection](/specifications/honda/hr-v-2026/ivi/file/12-music-playback-via-wired-connection.md?chapter=features) | Features | 31 | 2 | 2 | - |
| 13 | [Playing Bluetooth® Audio](/specifications/honda/hr-v-2026/ivi/file/13-playing-bluetooth-audio.md?chapter=features) | Features | 22 | 1 | 2 | - |
| 14 | [Apple CarPlay](/specifications/honda/hr-v-2026/ivi/file/14-apple-carplay.md?chapter=features) | Features | 32 | 1 | 0 | o |
| 15 | [Android AutoTM](/specifications/honda/hr-v-2026/ivi/file/15-android-autotm.md?chapter=features) | Features | 22 | 1 | 0 | o |
| 16 | [Audio Error Messages](/specifications/honda/hr-v-2026/ivi/file/16-audio-error-messages.md?chapter=features) | Features | 10 | 0 | 0 | - |
| 17 | [System](/specifications/honda/hr-v-2026/ivi/file/17-system.md?chapter=features) | Features | 59 | 0 | 4 | - |
| 18 | [Customized Features](/specifications/honda/hr-v-2026/ivi/file/18-customized-features.md?chapter=features) | Features | 69 | 1 | 0 | - |
| 19 | [Bluetooth® HandsFreeLink](/specifications/honda/hr-v-2026/ivi/file/19-bluetooth-handsfreelink.md?chapter=features) | Features | 106 | 8 | 0 | o |
<!-- GENERATED:END index -->



