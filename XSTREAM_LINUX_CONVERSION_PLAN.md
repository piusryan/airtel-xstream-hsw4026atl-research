# XStream Linux Conversion Research and Safety Tracker

## Project status

- **Status:** Read-only discovery; diagnostic dashboard implemented; conversion decision on hold
- **Started:** 2026-09-25
- **Last updated:** 2026-09-25
- **Target:** Airtel `XStream_Smart_Box_001` / Vantiva-Technicolor `HSW4026ATL` family (owner-confirmed; exact suffix remains unknown)
- **Observed IP:** `192.168.1.10`
- **Goal:** Determine whether the exact box can run a supported Linux distribution and build a separate read-only diagnostic UI while hardware compatibility is investigated.
- **Current decision:** No presently supportable or recoverable Linux conversion path has been established.
- **Important limitation:** The exact firmware, PCB revision, and suffix of the observed unit have not been captured from the owner.

## Revised plan after feasibility review

1. Keep the original firmware, configuration, and working state unchanged.
2. Use the local read-only dashboard to record evidence and verify service behavior.
3. Capture the exact model suffix, PCB markings, firmware version, and recovery indicators.
4. Establish a verified backup and rollback route before any write operation; without the current USB cable, investigate only documented network recovery or obtain a suitable data/adapter cable.
5. Obtain the HSW-specific vendor source and build a matching board support package; do not install a generic Linux image.
6. If no reversible recovery path can be verified, keep the box on its original software and use a separate computer for general-purpose Linux work.

## Build workspace status

- **Available:** Git for Windows.
- **Not currently available:** GCC, `make`, CMake, ARM cross-compiler, QEMU, Docker, and a registered WSL distribution.
- **Source status:** No Vantiva HSW4026ATL corresponding-source tree is present in the workspace.
- **Build rule:** Do not install a toolchain or start a board-specific build until the source package and target suffix are verified.
- **Planned environment:** An isolated Linux build environment with an ARMv7 hard-float cross-toolchain, vendor kernel source, board configuration, and reproducible rootfs tooling.

## Safety boundaries

- Work only on hardware owned by or explicitly authorized for testing.
- Do not erase, factory-reset, flash, unlock, alter partitions, or modify bootloader state during discovery.
- Do not bypass credentials, subscription controls, exploits, or access restrictions.
- Do not enable developer options, ADB, or fastboot solely for research without explicit owner approval.
- Identify and preserve the original firmware and configuration before any write operation.
- Establish a tested rollback or recovery method before installing software.
- Treat a generic Linux image as incompatible until the exact board, bootloader, kernel, storage layout, display pipeline, and required drivers are verified.
- Do not use subscription-bypass, rooting, or “soft-mod” instructions as conversion evidence.

## Confidence scale

| Level | Meaning |
|---|---|
| Confirmed | Directly observed from the target or supplied by an authoritative vendor document |
| High | Exact identifier reported consistently by multiple independent technical sources |
| Medium | Consistent secondary reporting, but not confirmed from the exact target or an authoritative hardware record |
| Low | Single secondary source, ambiguous identifier, or unresolved revision relationship |
| Unknown | No adequate evidence |

## Executive assessment

1. The target's `Technicolor` / `XStream_Smart_Box_001` network identity is confirmed.
2. `Broadcom BCM72604`, dual-core ARMv7, and approximately 1.84 GHz are high-confidence family characteristics; 2 GB RAM, 8 GB storage, and VideoCore V graphics remain medium-confidence until confirmed from the exact unit.
3. Vantiva's official `HSW4026ATL v1.0` open-source report confirms a Linux 4.9 vendor kernel and numerous HSW-specific Android boot, graphics, HDMI-CEC, audio, power, thermal, TV-input, Broadcom, and Realtek components.
4. The report is an inventory of 1,164 modules, not a source-code archive, board device tree, bootloader image, recovery image, or rollback procedure.
5. No exact HSW source archive, board-specific mainline Linux target, OpenWrt target, verified bootloader port, custom recovery image, or tested rollback path was found.
6. The project is therefore blocked, not proven impossible. A vendor BSP port may eventually be possible, but a supported distro image must not be attempted first.

## Device identity boundaries

| Identifier | Status | Research treatment |
|---|---|---|
| `XStream_Smart_Box_001` | Confirmed on the target through DIAL | Primary target identity |
| `HSW4026ATL` | High-confidence family identifier from the source document | Use for family-wide documentation, not as proof of the observed unit's suffix |
| `HSW4028ATL` | Owner-reported, then corrected as a mistaken model | Not the target; retain only as a correction record |
| `HSW4026ATL1`, `HSW4026ATL2`, `HSW4026ATL4` | Revision/suffix relationship unresolved | Do not treat images, source, or recovery files as interchangeable |
| LGE `SH960S-AT` / `ganesa` | Separate device | Excluded from all HSW findings |
| `UIW4078ATL` | Separate Amlogic-based generation | Excluded |
| `HT001` / `XStream Box 002` | Separate model family | Excluded |
| `Xstream4_AR` / newer Xstream 4 variants | Separate model family | Excluded |

## Confirmed target network evidence

| Item | Finding | Confidence |
|---|---|---|
| Device identity | DIAL XML advertises `Technicolor` and `XStream_Smart_Box_001` | Confirmed |
| TCP 8008 | Reachable; DIAL/UPnP device description returned `200 OK` | Confirmed |
| DIAL applications | `/apps/` returned `204 No Content` | Confirmed |
| TCP 8009 | Accepted a connection but returned no HTTP response to the root request | Confirmed open; service unknown |
| TCP 8443 | HTTPS responded; `/` returned `404 Not Found` | Confirmed reachable; service unknown |
| TCP 5555 | No network ADB service was observed | Confirmed for the tested check |
| SSH/Telnet | Ports 22 and 23 were not reachable | Confirmed for the tested scan |
| Other tested ports | 80, 443, 8080, and 53/TCP were not reachable | Confirmed for the tested scan |
| Device modification | No reset, erase, unlock, flash, or configuration change was performed | Confirmed |

These observations do not identify the installed Android build, hardware revision, bootloader, or partition layout.

### Latest read-only scan

- **Timestamp:** `2026-09-25T14:07:53Z` to `2026-09-25T14:07:59Z`
- **Target:** `192.168.1.10`
- **Open:** TCP `8008`, `8009`, and `8443`
- **Timeout:** TCP `22`, `23`, `53`, `80`, `443`, `5555`, and `8080`
- **DIAL:** `200 OK`; identity `Technicolor` / `XStream_Smart_Box_001`
- **HTTPS 8443:** TLS certificate verification failed; the service is reachable, but this probe did not capture its HTTP status
- **Write actions:** None

## Hardware evidence

| Component | Finding | Confidence and qualification |
|---|---|---|
| Brand / manufacturer | Airtel-distributed set-top box; DIAL reports `Technicolor` | Confirmed |
| SoC | Broadcom `BCM72604` | High; multiple secondary sources agree, but the official OSS report names only the `bcm-97xxx` kernel family |
| CPU | Dual-core ARMv7, approximately 1.84 GHz; commonly rounded to 1.8 GHz | High; Geekbench identifies ARMv7 and two cores, but target output is absent |
| GPU | Broadcom VideoCore V / V3D-510 class | Medium; secondary specifications and the target HAL inventory support this family, but exact target identification is absent |
| RAM | 2 GB nominal | Medium; secondary specifications agree, while Geekbench reports 1.39 GB available |
| Internal storage | 8 GB nominal | Medium; storage type, partition layout, and usable capacity are unknown |
| Broadcast input | `SAT IN` is documented | Confirmed connector; DVB-S2/OTT use is medium-confidence and the tuner model is unknown |
| Video output | HDMI and analog Video Out are documented | Confirmed |
| Audio output | HDMI, analog L/R, and SPDIF are documented | Confirmed |
| Ethernet | RJ-10 Ethernet is documented and the target has active LAN services | Confirmed |
| USB | USB is documented | Confirmed connector; version, count, and host/device behavior are unknown |
| Wi-Fi | Android Wi-Fi HAL plus Realtek `8822bu` driver/firmware artifacts are listed | Confirmed software inventory; physical radio and antenna implementation remain unknown |
| Bluetooth | Android Bluetooth, Realtek Bluetooth modules, and remote firmware artifacts are listed | Confirmed software inventory; physical Bluetooth radio and SKU population remain unknown |
| Remote control | Realtek-based remote firmware artifacts are listed | Medium; the exact remote variant is unknown |
| Expansion | No microSD slot is documented | Unknown; absence from the manual is not proof that no internal connector exists |
| Board / PCB revision | Not established | Unknown |
| Boot media | eMMC, NAND, NOR, or another layout is not established | Unknown |

The official manual confirms connectors, not the exact tuner, Wi-Fi/Bluetooth chips, USB generation/count, storage type, or PCB revision.

## Reported firmware history

These rows describe reported devices, not the currently observed unit.

| Reported release | Android / kernel | Build or user agent | Reported ADB state | Confidence |
|---|---|---|---|---|
| `hsw4026atl-1.0.9-19110817` | Android 9; `4.9.159-1-6pre` | `ptt1.190228.001.1.0.9-19110817` | Developer options and network ADB reported available | High for an observed Android 9 unit; not the target's current state |
| `hsw4026atl-2.3.0-21042717` | Android 9; `4.9.183-1-6pre` | `PTT1.210208.001.2.3.0-21042717` | Developer options and network ADB reported available | High for an observed Android 9 unit; not the target's current state |
| `hsw4026atl-3.1.6-220211` | Android generation not independently captured in the cited thread | Release reported after an OTA update | Multiple users reported USB debugging disabled or connection refused | Medium; version and ADB behavior are reported, but exact OS/kernel are not established here |
| `RTT4.230420.001` | Android 11 | `XStream_Smart_Box_001` Dalvik user agent | Unknown | Medium; model, OS, and build are explicit, but this is a user-agent observation rather than target metadata |
| `5.0.24-230803` | Unresolved | Previously collected as a possible kernel/build string | Unknown | Low; not independently reproduced in the final source pass and not used in the feasibility decision |

The Vantiva publication label `v1.0` is the disclosure document's product version. It must not be interpreted as firmware `hsw4026atl-1.0.9`.

## Official Vantiva open-source evidence

### Publication identity

- **Title:** `HSW4026ATL v1.0 OSS Publication`
- **Vantiva document ID:** `107788`
- **Format:** 44-page PDF
- **Declared modules:** 1,164
- **PDF size:** 1,022,018 bytes
- **PDF header:** `%PDF-1.7`
- **SHA-256:** `90c9c1c4df6e3a7121ce942c8c3cce4d69d2960f4b5913075224a878998f94d8`
- **Regulatory page:** https://www.vantiva.com/regulatory-information/?prod=hsw4026atl
- **Publication route:** https://www.vantiva.com/regulatory-information/hsw4026atl-v1-0-oss-publication/hsw4026atl-v1-0-oss-publication-1-pdf/
- **Verified direct PDF:** https://www.vantiva.com/app/uploads/2024/10/HSW4026ATL-v1.0-OSS-Publication-1.pdf

The PDF is copyrighted by Technicolor and marked not for redistribution. It is an inventory and license notice, not the corresponding source distribution.

### Material entries

| Area | Official report entry | Significance and limitation |
|---|---|---|
| Kernel | `kernel/private/bcm-97xxx/linux-4.9/vmlinux`, version `5821e01`, `GPL-2.0-with-LT-exception` | Confirms a vendor Linux 4.9 kernel family; the report does not provide source, config, DTS, or exact `BCM72604` mapping |
| Boot control | `boot_control/bootctrl.hsw4026atl`, version `137967b`, Apache-2.0 | Target-specific artifact name; does not establish bootloader unlockability or safe flashing |
| Android recovery | `recovery` at `android-9.0.0_r45-21-g0e57802`; `applypatch` at `android-9.0.0_r45-38-gfa58390` | Confirms Android 9-era recovery components; no target recovery image or tested key combination is provided |
| Update engine | `update_engine` at `android-9.0.0_r16-3-gc25e3da` | Confirms an Android update component; signing, rollback, and downgrade behavior remain unknown |
| Partition tools | `external/gptfdisk/sgdisk`, `android-p-preview-3`; `verity_key`, version `unknown` | Indicates GPT/verity-related artifacts, not a usable partition map or signing key |
| Graphics | `hwcomposer.hsw4026atl` `6f2f22f`; `gralloc.hsw4026atl` `9f21b85` | Target-specific Android graphics components; mainline DRM/KMS support is not established |
| HDMI / audio | `hdmi_cec.hsw4026atl` `201f0ad`; `audio.primary.hsw4026atl` `7f1169c` | Confirms HSW-specific multimedia integration, not generic Linux driver availability |
| Platform HALs | Target-specific power `38ded0c`, thermal `eea6fb9`, TV input `9f21b85`, keymaster `9f21b85` | Useful for source-request scoping |
| Technicolor HALs | `device/technicolor/avko/` processor, resolution, and SoC interfaces | Confirms vendor platform glue; source is not included in the PDF |
| Broadcom platform | Nexus, secure data, secure front end, DSP, HDMI CEC, hardware composer, TV input, and `nxdvb-player` components | Confirms a substantial Broadcom Android stack; it does not make that stack mainline-compatible |
| Realtek Wi-Fi | `vendor/realtek/wifi/drivers/8822bu/rtwpriv/`, version `258a6b9`, GPL-2.0; related RTL8761A/RTL8822B firmware | Confirms Android USB Wi-Fi artifacts; not evidence of mainline support or exact radio population |
| Realtek Bluetooth | `vendor/bin/rtlbtmp`, `vendor/lib/modules/rtk_btusb`, vendor Bluetooth library/commands, and RTL8761A firmware | Confirms Android Bluetooth artifacts; not proof that every HSW SKU has Bluetooth |
| Remote | Realtek/FreeRTOS remote firmware variants | Indicates a Realtek remote family; exact hardware remains unknown |

The `bcm-97xxx` path is a kernel-family name, not a board device tree. No `bcm72604.dtsi` or HSW DTS was found in the report.

## Source-code availability

Vantiva's official regulatory page states that corresponding source is made available free upon request at `contact-ch.opensource@vantiva.com`, subject to the applicable license.

No exact HSW source archive, commit repository, board configuration archive, or bootloader source was found publicly. Generic Realtek repositories found in code search do not contain the HSW target integration. The following request should be sent only after the user reviews it; it must not be sent automatically.

### Draft source request

```text
To: contact-ch.opensource@vantiva.com
Subject: HSW4026ATL v1.0 corresponding source request

Hello,

I am requesting the complete corresponding source code for the open-source
components listed in Vantiva regulatory document 107788, “HSW4026ATL v1.0
OSS Publication.”

The target family is XStream_Smart_Box_001 / HSW4026ATL. The exact PCB
revision and firmware build will be supplied if required.

Please provide, where covered by the applicable licenses:

1. The complete corresponding source for kernel/private/bcm-97xxx/linux-4.9
   at version 5821e01, including kernel configuration, defconfig fragments,
   board files, device-tree sources, build scripts, and build instructions.
2. Source for boot_control/bootctrl.hsw4026atl at 137967b.
3. Source for the device/technicolor/avko/ HALs and the HSW-specific
   Broadcom HALs identified in document 107788.
4. Source for the Realtek 8822bu Wi-Fi, Realtek Bluetooth, and remote-control
   components listed in the report.
5. Corresponding recovery and update-engine source, together with any
   documented partition layout, signing, update, and rollback procedure.
6. Any bootloader or boot-chain source made available under the applicable
   open-source terms, including the supported boot interfaces and board
   identification procedure.
7. The applicable board/PCB suffix mapping and instructions for selecting
   the correct source tree.

Please include archive names, versions or commit identifiers, licenses,
checksums, and the exact product or PCB revisions to which each source
applies. Thank you.
```

## Linux ecosystem assessment

| Platform / component | Result as of 2026-09-25 | Assessment |
|---|---|---|
| Mainline Linux | No HSW4026ATL or `BCM72604` board target, DTS, or maintained driver set was found | Not presently supported |
| OpenWrt | No HSW4026ATL / `BCM72604` device profile was found | Do not use a generic Broadcom image |
| U-Boot | Generic `BCM7260` / `BCM7xxx` BOLT-family support exists, but no verified `BCM72604` or HSW board port was found | Generic family support does not establish bootability |
| `ophub/amlogic-s9xxx-armbian` | Supports Amlogic, Rockchip, and Allwinner devices; no `BCM72604`/HSW4026ATL target is listed | Reject for this box; do not flash its image |
| Buildroot / Yocto | Can host a custom BSP, but neither provides an HSW target by itself | Possible development framework only after board data and boot support exist |
| OE Alliance `bcm72604` references | Unrelated BSP/reference trees; tuning targets do not match the HSW ARMv7 platform | Not evidence of HSW compatibility |
| CoreELEC and other media distributions | No verified HSW image or board target was found | Do not infer support from generic Broadcom devices |
| Vendor Android kernel | Official report confirms a Linux 4.9 kernel path | Best source-request starting point, not yet obtainable or build-tested |

Public code search is not proof that no private or unindexed support exists, but no public path currently meets the safety gates.

## Conversion blockers

| Blocker | Why it matters | Current state |
|---|---|---|
| Exact PCB and suffix | Selects the correct source, bootloader, recovery, and peripherals | Unknown |
| Exact installed firmware | Required to match source and preserve configuration | Unknown |
| Bootloader identity and interfaces | Determines whether an alternative kernel can be started at all | Unknown |
| Secure boot, verity, and update signing | Can prevent boot, recovery, or rollback | Unknown |
| Complete kernel source/config/DTS | Required to build a matching kernel | Not obtained |
| Mainline SoC/board support | Required for a practical modern Linux port | Not found |
| GPU/display/HDMI pipeline | A headless-only kernel would not provide normal TV-box operation | No mainline path established |
| Storage layout and driver | Boot and persistence depend on the exact eMMC/NAND device and partitions | Unknown |
| Ethernet, Wi-Fi, USB, audio, remote, and tuner drivers | Required for practical target functionality | Vendor Android components only; Linux status unknown |
| Original firmware backup | Protects activation, configuration, and recovery | Not obtained |
| Tested rollback | Mandatory before any write | Not established |

## Feasibility conclusion

- **Supported distribution today:** No.
- **Safe generic image installation:** No.
- **Custom vendor-kernel BSP:** Conceivable, but blocked on source, board data, bootloader access, and recovery.
- **Mainline Linux port:** Technically possible in principle, but currently high effort with no board target or verified boot path.
- **Permitted next phase:** Continue read-only evidence collection and prepare the vendor source request.
- **Prohibited next phase:** Reset, unlock, fastboot, partition writes, generic recovery flashing, or subscription-control bypass.

## Non-invasive owner verification checklist

### UI and physical evidence

- Capture clear photographs of the bottom and rear labels.
- Record the complete model, suffix, serial/revision fields, and PCB markings without exposing account credentials.
- Record Android version, build number, security patch, and any displayed hardware version from the About screen.
- Confirm whether the target is connected by Ethernet, Wi-Fi, or both; do not change network settings solely for research.
- If safe, photograph the exterior and any externally visible board marking. Disassembly is not required and is not authorized by this project.

### If ADB is already enabled and explicitly authorized

Run only read operations and redact serials, tokens, Wi-Fi credentials, account identifiers, and network details before sharing output:

```text
adb shell getprop ro.product.model
adb shell getprop ro.product.device
adb shell getprop ro.board.platform
adb shell getprop ro.hardware
adb shell getprop ro.build.fingerprint
adb shell getprop ro.build.display.id
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.security_patch
adb shell getprop ro.boot.hardware
adb shell getprop ro.boot.verifiedbootstate
adb shell getprop ro.boot.flash.locked
adb shell uname -a
adb shell cat /proc/cpuinfo
adb shell cat /proc/meminfo
adb shell cat /proc/partitions
adb shell cat /proc/mounts
adb shell ls -l /dev/block/by-name
adb shell ls -l /sys/class/graphics
adb shell ls -l /proc/device-tree
```

Do not run `adb root`, `adb remount`, `adb reboot bootloader`, `fastboot flashing`, `dd`, partition writes, package deletion, root scripts, or commands copied from forum posts.

## Decision gates

1. Exact model suffix, PCB revision, and installed firmware are identified.
2. Original firmware/configuration preservation method is verified.
3. Recovery and rollback path is tested without destroying the working configuration.
4. Vantiva supplies complete corresponding source or an independently verified equivalent.
5. Bootloader behavior and supported external/RAM boot interfaces are documented.
6. A board-specific kernel and device tree are built successfully.
7. Required display, storage, network, USB, audio, remote, and tuner functions are verified.
8. A reversible, non-destructive boot test is completed.
9. Explicit owner approval is obtained before erase, unlock, reset, partition change, or flash operations.

## Activity log

### 2026-09-25

- Reviewed the supplied Word research document and the initial conversion tracker.
- Performed read-only target service and identity discovery.
- Confirmed the target advertises `Technicolor` / `XStream_Smart_Box_001` through DIAL.
- Confirmed no tested network ADB, SSH, or Telnet service.
- Located and reviewed Airtel's official user manual.
- Catalogued reported Android 9, Android 11, and later HSW firmware identifiers without treating them as the target's current state.
- Rejected generic recovery and subscription-bypass articles as unsupported and unsafe evidence.
- Located Vantiva regulatory document `107788` and verified the official PDF.
- Extracted all 44 pages and recorded the 1,164-module inventory.
- Confirmed HSW-specific kernel, boot-control, graphics, multimedia, Broadcom, and Realtek entries.
- Confirmed Vantiva's source-on-request policy.
- Searched public source indexes, mainline Linux, OpenWrt, U-Boot, and related BSPs; no verified HSW target was found.
- Rechecked for a public HSW4026ATL build tree; none was found, so the safe first build prerequisite is Vantiva's complete corresponding source package.
- Checked the local build environment: Git is available, but no compiler, ARM cross-toolchain, QEMU, Docker, registered WSL distribution, or vendor source tree is present.
- Owner reported sending the Vantiva corresponding-source request; awaiting the reply and archive.
- Consolidated the evidence and safety decision into this tracker.
- No command that modifies the target box has been run.
- Implemented the local read-only diagnostic dashboard in `xstream_diagnostic_dashboard.py`.
- Restricted the dashboard to loopback binding, private IPv4 literals, fixed approved ports, bounded GET requests, and an authorization confirmation.
- Corrected the DIAL probe to use the documented `/ssdp/device-desc.xml` endpoint.
- Added regression coverage for the DIAL endpoint; all 10 unit tests and Python syntax checks pass.
- Browser verification returned HTTP 200 with zero console errors and zero failed requests.
- Reviewed the user-proposed `ophub/amlogic-s9xxx-armbian` repository; its supported platforms do not include the XStream's Broadcom HSW platform, so its image was rejected.
- Received `39607.jpg`; the image could not be visually or OCR-read in this session, so no hardware identification was added.
- Owner initially reported `HSW4028ATL`, then confirmed `HSW4026ATL`; the latter is now treated as the target model.
- Ran a fixed, read-only network scan against `192.168.1.10`; DIAL remained confirmed on 8008, 8009 and 8443 were reachable, and no write action was performed.
- Revised the conversion order after feasibility review: preserve and identify hardware before attempting any Linux installation.

## Change-control record

| Date | Proposed action | Risk | Approval | Result |
|---|---|---|---|---|
| 2026-09-25 | Read-only service discovery and documentation research | Low | User requested | Completed |
| 2026-09-25 | Local diagnostic dashboard | Low | User requested | Implemented; 10 tests passed; running on `127.0.0.1:8765` |
| 2026-09-25 | Prepare Vantiva source request | Low | User requested | Sent by owner; awaiting response |
| 2026-09-25 | Enable ADB or developer options for research | Medium | Not approved | Not performed |
| 2026-09-25 | Erase, reset, unlock, partition change, or flash firmware | High | Not approved | Not performed |

## References

### Authoritative

- Airtel Xstream support/manual page: https://www.airtel.in/xstream/user_manual
- Airtel Xstream manual PDF: https://assets.airtel.in/teams/simplycms/web/pdf/Airtel_XstreamBox_User_Manual-03052020.pdf
- Vantiva regulatory and open-source page: https://www.vantiva.com/regulatory-information/
- Vantiva HSW4026ATL filtered page: https://www.vantiva.com/regulatory-information/?prod=hsw4026atl
- Vantiva document `107788`: https://www.vantiva.com/regulatory-information/hsw4026atl-v1-0-oss-publication/hsw4026atl-v1-0-oss-publication-1-pdf/
- Verified direct PDF: https://www.vantiva.com/app/uploads/2024/10/HSW4026ATL-v1.0-OSS-Publication-1.pdf

### Technical corroboration

- Android 9 firmware `1.0.9` report: https://xdaforums.com/t/airtel-xstream-smart-box-vanilla-androidtv.4100639/
- Android 9 firmware `2.3.0` report: https://xdaforums.com/t/airtel-xstream-smart-box-vanilla-androidtv.4100639/page-3
- Android build fingerprint corroboration: https://stackoverflow.com/questions/69172629/fatal-signal-11-sigsegv-code-1-segv-maperr-we-are-facing-a-crash-when-we-are-reusing-the-surfaceview-for-playing-video
- Firmware `3.1.6` and disabled-ADB reports: https://xdaforums.com/t/airtel-xstream-smartbox-firmware-upgraded-to-hsw4026atl-3-1-6-220211.4424449/
- Android 11 / `RTT4.230420.001` user agent: https://user-agents.net/string/dalvik-2-1-0-linux-u-android-11-xstream-smart-box-001-build-rtt4-230420-001
- Android TV Guide hardware entry: https://www.androidtv-guide.com/pay-tv-provider/airtel-xstream-smart-box/
- Geekbench CPU record: https://browser.geekbench.com/v4/cpu/13658187
- Google certified-device spreadsheet mirror: https://docs.google.com/spreadsheets/d/1kdnHLt673EjoAJisOal2uIpcmVS2Defbgk1ntWRLY3E/

### Rejected as technical evidence

- Tweakdroid generic TWRP instructions: https://tweakdroid.com/twrp/airtel-xsmart-box-hsw4026atl/ — provides no verified HSW recovery image, bootloader procedure, or rollback evidence.
- Subscription-bypass, launcher-removal, rooting-script, and “unlock service” pages — outside scope and not evidence of hardware or boot support.
